"""EfficientAD 推理引擎。

基于 anomalib 的 EfficientAD 实现，加载 TorchScript 模型进行纹理异常检测。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
except ImportError:
    torch = None

from .config import EfficientADConfig
from ..core_types import TextureAnomalyResult

IMAGENET_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


class EfficientADService:
    """加载训练后的 EfficientAD TorchScript 模型并执行推理。"""

    def __init__(self, config: EfficientADConfig) -> None:
        if torch is None:
            raise RuntimeError("EfficientAD 需要 PyTorch 运行环境")
        self.config = config
        self.device = _resolve_device(config.device)
        self.model: Optional[torch.jit.ScriptModule] = None
        self._image_threshold = config.image_threshold
        if config.model_path:
            self._load_model(config.model_path)

    def _load_model(self, model_path: str) -> None:
        """加载 TorchScript 模型和阈值元数据。"""
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"EfficientAD 模型文件不存在: {model_path}")
        self.model = torch.jit.load(str(path), map_location=self.device)
        self.model.eval()
        # 从模型文件读取训练时保存的阈值
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            import json
            meta = json.loads(meta_path.read_text("utf-8"))
            self._image_threshold = float(meta.get("image_threshold", self._image_threshold))

    def predict(
        self,
        image: np.ndarray,
        target_mask: np.ndarray,
        ignore_mask: np.ndarray,
    ) -> TextureAnomalyResult:
        """对单张 ROI 图像执行异常检测。"""
        if self.model is None:
            raise RuntimeError("EfficientAD 模型未加载")

        original_h, original_w = image.shape[:2]
        valid_pixel_ratio = _compute_valid_pixel_ratio(target_mask, ignore_mask, image.shape[:2])

        # 计算有效像素比例，过低则 REJECT
        if valid_pixel_ratio < self.config.min_valid_pixel_ratio:
            return TextureAnomalyResult(
                score=0.0,
                threshold=self._image_threshold,
                is_anomaly=False,
                heatmap=np.zeros((original_h, original_w), dtype=np.float32),
                anomaly_map=np.zeros((original_h, original_w), dtype=np.float32),
                valid_pixel_ratio=valid_pixel_ratio,
            )

        # 预处理：BGR → RGB, resize, normalize
        input_tensor = _prepare_input(image, self.config.input_size).to(self.device)

        with torch.inference_mode():
            output = self.model(input_tensor)

        # 解析 anomalib 输出：通常是 (anomaly_map, anomaly_score)
        if isinstance(output, (tuple, list)):
            anomaly_map_tensor = output[0]
            anomaly_score = float(output[1].item()) if len(output) > 1 else 0.0
        elif torch.is_tensor(output):
            anomaly_map_tensor = output
            anomaly_score = float(anomaly_map_tensor.mean().item())
        else:
            raise RuntimeError(f"EfficientAD 输出格式不支持: {type(output)}")

        # anomaly_map 双线性插值回原始 ROI 尺寸
        anomaly_map = _resize_anomaly_map(anomaly_map_tensor, original_h, original_w)

        # 应用 ignore_mask 清零忽略区域
        if ignore_mask is not None and ignore_mask.any():
            ignore_binary = _to_binary_mask(ignore_mask, (original_h, original_w))
            anomaly_map[ignore_binary > 0] = 0.0

        # 热力图 = anomaly_map（直接用作可视化）
        heatmap = anomaly_map.copy()

        # 异常判定
        is_anomaly = anomaly_score > self._image_threshold

        return TextureAnomalyResult(
            score=anomaly_score,
            threshold=self._image_threshold,
            is_anomaly=is_anomaly,
            heatmap=heatmap,
            anomaly_map=anomaly_map,
            valid_pixel_ratio=valid_pixel_ratio,
        )

    def predict_batch(
        self,
        items: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    ) -> List[TextureAnomalyResult]:
        """批量推理，逐张处理避免显存溢出。"""
        return [self.predict(image, target_mask, ignore_mask) for image, target_mask, ignore_mask in items]

    @classmethod
    def load_bundle(cls, model_path: str | Path) -> "EfficientADService":
        """从路径加载 EfficientAD 模型。"""
        config = EfficientADConfig(model_path=str(model_path))
        return cls(config)


def _resolve_device(requested: str) -> torch.device:
    """解析设备，支持自动回退。"""
    normalized = requested.strip().lower()
    if normalized.startswith("cuda") and torch.cuda.is_available():
        return torch.device(requested)
    if normalized == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _prepare_input(image: np.ndarray, input_size: int) -> torch.Tensor:
    """BGR 或 RGBA → RGB → resize → normalize → tensor。"""
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (input_size, input_size), interpolation=cv2.INTER_AREA)
    normalized = (resized.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(np.transpose(normalized, (2, 0, 1))).unsqueeze(0).float()
    return tensor


def _resize_anomaly_map(
    anomaly_map_tensor: torch.Tensor,
    target_h: int,
    target_w: int,
) -> np.ndarray:
    """把模型输出的 anomaly_map 缩放到目标尺寸。"""
    amap = anomaly_map_tensor.detach().cpu()
    # anomalib 输出 shape: (1, 1, H, W) 或 (1, H, W)
    if amap.ndim == 4:
        amap = amap.squeeze(0).squeeze(0)
    elif amap.ndim == 3:
        amap = amap.squeeze(0)
    amap_np = amap.float().numpy()
    resized = cv2.resize(amap_np, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    return resized.astype(np.float32)


def _compute_valid_pixel_ratio(
    target_mask: np.ndarray,
    ignore_mask: np.ndarray,
    shape: Tuple[int, int],
) -> float:
    """计算目标区域内有效像素比例。"""
    target_binary = _to_binary_mask(target_mask, shape)
    total = target_binary.sum()
    if total == 0:
        return 0.0
    ignore_binary = _to_binary_mask(ignore_mask, shape) if ignore_mask is not None and ignore_mask.any() else np.zeros(shape, dtype=np.uint8)
    valid = total - (ignore_binary * target_binary).sum()
    return float(valid / total)


def _to_binary_mask(mask: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """归一化为二值掩膜并缩放到目标尺寸。"""
    array = np.asarray(mask)
    if array.ndim == 3:
        if array.shape[2] == 4:
            array = array[:, :, 3]
        else:
            array = np.any(array > 0, axis=2)
    binary = (array > 0).astype(np.uint8)
    if binary.shape != shape:
        binary = cv2.resize(binary, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return binary
