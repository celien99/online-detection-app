"""Core inspect runtime configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


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

    # 屏蔽边缘像素，减少座椅边界和背景混入 PatchCore。
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
    # YOLO 实例 mask 可能在目标内部留下低置信空洞；PatchCore 需要完整前景区域。
    fill_segmentation_holes: bool = True
    segmentation_hole_fill_max_area_ratio: float = 0.08


@dataclass
class PatchCoreConfig:
    """PatchCore model and decision parameters."""

    # patch 提取和 memory bank。
    backend: str = "full"
    image_size: int = 256
    patch_size: int = 32
    stride: int = 16
    max_memory: int = 1024
    threshold_quantile: float = 0.99
    texture_input: str = "lab_l"

    # 有效 patch 过滤。
    min_target_coverage: float = 0.8
    max_ignore_overlap: float = 0.1
    min_valid_patch_ratio: float = 0.65

    # 训练时阈值上限分位数（替代 max*1.1 的统计鲁棒上界）。
    training_threshold_upper_quantile: float = 0.995

    # 图像级与连通域判定。
    decision_score_margin: float = 1.08
    strong_patch_score_ratio: float = 0.9
    min_strong_patch_count: int = 3
    min_strong_component_count: int = 2
    min_strong_patch_ratio: float = 0.015
    min_strong_component_ratio: float = 0.01

    # 小面积高峰值缺陷的快速放行规则。
    critical_score_margin: float = 1.35
    critical_peak_score_margin: float = 1.45
    critical_min_component_patch_count: int = 2

    # 峰值规则（peak_rule）最小连通 patch 数，防止单 patch 噪声误触发。
    min_peak_component_patch_count: int = 1

    # full 后端的骨干网络参数。
    backbone_name: str = "wide_resnet50_2"
    feature_layers: List[str] = field(default_factory=lambda: ["layer2", "layer3"])
    backbone_pretrained: bool = True
    backbone_weights_path: Optional[str] = None
    backbone_device: str = "cpu"
    feature_pool_kernel_size: int = 3
    coreset_sampling_ratio: float = 0.1


@dataclass
class ColorBranchConfig:
    """颜色一致性分支配置。"""

    enabled: bool = False
    threshold_quantile: float = 0.99
    threshold: Optional[float] = None
    min_valid_pixel_ratio: float = 0.4
    training_threshold_upper_quantile: float = 0.995


@dataclass
class FilterClassifierConfig:
    """过滤器分类器配置，用于抑制 PatchCore 误报。"""

    enabled: bool = False
    model_path: Optional[str] = None
    device: str = "cpu"
    input_size: int = 224
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
class RegionConfig:
    """单机位标准 ROI 内的局部 PatchCore 区域。"""

    region_id: str
    # 标准 ROI 内的归一化矩形：[x1, y1, x2, y2]，取值范围 0-1。
    box: List[float]
    patchcore_model_path: str
    enabled: bool = True
    patchcore: Optional[PatchCoreConfig] = None


@dataclass
class CameraConfig:
    """单机位 runtime 配置。"""

    camera_id: str
    patchcore_model_path: str
    source: str = ""
    enabled: bool = True
    color_insensitive_mode: bool = False
    quality: QualityGuardConfig = field(default_factory=QualityGuardConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    roi: RoiRefineConfig = field(default_factory=RoiRefineConfig)
    patchcore: PatchCoreConfig = field(default_factory=PatchCoreConfig)
    color_branch: ColorBranchConfig = field(default_factory=ColorBranchConfig)
    filter_classifier: FilterClassifierConfig = field(default_factory=FilterClassifierConfig)
    rule_engine: RuleEngineConfig = field(default_factory=RuleEngineConfig)
    regions: List[RegionConfig] = field(default_factory=list)


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
    "ColorBranchConfig",
    "DetectionConfig",
    "FilterClassifierConfig",
    "FusionConfig",
    "InspectionConfig",
    "PatchCoreConfig",
    "QualityGuardConfig",
    "RegionConfig",
    "RoiRefineConfig",
    "RuleConfig",
    "RuleEngineConfig",
    "SeatModelConfig",
]
