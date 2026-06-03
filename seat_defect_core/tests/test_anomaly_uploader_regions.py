from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from seat_defect_core.anomaly_uploader import upload_camera_result
from seat_defect_core.core_types import (
    BoundingBox,
    CameraInspectionResult,
    RegionPatchCoreResult,
    TextureAnomalyResult,
)


def _texture(score: float) -> TextureAnomalyResult:
    heatmap = np.zeros((32, 32), dtype=np.float32)
    heatmap[10:20, 10:20] = score
    return TextureAnomalyResult(
        score=score,
        threshold=0.5,
        is_anomaly=True,
        heatmap=heatmap,
        valid_patch_ratio=1.0,
        valid_patch_count=1024,
        total_patch_count=1024,
    )


def _region(region_id: str, score: float) -> RegionPatchCoreResult:
    return RegionPatchCoreResult(
        region_id=region_id,
        status="NG",
        reason="texture_anomaly",
        box=BoundingBox(x1=0, y1=0, x2=32, y2=32),
        texture_result=_texture(score),
        sample=SimpleNamespace(image=np.full((32, 32, 3), 128, dtype=np.uint8)),
    )


def test_region_mode_uploads_each_ng_region_with_region_id() -> None:
    result = CameraInspectionResult(
        camera_id="cam_front",
        frame_id="frame_1",
        source="unit-test",
        source_kind="image",
        status="NG",
        reason="region_texture_anomaly:upper,lower",
        seat_model_id="seat_a",
        region_results=[
            _region("upper", 0.8),
            _region("lower", 0.9),
        ],
        original_image=np.full((64, 64, 3), 100, dtype=np.uint8),
    )

    responses = [
        {"anomaly_ids": ["a1"], "count": 1, "schema_version": "1.0"},
        {"anomaly_ids": ["a2"], "count": 1, "schema_version": "1.0"},
    ]

    with patch("seat_defect_core.anomaly_uploader.requests.post") as post:
        post.side_effect = [
            Mock(status_code=200, json=Mock(return_value=responses[0]), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=responses[1]), raise_for_status=Mock()),
        ]

        uploaded = upload_camera_result(result, "http://backend", date_folder="2026-06-02")

    assert uploaded is not None
    assert uploaded["anomaly_ids"] == ["a1", "a2"]
    assert uploaded["count"] == 2
    assert post.call_count == 2
    assert post.call_args_list[0].kwargs["data"]["region_id"] == "upper"
    assert post.call_args_list[0].kwargs["data"]["anomaly_score"] == 0.8
    assert post.call_args_list[1].kwargs["data"]["region_id"] == "lower"
    assert post.call_args_list[1].kwargs["data"]["anomaly_score"] == 0.9
