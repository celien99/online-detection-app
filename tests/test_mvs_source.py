"""Tests for Hikrobot MVS source parsing."""
from __future__ import annotations

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
