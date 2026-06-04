"""Tests for Hikrobot MVS source parsing."""
from __future__ import annotations

import logging

import numpy as np

from app.infrastructure.camera.mvs_adapter import MvsCameraAdapter
from app.infrastructure.camera.mvs.camera_controller import HikCamera
from app.infrastructure.camera.mvs import camera_controller
from app.infrastructure.camera.mvs.frame_source import parse_mvs_source


def test_parse_hardware_trigger_source() -> None:
    cfg = parse_mvs_source(
        "mvs://sn/ABC123?trigger=hardware&trigger_source=Line0&trigger_activation=rising_edge&pixel_format=bgr8"
    )

    assert cfg.serial_number == "ABC123"
    assert cfg.device_index is None
    assert cfg.trigger_mode == "hardware"
    assert cfg.trigger_source == "line0"
    assert cfg.trigger_activation == "rising_edge"
    assert cfg.pixel_format == "bgr8"


def test_parse_software_trigger_source() -> None:
    cfg = parse_mvs_source("mvs://0?trigger=software&timeout_ms=250")

    assert cfg.device_index == 0
    assert cfg.trigger_mode == "software"
    assert cfg.trigger_source == "software"
    assert cfg.grab_timeout_ms == 250


def test_mvs_adapter_passes_grab_timeout_to_capture() -> None:
    class FakeCapture:
        def __init__(self) -> None:
            self.timeout_ms = None

        def isOpened(self):
            return True

        def read(self, timeout_ms=None):
            self.timeout_ms = timeout_ms
            return True, np.zeros((2, 3, 3), dtype=np.uint8)

    capture = FakeCapture()
    adapter = MvsCameraAdapter("CAM_A", "mvs://0?timeout_ms=250")
    adapter._capture = capture

    frame = adapter.grab_frame(timeout_ms=4321)

    assert frame is not None
    assert capture.timeout_ms == 4321
    assert adapter.get_status().frames_grabbed == 1


def test_software_trigger_does_not_set_trigger_activation() -> None:
    calls: list[tuple[str, int]] = []

    class FakeCam:
        def MV_CC_SetEnumValue(self, key, value):
            calls.append((key, value))
            return 0

    camera = object.__new__(HikCamera)
    camera.cam = FakeCam()

    HikCamera.set_trigger_mode(camera, True, source="software", activation="rising_edge")

    assert [key for key, _ in calls] == ["TriggerMode", "TriggerSource"]


def test_hardware_trigger_skips_inaccessible_trigger_activation(caplog) -> None:
    calls: list[tuple[str, int]] = []

    class FakeCam:
        def MV_CC_SetEnumValue(self, key, value):
            calls.append((key, value))
            if key == "TriggerActivation":
                return camera_controller.error_constants.MV_E_GC_ACCESS
            return 0

    camera = object.__new__(HikCamera)
    camera.cam = FakeCam()

    with caplog.at_level(logging.WARNING):
        HikCamera.set_trigger_mode(camera, True, source="line0", activation="rising_edge")

    assert [key for key, _ in calls] == ["TriggerMode", "TriggerSource", "TriggerActivation"]
    assert "Skipping TriggerActivation" in caplog.text
