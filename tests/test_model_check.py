"""Tests for packaged model runtime checks."""
from __future__ import annotations

import json
from pathlib import Path

from app.model_check import ModuleCheck, main as model_check_main


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_model_check_skip_warmup_parses_config_and_restores_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
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
                    "efficientad_model_path": "./models/cam_a.pt",
                }
            ],
        },
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "app.model_check._check_runtime_modules",
        lambda **_: [
            ModuleCheck(name="numpy", status="OK", message="imported", version="1.0"),
            ModuleCheck(name="torch", status="OK", message="imported", version="2.0 (cpu)"),
        ],
    )

    exit_code = model_check_main(["--config", str(config_path), "--skip-warmup", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert payload["status"] == "OK"
    assert payload["camera_count"] == 1
    assert payload["warmup_skipped"] is True
    assert payload["runtime_modules"][0]["name"] == "numpy"


def test_model_check_warmup_passes_seat_model_id(tmp_path: Path, monkeypatch, capsys) -> None:
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
                    "efficientad_model_path": "./models/cam_a.pt",
                }
            ],
        },
    )
    calls = []

    class FakeInspectionService:
        def __init__(self, config) -> None:
            self.config = config

        def warmup(self, *, seat_model_id=None) -> None:
            calls.append(seat_model_id)

        def shutdown(self) -> None:
            calls.append("shutdown")

    monkeypatch.setattr(
        "app.model_check._check_runtime_modules",
        lambda **_: [ModuleCheck(name="torch", status="OK", message="imported", version="2.0 (cpu)")],
    )
    monkeypatch.setattr("app.model_check.InspectionService", FakeInspectionService)

    exit_code = model_check_main(["--config", str(config_path), "--seat-model-id", "MODEL_A", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "OK"
    assert payload["seat_model_id"] == "MODEL_A"
    assert calls == ["MODEL_A", "shutdown"]


def test_model_check_returns_failure_when_import_fails(tmp_path: Path, monkeypatch, capsys) -> None:
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
                    "efficientad_model_path": "./models/cam_a.pt",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "app.model_check._check_runtime_modules",
        lambda **_: [ModuleCheck(name="torch", status="FAIL", message="missing")],
    )

    exit_code = model_check_main(["--config", str(config_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "FAIL"
    assert "failed to import" in payload["message"]


def test_model_check_basic_mode_does_not_require_ml_imports(tmp_path: Path, monkeypatch, capsys) -> None:
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
                    "efficientad_model_path": "",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "app.model_check._check_runtime_modules",
        lambda **_: [ModuleCheck(name="seat_defect_core", status="OK", message="imported")],
    )

    exit_code = model_check_main(["--config", str(config_path), "--skip-warmup", "--basic", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "OK"


def test_model_check_missing_config_returns_usage_failure(tmp_path: Path, capsys) -> None:
    exit_code = model_check_main(["--config", str(tmp_path / "missing.json")])

    assert exit_code == 2
    assert "Config file not found" in capsys.readouterr().err
