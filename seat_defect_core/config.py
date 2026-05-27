"""Core inspect runtime configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .calibration import CalibrationConfig
from .efficientad import EfficientADConfig
from .proposal import ProposalConfig
from .tracking import TrackConfig


@dataclass
class QualityGuardConfig:
    """检测前的图像质量阈值。"""

    min_laplacian_variance: float = 80.0
    min_brightness_mean: float = 30.0
    max_brightness_mean: float = 225.0
    max_overexposed_ratio: float = 0.25
    max_underexposed_ratio: float = 0.35


@dataclass
class AlignmentConfig:
    """ROI 裁剪后的输出尺寸。"""

    output_width: int = 256
    output_height: int = 256


@dataclass
class RoiRefineConfig:
    """ROI 裁剪与有效区域配置。"""

    # 基于 YOLO 分割外接框做轻量扩缩，避免裁得过紧或过松。
    crop_expand_ratio: float = 0.05
    crop_shrink_ratio: float = 0.0

    # 对 YOLO 前景 mask 做保守内缩，剔除座椅轮廓边缘的无效像素。
    mask_erode_pixels: int = 1

    # 屏蔽边缘像素，减少座椅边界和背景混入纹理异常检测。
    edge_ignore_pixels: int = 6
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)


@dataclass
class DetectionConfig:
    """单机位 YOLO 检测配置。"""

    model_path: Optional[str] = None
    target_class: str = "seat"
    # 保持与历史版本一致，避免结构重构时悄悄改变 YOLO 检测策略。
    confidence: float = 0.25
    iou: float = 0.45
    device: str = "cpu"
    imgsz: int = 960
    # YOLO 实例 mask 可能在目标内部留下低置信空洞；纹理异常检测需要完整前景区域。
    fill_segmentation_holes: bool = True
    segmentation_hole_fill_max_area_ratio: float = 0.08


@dataclass
class FilterClassifierConfig:
    """过滤器分类器配置，用于抑制纹理异常检测误报。"""

    enabled: bool = False
    model_path: Optional[str] = None
    device: str = "cpu"
    input_size: int = 448
    confidence_threshold: float = 0.5


@dataclass
class RuleConfig:
    """单条后处理规则配置。

    支持两类条件：
    1. 阈值条件（max_anomaly_score, min_strong_patch_count, ...）
    2. 知识条件（camera_id, defect_type, classifier_confidence）
    两类条件可组合使用，全部满足时规则命中。
    """

    name: str
    """规则名称，用于调试和日志。"""

    enabled: bool = True
    """是否启用。"""

    # ── 阈值条件（离线统计规则）──
    max_anomaly_score: Optional[float] = None
    """异常分数低于此值触发。"""

    min_strong_patch_count: Optional[int] = None
    """强异常 patch 数低于此值触发。"""

    max_strong_patch_ratio: Optional[float] = None
    """强异常 patch 比例低于此值触发。"""

    require_filter_false_alarm: bool = False
    """要求 Filter Classifier 也将此判定为误报。"""

    require_filter_real_defect: bool = False
    """要求 Filter Classifier 判定为真实缺陷。"""

    # ── 知识条件（离线平台 Knowledge → Rules 部署）──
    camera_id: Optional[str] = None
    """限定规则的机位 ID，None 表示所有机位。"""

    defect_type: Optional[str] = None
    """限定规则匹配的缺陷类型。需 Filter Classifier 支持多分类输出。"""

    min_classifier_confidence: Optional[float] = None
    """Filter Classifier 预测置信度下限。"""

    max_classifier_confidence: Optional[float] = None
    """Filter Classifier 预测置信度上限。"""

    # ── 动作 ──
    action: str = "suppress_to_ok"
    """命中规则后的动作：suppress_to_ok / flag_for_review / escalate。"""

    # ── 元数据 ──
    source: str = "manual"
    """规则来源：manual / offline_platform。"""

    knowledge_entry_id: Optional[str] = None
    """离线平台 Knowledge Entry ID（溯源用）。"""

    priority: int = 0
    """规则优先级，数值越大越优先。多规则命中时取最高优先级的 action。"""


@dataclass
class RuleEngineConfig:
    """规则引擎后处理配置，在 Filter Classifier 之后、Fusion 之前执行。"""

    enabled: bool = False
    rules: List[RuleConfig] = field(default_factory=list)
    deployed_rules_path: Optional[str] = None
    """离线平台部署的规则 JSON 文件路径。加载时与本地 rules 合并。"""


@dataclass
class CameraConfig:
    """单机位 runtime 配置。"""

    camera_id: str
    efficientad_model_path: str
    source: str = ""
    enabled: bool = True
    quality: QualityGuardConfig = field(default_factory=QualityGuardConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    roi: RoiRefineConfig = field(default_factory=RoiRefineConfig)
    efficientad: EfficientADConfig = field(default_factory=EfficientADConfig)
    filter_classifier: FilterClassifierConfig = field(default_factory=FilterClassifierConfig)
    rule_engine: RuleEngineConfig = field(default_factory=RuleEngineConfig)
    proposal: ProposalConfig | None = None
    calibration: CalibrationConfig | None = None
    track: TrackConfig | None = None


@dataclass
class FusionConfig:
    """多机位融合判定策略。"""

    reject_on_any_reject: bool = True
    ng_strategy: str = "any"
    defect_overrides_reject: bool = True


@dataclass
class SeatModelConfig:
    """按座椅型号组织的多机位配置。"""

    seat_model_id: str
    cameras: List[CameraConfig] = field(default_factory=list)
    display_name: Optional[str] = None


@dataclass
class InspectionConfig:
    """core 顶层 inspect runtime 配置。"""

    cameras: List[CameraConfig] = field(default_factory=list)
    seat_models: List[SeatModelConfig] = field(default_factory=list)
    default_seat_model_id: Optional[str] = None
    output_json_path: str = "outputs/seat_defect_inspection/results.json"
    debug_dir: str = "outputs/seat_defect_inspection/debug"
    debug_artifacts_enabled: bool = True
    debug_artifact_names: List[str] = field(
        default_factory=lambda: ["overlay"],
    )
    part_id: str = "seat_demo"
    fusion: FusionConfig = field(default_factory=FusionConfig)
    # 如果设置了此 URL，检测完成后会自动将 NG 结果上传到离线平台
    upload_base_url: Optional[str] = None


__all__ = [
    "AlignmentConfig",
    "CameraConfig",
    "DetectionConfig",
    "EfficientADConfig",
    "FilterClassifierConfig",
    "FusionConfig",
    "InspectionConfig",
    "QualityGuardConfig",
    "RoiRefineConfig",
    "RuleConfig",
    "RuleEngineConfig",
    "SeatModelConfig",
]
