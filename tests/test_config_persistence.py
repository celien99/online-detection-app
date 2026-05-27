"""Tests for ConfigPersistenceService."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService


def test_init_db_creates_tables(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    svc = ConfigPersistenceService(db_path)
    svc.init_db()

    import sqlite3
    conn = sqlite3.connect(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [r[0] for r in tables]
    assert "seat_models" in table_names
    assert "camera_configs" in table_names
    assert "model_files" in table_names
    assert "system_config" in table_names
    conn.close()


def test_set_and_get_kv(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    svc = ConfigPersistenceService(db_path)

    svc.set("app.line_id", "A-03")
    svc.set("plc.host", "192.168.1.100")
    svc.set("plc.port", "502")

    assert svc.get("app.line_id") == "A-03"
    assert svc.get("plc.host") == "192.168.1.100"
    assert svc.get("plc.port") == "502"
    assert svc.get("nonexistent") is None


def test_set_creates_init_db_implicitly(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    svc = ConfigPersistenceService(db_path)
    svc.set("key", "value")
    assert svc.get("key") == "value"


def test_get_all_kv(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    svc = ConfigPersistenceService(db_path)
    svc.set("a", "1")
    svc.set("b", "2")
    all_kv = svc.get_all()
    assert all_kv["a"] == "1"
    assert all_kv["b"] == "2"


def test_sync_json_to_db(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    json_path = tmp_path / "config.json"
    json_path.write_text(json.dumps({
        "app": {"line_id": "B-01", "grid_layout": "3x2"},
        "plc": {"host": "10.0.0.1", "port": 502},
        "storage": {"log_dir": "/var/log"},
    }), encoding="utf-8")

    svc = ConfigPersistenceService(db_path)
    svc.sync_json_to_db(str(json_path))

    assert svc.get("app.line_id") == "B-01"
    assert svc.get("app.grid_layout") == "3x2"
    assert svc.get("plc.host") == "10.0.0.1"


def test_sync_db_to_json_atomic(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    json_path = str(tmp_path / "config.json")

    svc = ConfigPersistenceService(db_path)
    svc.set("app.line_id", "C-03")
    svc.set("plc.host", "192.168.2.1")
    svc.sync_db_to_json(json_path)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["app"]["line_id"] == "C-03"
    assert data["plc"]["host"] == "192.168.2.1"


def test_json_to_db_roundtrip_preserves_structure(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    json_path = tmp_path / "config.json"
    original = {
        "app": {"line_id": "D-01", "fullscreen": True, "grid_layout": "2x2"},
        "plc": {"enabled": True, "host": "10.1.1.1", "port": 502},
    }
    json_path.write_text(json.dumps(original), encoding="utf-8")

    svc = ConfigPersistenceService(db_path)
    svc.sync_json_to_db(str(json_path))

    out_path = str(tmp_path / "out.json")
    svc.sync_db_to_json(out_path)

    with open(out_path, encoding="utf-8") as f:
        restored = json.load(f)
    assert restored["app"]["line_id"] == "D-01"
    assert restored["app"]["fullscreen"] is True
    assert restored["plc"]["port"] == 502


def test_import_config_from_file(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    json_path = tmp_path / "import.json"
    json_path.write_text(json.dumps({"app": {"line_id": "imported"}}), encoding="utf-8")

    svc = ConfigPersistenceService(db_path)
    svc.import_from_json(str(json_path))

    assert svc.get("app.line_id") == "imported"


def test_export_config_to_file(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    svc = ConfigPersistenceService(db_path)
    svc.set("app.line_id", "export-test")

    export_path = str(tmp_path / "export.json")
    svc.export_to_json(export_path)

    with open(export_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["app"]["line_id"] == "export-test"
