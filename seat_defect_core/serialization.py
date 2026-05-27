"""Stable JSON-serializable result mapping helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .core_types import BoundingBox, CameraInspectionResult, InspectionError, InspectionResult


def inspection_result_to_dict(result: InspectionResult) -> Dict[str, Any]:
    """Convert an inspection result to the public/report JSON payload."""
    return {
        "part_id": result.part_id,
        "frame_id": result.frame_id,
        "timestamp": result.timestamp,
        "status": result.status,
        "decision_reason": result.decision_reason,
        "seat_model_id": result.seat_model_id,
        "timings_ms": dict(result.timings_ms),
        "camera_results": [
            camera_result_to_dict(item)
            for item in result.camera_results
        ],
    }


def camera_result_to_dict(result: CameraInspectionResult) -> Dict[str, Any]:
    """Convert one camera result to a JSON-safe payload."""
    out: Dict[str, Any] = {
        "camera_id": result.camera_id,
        "frame_id": result.frame_id,
        "source": result.source,
        "source_kind": result.source_kind,
        "status": result.status,
        "reason": result.reason,
        "seat_model_id": result.seat_model_id,
        "timings_ms": dict(result.timings_ms),
        "error": error_to_dict(result.error),
        "quality": quality_to_dict(result.quality),
        "target_box": resolve_target_box(result),
        "crop_box": box_to_dict(result.crop_box),
        "texture_result": texture_result_to_dict(result.texture_result),
        "filter_result": filter_result_to_dict(result.filter_result),
        "artifact_paths": dict(result.artifact_paths),
    }
    # Add proposals if present
    if result.proposals:
        from ._protocol import proposals_to_json
        import json as _json

        out["proposals"] = _json.loads(proposals_to_json(result.proposals))
    return out


def quality_to_dict(quality) -> Optional[Dict[str, Any]]:
    if quality is None:
        return None
    return {
        "accepted": quality.accepted,
        "reason": quality.reason,
        "metrics": {
            "laplacian_variance": quality.metrics.laplacian_variance,
            "brightness_mean": quality.metrics.brightness_mean,
            "overexposed_ratio": quality.metrics.overexposed_ratio,
            "underexposed_ratio": quality.metrics.underexposed_ratio,
            "is_black_frame": quality.metrics.is_black_frame,
            "is_white_frame": quality.metrics.is_white_frame,
        },
    }


def texture_result_to_dict(texture_result) -> Optional[Dict[str, Any]]:
    if texture_result is None:
        return None
    return {
        "score": texture_result.score,
        "threshold": texture_result.threshold,
        "is_anomaly": texture_result.is_anomaly,
        "valid_pixel_ratio": texture_result.valid_pixel_ratio,
    }


def filter_result_to_dict(filter_result) -> Optional[Dict[str, Any]]:
    if filter_result is None:
        return None
    return {
        "is_real_defect": filter_result.is_real_defect,
        "confidence": filter_result.confidence,
        "real_defect_score": filter_result.real_defect_score,
        "false_alarm_score": filter_result.false_alarm_score,
        "class_id": filter_result.class_id,
        "diagnostics": dict(filter_result.diagnostics),
    }


def error_to_dict(error: Optional[InspectionError]) -> Optional[Dict[str, str]]:
    if error is None:
        return None
    return {
        "code": error.code,
        "message": error.message,
        "stage": error.stage,
    }


def box_to_dict(box: Optional[BoundingBox]) -> Optional[Dict[str, float]]:
    if box is None:
        return None
    return {
        "x1": box.x1,
        "y1": box.y1,
        "x2": box.x2,
        "y2": box.y2,
    }


def resolve_target_box(result: CameraInspectionResult) -> Optional[Dict[str, float]]:
    detection = result.detection
    if detection is None or detection.target is None:
        return None
    return box_to_dict(detection.target.bounding_box)


__all__ = [
    "box_to_dict",
    "camera_result_to_dict",
    "filter_result_to_dict",
    "error_to_dict",
    "inspection_result_to_dict",
    "quality_to_dict",
    "resolve_target_box",
    "texture_result_to_dict",
]
