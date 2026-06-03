from __future__ import annotations

import numpy as np

from seat_defect_core.config import CameraConfig, QualityGuardConfig, RegionConfig
from seat_defect_core.core_types import BoundingBox, DetectionObject, DetectionResult
from seat_defect_core.training.patchcore import prepare_patchcore_training_samples


def _camera_config() -> CameraConfig:
    return CameraConfig(
        camera_id="cam_front",
        patchcore_model_path="unused.npz",
        quality=QualityGuardConfig(min_laplacian_variance=0.0),
        regions=[
            RegionConfig(
                region_id="upper",
                box=[0.0, 0.0, 1.0, 0.5],
                patchcore_model_path="upper.npz",
            ),
            RegionConfig(
                region_id="lower",
                box=[0.0, 0.5, 1.0, 1.0],
                patchcore_model_path="lower.npz",
            ),
        ],
    )


def _image_and_detection() -> tuple[np.ndarray, DetectionResult]:
    image = np.full((80, 100, 3), 128, dtype=np.uint8)
    image[20:60, 25:75] = 180
    mask = np.zeros((80, 100), dtype=np.uint8)
    mask[20:60, 25:75] = 1
    detection = DetectionResult(
        target=DetectionObject(
            label="seat",
            confidence=0.99,
            bounding_box=BoundingBox(x1=25, y1=20, x2=75, y2=60),
            segmentation_mask=mask,
        )
    )
    return image, detection


def test_online_mode_uses_roi_pipeline_masks() -> None:
    image, detection = _image_and_detection()
    samples, skipped_reason = prepare_patchcore_training_samples(
        image,
        _camera_config(),
        input_mode="online",
        detection_result=detection,
    )

    assert skipped_reason is None
    assert len(samples) == 1
    sample = samples[0]
    assert sample.image.shape == (256, 256, 4)
    assert sample.image.dtype == np.uint8
    assert sample.target_mask.shape == (256, 256)
    assert sample.ignore_mask.shape == (256, 256)
    assert int(sample.target_mask.sum()) > 0


def test_online_mode_region_id_returns_only_requested_region() -> None:
    image, detection = _image_and_detection()
    samples, skipped_reason = prepare_patchcore_training_samples(
        image,
        _camera_config(),
        input_mode="online",
        region_id="upper",
        detection_result=detection,
    )

    assert skipped_reason is None
    assert len(samples) == 1
    assert samples[0].region_id == "upper"
    assert samples[0].image.shape[0] == 128
    assert samples[0].image.shape[1] == 256
    assert int(samples[0].target_mask.sum()) > 0


def test_online_mode_reports_skipped_reason_for_missing_target() -> None:
    image = np.full((80, 100, 3), 128, dtype=np.uint8)
    samples, skipped_reason = prepare_patchcore_training_samples(
        image,
        _camera_config(),
        input_mode="online",
        detection_result=DetectionResult(target=None),
    )

    assert samples == []
    assert skipped_reason == "target_not_found"
