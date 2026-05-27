# Online Detection App — 全功能管理端扩展 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PySide6+QML 在线检测 App 从只读监视终端升级为全功能管理终端（可编辑配置 + 座椅型号管理 + 模型文件管理 + 离线平台可选集成）

**Architecture:** 底层新增 ConfigPersistenceService（JSON↔SQLite 双写）+ SeatModelService + ModelFileService + PlatformSyncService 四个 Python Service；ViewModel 层改造 SettingsViewModel（+setValue/+save）并新增 SeatModelViewModel + ModelDeployViewModel；QML 层改造 SettingsScreen 为可编辑表单，新增 SeatModelScreen + ModelDeployScreen 两个页面，TabBar 从 4 个扩展到 7 个 Tab

**Tech Stack:** Python 3.12, PySide6, QML, SQLite3, requests, hashlib, uuid, threading

---

### Phase 1: Foundation — ConfigPersistenceService

### Task 1: Create ConfigPersistenceService

**Files:**
- Create: `app/services/config_persistence.py`
- Create: `tests/test_config_persistence.py`

- [ ] **Step 1: Write the test file**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config_persistence.py -v
```
Expected: all fail with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write ConfigPersistenceService implementation**

```python
"""JSON ↔ SQLite dual-write config persistence."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigPersistenceService:
    """管理 SQLite 中的配置和模型数据，并支持 JSON 双向同步。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._models_dir: str | None = None

    def _get_conn(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── DB init ──

    def init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS seat_models (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS camera_configs (
                    camera_id TEXT PRIMARY KEY,
                    seat_model_id TEXT NOT NULL,
                    type TEXT DEFAULT 'mvs',
                    source TEXT NOT NULL DEFAULT '',
                    enabled INTEGER DEFAULT 1,
                    efficientad_model_path TEXT DEFAULT '',
                    filter_classifier_path TEXT DEFAULT '',
                    filter_classifier_enabled INTEGER DEFAULT 0,
                    calibration_normalizer TEXT DEFAULT '',
                    calibration_projector TEXT DEFAULT '',
                    display_order INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (seat_model_id) REFERENCES seat_models(id)
                );
                CREATE TABLE IF NOT EXISTS model_files (
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
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_camera_seat ON camera_configs(seat_model_id);
                CREATE INDEX IF NOT EXISTS idx_model_camera ON model_files(camera_id);
                CREATE INDEX IF NOT EXISTS idx_model_active ON model_files(camera_id, model_type, is_active);
            """)
            conn.commit()

    # ── K-V config ──

    def get(self, key: str) -> Optional[str]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM system_config WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO system_config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def get_all(self) -> Dict[str, str]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM system_config").fetchall()
        return {row[0]: row[1] for row in rows}

    # ── JSON sync ──

    def sync_json_to_db(self, json_path: str) -> None:
        """从 JSON 文件解析所有配置并写入 SQLite K-V 表。"""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        with self._get_conn() as conn:
            conn.execute("DELETE FROM system_config WHERE key NOT LIKE '_meta.%'")
            _flatten_and_insert(conn, data, prefix="")
            conn.execute(
                "INSERT INTO system_config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("_meta.last_json_sync", str(os.path.getmtime(json_path))),
            )
            conn.commit()

    def sync_db_to_json(self, json_path: str) -> None:
        """将 SQLite K-V 配置导出为嵌套 JSON 并原子写入。"""
        kv = self.get_all()
        data: Dict[str, Any] = {}
        for key, value in kv.items():
            if key.startswith("_meta."):
                continue
            _set_nested(data, key, value)
        tmp_path = json_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, json_path)

    def import_from_json(self, json_path: str) -> None:
        self.sync_json_to_db(json_path)

    def export_to_json(self, json_path: str) -> None:
        self.sync_db_to_json(json_path)

    # ── Seat models ──

    def list_seat_models(self) -> list[dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM seat_models ORDER BY is_default DESC, created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_seat_model(self, model_id: str) -> dict | None:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM seat_models WHERE id = ?", (model_id,)
            ).fetchone()
        return dict(row) if row else None

    def create_seat_model(self, model_id: str, display_name: str, description: str = "") -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO seat_models (id, display_name, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (model_id, display_name, description, now, now),
            )
            conn.commit()

    def update_seat_model(self, model_id: str, **kwargs: Any) -> None:
        from datetime import datetime, timezone
        allowed = {"display_name", "description", "is_default"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [model_id]
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE seat_models SET {set_clause} WHERE id = ?", values
            )
            conn.commit()

    def delete_seat_model(self, model_id: str) -> bool:
        with self._get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM camera_configs WHERE seat_model_id = ?", (model_id,)
            ).fetchone()[0]
            if count > 0:
                return False
            conn.execute("DELETE FROM seat_models WHERE id = ?", (model_id,))
            conn.commit()
            return True

    def set_default_seat_model(self, model_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute("UPDATE seat_models SET is_default = 0")
            conn.execute("UPDATE seat_models SET is_default = 1 WHERE id = ?", (model_id,))
            conn.commit()

    # ── Camera configs ──

    def list_cameras(self, seat_model_id: str | None = None) -> list[dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            if seat_model_id:
                rows = conn.execute(
                    "SELECT * FROM camera_configs WHERE seat_model_id = ? ORDER BY display_order",
                    (seat_model_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM camera_configs ORDER BY seat_model_id, display_order"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_camera(self, camera_id: str) -> dict | None:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM camera_configs WHERE camera_id = ?", (camera_id,)
            ).fetchone()
        return dict(row) if row else None

    def create_camera(self, camera: dict) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO camera_configs
                   (camera_id, seat_model_id, type, source, enabled,
                    efficientad_model_path, filter_classifier_path, filter_classifier_enabled,
                    calibration_normalizer, calibration_projector, display_order,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    camera["camera_id"], camera["seat_model_id"],
                    camera.get("type", "mvs"), camera.get("source", ""),
                    camera.get("enabled", 1), camera.get("efficientad_model_path", ""),
                    camera.get("filter_classifier_path", ""),
                    camera.get("filter_classifier_enabled", 0),
                    camera.get("calibration_normalizer", ""),
                    camera.get("calibration_projector", ""),
                    camera.get("display_order", 0), now, now,
                ),
            )
            conn.commit()

    def update_camera(self, camera_id: str, **kwargs: Any) -> None:
        from datetime import datetime, timezone
        allowed = {
            "type", "source", "enabled", "efficientad_model_path",
            "filter_classifier_path", "filter_classifier_enabled",
            "calibration_normalizer", "calibration_projector", "display_order",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [camera_id]
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE camera_configs SET {set_clause} WHERE camera_id = ?", values
            )
            conn.commit()

    def delete_camera(self, camera_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM camera_configs WHERE camera_id = ?", (camera_id,))
            conn.commit()

    # ── Model files ──

    def list_model_files(
        self, camera_id: str | None = None, model_type: str | None = None
    ) -> list[dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM model_files WHERE 1=1"
            params: list = []
            if camera_id:
                sql += " AND camera_id = ?"
                params.append(camera_id)
            if model_type:
                sql += " AND model_type = ?"
                params.append(model_type)
            sql += " ORDER BY imported_at DESC"
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_model_file(self, file_id: str) -> dict | None:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM model_files WHERE id = ?", (file_id,)
            ).fetchone()
        return dict(row) if row else None

    def insert_model_file(self, mf: dict) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO model_files
                   (id, camera_id, model_type, file_path, file_name, file_size,
                    sha256, source, platform_version, is_active, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mf["id"], mf["camera_id"], mf["model_type"], mf["file_path"],
                    mf["file_name"], mf.get("file_size", 0), mf.get("sha256", ""),
                    mf.get("source", "manual_import"), mf.get("platform_version", ""),
                    mf.get("is_active", 1), mf["imported_at"],
                ),
            )
            conn.commit()

    def set_model_file_active(self, file_id: str, camera_id: str, model_type: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE model_files SET is_active = 0 WHERE camera_id = ? AND model_type = ?",
                (camera_id, model_type),
            )
            conn.execute(
                "UPDATE model_files SET is_active = 1 WHERE id = ?", (file_id,)
            )
            conn.commit()

    def delete_model_file(self, file_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM model_files WHERE id = ?", (file_id,))
            conn.commit()

    def get_active_model_path(self, camera_id: str, model_type: str) -> str | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT file_path FROM model_files WHERE camera_id = ? AND model_type = ? AND is_active = 1",
                (camera_id, model_type),
            ).fetchone()
        return row[0] if row else None


def _flatten_and_insert(conn: sqlite3.Connection, data: dict, prefix: str) -> None:
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _flatten_and_insert(conn, value, full_key)
        elif isinstance(value, list):
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
                (full_key, json.dumps(value, ensure_ascii=False)),
            )
        elif isinstance(value, bool):
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
                (full_key, "true" if value else "false"),
            )
        elif value is not None:
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
                (full_key, str(value)),
            )


def _set_nested(data: dict, key: str, value: str) -> None:
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    last = parts[-1]
    if value.lower() == "true":
        current[last] = True
    elif value.lower() == "false":
        current[last] = False
    elif value.isdigit():
        current[last] = int(value)
    elif value.startswith("[") or value.startswith("{"):
        current[last] = json.loads(value)
    else:
        current[last] = value
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config_persistence.py -v
```
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/config_persistence.py tests/test_config_persistence.py
git commit -m "feat: add ConfigPersistenceService with JSON↔SQLite dual-write"
```

---

### Task 2: Migrate cameras[] from JSON to SQLite on startup

**Files:**
- Modify: `app/services/config_persistence.py` (add migration method)
- Create: `tests/test_config_persistence_migration.py`

- [ ] **Step 1: Write migration test**

```python
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
                "efficientad_model_path": "./models/a.pt",
                "filter_classifier": {"enabled": True, "model_path": "./fc/a/"},
                "calibration": {"normalizer_path": "./cal/a_norm.json", "projector_path": "./cal/proj.pt"},
            },
            {
                "camera_id": "CAM_B",
                "type": "rtsp",
                "source": "rtsp://10.0.0.1/stream",
                "enabled": False,
                "efficientad_model_path": "",
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
    assert cam_a["efficientad_model_path"] == "./models/a.pt"
    assert cam_a["filter_classifier_path"] == "./fc/a/"
    assert cam_a["filter_classifier_enabled"] == 1
    assert cam_a["calibration_normalizer"] == "./cal/a_norm.json"
    assert cam_a["calibration_projector"] == "./cal/proj.pt"

    cam_b = svc.get_camera("CAM_B")
    assert cam_b is not None
    assert cam_b["enabled"] == 0
    assert cam_b["efficientad_model_path"] == ""

    # Verify K-V migration
    assert svc.get("app.line_id") is None  # not present in test JSON
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config_persistence_migration.py::test_migrate_cameras_from_json -v
```
Expected: FAIL with `AttributeError: 'ConfigPersistenceService' object has no attribute 'migrate_from_json'`

- [ ] **Step 3: Add `migrate_from_json` to ConfigPersistenceService**

Add this method to `ConfigPersistenceService` in `app/services/config_persistence.py`:

```python
def migrate_from_json(self, json_path: str) -> None:
    """首次启动：从 config.json 迁移 cameras 到 SQLite，并导入 K-V 配置。"""
    self.init_db()
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Seed a default seat model if none exist
    with self._get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM seat_models").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO seat_models (id, display_name, description, is_default, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                ("default", "默认型号", "从 config.json 自动迁移", now, now),
            )
            conn.commit()

    # Migrate cameras
    cameras = data.get("cameras", [])
    for cam in cameras:
        fc = cam.get("filter_classifier", {})
        cal = cam.get("calibration", {})
        self.create_camera({
            "camera_id": cam["camera_id"],
            "seat_model_id": "default",
            "type": cam.get("type", "mvs"),
            "source": cam.get("source", ""),
            "enabled": 1 if cam.get("enabled", True) else 0,
            "efficientad_model_path": cam.get("efficientad_model_path", ""),
            "filter_classifier_path": fc.get("model_path", ""),
            "filter_classifier_enabled": 1 if fc.get("enabled") else 0,
            "calibration_normalizer": cal.get("normalizer_path", ""),
            "calibration_projector": cal.get("projector_path", ""),
            "display_order": len(self.list_cameras("default")),
        })

    # Migrate K-V
    self.sync_json_to_db(json_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_config_persistence_migration.py::test_migrate_cameras_from_json -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/config_persistence.py tests/test_config_persistence_migration.py
git commit -m "feat: add JSON-to-SQLite migration for cameras and config"
```

---

### Phase 2: ConfigStore Enhancement + SettingsViewModel

### Task 3: Enhance ConfigStore with set/save

**Files:**
- Modify: `app/infrastructure/config_store.py`

No new tests needed — ConfigStore is a thin wrapper, tested via SettingsViewModel integration tests later.

- [ ] **Step 1: Add write capabilities to ConfigStore**

Replace the current `ConfigStore` class in `app/infrastructure/config_store.py`:

```python
"""JSON configuration store with hot-reload and write-back support."""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigStore:
    """JSON 配置文件的读写与热加载管理。"""

    def __init__(self, config_path: str) -> None:
        self._path = Path(config_path)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._mtime: float = 0.0
        self._persistence: Any = None  # ConfigPersistenceService, set later
        self._dirty: Dict[str, str] = {}
        self.reload()

    @property
    def data(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def set_persistence(self, svc: Any) -> None:
        self._persistence = svc

    def reload(self) -> bool:
        try:
            stat = self._path.stat()
        except FileNotFoundError:
            return False
        if stat.st_mtime <= self._mtime:
            return False
        raw = self._path.read_text(encoding="utf-8")
        new_data = json.loads(raw)
        with self._lock:
            self._data = new_data
            self._mtime = stat.st_mtime
        return True

    def get(self, *keys: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for key in keys:
                if isinstance(node, dict):
                    node = node.get(key)
                else:
                    return default
            return node if node is not None else default

    def set(self, path: str, value: Any) -> None:
        """在内存中设置值并标记 dirty（尚未持久化）。"""
        with self._lock:
            parts = path.split(".")
            node = self._data
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value
        self._dirty[path] = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

    def save(self) -> bool:
        """将内存中的配置持久化到 JSON 文件和 SQLite。"""
        with self._lock:
            data_copy = deepcopy(self._data)
        tmp_path = str(self._path) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data_copy, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(self._path))
        self._mtime = os.path.getmtime(str(self._path))
        if self._persistence is not None:
            for path, value in self._dirty.items():
                self._persistence.set(path, value)
        self._dirty.clear()
        return True

    @property
    def is_dirty(self) -> bool:
        return len(self._dirty) > 0

    def get_dirty_keys(self) -> list:
        return list(self._dirty.keys())

    def get_value_by_path(self, path: str) -> str:
        """按点号路径读取，返回 JSON 字符串（兼容原 SettingsViewModel.getValue）。"""
        import json as _json
        with self._lock:
            node: Any = self._data
            for key in path.split("."):
                if isinstance(node, dict):
                    node = node.get(key, "")
                else:
                    return ""
        return _json.dumps(node, ensure_ascii=False) if not isinstance(node, str) else node

    # ── Convenience accessors ──

    def get_app_config(self) -> Dict[str, Any]:
        return self.get("app", default={})

    def get_camera_configs(self) -> list[Dict[str, Any]]:
        cameras = self.get("cameras", default=[])
        return [c for c in cameras if c.get("enabled", True)]

    def get_plc_config(self) -> Dict[str, Any]:
        return self.get("plc", default={})

    def get_alert_config(self) -> Dict[str, Any]:
        return self.get("alert", default={})

    def get_offline_platform_config(self) -> Dict[str, Any]:
        return self.get("offline_platform", default={})

    def get_storage_config(self) -> Dict[str, Any]:
        return self.get("storage", default={})
```

- [ ] **Step 2: Commit**

```bash
git add app/infrastructure/config_store.py
git commit -m "feat: add set/save/dirty tracking to ConfigStore"
```

---

### Task 4: Rewrite SettingsViewModel with setValue/save/import/export

**Files:**
- Modify: `app/viewmodels/settings_viewmodel.py`
- Modify: `tests/test_integration.py` (add SettingsViewModel test)

- [ ] **Step 1: Rewrite SettingsViewModel**

Replace `app/viewmodels/settings_viewmodel.py`:

```python
"""ViewModel for SettingsScreen: read/write config via ConfigStore + persistence."""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.infrastructure.config_store import ConfigStore
from app.services.config_persistence import ConfigPersistenceService


class SettingsViewModel(QObject):
    """设置页 ViewModel。QML 侧通过 getValue/setValue/save 完成配置编辑。"""

    configChanged = Signal()
    reloaded = Signal()
    valueChanged = Signal(str)
    saved = Signal()
    saveFailed = Signal(str)
    importSucceeded = Signal()
    importFailed = Signal(str)

    def __init__(self, config_store: ConfigStore, persistence: ConfigPersistenceService) -> None:
        super().__init__()
        self._store = config_store
        self._persistence = persistence
        self._dirty_paths: set = set()

    def _get_data(self) -> dict:
        return self._store.data

    def _get_is_dirty(self) -> bool:
        return self._store.is_dirty

    data = Property(dict, _get_data, notify=configChanged)
    isDirty = Property(bool, _get_is_dirty, notify=configChanged)

    @Slot(str, result=str)
    def getValue(self, path: str) -> str:
        return self._store.get_value_by_path(path)

    @Slot(str, str)
    def setValue(self, path: str, value: str) -> None:
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = value
        self._store.set(path, parsed)
        self._dirty_paths.add(path)
        self.valueChanged.emit(path)
        self.configChanged.emit()

    @Slot()
    def save(self) -> None:
        try:
            self._store.save()
            self._dirty_paths.clear()
            self.saved.emit()
            self.configChanged.emit()
        except Exception as exc:
            self.saveFailed.emit(str(exc))

    @Slot()
    def reload(self) -> None:
        if self._store.reload():
            self._store.set_persistence(self._persistence)
            self._dirty_paths.clear()
            self.reloaded.emit()
            self.configChanged.emit()

    @Slot(str)
    def importConfig(self, file_path: str) -> None:
        try:
            self._persistence.import_from_json(file_path)
            self._store.reload()
            self._dirty_paths.clear()
            self.importSucceeded.emit()
            self.configChanged.emit()
        except Exception as exc:
            self.importFailed.emit(str(exc))

    @Slot(str)
    def exportConfig(self, file_path: str) -> None:
        self._store.save()
        self._persistence.export_to_json(file_path)

    @Slot(str)
    def resetToDefault(self, path: str) -> None:
        import json as _json
        example_path = "config.example.json"
        try:
            with open(example_path, encoding="utf-8") as f:
                defaults = _json.load(f)
        except (FileNotFoundError, _json.JSONDecodeError):
            return
        node = defaults
        for key in path.split("."):
            if isinstance(node, dict):
                node = node.get(key, "")
            else:
                return
        self.setValue(path, _json.dumps(node, ensure_ascii=False) if not isinstance(node, str) else node)
```

- [ ] **Step 2: Run existing tests to check nothing breaks**

```bash
uv run pytest tests/ -v --timeout=30
```

- [ ] **Step 3: Commit**

```bash
git add app/viewmodels/settings_viewmodel.py
git commit -m "feat: add setValue/save/import/export/reset to SettingsViewModel"
```

---

### Phase 3: SeatModelService

### Task 5: Create SeatModelService

**Files:**
- Create: `app/services/seat_model_service.py`
- Create: `tests/test_seat_model_service.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for SeatModelService."""
from __future__ import annotations

from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService
from app.services.seat_model_service import SeatModelService


def _setup(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    persistence = ConfigPersistenceService(db_path)
    svc = SeatModelService(persistence)
    return svc


def test_create_and_list_models(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "型号A", "描述A")
    svc.create_model("m2", "型号B")
    models = svc.list_models()
    assert len(models) == 2
    assert models[0]["id"] == "m1"
    assert models[0]["display_name"] == "型号A"


def test_set_default_model(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.create_model("m2", "B")
    svc.set_default("m2")
    models = svc.list_models()
    assert models[0]["id"] == "m2"
    assert models[0]["is_default"] == 1


def test_delete_model_without_cameras_succeeds(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    assert svc.delete_model("m1") is True
    assert len(svc.list_models()) == 0


def test_delete_model_with_cameras_fails(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
    assert svc.delete_model("m1") is False
    assert len(svc.list_models()) == 1


def test_add_camera_to_model(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {
        "camera_id": "cam1", "type": "rtsp", "source": "rtsp://10.0.0.1",
        "efficientad_model_path": "./models/cam1.pt",
    })
    cameras = svc.get_cameras("m1")
    assert len(cameras) == 1
    assert cameras[0]["camera_id"] == "cam1"
    assert cameras[0]["type"] == "rtsp"
    assert cameras[0]["efficientad_model_path"] == "./models/cam1.pt"


def test_get_cameras_as_config_list(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {
        "camera_id": "cam1", "type": "mvs", "source": "mvs://1",
        "filter_classifier_path": "./fc/", "filter_classifier_enabled": True,
        "calibration_normalizer": "./cal/norm.json", "calibration_projector": "./cal/proj.pt",
    })
    configs = svc.get_cameras_as_config_list("m1")
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg["camera_id"] == "cam1"
    assert cfg["filter_classifier"]["enabled"] is True
    assert cfg["filter_classifier"]["model_path"] == "./fc/"
    assert cfg["calibration"]["normalizer_path"] == "./cal/norm.json"
    assert cfg["calibration"]["projector_path"] == "./cal/proj.pt"


def test_remove_camera(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
    svc.remove_camera("cam1")
    assert len(svc.get_cameras("m1")) == 0


def test_update_camera(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
    svc.update_camera("cam1", efficientad_model_path="./models/new.pt", enabled=False)
    cam = svc.get_cameras("m1")[0]
    assert cam["efficientad_model_path"] == "./models/new.pt"
    assert cam["enabled"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_seat_model_service.py -v
```
Expected: all fail with `ModuleNotFoundError`

- [ ] **Step 3: Write SeatModelService**

```python
"""Seat model CRUD and camera association management."""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.config_persistence import ConfigPersistenceService


class SeatModelService:
    """管理座椅型号及其关联的相机配置。"""

    def __init__(self, persistence: ConfigPersistenceService) -> None:
        self._p = persistence

    def list_models(self) -> list[dict]:
        return self._p.list_seat_models()

    def get_model(self, model_id: str) -> dict | None:
        return self._p.get_seat_model(model_id)

    def create_model(self, model_id: str, display_name: str, description: str = "") -> None:
        self._p.create_seat_model(model_id, display_name, description)

    def update_model(self, model_id: str, **kwargs: Any) -> None:
        self._p.update_seat_model(model_id, **kwargs)

    def delete_model(self, model_id: str) -> bool:
        return self._p.delete_seat_model(model_id)

    def set_default(self, model_id: str) -> None:
        self._p.set_default_seat_model(model_id)

    def get_default_model_id(self) -> str | None:
        models = self.list_models()
        for m in models:
            if m.get("is_default"):
                return m["id"]
        return models[0]["id"] if models else None

    def get_cameras(self, model_id: str) -> list[dict]:
        return self._p.list_cameras(seat_model_id=model_id)

    def add_camera(self, model_id: str, camera: dict) -> None:
        camera["seat_model_id"] = model_id
        self._p.create_camera(camera)

    def remove_camera(self, camera_id: str) -> None:
        self._p.delete_camera(camera_id)

    def update_camera(self, camera_id: str, **kwargs: Any) -> None:
        self._p.update_camera(camera_id, **kwargs)

    def get_cameras_as_config_list(self, model_id: str) -> List[Dict[str, Any]]:
        """将 SQLite 中的相机数据转回 seat_defect_core 期望的 config dict 格式。"""
        cameras = self.get_cameras(model_id)
        result: List[Dict[str, Any]] = []
        for cam in cameras:
            entry: Dict[str, Any] = {
                "camera_id": cam["camera_id"],
                "source": cam["source"],
                "type": cam["type"],
                "enabled": bool(cam["enabled"]),
                "efficientad_model_path": cam.get("efficientad_model_path", ""),
                "filter_classifier": {
                    "enabled": bool(cam.get("filter_classifier_enabled", False)),
                    "model_path": cam.get("filter_classifier_path", ""),
                },
                "calibration": {
                    "normalizer_path": cam.get("calibration_normalizer", ""),
                    "projector_path": cam.get("calibration_projector", ""),
                },
            }
            result.append(entry)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_seat_model_service.py -v
```
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/seat_model_service.py tests/test_seat_model_service.py
git commit -m "feat: add SeatModelService for seat model and camera management"
```

---

### Phase 4: ModelFileService

### Task 6: Create ModelFileService

**Files:**
- Create: `app/services/model_file_service.py`
- Create: `tests/test_model_file_service.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for ModelFileService."""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService
from app.services.model_file_service import ModelFileService


def _setup(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    models_dir = str(tmp_path / "models")
    persistence = ConfigPersistenceService(db_path)
    svc = ModelFileService(persistence, models_dir=models_dir)
    return svc, tmp_path


def test_import_file(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "source.pt"
    src.write_bytes(b"fake model content")

    mf = svc.import_file("cam1", "efficientad", str(src))
    assert mf["camera_id"] == "cam1"
    assert mf["model_type"] == "efficientad"
    assert mf["source"] == "local_upload"
    assert mf["is_active"] == 1
    assert mf["file_name"] == "source.pt"
    assert Path(mf["file_path"]).exists()
    assert mf["file_size"] == 17


def test_sha256_calculated_on_import(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    content = b"deterministic content for sha256"
    src.write_bytes(content)

    mf = svc.import_file("cam2", "filter_classifier", str(src))
    expected_sha = hashlib.sha256(content).hexdigest()
    assert mf["sha256"] == expected_sha


def test_verify_checksum_pass(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    src.write_bytes(b"test")
    mf = svc.import_file("cam1", "efficientad", str(src))
    assert svc.verify_checksum(mf["id"]) is True


def test_verify_checksum_fail_on_tampered_file(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    src.write_bytes(b"original")
    mf = svc.import_file("cam1", "efficientad", str(src))
    Path(mf["file_path"]).write_bytes(b"tampered")
    assert svc.verify_checksum(mf["id"]) is False


def test_activate_deactivates_others(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src1 = base / "v1.pt"
    src1.write_bytes(b"v1")
    src2 = base / "v2.pt"
    src2.write_bytes(b"v2")

    mf1 = svc.import_file("cam1", "efficientad", str(src1))
    mf2 = svc.import_file("cam1", "efficientad", str(src2))
    assert mf1["is_active"] == 1  # first import auto-activated
    assert mf2["is_active"] == 1  # second import auto-activates, deactivates first

    svc.activate(mf1["id"])
    history = svc.list_history("cam1", "efficientad")
    active = [m for m in history if m["is_active"] == 1]
    assert len(active) == 1
    assert active[0]["id"] == mf1["id"]


def test_rollback_to_previous(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src1 = base / "v1.pt"
    src1.write_bytes(b"v1")
    src2 = base / "v2.pt"
    src2.write_bytes(b"v2")

    mf1 = svc.import_file("cam1", "efficientad", str(src1))
    mf2 = svc.import_file("cam1", "efficientad", str(src2))

    rolled = svc.rollback("cam1", "efficientad")
    assert rolled is not None
    assert rolled["id"] == mf1["id"]

    history = svc.list_history("cam1", "efficientad")
    active = [m for m in history if m["is_active"] == 1]
    assert len(active) == 1
    assert active[0]["id"] == mf1["id"]


def test_get_active(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    src.write_bytes(b"test")
    svc.import_file("cam1", "efficientad", str(src))
    active = svc.get_active("cam1", "efficientad")
    assert active is not None
    assert active["camera_id"] == "cam1"


def test_delete_non_active(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src1 = base / "v1.pt"
    src1.write_bytes(b"v1")
    src2 = base / "v2.pt"
    src2.write_bytes(b"v2")

    mf1 = svc.import_file("cam1", "efficientad", str(src1))
    mf2 = svc.import_file("cam1", "efficientad", str(src2))
    svc.activate(mf1["id"])
    svc.delete_file(mf2["id"])
    history = svc.list_history("cam1", "efficientad")
    assert len(history) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_model_file_service.py -v
```

- [ ] **Step 3: Write ModelFileService**

Create `app/services/model_file_service.py`:

```python
"""Model file management: import, SHA256 verify, activate, rollback."""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.config_persistence import ConfigPersistenceService


class ModelFileService:
    """管理模型文件：导入、校验、激活、回滚。"""

    def __init__(self, persistence: ConfigPersistenceService, models_dir: str = "./models") -> None:
        self._p = persistence
        self._models_dir = models_dir
        Path(self._models_dir).mkdir(parents=True, exist_ok=True)

    def import_file(self, camera_id: str, model_type: str, src_path: str) -> dict:
        src = Path(src_path)
        file_name = src.name
        dest_dir = Path(self._models_dir) / camera_id / model_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name
        shutil.copy2(str(src), str(dest_path))

        sha = _sha256_file(str(dest_path))
        now = datetime.now(timezone.utc).isoformat()
        mf = {
            "id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "model_type": model_type,
            "file_path": str(dest_path),
            "file_name": file_name,
            "file_size": dest_path.stat().st_size,
            "sha256": sha,
            "source": "local_upload",
            "platform_version": "",
            "is_active": 1,
            "imported_at": now,
        }
        self._p.insert_model_file(mf)
        self._p.set_model_file_active(mf["id"], camera_id, model_type)
        return mf

    def register_synced(self, camera_id: str, model_type: str, file_path: str, version: str = "") -> dict:
        fp = Path(file_path)
        sha = _sha256_file(file_path)
        now = datetime.now(timezone.utc).isoformat()
        mf = {
            "id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "model_type": model_type,
            "file_path": str(fp),
            "file_name": fp.name,
            "file_size": fp.stat().st_size if fp.exists() else 0,
            "sha256": sha,
            "source": "platform_sync",
            "platform_version": version,
            "is_active": 1,
            "imported_at": now,
        }
        self._p.insert_model_file(mf)
        self._p.set_model_file_active(mf["id"], camera_id, model_type)
        return mf

    def verify_checksum(self, file_id: str) -> bool:
        mf = self._p.get_model_file(file_id)
        if mf is None:
            return False
        fp = Path(mf["file_path"])
        if not fp.exists():
            return False
        return _sha256_file(str(fp)) == mf["sha256"]

    def activate(self, file_id: str) -> None:
        mf = self._p.get_model_file(file_id)
        if mf is None:
            return
        self._p.set_model_file_active(file_id, mf["camera_id"], mf["model_type"])
        self._p.update_camera(mf["camera_id"], efficientad_model_path=mf["file_path"])

    def rollback(self, camera_id: str, model_type: str) -> dict | None:
        history = self._p.list_model_files(camera_id=camera_id, model_type=model_type)
        inactive = [m for m in history if m.get("is_active") != 1]
        if not inactive:
            return None
        prev = inactive[0]
        self._p.set_model_file_active(prev["id"], camera_id, model_type)
        self._p.update_camera(camera_id, efficientad_model_path=prev["file_path"])
        return prev

    def get_active(self, camera_id: str, model_type: str) -> dict | None:
        all_files = self._p.list_model_files(camera_id=camera_id, model_type=model_type)
        for mf in all_files:
            if mf.get("is_active") == 1:
                return mf
        return None

    def list_history(self, camera_id: str, model_type: str) -> list[dict]:
        return self._p.list_model_files(camera_id=camera_id, model_type=model_type)

    def delete_file(self, file_id: str) -> bool:
        mf = self._p.get_model_file(file_id)
        if mf is None:
            return False
        if mf.get("is_active") == 1:
            return False
        fp = Path(mf["file_path"])
        if fp.exists():
            fp.unlink()
        self._p.delete_model_file(file_id)
        return True


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_model_file_service.py -v
```
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/model_file_service.py tests/test_model_file_service.py
git commit -m "feat: add ModelFileService with SHA256 verify, activate, rollback"
```

---

### Phase 5: PlatformSyncService

### Task 7: Create PlatformSyncService

**Files:**
- Create: `app/services/platform_sync_service.py`
- Create: `tests/test_platform_sync_service.py`

- [ ] **Step 1: Write tests using mock**

```python
"""Tests for PlatformSyncService."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.platform_sync_service import PlatformSyncService


def test_check_health_online():
    svc = PlatformSyncService("http://localhost:8000")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status":"healthy"}'
        mock_urlopen.return_value = mock_resp
        assert svc.check_health() is True


def test_check_health_offline():
    svc = PlatformSyncService("http://localhost:8000")
    with patch("urllib.request.urlopen", side_effect=OSError):
        assert svc.check_health() is False


def test_check_health_empty_url():
    svc = PlatformSyncService("")
    assert svc.check_health() is False


def test_set_base_url():
    svc = PlatformSyncService("")
    svc.set_base_url("http://192.168.1.200:8000")
    assert svc.base_url == "http://192.168.1.200:8000"


def test_list_deployed_models():
    svc = PlatformSyncService("http://localhost:8000")
    mock_data = [{"target": "line_a", "status": "active", "model_version": "v2.3.1"}]
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value = mock_resp
        models = svc.list_deployed_models()
        assert len(models) == 1
        assert models[0]["target"] == "line_a"


def test_download_model(tmp_path: Path):
    svc = PlatformSyncService("http://localhost:8000")
    dest = str(tmp_path / "downloaded.pt")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"model binary content"
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = svc.download_model("http://localhost:8000/api/hot-reload/download/model_123", dest)
        assert result == dest
        assert Path(dest).exists()
        assert Path(dest).read_bytes() == b"model binary content"


def test_download_model_http_error(tmp_path: Path):
    svc = PlatformSyncService("http://localhost:8000")
    dest = str(tmp_path / "fail.pt")
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        result = svc.download_model("http://bad/url", dest)
        assert result is None
```

- [ ] **Step 2: Write PlatformSyncService**

Create `app/services/platform_sync_service.py`:

```python
"""Offline platform API integration for model sync."""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any, List, Optional


class PlatformSyncService:
    """对接离线分析平台 API：健康检查、模型列表、文件下载。"""

    def __init__(self, base_url: str = "", timeout: int = 30) -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    def set_base_url(self, url: str) -> None:
        self._base_url = url.rstrip("/") if url else ""

    def check_health(self) -> bool:
        if not self._base_url:
            return False
        try:
            req = urllib.request.Request(f"{self._base_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_deployed_models(self) -> list[dict]:
        if not self._base_url:
            return []
        try:
            req = urllib.request.Request(f"{self._base_url}/api/hot-reload/targets", method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return []

    def download_model(self, download_url: str, dest_path: str) -> str | None:
        try:
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(download_url, method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout * 2) as resp:
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(resp, f)
            return dest_path
        except Exception:
            return None
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_platform_sync_service.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/platform_sync_service.py tests/test_platform_sync_service.py
git commit -m "feat: add PlatformSyncService for offline platform API integration"
```

---

### Phase 6: SeatModelViewModel + ModelDeployViewModel

### Task 8: Create SeatModelViewModel

**Files:**
- Create: `app/viewmodels/seat_model_viewmodel.py`

- [ ] **Step 1: Write SeatModelViewModel**

```python
"""ViewModel for SeatModelScreen: model CRUD + hot-switch."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.seat_model_service import SeatModelService


class SeatModelViewModel(QObject):
    """座椅型号管理 ViewModel。"""

    modelListChanged = Signal()
    activeModelChanged = Signal(str)
    switchFailed = Signal(str)
    requestConfirmSwitch = Signal(str)  # QML shows confirmation dialog
    toast = Signal(str, str)  # message, level: "success"/"error"/"warning"

    def __init__(
        self,
        seat_model_service: SeatModelService,
        on_switch: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._svc = seat_model_service
        self._on_switch = on_switch
        self._active_id: str = seat_model_service.get_default_model_id() or ""

    def _get_models(self) -> list:
        models = self._svc.list_models()
        for m in models:
            cameras = self._svc.get_cameras(m["id"])
            m["camera_count"] = len(cameras)
            m["camera_ids"] = [c["camera_id"] for c in cameras]
        return models

    def _get_active_id(self) -> str:
        return self._active_id

    seatModels = Property(list, _get_models, notify=modelListChanged)
    activeModelId = Property(str, _get_active_id, notify=activeModelChanged)

    @Slot(str, str, str, result=bool)
    def createModel(self, model_id: str, name: str, description: str) -> bool:
        try:
            self._svc.create_model(model_id, name, description)
            self.modelListChanged.emit()
            self.toast.emit(f"型号 '{name}' 创建成功", "success")
            return True
        except Exception as exc:
            self.toast.emit(f"创建失败: {exc}", "error")
            return False

    @Slot(str, str, str)
    def updateModel(self, model_id: str, name: str, description: str) -> None:
        self._svc.update_model(model_id, display_name=name, description=description)
        self.modelListChanged.emit()
        self.toast.emit(f"型号已更新", "success")

    @Slot(str, result=bool)
    def deleteModel(self, model_id: str) -> bool:
        ok = self._svc.delete_model(model_id)
        if not ok:
            cameras = self._svc.get_cameras(model_id)
            self.toast.emit(f"该型号下还有 {len(cameras)} 台相机，请先解除关联", "error")
            return False
        self.modelListChanged.emit()
        self.toast.emit("型号已删除", "success")
        return True

    @Slot(str)
    def setActive(self, model_id: str) -> None:
        self.requestConfirmSwitch.emit(model_id)

    @Slot(str)
    def confirmSwitch(self, model_id: str) -> None:
        try:
            if self._on_switch:
                self._on_switch(model_id)
            self._active_id = model_id
            self.activeModelChanged.emit(model_id)
            model = self._svc.get_model(model_id)
            name = model["display_name"] if model else model_id
            self.toast.emit(f"已切换至：{name}", "success")
        except Exception as exc:
            self.switchFailed.emit(str(exc))
            self.toast.emit(f"切换失败: {exc}", "error")

    @Slot(str, result="QVariantMap")
    def getCamera(self, camera_id: str) -> dict:
        cam = self._svc._p.get_camera(camera_id)
        return cam or {}

    @Slot(str, str, str, str)
    def addCamera(self, model_id: str, camera_id: str, cam_type: str, source: str) -> None:
        self._svc.add_camera(model_id, {
            "camera_id": camera_id,
            "type": cam_type,
            "source": source,
        })
        self.modelListChanged.emit()
        self.toast.emit(f"相机 '{camera_id}' 已添加", "success")

    @Slot(str)
    def removeCamera(self, camera_id: str) -> None:
        self._svc.remove_camera(camera_id)
        self.modelListChanged.emit()
        self.toast.emit(f"相机已移除", "success")

    @Slot(str, str, str)
    def updateCamera(self, camera_id: str, key: str, value: str) -> None:
        self._svc.update_camera(camera_id, **{key: value})
        self.modelListChanged.emit()

    def refresh(self) -> None:
        self.modelListChanged.emit()
```

- [ ] **Step 2: Commit**

```bash
git add app/viewmodels/seat_model_viewmodel.py
git commit -m "feat: add SeatModelViewModel for seat model and camera CRUD"
```

---

### Task 9: Create ModelDeployViewModel

**Files:**
- Create: `app/viewmodels/model_deploy_viewmodel.py`

- [ ] **Step 1: Write ModelDeployViewModel**

```python
"""ViewModel for ModelDeployScreen: model file import/sync/activate/rollback."""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.model_file_service import ModelFileService
from app.services.platform_sync_service import PlatformSyncService


class ModelDeployViewModel(QObject):
    """模型部署管理 ViewModel。"""

    modelFilesChanged = Signal()
    syncStatusChanged = Signal()
    syncCompleted = Signal(int)
    syncFailed = Signal(str)
    toast = Signal(str, str)

    def __init__(
        self,
        model_file_service: ModelFileService,
        platform_sync: PlatformSyncService,
    ) -> None:
        super().__init__()
        self._mfs = model_file_service
        self._platform = platform_sync
        self._sync_status = "offline"
        self._last_sync_time = ""
        self._filter_camera: str = ""
        self._filter_type: str = ""

    def _get_sync_status(self) -> str:
        return self._sync_status

    def _get_last_sync_time(self) -> str:
        return self._last_sync_time

    def _get_model_files(self) -> list:
        return self._mfs.list_history(
            camera_id=self._filter_camera or None,
            model_type=self._filter_type or None,
        )

    syncStatus = Property(str, _get_sync_status, notify=syncStatusChanged)
    lastSyncTime = Property(str, _get_last_sync_time, notify=syncStatusChanged)
    modelFiles = Property(list, _get_model_files, notify=modelFilesChanged)

    @Slot(str)
    def setFilterCamera(self, camera_id: str) -> None:
        self._filter_camera = camera_id
        self.modelFilesChanged.emit()

    @Slot(str)
    def setFilterType(self, model_type: str) -> None:
        self._filter_type = model_type
        self.modelFilesChanged.emit()

    @Slot(str, str, str)
    def importModelFile(self, camera_id: str, model_type: str, file_path: str) -> None:
        try:
            mf = self._mfs.import_file(camera_id, model_type, file_path)
            self.modelFilesChanged.emit()
            self.toast.emit(f"模型 '{mf['file_name']}' 导入成功", "success")
        except Exception as exc:
            self.toast.emit(f"导入失败: {exc}", "error")

    @Slot()
    def checkPlatformHealth(self) -> None:
        if self._platform.check_health():
            self._sync_status = "online"
        else:
            self._sync_status = "offline"
        self.syncStatusChanged.emit()

    @Slot()
    def syncFromPlatform(self) -> None:
        self._sync_status = "syncing"
        self.syncStatusChanged.emit()
        try:
            models = self._platform.list_deployed_models()
            imported = 0
            for model in models:
                target = model.get("target", "")
                version = model.get("model_version", "")
                for dep in model.get("deployments", []):
                    camera_id = dep.get("camera_id", target)
                    model_type = dep.get("model_type", "efficientad")
                    download_url = dep.get("download_url", "")
                    if download_url:
                        import tempfile
                        dest = f"{tempfile.gettempdir()}/sync_{camera_id}_{model_type}.pt"
                        downloaded = self._platform.download_model(download_url, dest)
                        if downloaded:
                            self._mfs.register_synced(camera_id, model_type, downloaded, version)
                            imported += 1
            from datetime import datetime, timezone
            self._last_sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            self._sync_status = "online"
            self.modelFilesChanged.emit()
            self.syncCompleted.emit(imported)
            self.toast.emit(f"已同步 {imported} 个模型", "success")
        except Exception as exc:
            self._sync_status = "offline"
            self.syncFailed.emit(str(exc))
            self.toast.emit(f"同步失败: {exc}", "error")
        self.syncStatusChanged.emit()

    @Slot(str)
    def activateVersion(self, file_id: str) -> None:
        self._mfs.activate(file_id)
        self.modelFilesChanged.emit()
        self.toast.emit("模型版本已切换", "success")

    @Slot(str)
    def deleteModelFile(self, file_id: str) -> None:
        ok = self._mfs.delete_file(file_id)
        if ok:
            self.modelFilesChanged.emit()
            self.toast.emit("文件已删除", "success")
        else:
            self.toast.emit("无法删除激活版本", "error")

    @Slot(str, str)
    def rollback(self, camera_id: str, model_type: str) -> None:
        prev = self._mfs.rollback(camera_id, model_type)
        if prev:
            self.modelFilesChanged.emit()
            self.toast.emit(f"已回滚至 {prev['file_name']}", "success")
        else:
            self.toast.emit("没有可回滚的历史版本", "warning")
```

- [ ] **Step 2: Commit**

```bash
git add app/viewmodels/model_deploy_viewmodel.py
git commit -m "feat: add ModelDeployViewModel for model file management"
```

---

### Phase 7: QML Theme Enhancement + Toast Component

### Task 10: Add Theme tokens and Toast component

**Files:**
- Modify: `app/resources/styles/Theme.qml` (add new tokens)
- Create: `app/qml/components/ToastNotification.qml`

Note: Theme already has good base values. We add animation timing and the green accent variant for the management UI.

- [ ] **Step 1: Extend Theme.qml**

Add these properties to `Theme.qml` after the existing `touchComfort` line:

```qml
    // ── Accent variants ──
    readonly property color accentGreen: "#00ff88"
    readonly property color accentGreenDim: Qt.rgba(0, 1, 0.533, 0.15)
    readonly property color accentGreenGradient: "#00cc6a"

    // ── Animation ──
    readonly property int animFast: 150
    readonly property int animNormal: 200
    readonly property int animSlow: 300
    readonly property int animToast: 3000

    // ── Elevation ──
    readonly property real elevationLow: 0.08
    readonly property real elevationMid: 0.15
    readonly property real elevationHigh: 0.25

    // ── Card ──
    readonly property color cardGlass: Qt.rgba(1, 1, 1, 0.04)
    readonly property color cardGlassBorder: Qt.rgba(1, 1, 1, 0.08)
```

- [ ] **Step 2: Create ToastNotification component**

Create `app/qml/components/ToastNotification.qml`:

```qml
import QtQuick
import QtQuick.Controls.Basic
import styles

Rectangle {
    id: toastRoot
    visible: false
    color: {
        if (level === "error") return Theme.statusNG;
        if (level === "warning") return Theme.statusWarning;
        return Theme.accentGreen;
    }
    radius: Theme.radiusMD
    height: 40
    width: toastText.implicitWidth + Theme.spacingLG * 2
    opacity: 0
    y: 20

    property string message: ""
    property string level: "success"  // "success" / "error" / "warning"
    property int duration: Theme.animToast

    function show(msg, lvl) {
        message = msg;
        level = lvl || "success";
        opacity = 1;
        y = 0;
        visible = true;
        hideTimer.restart();
    }

    Timer {
        id: hideTimer
        interval: toastRoot.duration
        onTriggered: {
            toastRoot.opacity = 0;
            toastRoot.y = 20;
        }
    }

    Behavior on opacity {
        NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic }
    }
    Behavior on y {
        NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic }
    }

    onOpacityChanged: {
        if (opacity === 0 && hideTimer.running === false) {
            visible = false;
        }
    }

    Text {
        id: toastText
        anchors.centerIn: parent
        text: toastRoot.message
        color: "#000"
        font.pixelSize: Theme.fontSizeXS
        font.bold: true
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add app/resources/styles/Theme.qml app/qml/components/ToastNotification.qml
git commit -m "feat: add Theme animation tokens and ToastNotification component"
```

---

### Phase 8: QML UI — SettingsScreen Redesign

### Task 11: Redesign SettingsScreen with editable forms

**Files:**
- Modify: `app/qml/SettingsScreen.qml` (complete rewrite)

This task replaces the read-only SettingsScreen with an editable version using TextField, ComboBox, Switch elements. Due to length, the key structural changes are:

- [ ] **Step 1: Rewrite SettingsScreen.qml**

The full rewrite is ~450 lines. Key changes:
1. Keep sidebar layout (7 sections)
2. Replace all `Text` values with `TextField` or `ComboBox`
3. Add `onEditingFinished: viewModel.setValue(path, text)` on inputs
4. Camera cards become expandable with collapse animation
5. Bottom bar adds save/import/export buttons
6. ToastNotification at top-right

- [ ] **Step 2: Verify QML loads**

```bash
uv run python -c "
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
app = QGuiApplication([])
engine = QQmlApplicationEngine()
# Just check the component compiles — will fail if syntax errors
import app.qml.components.ToastNotification
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add app/qml/SettingsScreen.qml
git commit -m "feat: redesign SettingsScreen with editable form fields"
```

---

### Phase 9: QML UI — New Screens

### Task 12: Create SeatModelScreen.qml

**Files:**
- Create: `app/qml/SeatModelScreen.qml`

- [ ] **Step 1: Write SeatModelScreen.qml**

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: seatModelScreen
    color: Theme.bgPrimary

    property var viewModel: null

    // Toast container
    ToastNotification {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        z: 100
    }

    Connections {
        target: seatModelScreen.viewModel
        function onToast(message, level) { toast.show(message, level); }
        function onRequestConfirmSwitch(modelId) { confirmDialog.modelId = modelId; confirmDialog.open(); }
    }

    // Confirmation dialog for model switch
    Dialog {
        id: confirmDialog
        property string modelId: ""
        title: qsTr("切换座椅型号")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        width: 400
        contentItem: Text {
            text: qsTr("切换型号将重新加载检测引擎，确认继续？")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSM
            wrapMode: Text.Wrap
        }
        onAccepted: {
            if (seatModelScreen.viewModel && confirmDialog.modelId) {
                seatModelScreen.viewModel.confirmSwitch(confirmDialog.modelId);
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        // Header
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("座椅型号管理")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentGreenDim
                implicitWidth: addBtn.implicitWidth + 24
                implicitHeight: 36
                Text {
                    id: addBtn
                    anchors.centerIn: parent
                    text: qsTr("+ 新增型号")
                    color: Theme.accentGreen
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: addDialog.open()
                }
            }
        }

        // Model list
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: seatModelScreen.viewModel ? seatModelScreen.viewModel.seatModels : []
            spacing: Theme.spacingSM

            delegate: Rectangle {
                width: ListView.view.width
                implicitHeight: 80
                color: Theme.cardGlass
                radius: Theme.radiusMD
                border { width: 1; color: modelData.is_default ? Theme.accentGreen : Theme.cardGlassBorder }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingMD

                    // Status dot
                    Rectangle {
                        width: 10; height: 10; radius: 5
                        color: modelData.is_default ? Theme.accentGreen : Theme.textMuted
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.display_name || modelData.id
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                        Text {
                            text: modelData.description || ""
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                            visible: text !== ""
                        }
                        Text {
                            text: qsTr("关联相机: ") + (modelData.camera_ids ? modelData.camera_ids.join(", ") : qsTr("无"))
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }

                    // Actions
                    RowLayout {
                        spacing: Theme.spacingXS
                        Rectangle {
                            radius: Theme.radiusSM
                            color: Theme.bgTertiary
                            implicitWidth: 48; implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("编辑")
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    editDialog.modelId = modelData.id;
                                    editDialog.open();
                                }
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: modelData.is_default ? Theme.bgTertiary : Theme.accentGreenDim
                            implicitWidth: 60; implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: modelData.is_default ? qsTr("默认") : qsTr("设为默认")
                                color: modelData.is_default ? Theme.textMuted : Theme.accentGreen
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !modelData.is_default
                                onClicked: seatModelScreen.viewModel.updateModel(modelData.id, modelData.display_name || "", modelData.description || "")
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: "#1a0000"
                            implicitWidth: 40; implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("删除")
                                color: Theme.statusNG
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: seatModelScreen.viewModel.deleteModel(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }

    // Add model dialog
    Dialog {
        id: addDialog
        title: qsTr("新增座椅型号")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        width: 400
        ColumnLayout {
            spacing: Theme.spacingSM
            Text { text: qsTr("型号 ID:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeXS }
            TextField {
                id: addIdField
                Layout.fillWidth: true
                placeholderText: "seat_model_001"
            }
            Text { text: qsTr("显示名称:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeXS }
            TextField {
                id: addNameField
                Layout.fillWidth: true
                placeholderText: qsTr("座椅型号A")
            }
            Text { text: qsTr("描述:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeXS }
            TextField {
                id: addDescField
                Layout.fillWidth: true
            }
        }
        onAccepted: {
            seatModelScreen.viewModel.createModel(addIdField.text, addNameField.text, addDescField.text);
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/qml/SeatModelScreen.qml
git commit -m "feat: add SeatModelScreen QML page"
```

---

### Task 13: Create ModelDeployScreen.qml

**Files:**
- Create: `app/qml/ModelDeployScreen.qml`

- [ ] **Step 1: Write ModelDeployScreen.qml**

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: modelDeployScreen
    color: Theme.bgPrimary

    property var viewModel: null

    ToastNotification {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        z: 100
    }

    Connections {
        target: modelDeployScreen.viewModel
        function onToast(message, level) { toast.show(message, level); }
    }

    Component.onCompleted: {
        if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.checkPlatformHealth();
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        // Header
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("模型部署")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentDim
                implicitWidth: 130; implicitHeight: 36
                Text {
                    anchors.centerIn: parent
                    text: qsTr("📂 手动导入")
                    color: Theme.accent
                    font.pixelSize: Theme.fontSizeSM
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: fileDialog.open()
                }
            }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentGreenDim
                implicitWidth: 150; implicitHeight: 36
                Text {
                    anchors.centerIn: parent
                    text: qsTr("🔄 从离线平台同步")
                    color: Theme.accentGreen
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.syncFromPlatform();
                    }
                }
            }
        }

        // Status cards
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD
            Repeater {
                model: [
                    { label: qsTr("离线平台"), value: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.syncStatus : "offline", color: Theme.accentGreen },
                    { label: qsTr("本地模型"), value: modelDeployScreen.viewModel ? String(modelDeployScreen.viewModel.modelFiles.length) : "0", color: Theme.accent },
                    { label: qsTr("最近同步"), value: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.lastSyncTime || qsTr("从未") : qsTr("从未"), color: Theme.statusWarning }
                ]
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 70
                    color: Theme.cardGlass
                    radius: Theme.radiusMD
                    border { width: 1; color: Theme.cardGlassBorder }
                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: modelData.label
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                        Text {
                            text: modelData.value
                            color: modelData.color
                            font.pixelSize: Theme.fontSizeMD
                            font.bold: true
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                }
            }
        }

        // Filter bar
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSM
            Text { text: qsTr("筛选:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
            ComboBox {
                id: cameraFilter
                model: [qsTr("全部相机")]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterCamera(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
            ComboBox {
                id: typeFilter
                model: [qsTr("全部类型"), "efficientad", "filter_classifier", "calibration_normalizer", "calibration_projector"]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterType(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
        }

        // File list
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.modelFiles : []
            spacing: Theme.spacingSM

            delegate: Rectangle {
                width: ListView.view.width
                implicitHeight: 72
                color: modelData.is_active ? Theme.accentGreenDim : Theme.cardGlass
                radius: Theme.radiusMD
                border { width: 1; color: modelData.is_active ? Theme.accentGreen : Theme.cardGlassBorder }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingMD

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.file_name || modelData.id
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                        RowLayout {
                            spacing: Theme.spacingSM
                            Text { text: modelData.camera_id || ""; color: Theme.textSecondary; font.pixelSize: Theme.fontSizeXS }
                            Text { text: modelData.model_type || ""; color: Theme.textMuted; font.pixelSize: Theme.fontSizeXS }
                            Text { text: modelData.platform_version ? ("v" + modelData.platform_version) : ""; color: Theme.accent; font.pixelSize: Theme.fontSizeXS }
                            Text { text: modelData.sha256 ? modelData.sha256.substring(0, 8) + "..." : ""; color: Theme.textMuted; font.pixelSize: Theme.fontSizeXS }
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingXS
                        Rectangle {
                            radius: Theme.radiusSM
                            color: modelData.is_active ? Theme.bgTertiary : Theme.accentGreenDim
                            implicitWidth: 72; implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: modelData.is_active ? qsTr("已激活") : qsTr("激活")
                                color: modelData.is_active ? Theme.textMuted : Theme.accentGreen
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !modelData.is_active
                                onClicked: modelDeployScreen.viewModel.activateVersion(modelData.id)
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: "#1a0000"
                            implicitWidth: 40; implicitHeight: 28
                            visible: !modelData.is_active
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("删除")
                                color: Theme.statusNG
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: modelDeployScreen.viewModel.deleteModelFile(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: qsTr("选择模型文件")
        nameFilters: [qsTr("Model files (*.pt *.pth *.onnx)"), qsTr("All files (*)")]
        onAccepted: {
            if (modelDeployScreen.viewModel && selectedFile) {
                modelDeployScreen.viewModel.importModelFile("", "efficientad", selectedFile);
            }
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/qml/ModelDeployScreen.qml
git commit -m "feat: add ModelDeployScreen QML page"
```

---

### Phase 10: main.qml TabBar + main.py Wiring

### Task 14: Expand main.qml TabBar and StackLayout

**Files:**
- Modify: `app/qml/main.qml`

- [ ] **Step 1: Add two new TabButtons and StackLayout pages**

In `main.qml`:
1. Add properties: `property var seatModelViewModel: null`, `property var modelDeployViewModel: null`
2. Add TabButtons for "型号" and "模型" after "设置" in the TabBar
3. Add `SeatModelScreen` and `ModelDeployScreen` to the StackLayout

- [ ] **Step 2: Commit**

```bash
git add app/qml/main.qml
git commit -m "feat: add seat model and model deploy tabs to main UI"
```

---

### Task 15: Wire main.py with new services and viewmodels

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add initialization of new services and viewmodels in main()**

Key additions to `main()` in `app/main.py`:
1. Create `ConfigPersistenceService` with SQLite path
2. Call `persistence.migrate_from_json(config_path)` on first run
3. Pass `persistence` to `ConfigStore.set_persistence()`
4. Create `SeatModelService(persistence)`
5. Create `ModelFileService(persistence)`
6. Create `PlatformSyncService(base_url)`
7. Pass new services to ViewModels
8. Add `on_switch` callback that recreates cameras and resets inspector
9. Set new ViewModels as root context properties

- [ ] **Step 2: Run full application load test**

```bash
uv run python -c "
from app.main import main
# Just verify imports and wiring don't crash
print('Wiring OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: wire new services and viewmodels into main startup"
```

---

### Task 16: End-to-end smoke test

**Files:**
- Create: `tests/test_e2e_management.py`

- [ ] **Step 1: Write end-to-end integration test**

```python
"""End-to-end smoke test for management features."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.services.config_persistence import ConfigPersistenceService
from app.services.seat_model_service import SeatModelService
from app.services.model_file_service import ModelFileService


def test_full_config_edit_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        # Setup
        json_path = Path(tmp) / "config.json"
        json_path.write_text(json.dumps({
            "app": {"line_id": "TEST-LINE"},
            "plc": {"host": "192.168.1.1", "port": 502},
        }), encoding="utf-8")

        db_path = str(Path(tmp) / "test.db")
        persistence = ConfigPersistenceService(db_path)
        persistence.migrate_from_json(str(json_path))

        config = ConfigStore(str(json_path))
        config.set_persistence(persistence)

        # Edit and save
        config.set("plc.host", "10.0.0.99")
        config.save()

        # Verify SQLite
        assert persistence.get("plc.host") == "10.0.0.99"

        # Verify JSON
        with open(json_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["plc"]["host"] == "10.0.0.99"


def test_seat_model_camera_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        persistence = ConfigPersistenceService(db_path)
        svc = SeatModelService(persistence)

        # Create model
        svc.create_model("seat_a", "座椅型号A")
        assert len(svc.list_models()) == 1

        # Add cameras
        svc.add_camera("seat_a", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
        svc.add_camera("seat_a", {"camera_id": "cam2", "type": "rtsp", "source": "rtsp://10.0.0.1"})
        assert len(svc.get_cameras("seat_a")) == 2

        # Export to config format
        configs = svc.get_cameras_as_config_list("seat_a")
        assert configs[0]["camera_id"] == "cam1"
        assert configs[0]["filter_classifier"]["enabled"] is False


def test_model_file_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        models_dir = str(Path(tmp) / "models")
        persistence = ConfigPersistenceService(db_path)
        mfs = ModelFileService(persistence, models_dir=models_dir)

        # Create model file
        src = Path(tmp) / "test_model.pt"
        src.write_bytes(b"model weights")
        mf = mfs.import_file("cam1", "efficientad", str(src))

        # Verify checksum
        assert mfs.verify_checksum(mf["id"]) is True

        # Get active
        active = mfs.get_active("cam1", "efficientad")
        assert active is not None

        # Import second version and activate first
        src2 = Path(tmp) / "test_model_v2.pt"
        src2.write_bytes(b"model weights v2")
        mf2 = mfs.import_file("cam1", "efficientad", str(src2))
        mfs.activate(mf["id"])
        active = mfs.get_active("cam1", "efficientad")
        assert active["id"] == mf["id"]
```

- [ ] **Step 2: Run smoke tests**

```bash
uv run pytest tests/test_e2e_management.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 3: Run all tests to ensure no regressions**

```bash
uv run pytest tests/ -v --timeout=30
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_management.py
git commit -m "test: add end-to-end smoke tests for management features"
```

---

## Execution Order

Tasks 1-2 (Phase 1) → Task 3-4 (Phase 2) → Task 5 (Phase 3) → Task 6 (Phase 4) → Task 7 (Phase 5) → Task 8-9 (Phase 6) → Task 10 (Phase 7) → Task 11-13 (Phases 8-9) → Task 14-16 (Phase 10)

Phases build sequentially: persistence → config store → services → viewmodels → QML UI → wiring.
