"""Tests for production diagnostics."""
from __future__ import annotations

import json
from types import SimpleNamespace
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


def test_diagnostics_warns_when_production_mvs_source_is_not_hardware_triggered(tmp_path: Path) -> None:
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
                    "type": "mvs",
                    "source": "mvs://0?trigger=continuous",
                    "enabled": True,
                    "efficientad_model_path": str(model_path),
                }
            ],
            "line_signal": {"enabled": True, "type": "modbus", "host": "127.0.0.1", "port": 502},
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert any(item.name == "CAM_A 相机选择" and item.status == "WARN" for item in report.items)
    assert any(item.name == "CAM_A 触发模式" and item.status == "WARN" for item in report.items)


def test_diagnostics_fails_when_production_template_placeholders_remain(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "triggered"},
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "mvs",
                    "source": "mvs://sn/REPLACE_WITH_CAMERA_SN?trigger=hardware&trigger_source=Line0",
                    "enabled": True,
                    "efficientad_model_path": "./models/<camera-model>.pt",
                }
            ],
            "line_signal": {"enabled": True, "type": "modbus", "host": "REPLACE_WITH_PLC_IP", "port": 502},
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert report.status == "FAIL"
    assert any(item.name == "相机 CAM_A source" and item.status == "FAIL" for item in report.items)
    assert any(item.name == "CAM_A EfficientAD 模型" and item.status == "FAIL" for item in report.items)
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


def test_diagnostics_uses_config_directory_for_relative_paths(tmp_path: Path, monkeypatch) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "model.pt").write_bytes(b"model")
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
                    "watch_dir": ".",
                    "efficientad_model_path": "./model.pt",
                }
            ],
            "storage": {"log_dir": ".", "screenshot_dir": "."},
        },
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "app.services.diagnostics.sys.version_info",
        SimpleNamespace(major=3, minor=12, micro=0),
    )

    exit_code = diagnostics_main(["--config", str(config_path), "--json"])

    assert exit_code == 0
    assert Path.cwd() == tmp_path


def test_diagnostics_fails_for_unsupported_python_version(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [],
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )
    monkeypatch.setattr(
        "app.services.diagnostics.sys.version_info",
        SimpleNamespace(major=3, minor=13, micro=0),
    )

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert any(item.name == "Python 版本" and item.status == "FAIL" for item in report.items)
