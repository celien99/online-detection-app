"""Tests for packaged site troubleshooting reports."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from app import mvs_list
from app.model_check import ModelCheckResult
from app.infrastructure.line_signal import InspectionDecision
from app.infrastructure.camera.mvs.camera_controller import MvsDeviceInfo
from app.site_report import main as site_report_main


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _ok_model_check(config_path: Path, seat_model_id: str | None = None) -> ModelCheckResult:
    return ModelCheckResult(
        status="OK",
        message="Model runtime warmup succeeded",
        config_path=str(config_path),
        camera_count=1,
        seat_model_id=seat_model_id or "",
        warmup_skipped=False,
        elapsed_ms=12,
        runtime_modules=[],
    )


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
    monkeypatch.setattr("app.site_report.check_models", _ok_model_check)

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
    assert payload["model_check"]["status"] == "OK"
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
    monkeypatch.setattr("app.site_report.check_models", _ok_model_check)

    exit_code = site_report_main(["--config", str(config_path), "--output", "site_report.json", "--json"])

    assert exit_code == 1
    payload = json.loads((tmp_path / "site_report.json").read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["camera_check"]["items"][0]["status"] == "FAIL"


def test_site_report_can_send_line_test_result(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [],
            "line_signal": {"enabled": True, "type": "virtual"},
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    sent_results = []

    class CapturingVirtualAdapter:
        enabled = True

        def __init__(self) -> None:
            from app.infrastructure.line_signal import VirtualLineSignalAdapter

            self._inner = VirtualLineSignalAdapter()

        @property
        def connected(self):
            return self._inner.connected

        def connect(self):
            self._inner.connect()

        def disconnect(self):
            self._inner.disconnect()

        def poll_capture_request(self):
            return self._inner.poll_capture_request()

        def send_busy(self, request, busy):
            self._inner.send_busy(request, busy)

        def send_result(self, result):
            sent_results.append(result)
            self._inner.send_result(result)

        def send_fault(self, request, code, message):
            self._inner.send_fault(request, code, message)

        def read_line_status(self):
            return self._inner.read_line_status()

    monkeypatch.setattr("app.line_check.create_line_signal", lambda line_config, plc_config: CapturingVirtualAdapter())
    monkeypatch.setattr(mvs_list, "list_mvs_devices", lambda: [])
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])
    monkeypatch.setattr("app.site_report.check_models", _ok_model_check)

    exit_code = site_report_main(
        [
            "--config",
            str(config_path),
            "--output",
            "site_report.json",
            "--skip-camera-check",
            "--send-test-result",
            "NG",
            "--defect-code",
            "88",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["line_signal"]["test_result_sent"] == "NG"
    assert payload["line_signal"]["defect_code"] == 88
    assert sent_results[0].status == InspectionDecision.NG
    assert sent_results[0].defect_code == 88


def test_site_report_camera_connect_only_skips_sample_grab(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    input_dir = site_dir / "input" / "CAM_A"
    input_dir.mkdir(parents=True)
    model_path = site_dir / "model.pt"
    model_path.write_bytes(b"model")
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
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    monkeypatch.setattr(mvs_list, "list_mvs_devices", lambda: [])
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])
    monkeypatch.setattr("app.site_report.check_models", _ok_model_check)

    exit_code = site_report_main(
        [
            "--config",
            str(config_path),
            "--output",
            "site_report.json",
            "--camera-samples-dir",
            "camera_samples",
            "--camera-connect-only",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    camera_item = payload["camera_check"]["items"][0]

    assert exit_code == 0
    assert camera_item["status"] == "OK"
    assert camera_item["frames_grabbed"] == 0
    assert camera_item["sample_path"] == ""
    assert not (site_dir / "camera_samples").exists()


def test_site_report_can_skip_model_check(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "model.pt").write_bytes(b"model")
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
                    "watch_dir": "./input/CAM_A",
                    "efficientad_model_path": "./model.pt",
                }
            ],
            "line_signal": {"enabled": True, "type": "virtual"},
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    calls = []
    monkeypatch.setattr(mvs_list, "list_mvs_devices", lambda: [])
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])
    monkeypatch.setattr("app.site_report.check_models", lambda **kwargs: calls.append(kwargs))

    exit_code = site_report_main(
        [
            "--config",
            str(config_path),
            "--output",
            "site_report.json",
            "--skip-model-check",
            "--skip-camera-check",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert calls == []
    assert payload["model_check"]["status"] == "SKIP"
    assert payload["model_check"]["message"] == "Model runtime check skipped"


def test_site_report_passes_seat_model_id_to_model_check(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "model.pt").write_bytes(b"model")
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
                    "watch_dir": "./input/CAM_A",
                    "efficientad_model_path": "./model.pt",
                }
            ],
            "line_signal": {"enabled": True, "type": "virtual"},
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    seen = []

    def fake_model_check(*, config_path: Path, seat_model_id: str | None = None, skip_warmup: bool = False):
        seen.append((config_path.name, seat_model_id, skip_warmup))
        return _ok_model_check(config_path, seat_model_id)

    monkeypatch.setattr(mvs_list, "list_mvs_devices", lambda: [])
    monkeypatch.setattr(mvs_list, "describe_mvs_sdk_candidates", lambda path: [str(path)])
    monkeypatch.setattr("app.site_report.check_models", fake_model_check)

    exit_code = site_report_main(
        [
            "--config",
            str(config_path),
            "--output",
            "site_report.json",
            "--skip-camera-check",
            "--seat-model-id",
            "MODEL_A",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert seen == [("config.json", "MODEL_A", False)]
    assert payload["model_check"]["seat_model_id"] == "MODEL_A"
