"""Tests for config migration from JSON to SQLite."""
from __future__ import annotations

import json
import sqlite3
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
                "regions": [
                    {
                        "region_id": "upper",
                        "box": [0.0, 0.0, 1.0, 0.5],
                        "patchcore_model_path": "./models/a_upper.pt",
                    }
                ],
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
    assert json.loads(cam_a["regions_json"])[0]["patchcore_model_path"] == "./models/a_upper.pt"
    assert cam_a["filter_classifier_path"] == "./fc/a/"
    assert cam_a["filter_classifier_enabled"] == 1

    cam_b = svc.get_camera("CAM_B")
    assert cam_b is not None
    assert cam_b["enabled"] == 0
    assert cam_b["patchcore_model_path"] == ""


def test_legacy_camera_primary_key_schema_migrates_to_seat_scoped_schema(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    now = "2026-06-01T00:00:00+00:00"
    conn.executescript("""
        CREATE TABLE seat_models (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE camera_configs (
            camera_id TEXT PRIMARY KEY,
            type TEXT DEFAULT 'mvs',
            source TEXT NOT NULL DEFAULT '',
            enabled INTEGER DEFAULT 1,
            patchcore_model_path TEXT DEFAULT '',
            filter_classifier_path TEXT DEFAULT '',
            filter_classifier_enabled INTEGER DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE model_files (
            id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            model_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            sha256 TEXT DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual_import',
            platform_version TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            imported_at TEXT NOT NULL
        );
        CREATE TABLE system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT INTO camera_configs "
        "(camera_id, type, source, enabled, patchcore_model_path, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("CAM_A", "file_watcher", "./input", 1, "./legacy.pt", now, now),
    )
    conn.commit()
    conn.close()

    svc = ConfigPersistenceService(str(db_path))
    svc.set("migration.touch", "1")

    migrated = svc.get_camera("CAM_A", seat_model_id="default")
    assert migrated is not None
    assert migrated["patchcore_model_path"] == "./legacy.pt"

    svc.create_seat_model("MODEL_B", "型号B")
    svc.create_camera(
        {
            "seat_model_id": "MODEL_B",
            "camera_id": "CAM_A",
            "type": "file_watcher",
            "source": "./input_b",
            "patchcore_model_path": "./model_b.pt",
        }
    )

    assert svc.get_camera("CAM_A", seat_model_id="default")["patchcore_model_path"] == "./legacy.pt"
    assert svc.get_camera("CAM_A", seat_model_id="MODEL_B")["patchcore_model_path"] == "./model_b.pt"
