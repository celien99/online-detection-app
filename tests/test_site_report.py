"""Tests for packaged site troubleshooting reports."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from app import mvs_list
from app.infrastructure.camera.mvs.camera_controller import MvsDeviceInfo
from app.site_report import main as site_report_main


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_site_report_collects_checks_and_restores_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    input_dir = site_dir / "input" / "CAM_A"
    input_dir.mkdir(parents=True)
    model_path = site_dir / "model.pt"
    model_path.write_bytes(b"model")
    frame_path = input_dir / "frame.jpg"
    image = np.zeros((8, 10, 3), dtype=np.uint8)
    image[:, :, 2] = 48
    assert cv2.imwrite(str(frame_path), image)
    config_path = site_dir / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": "./input/CAM_A",
                    "pattern": "*.jpg",
                    "efficientad_model_path": "./model.pt",
                }
            ],
            "line_signal": {"enabled": True, "type": "virtual"},
            "plc": {"enabled": False},
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        mvs_list,
        "list_mvs_devices",
        lambda: [MvsDeviceInfo(index=0, tlayer_type=1, serial_number="ABC123", model_name="MV-TEST")],
    )
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])

    exit_code = site_report_main(
        [
            "--config",
            str(config_path),
            "--output",
            "site_report.json",
            "--camera-samples-dir",
            "camera_samples",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    report_path = site_dir / "site_report.json"

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert report_path.exists()
    assert payload == json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "WARN"
    assert payload["diagnostics"]["status"] == "WARN"
    assert payload["line_signal"]["status"] == "OK"
    assert payload["mvs_devices"]["devices"][0]["serial_number"] == "ABC123"
    camera_item = payload["camera_check"]["items"][0]
    assert camera_item["status"] == "OK"
    assert camera_item["width"] == 10
    assert camera_item["height"] == 8
    assert (site_dir / camera_item["sample_path"]).exists()


def test_site_report_returns_failure_when_camera_check_fails(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": "./empty",
                    "pattern": "*.jpg",
                }
            ],
            "line_signal": {"enabled": True, "type": "virtual"},
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    monkeypatch.setattr(mvs_list, "list_mvs_devices", lambda: [])
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])

    exit_code = site_report_main(["--config", str(config_path), "--output", "site_report.json", "--json"])

    assert exit_code == 1
    payload = json.loads((tmp_path / "site_report.json").read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["camera_check"]["items"][0]["status"] == "FAIL"
