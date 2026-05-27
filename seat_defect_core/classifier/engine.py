"""基于 TorchScript 的过滤器分类器推理引擎。

与 ml/classifier/trainer.py 中 FilterClassifierTrainer 导出的 TorchScript 模型配合使用。
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Optional, Union

import cv2
import numpy as np

if TYPE_CHECKING:
    import torch

from ..config import FilterClassifierConfig
from ..core_types import FilterClassifierResult

# 与 ml/classifier/trainer.py:_build_transform() 保持严格一致
_IMAGE_NET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGE_NET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class FilterClassifierService:
    """加载 TorchScript 分类器模型，对 ROI 裁剪图执行误报过滤推理。"""

    def __init__(
        self,
        config: FilterClassifierConfig,
        model: Optional["torch.jit.ScriptModule"] = None,
    ) -> None:
        self.config = config
        self._model = model
        self._device: str = config.device

    @classmethod
    def load(cls, model_path: Union[str, Path]) -> "FilterClassifierService":
        """从 TorchScript 文件加载分类器模型。"""
        import torch

        path = str(model_path)
        model = torch.jit.load(path)
        model.eval()
        # 使用默认配置，模型路径在运行时由调用方通过 config 补全
        return cls(
            config=FilterClassifierConfig(
                enabled=True,
                model_path=path,
            ),
            model=model,
        )

    def predict(self, roi_bgr_image: np.ndarray) -> FilterClassifierResult:
        """对单张 ROI BGR 图像运行分类推理。

        Returns:
            FilterClassifierResult，其中 is_real_defect=True 表示保留纹理异常检测的 NG 判定，
            is_real_defect=False 表示分类器认为这是误报，应抑制为 OK。
        """
        import torch

        started_at = perf_counter()
        diagnostics: dict[str, float | str] = {}

        try:
            if self._model is None:
                return FilterClassifierResult(
                    is_real_defect=True,
                    confidence=0.0,
                    real_defect_score=0.0,
                    false_alarm_score=0.0,
                    class_id=1,
                    diagnostics={"error_model_not_loaded": 1.0},
                )

            input_size = int(self.config.input_size)
            device = str(self.config.device)

            # 预处理：与 ml/classifier/trainer.py:_build_transform() 保持严格一致
            # BGR → RGB → Resize → float32[0,1] → Normalize(ImageNet)
            preprocess_started_at = perf_counter()
            rgb = cv2.cvtColor(roi_bgr_image, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (input_size, input_size), interpolation=cv2.INTER_LINEAR)
            tensor = torch.from_numpy(
                resized.astype(np.float32) / 255.0
            ).permute(2, 0, 1).unsqueeze(0).to(device)
            # 应用归一化
            mean = torch.as_tensor(_IMAGE_NET_MEAN, device=device).view(1, 3, 1, 1)
            std = torch.as_tensor(_IMAGE_NET_STD, device=device).view(1, 3, 1, 1)
            tensor = (tensor - mean) / std
            diagnostics["preprocess_ms"] = (perf_counter() - preprocess_started_at) * 1000.0

            # 推理
            inference_started_at = perf_counter()
            with torch.no_grad():
                logits = self._model(tensor)
            diagnostics["inference_ms"] = (perf_counter() - inference_started_at) * 1000.0

            # Softmax 提取置信度
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
            false_alarm_score = float(probs[0])
            real_defect_score = float(probs[1])
            class_id = int(probs.argmax())
            confidence = float(probs[class_id])
            is_real_defect = bool(
                class_id == 1 and confidence >= self.config.confidence_threshold
            )

            diagnostics["total_ms"] = (perf_counter() - started_at) * 1000.0

            return FilterClassifierResult(
                is_real_defect=is_real_defect,
                confidence=confidence,
                real_defect_score=real_defect_score,
                false_alarm_score=false_alarm_score,
                class_id=class_id,
                diagnostics=diagnostics,
            )

        except Exception as exc:
            diagnostics["total_ms"] = (perf_counter() - started_at) * 1000.0
            diagnostics["error_prediction_failed"] = 1.0
            return FilterClassifierResult(
                is_real_defect=True,  # 故障安全：不抑制纹理异常检测结果
                confidence=0.0,
                real_defect_score=0.0,
                false_alarm_score=0.0,
                class_id=1,
                diagnostics=diagnostics,
            )

    def predict_dual_modal(
        self, patch_image: np.ndarray,
        ead_features: dict[str, np.ndarray] | None = None,
        unified_emb: list[float] | None = None,
    ) -> FilterClassifierResult:
        """Predict with dual-modal input: patch image + EfficientAD features."""
        import torch

        if self._model is None:
            return FilterClassifierResult(
                is_real_defect=True, confidence=0.0,
                real_defect_score=0.0, false_alarm_score=0.0,
                class_id=1,
                diagnostics={"mode": "fallback_no_model", "reason": "model not loaded"},
            )

        try:
            # Preprocess image: BGR -> RGB -> resize -> normalize
            rgb = cv2.cvtColor(patch_image, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (self.config.input_size, self.config.input_size))
            tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
            tensor = (tensor - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)) / \
                     torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            tensor = tensor.unsqueeze(0).to(self._device)

            # Preprocess EfficientAD features to torch tensors
            feat_tensors = None
            if ead_features is not None:
                feat_tensors = {}
                for key in ["teacher_l1", "teacher_l2", "teacher_l3", "difference"]:
                    if key in ead_features:
                        arr = ead_features[key]
                        t = torch.from_numpy(arr).float().to(self._device)
                        if t.dim() == 3:
                            t = t.permute(2, 0, 1).unsqueeze(0)  # HWC -> 1CHW
                        elif t.dim() == 4:
                            t = t.permute(0, 3, 1, 2)  # NHWC -> NCHW
                        feat_tensors[key] = t

            # Preprocess unified embedding
            uni_tensor = None
            if unified_emb is not None:
                uni_tensor = torch.tensor(unified_emb, dtype=torch.float32).unsqueeze(0).to(self._device)

            with torch.no_grad():
                logits = self._model(tensor, feat_tensors if feat_tensors else None, uni_tensor)

            probs = torch.softmax(logits, dim=1)[0]
            false_alarm_score = float(probs[0].cpu())
            real_defect_score = float(probs[1].cpu())
            class_id = int(torch.argmax(probs).cpu())
            confidence = float(probs[class_id].cpu())
            is_real_defect = class_id == 1 and confidence >= self.config.confidence_threshold

            return FilterClassifierResult(
                is_real_defect=is_real_defect,
                confidence=confidence,
                real_defect_score=real_defect_score,
                false_alarm_score=false_alarm_score,
                class_id=class_id,
                diagnostics={"mode": "three_modal" if unified_emb is not None else "dual_modal"},
            )
        except Exception:
            import traceback
            traceback.print_exc()
            return FilterClassifierResult(
                is_real_defect=True, confidence=0.0,
                real_defect_score=0.0, false_alarm_score=0.0,
                class_id=1,
                diagnostics={"mode": "error_fallback", "reason": "inference failed"},
            )
