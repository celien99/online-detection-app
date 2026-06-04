"""Tests for camera image provider display variants."""
from __future__ import annotations

import numpy as np

from app.infrastructure.image_provider import CameraImageProvider


def test_image_provider_serves_original_and_overlay_images() -> None:
    provider = CameraImageProvider()
    original = np.zeros((2, 3, 3), dtype=np.uint8)
    original[:, :, 0] = 255
    overlay = np.zeros((4, 5, 3), dtype=np.uint8)
    overlay[:, :, 1] = 128

    provider.update_frame("CAM_A", original)
    provider.update_overlay("CAM_A", overlay)

    original_image = provider.requestImage("CAM_A_original", None, None)
    overlay_image = provider.requestImage("CAM_A_overlay", None, None)

    assert original_image.width() == 3
    assert original_image.height() == 2
    assert overlay_image.width() == 5
    assert overlay_image.height() == 4
