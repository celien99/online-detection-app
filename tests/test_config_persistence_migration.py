"""Tests for config migration from JSON to SQLite."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService


def test_migrate_cameras_from_json(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    json_path = tmp_path / "config.json"
    json_path.write_text(json.dumps({
        "cameras": [
            {
                "camera_id": "CAM_A",
                "type": "mvs",
                "source": "mvs://1",
                "enabled": True,
                "patchcore_model_path": "./models/a.pt",
                "filter_classifier": {"enabled": True, "model_path": "./fc/a/"},
            },
            {
                "camera_id": "CAM_B",
                "type": "rtsp",
                "source": "rtsp://10.0.0.1/stream",
                "enabled": False,
                "patchcore_model_path": "",
            },
        ]
    }), encoding="utf-8")

    svc = ConfigPersistenceService(db_path)
    svc.migrate_from_json(str(json_path))

    cameras = svc.list_cameras()
    assert len(cameras) == 2

    cam_a = svc.get_camera("CAM_A")
    assert cam_a is not None
    assert cam_a["type"] == "mvs"
    assert cam_a["patchcore_model_path"] == "./models/a.pt"
    assert cam_a["filter_classifier_path"] == "./fc/a/"
    assert cam_a["filter_classifier_enabled"] == 1

    cam_b = svc.get_camera("CAM_B")
    assert cam_b is not None
    assert cam_b["enabled"] == 0
    assert cam_b["patchcore_model_path"] == ""
