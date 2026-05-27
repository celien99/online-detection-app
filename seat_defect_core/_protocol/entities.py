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
    """Multi-scale teacher features + student-teacher difference."""

    teacher_l1_ref: FeatureRef
    teacher_l2_ref: FeatureRef
    teacher_l3_ref: FeatureRef
    difference_ref: FeatureRef
    teacher_l1_shape: tuple[int, int, int] = (56, 56, 64)
    teacher_l2_shape: tuple[int, int, int] = (28, 28, 128)
    teacher_l3_shape: tuple[int, int, int] = (14, 14, 256)
    difference_shape: tuple[int, int, int] = (224, 224, 64)


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
