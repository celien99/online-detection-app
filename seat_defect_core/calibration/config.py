"""Calibration layer configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CameraNormConfig:
    """Per-camera normalization settings."""
    enabled: bool = True
    stats_path: str = ""  # 预计算的 mean/std .npz 文件路径


@dataclass
class ProjectionConfig:
    """Embedding projection settings."""
    enabled: bool = True
    projector_path: str = ""  # 投影矩阵 .npz 文件路径


@dataclass
class WhiteningConfig:
    """ZCA/PCA whitening settings."""
    enabled: bool = True
    method: str = "zca"  # "zca" | "pca"
    regularization: float = 1e-4
    matrix_path: str = ""  # 预计算的白化矩阵 .npz 文件路径


@dataclass
class EMACenterConfig:
    """EMA feature center tracking settings."""
    enabled: bool = True
    alpha: float = 0.99  # EMA 衰减系数
    min_samples: int = 10  # 建立有效中心的最小样本数
    novelty_threshold: float = 0.3  # is_novel 的距离阈值
    centers_path: str = ""  # 预存中心文件的路径


@dataclass
class CalibrationConfig:
    """Feature calibration layer top-level config."""
    enabled: bool = True

    camera_norm: CameraNormConfig = field(default_factory=CameraNormConfig)
    projection: ProjectionConfig = field(default_factory=ProjectionConfig)
    whitening: WhiteningConfig = field(default_factory=WhiteningConfig)
    ema_center: EMACenterConfig = field(default_factory=EMACenterConfig)
    # 每个 camera_id 对应的 CameraNormalizer stats 文件路径
    # 例如 {"cam_front": "./calibration/cam_front_norm.npz"}
    camera_norm_paths: dict[str, str] = field(default_factory=dict)
