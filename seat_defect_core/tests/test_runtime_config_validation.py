from __future__ import annotations

import pytest

from seat_defect_core.config import (
    CameraConfig,
    InspectionConfig,
    PatchCoreConfig,
    SeatModelConfig,
)
from seat_defect_core.runtime_config import validate_inspection_config


def test_default_patchcore_full_config_has_usable_backbone_source() -> None:
    config = InspectionConfig(
        seat_models=[
            SeatModelConfig(
                seat_model_id="seat_model_A",
                display_name="Seat A",
                cameras=[
                    CameraConfig(
                        camera_id="cam_back",
                        patchcore_model_path="unused.npz",
                    )
                ],
            )
        ]
    )

    validate_inspection_config(config)
    assert config.seat_models[0].cameras[0].patchcore.backbone_pretrained is True


def test_patchcore_full_without_backbone_source_is_rejected() -> None:
    config = InspectionConfig(
        cameras=[
            CameraConfig(
                camera_id="cam_back",
                patchcore_model_path="unused.npz",
                patchcore=PatchCoreConfig(backbone_pretrained=False),
            )
        ]
    )

    with pytest.raises(ValueError, match="没有提供可用 backbone 权重"):
        validate_inspection_config(config)
