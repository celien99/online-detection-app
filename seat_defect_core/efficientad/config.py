"""EfficientAD 模型和推理配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EfficientADConfig:
    """EfficientAD 纹理异常检测配置。"""

    model_path: str = ""
    """训练后的 .pt 模型文件路径。"""

    device: str = "cpu"
    """推理设备：cpu / cuda / mps。"""

    input_size: int = 256
    """模型输入尺寸 (正方形)。"""

    teacher_backbone: str = "wide_resnet50_2"
    """教师网络 backbone。"""

    student_backbone: str = "resnet18"
    """学生网络 backbone。"""

    # 推理控制
    min_valid_pixel_ratio: float = 0.3
    """ROI 内有效像素最低比例，低于此值判定为 REJECT。"""

    # 阈值（训练时填充，推理时直接从模型文件读取）
    image_threshold: float = 0.0
    """图像级异常分数阈值。"""

    pixel_threshold: float = 0.0
    """像素级异常分数阈值。"""

    # 训练参数
    epochs: int = 100
    """训练轮数。"""

    batch_size: int = 16
    """训练批次大小。"""

    learning_rate: float = 0.0001
    """学习率。"""

    validation_split: float = 0.1
    """验证集比例。"""

    early_stopping_patience: int = 10
    """早停耐心轮数。"""
