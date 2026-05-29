from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .types import FeatureRef, IsolationKeyStr, ProposalId


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @classmethod
    def from_tuple(cls, t: tuple[float, float, float, float]) -> "BoundingBox":
        return cls(x1=t[0], y1=t[1], x2=t[2], y2=t[3])


@dataclass
class EfficientADFeatures:
    """EfficientAD teacher/student 完整输出特征 + teacher-student 差异。

    通过 forward hook 捕获 teacher 和 student 网络的完整输出，
    与 _extract_features() 产出的键名 (teacher, student, difference) 保持一致。
    """

    teacher_ref: FeatureRef
    student_ref: FeatureRef
    difference_ref: FeatureRef
    # teacher/student 输出通道数取决于 EfficientAdModel 的 teacher_out_channels 和 model_size
    # teacher: (H, W, 384) for medium model with teacher_out_channels=384
    # student: (H, W, 768) for medium model (内部自动计算)
    teacher_shape: tuple[int, int, int] = (64, 64, 384)
    student_shape: tuple[int, int, int] = (64, 64, 768)
    difference_shape: tuple[int, int, int] = (64, 64, 384)


@dataclass
class ImageRef:
    """Reference to an image stored in MinIO."""

    key: str
    width: int = 0
    height: int = 0


@dataclass
class ROIContext:
    """Parent ROI metadata."""

    roi_bbox: BoundingBox
    roi_image_ref: ImageRef
    roi_size: tuple[int, int]


@dataclass
class AnomalyContext:
    """EfficientAD anomaly context for this patch."""

    anomaly_score: float
    anomaly_threshold: float
    heatmap_ref: ImageRef
    feature_ref: FeatureRef


@dataclass
class ProposalMetadata:
    """Proposal generation metadata."""

    component_area: int
    component_solidity: float
    rank: int
    total_proposals: int
    generation_params: dict = field(default_factory=dict)


@dataclass
class FilterResult:
    """Per-patch filter classification result."""

    is_real_defect: bool
    confidence: float
    real_defect_score: float
    false_alarm_score: float
    class_id: int
    diagnostics: dict[str, float | str] = field(default_factory=dict)


@dataclass
class PatchProposal:
    """Unified patch-level anomaly proposal — the core data contract."""

    proposal_id: ProposalId
    isolation_key: IsolationKeyStr
    source_roi: ROIContext
    patch_image: ImageRef
    patch_bbox: BoundingBox
    anomaly_context: AnomalyContext
    efficientad_features: EfficientADFeatures
    proposal_metadata: ProposalMetadata
    filter_result: Optional[FilterResult] = None
    identity_id: Optional[str] = None  # 由 DefectTracker 跨帧追踪时填充
