"""Tests for production diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from app.diagnostics import main as diagnostics_main
from app.infrastructure.config_store import ConfigStore
from app.services.diagnostics import ProductionDiagnostics


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_diagnostics_fails_without_enabled_cameras(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "triggered"},
            "cameras": [],
            "line_signal": {"enabled": True, "type": "modbus", "host": "127.0.0.1", "port": 502},
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert report.status == "FAIL"
    assert any(item.name == "相机配置" and item.status == "FAIL" for item in report.items)


def test_diagnostics_reports_missing_model_files(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "triggered"},
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": str(tmp_path),
                    "efficientad_model_path": "./missing.pt",
                }
            ],
            "line_signal": {"enabled": True, "type": "modbus", "host": "127.0.0.1", "port": 502},
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert report.status == "FAIL"
    assert any(item.name == "CAM_A EfficientAD 模型" and item.status == "FAIL" for item in report.items)


def test_diagnostics_warns_when_triggered_line_signal_disabled(tmp_path: Path) -> None:
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"model")
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "triggered"},
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": str(tmp_path),
                    "efficientad_model_path": str(model_path),
                }
            ],
            "line_signal": {"enabled": False, "type": "virtual"},
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert report.status == "FAIL"
    assert any(item.name == "产线触发" and item.status == "FAIL" for item in report.items)


def test_diagnostics_json_output_shape(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [],
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    exit_code = diagnostics_main(["--config", str(config_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "FAIL"
    assert isinstance(payload["items"], list)
    assert {"name", "status", "message", "suggestion"} <= set(payload["items"][0])
