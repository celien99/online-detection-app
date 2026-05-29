"""EfficientAD 推理引擎。

基于 anomalib 的 EfficientAD 实现，加载 TorchScript 模型进行纹理异常检测。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
except ImportError:
    torch = None

from .config import EfficientADConfig
from ..core_types import TextureAnomalyResult

_logger = logging.getLogger(__name__)

IMAGENET_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)

# Torch tensor 版本，用于在 inference_mode 内还原 ImageNet normalize
IMAGENET_MEAN_TS = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 3, 1, 1) if torch is not None else None
IMAGENET_STD_TS = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 3, 1, 1) if torch is not None else None

# ImageNet 均值灰（RGB uint8），用于填充非目标区域避免黑边引入异常响应
IMAGENET_MEAN_GRAY_RGB = np.asarray([124, 116, 104], dtype=np.uint8)


class EfficientADService:
    """加载训练后的 EfficientAD 模型并执行推理。

    优先使用 TorchScript 模型（性能更好），加载时会做一次预热推理验证。
    如果 TorchScript 模型失败（如 CUDA 设备不兼容），自动回退到 state_dict
    加载 + eager 模式（兼容性更好，跨平台稳定）。
    """

    def __init__(self, config: EfficientADConfig) -> None:
        if torch is None:
            raise RuntimeError("EfficientAD 需要 PyTorch 运行环境")
        self.config = config
        self.device = _resolve_device(config.device)
        self.model: Optional[torch.jit.ScriptModule | torch.nn.Module] = None
        self._feature_model: Optional[torch.nn.Module] = None
        self._image_threshold = config.image_threshold
        self._threshold_from_meta = False
        if config.model_path:
            self._load_model(config.model_path)

    def _load_model(self, model_path: str) -> None:
        """加载模型：优先 TorchScript，失败时回退 state_dict eager 模式。"""
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"EfficientAD 模型文件不存在: {model_path}")
        self._load_meta(path)

        state_dict_path = path.with_suffix(".state_dict.pt")

        # 尝试 TorchScript 加载 + 预热验证
        jit_ok = False
        try:
            jit_model = torch.jit.load(str(path), map_location=self.device)
            jit_model.eval()
            # 用 dummy 输入做一次预热推理，验证 TorchScript 图在当期设备上能正常执行
            dummy = torch.randn(1, 3, self.config.input_size, self.config.input_size,
                                device=self.device)
            with torch.inference_mode():
                _ = jit_model(dummy)
            self.model = jit_model
            jit_ok = True
            _logger.info("efficientad_jit_loaded model_path=%s", model_path)
        except Exception:
            _logger.warning("efficientad_jit_failed_fallback_state_dict", exc_info=True)

        # TorchScript 失败时用 state_dict 重建 eager 模式模型
        if not jit_ok and state_dict_path.exists():
            try:
                from anomalib.models.image.efficient_ad.torch_model import EfficientAdModel
                from ..training.efficientad import _EfficientADExportWrapper

                state_dict = torch.load(str(state_dict_path), map_location=self.device,
                                       weights_only=True)
                raw_model = EfficientAdModel(teacher_out_channels=384, model_size="medium")
                raw_model.load_state_dict(state_dict)
                raw_model.to(self.device)
                raw_model.eval()

                eager_model = _EfficientADExportWrapper(raw_model).to(self.device).eval()
                self.model = eager_model
                _logger.info("efficientad_eager_loaded model_path=%s", model_path)
            except Exception:
                _logger.error("efficientad_state_dict_load_failed", exc_info=True)

        if self.model is None:
            raise RuntimeError(
                f"EfficientAD 模型加载失败: {model_path}。"
                f"TorchScript 和 state_dict 两种方式均无法加载。"
            )

        # 尝试加载特征提取模型（同样优先从 state_dict 重建）
        if state_dict_path.exists():
            self._load_feature_model(str(state_dict_path))

    def _load_meta(self, path: Path) -> None:
        """从 .meta.json 加载训练时保存的阈值。"""
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            import json

            try:
                meta = json.loads(meta_path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                _logger.warning("efficientad_meta_invalid", exc_info=True)
                meta = {}
            if "image_threshold" in meta:
                self._image_threshold = float(meta["image_threshold"])
                self._threshold_from_meta = True
        if not self._threshold_from_meta:
            _logger.warning(
                "efficientad_threshold_not_loaded",
                extra={
                    "model_path": str(path),
                    "fallback_threshold": self._image_threshold,
                    "hint": "请检查 .meta.json 是否与模型文件在同一目录，或重新训练生成阈值",
                },
            )

    def _load_feature_model(self, state_dict_path: str) -> None:
        """尝试从 state_dict 重建模型用于多尺度特征提取。

        state_dict 来自 model.model (raw EfficientAdModel)，需加载到同名 raw model，
        而非 LightningModule wrapper（两者 state_dict key 前缀不同）。
        """
        try:
            from anomalib.models.image.efficient_ad.torch_model import EfficientAdModel

            state_dict = torch.load(state_dict_path, map_location=self.device, weights_only=True)
            feature_model = EfficientAdModel(
                teacher_out_channels=384,
                model_size="medium",
            )
            feature_model.load_state_dict(state_dict)
            feature_model.to(self.device)
            feature_model.eval()
            self._feature_model = feature_model
            _logger.info("efficientad_feature_model_loaded")
        except Exception:
            _logger.warning("efficientad_feature_model_unavailable", exc_info=True)

    @property
    def image_threshold(self) -> float:
        return self._image_threshold

    @property
    def has_features(self) -> bool:
        """是否支持多尺度特征提取。"""
        return self._feature_model is not None

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

        # 预处理：BGR → RGB, resize, normalize，非目标区域用 ImageNet 均值灰填充
        input_tensor = _prepare_input(image, self.config.input_size).to(self.device)

        with torch.inference_mode():
            output = self.model(input_tensor)

        # 解析模型输出：(anomaly_map, pred_score)
        if isinstance(output, (tuple, list)):
            anomaly_map_tensor = output[0]
            anomaly_score_raw = float(output[1].item()) if len(output) > 1 else 0.0
        elif torch.is_tensor(output):
            anomaly_map_tensor = output
            anomaly_score_raw = float(anomaly_map_tensor.mean().item())
        else:
            raise RuntimeError(f"EfficientAD 输出格式不支持: {type(output)}")

        # anomaly_map 双线性插值回原始 ROI 尺寸
        anomaly_map = _resize_anomaly_map(anomaly_map_tensor, original_h, original_w)

        # 应用 ignore_mask 清零忽略区域（边缘像素）
        if ignore_mask is not None and ignore_mask.any():
            ignore_binary = _to_binary_mask(ignore_mask, (original_h, original_w))
            anomaly_map[ignore_binary > 0] = 0.0

        # 构建目标区域二值掩膜，清零非目标区域（letterbox padding 等）
        target_binary = _to_binary_mask(target_mask, (original_h, original_w))

        # 使用模型内置的 pred_score（全图 grid-pooled），与训练时 _compute_threshold
        # 的 scoring 方法完全一致，确保阈值跨训练/推理可比。
        # masked scoring (_grid_pool_score) 仅在 target_binary 存在且需要
        # 排除背景区域时使用，但阈值的语义需要匹配。
        anomaly_score = anomaly_score_raw

        # 热力图：以阈值为锚点做归一化，阈值≈0.5，2×阈值≈1.0
        # 正常区域（远低于阈值）→ dark blue，边界 → yellow，异常 → red
        heatmap = _normalize_heatmap(anomaly_map, target_binary, self._image_threshold)

        # 统计强异常 patch（用于规则引擎后处理）
        strong_patch_count, strong_patch_ratio = _compute_strong_patches(
            anomaly_map, target_binary, self._image_threshold
        )

        # 异常判定
        is_anomaly = anomaly_score > self._image_threshold

        # 多尺度特征提取（如果可用；None 表示不可用或提取失败）
        features = None
        if self._feature_model is not None:
            raw = self._extract_features(input_tensor)
            features = raw if raw else None

        return TextureAnomalyResult(
            score=anomaly_score,
            threshold=self._image_threshold,
            is_anomaly=is_anomaly,
            heatmap=heatmap,
            anomaly_map=anomaly_map,
            valid_pixel_ratio=valid_pixel_ratio,
            features=features,
            strong_patch_count=strong_patch_count,
            strong_patch_ratio=strong_patch_ratio,
        )

    def predict_batch(
        self,
        items: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    ) -> List[TextureAnomalyResult]:
        """批量推理，逐张处理避免显存溢出。"""
        return [self.predict(image, target_mask, ignore_mask) for image, target_mask, ignore_mask in items]

    def _extract_features(self, input_tensor: torch.Tensor) -> dict[str, np.ndarray]:
        """从 EfficientAD 模型提取 teacher/student 特征图及差异。

        通过 forward hook 捕获 teacher 和 student 网络的完整输出，
        返回 calibration 模块所需的特征字典。
        特征模型不可用时返回空 dict。
        """
        if self._feature_model is None:
            return {}

        features: dict[str, torch.Tensor] = {}
        handles: list[torch.utils.hooks.RemovableHandle] = []

        def _make_hook(name: str) -> Callable[[torch.nn.Module, torch.Tensor, torch.Tensor], None]:
            def hook(_module: torch.nn.Module, _input: torch.Tensor, output: torch.Tensor) -> None:
                features[name] = output.detach()

            return hook

        # 注册 teacher 和 student 的 module-level hook（捕获整个 teacher/student 的输出）
        if hasattr(self._feature_model, "teacher"):
            handles.append(
                self._feature_model.teacher.register_forward_hook(_make_hook("teacher"))
            )
        if hasattr(self._feature_model, "student"):
            handles.append(
                self._feature_model.student.register_forward_hook(_make_hook("student"))
            )

        # _feature_model 是 raw anomalib EfficientAdModel，内部自行做 ImageNet normalize，
        # 而 input_tensor 已被 _prepare_input 做过一次 normalize，需要先还原到 [0, 1]
        dev = input_tensor.device
        unnorm_input = (input_tensor * IMAGENET_STD_TS.to(dev) + IMAGENET_MEAN_TS.to(dev)).clamp(0.0, 1.0)
        try:
            with torch.inference_mode():
                self._feature_model(unnorm_input)
        except Exception:
            _logger.warning("efficientad_feature_extraction_failed", exc_info=True)
            return None
        finally:
            for h in handles:
                h.remove()

        if not features:
            return {}

        result: dict[str, np.ndarray] = {}
        for key, tensor in features.items():
            result[key] = tensor.squeeze(0).permute(1, 2, 0).cpu().float().numpy()

        # 计算 teacher-student 差异（取 student 的前 teacher_out_channels 个通道与 teacher 对齐）
        if "teacher" in result and "student" in result:
            t_out = result["teacher"]
            s_out = result["student"]
            teacher_channels = min(t_out.shape[2], s_out.shape[2])
            t_aligned = t_out[:, :, :teacher_channels]
            s_aligned = s_out[:, :, :teacher_channels]
            # 对齐 spatial 尺寸（可能因 padding 不同而不同）
            if t_aligned.shape[:2] != s_aligned.shape[:2]:
                s_aligned = cv2.resize(
                    s_aligned, (t_aligned.shape[1], t_aligned.shape[0]), interpolation=cv2.INTER_LINEAR
                )
            result["difference"] = (t_aligned - s_aligned).astype(np.float32)

        return result

    def extract_features_batch(
        self, input_batch: torch.Tensor
    ) -> list[dict[str, np.ndarray]]:
        """批量提取 teacher/student 特征图及差异。

        对一批已预处理（ImageNet normalize）的图像同时提取多尺度特征，
        返回 per-image 的特征字典列表，用于 calibration 的批量计算。

        Args:
            input_batch: (B, 3, H, W) 已做 ImageNet normalize 的 tensor。

        Returns:
            list[dict]: 每张图的特征字典，key 为 teacher/student/difference。
        """
        if self._feature_model is None:
            return [{} for _ in range(input_batch.shape[0])]

        features: dict[str, torch.Tensor] = {}
        handles: list[torch.utils.hooks.RemovableHandle] = []

        def _make_hook(name: str) -> Callable[[torch.nn.Module, torch.Tensor, torch.Tensor], None]:
            def hook(_module: torch.nn.Module, _input: torch.Tensor, output: torch.Tensor) -> None:
                features[name] = output.detach()

            return hook

        if hasattr(self._feature_model, "teacher"):
            handles.append(
                self._feature_model.teacher.register_forward_hook(_make_hook("teacher"))
            )
        if hasattr(self._feature_model, "student"):
            handles.append(
                self._feature_model.student.register_forward_hook(_make_hook("student"))
            )

        # _feature_model 内部自行做 ImageNet normalize，需先还原到 [0, 1]
        dev = input_batch.device
        unnorm_input = (
            input_batch * IMAGENET_STD_TS.to(dev) + IMAGENET_MEAN_TS.to(dev)
        ).clamp(0.0, 1.0)
        try:
            with torch.inference_mode():
                self._feature_model(unnorm_input)
        except Exception:
            _logger.warning("efficientad_feature_extraction_batch_failed", exc_info=True)
            return None
        finally:
            for h in handles:
                h.remove()

        if not features:
            return [{} for _ in range(input_batch.shape[0])]

        batch_size = input_batch.shape[0]
        results: list[dict[str, np.ndarray]] = []
        for i in range(batch_size):
            per_image: dict[str, np.ndarray] = {}
            for key, tensor in features.items():
                per_image[key] = tensor[i].permute(1, 2, 0).cpu().float().numpy()

            if "teacher" in per_image and "student" in per_image:
                t_out = per_image["teacher"]
                s_out = per_image["student"]
                teacher_channels = min(t_out.shape[2], s_out.shape[2])
                t_aligned = t_out[:, :, :teacher_channels]
                s_aligned = s_out[:, :, :teacher_channels]
                if t_aligned.shape[:2] != s_aligned.shape[:2]:
                    s_aligned = cv2.resize(
                        s_aligned,
                        (t_aligned.shape[1], t_aligned.shape[0]),
                        interpolation=cv2.INTER_LINEAR,
                    )
                per_image["difference"] = (t_aligned - s_aligned).astype(np.float32)

            results.append(per_image)

        return results

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
    """BGR 或 BGRA → RGB → resize → 非目标区域用 ImageNet 均值灰填充 → normalize → tensor。

    当输入包含 alpha 通道时，alpha=0 的区域（letterbox padding）会被填充为
    ImageNet 均值灰，避免黑边在 EfficientAD 中产生异常响应。
    """
    has_alpha = image.ndim == 3 and image.shape[2] == 4
    if has_alpha:
        alpha = image[:, :, 3].copy()
        image = image[:, :, :3]

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # 保持宽高比的 resize（letterbox 等效：先 resize 再放 canvas 中央）
    h, w = rgb.shape[:2]
    scale = min(float(input_size) / float(h), float(input_size) / float(w))
    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))
    resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # 放在 ImageNet 均值灰画布中央
    canvas = np.full(
        (input_size, input_size, 3),
        IMAGENET_MEAN_GRAY_RGB,
        dtype=np.uint8,
    )
    offset_y = (input_size - new_h) // 2
    offset_x = (input_size - new_w) // 2
    canvas[offset_y : offset_y + new_h, offset_x : offset_x + new_w] = resized

    # 如果原图有 alpha 通道，将 alpha=0 的 padding 也填充为均值灰
    if has_alpha:
        alpha_resized = cv2.resize(alpha, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
        alpha_canvas = np.zeros((input_size, input_size), dtype=np.uint8)
        alpha_canvas[offset_y : offset_y + new_h, offset_x : offset_x + new_w] = alpha_resized
        non_target_mask = alpha_canvas == 0
        canvas[non_target_mask] = IMAGENET_MEAN_GRAY_RGB

    normalized = (canvas.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(np.transpose(normalized, (2, 0, 1))).unsqueeze(0).float()
    return tensor


def _grid_pool_score(anomaly_map: np.ndarray, target_binary: np.ndarray, grid_size: int = 8) -> float:
    """对 masked anomaly_map 做空间网格池化，取最高网格均值作为异常分数。

    相比 amax 单像素，网格均值：
    - 不被边缘/噪声单点干扰
    - 捕获缺陷的空间聚集特征
    - 对暗表面微弱缺陷的分离度远优于 amax
    """
    masked = anomaly_map * target_binary.astype(np.float32)
    h, w = masked.shape
    gh = max(1, h // grid_size)
    gw = max(1, w // grid_size)
    cell_means = []
    for y in range(0, h, gh):
        for x in range(0, w, gw):
            cell = masked[y : y + gh, x : x + gw]
            cell_target = target_binary[y : y + gh, x : x + gw]
            if cell_target.sum() > 0:
                cell_means.append(float(cell[cell_target > 0].mean()))
    if not cell_means:
        return 0.0
    return float(np.max(cell_means))


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
    ignore_binary = (
        _to_binary_mask(ignore_mask, shape)
        if ignore_mask is not None and ignore_mask.any()
        else np.zeros(shape, dtype=np.uint8)
    )
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


def _compute_strong_patches(
    anomaly_map: np.ndarray,
    target_binary: np.ndarray,
    threshold: float,
) -> Tuple[int, float]:
    """统计目标区域内超过阈值的强异常连通域数量和面积比例。"""
    target_pixels = target_binary.sum()
    if target_pixels == 0:
        return 0, 0.0

    strong_binary: np.ndarray = (anomaly_map > threshold).astype(np.uint8)
    strong_mask: np.ndarray = strong_binary * target_binary
    strong_area: int = int(strong_mask.sum())
    if strong_area == 0:
        return 0, 0.0

    # 连通域分析
    num_labels, labels, _stats, _centroids = cv2.connectedComponentsWithStats(
        strong_mask, connectivity=8
    )
    # 减去背景标签
    patch_count = max(0, num_labels - 1)
    patch_ratio = float(strong_area / target_pixels)
    return patch_count, patch_ratio


def _normalize_heatmap(
    anomaly_map: np.ndarray,
    target_binary: np.ndarray,
    threshold: float,
) -> np.ndarray:
    """以检测阈值为锚点归一化 anomaly_map 到 [0, 1]。

    映射规则：
    - 0.0      → 完全正常（dark blue）
    - threshold → 0.5 边界（yellow/green）
    - 2*threshold → 1.0 明确异常（red）

    这样正常图像上远低于阈值的区域不会产生虚假的暖色信号，
    只有真正接近或超过阈值的区域才会在 overlay 中显示为红/黄色。
    """
    target_pixels = anomaly_map[target_binary > 0]
    if target_pixels.size == 0:
        return np.zeros_like(anomaly_map, dtype=np.float32)

    if threshold > 0:
        # 阈值锚定：threshold → 0.5
        vmax = threshold * 2.0
    else:
        # 无有效阈值时，使用目标区域 99 分位数作为参考
        vmax = float(np.percentile(target_pixels, 99.0))
        if vmax < 1e-8:
            vmax = 1.0

    # 非目标区域清零，避免背景噪声在热力图中显示为异常信号
    masked = anomaly_map.copy()
    masked[target_binary == 0] = 0.0
    normalized = masked / vmax
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)
