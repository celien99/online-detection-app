"""Tests for Hikrobot MVS device listing CLI."""
from __future__ import annotations

import json

from app.infrastructure.camera.mvs.camera_controller import MvsDeviceInfo
from app import mvs_list


def test_suggest_source_prefers_serial_number() -> None:
    device = MvsDeviceInfo(index=0, tlayer_type=1, serial_number="ABC123", ip_address="192.168.1.10")

    source = mvs_list._suggest_source(device)

    assert source.startswith("mvs://sn/ABC123?")
    assert "trigger=hardware" in source
    assert "trigger_source=Line0" in source


def test_mvs_list_outputs_json_for_devices(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        mvs_list,
        "list_mvs_devices",
        lambda: [MvsDeviceInfo(index=0, tlayer_type=1, serial_number="ABC123", model_name="MV-TEST")],
    )
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])

    exit_code = mvs_list.main(["--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "OK"
    assert payload["devices"][0]["serial_number"] == "ABC123"
    assert payload["devices"][0]["suggested_source"].startswith("mvs://sn/ABC123?")


def test_mvs_list_reports_loader_failure(monkeypatch, capsys) -> None:
    def fail():
        raise RuntimeError("SDK missing")

    monkeypatch.setattr(mvs_list, "list_mvs_devices", fail)
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])

    exit_code = mvs_list.main(["--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "FAIL"
    assert "SDK missing" in payload["message"]
    assert payload["sdk_candidates"]
