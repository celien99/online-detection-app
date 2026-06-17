"""Tests for DiagnosticsViewModel site report generation."""
from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.viewmodels.diagnostics_viewmodel import DiagnosticsViewModel


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_generate_site_report_uses_runtime_camera_configs(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "app": {"inspection_mode": "continuous"},
            "cameras": [
                {
                    "camera_id": "CAM_JSON",
                    "type": "file_watcher",
                    "enabled": True,
                    "patchcore_model_path": "./json.pt",
                }
            ],
            "storage": {"log_dir": "./logs", "screenshot_dir": "."},
        },
    )
    runtime_cameras = [
        {
            "camera_id": "CAM_RUNTIME",
            "type": "file_watcher",
            "enabled": True,
            "patchcore_model_path": str(tmp_path / "runtime.pt"),
        }
    ]
    seen = {}

    def fake_collect_site_report(**kwargs):
        seen.update(kwargs)
        return {
            "status": "OK",
            "diagnostics": {
                "status": "OK",
                "items": [
                    {
                        "name": "运行时模型",
                        "status": "OK",
                        "message": "runtime model checked",
                        "suggestion": "",
                    }
                ],
            },
        }

    monkeypatch.setattr(
        "app.viewmodels.diagnostics_viewmodel.collect_site_report",
        fake_collect_site_report,
    )
    vm = DiagnosticsViewModel(
        ConfigStore(str(config_path)),
        str(config_path),
        camera_configs_provider=lambda: runtime_cameras,
        seat_model_id_provider=lambda: "MODEL_A",
    )

    assert vm.generateSiteReport() is True

    assert seen["camera_configs"] == runtime_cameras
    assert seen["seat_model_id"] == "MODEL_A"
    assert Path(vm.lastReportPath).exists()
    payload = json.loads(Path(vm.lastReportPath).read_text(encoding="utf-8"))
    assert payload["status"] == "OK"
    assert vm.overallStatus == "OK"
    assert vm.reportStatus == "OK"
    assert vm.items[0]["name"] == "运行时模型"

