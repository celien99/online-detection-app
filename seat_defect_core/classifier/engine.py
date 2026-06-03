"""基于 TorchScript 的过滤器分类器推理引擎。

与 ml/classifier/trainer.py 中 FilterClassifierTrainer 导出的 TorchScript 模型配合使用。
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Optional, Union

import cv2
import numpy as np

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
            FilterClassifierResult，其中 is_real_defect=True 表示保留 PatchCore 的 NG 判定，
            is_real_defect=False 表示分类器认为这是误报，应抑制为 OK。
        """
        import torch

        started_at = perf_counter()
        diagnostics: dict[str, float] = {}

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
                is_real_defect=True,  # 故障安全：不抑制 PatchCore 结果
                confidence=0.0,
                real_defect_score=0.0,
                false_alarm_score=0.0,
                class_id=1,
                diagnostics=diagnostics,
            )
