from __future__ import annotations

import importlib
import json
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.services.diagnostics import ProductionDiagnostics


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_diagnostics_reports_missing_ultralytics_module(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"model")
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": str(tmp_path),
                    "patchcore_model_path": str(model_path),
                }
            ],
            "storage": {"log_dir": str(tmp_path), "screenshot_dir": str(tmp_path)},
        },
    )

    real_import_module = importlib.import_module

    def fake_import_module(name: str, package=None):
        if name == "ultralytics":
            raise ModuleNotFoundError("No module named 'ultralytics'")
        return real_import_module(name, package)

    monkeypatch.setattr("app.services.diagnostics.importlib.import_module", fake_import_module)

    report = ProductionDiagnostics(ConfigStore(str(config_path)), config_path).run()

    assert any(item.name == "Python 模块 ultralytics" and item.status == "FAIL" for item in report.items)
