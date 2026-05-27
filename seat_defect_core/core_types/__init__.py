"""检测运行时类型聚合导出。"""

from __future__ import annotations

from .geometry import BoundingBox
from .input import FramePacket, InspectionFrame
from .pipeline import (
    DetectionObject,
    DetectionResult,
    ImageQualityDecision,
    ImageQualityMetrics,
    RoiRefineResult,
)
from .results import (
    CameraInspectionResult,
    FilterClassifierResult,
    InspectionError,
    InspectionResponse,
    InspectionResult,
    TextureAnomalyResult,
)

__all__ = [
    "BoundingBox",
    "CameraInspectionResult",
    "DetectionObject",
    "DetectionResult",
    "FilterClassifierResult",
    "FramePacket",
    "ImageQualityDecision",
    "ImageQualityMetrics",
    "InspectionError",
    "InspectionFrame",
    "InspectionResponse",
    "InspectionResult",
    "RoiRefineResult",
    "TextureAnomalyResult",
]
