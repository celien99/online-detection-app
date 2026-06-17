"""JSON SQLite dual-write config persistence."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional


class ConfigPersistenceService:
    """Manage configuration and model data in SQLite with JSON bidirectional sync."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def migrate_from_json(self, json_path: str) -> None:
        """首次启动：从 config.json 迁移 cameras 到 SQLite，并导入 K-V 配置。"""
        if not Path(json_path).exists():
            return
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
        existing = {(c.get("seat_model_id", ""), c["camera_id"]) for c in self.list_cameras()}
        for idx, cam in enumerate(cameras):
            cid = cam.get("camera_id", "")
            if not cid or ("default", cid) in existing:
                continue
            fc = cam.get("filter_classifier", {})
            self.create_camera({
                "camera_id": cid,
                "seat_model_id": "default",
                "type": cam.get("type", "mvs"),
                "source": cam.get("source", ""),
                "enabled": 1 if cam.get("enabled", True) else 0,
                "patchcore_model_path": cam.get("patchcore_model_path", ""),
                "regions_json": json.dumps(cam.get("regions", []), ensure_ascii=False),
                "filter_classifier_path": fc.get("model_path", ""),
                "filter_classifier_enabled": 1 if fc.get("enabled") else 0,
                "display_order": idx,
            })

        # Migrate K-V config
        self.sync_json_to_db(json_path)

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            # Auto-initialize tables on first connection so callers don't need
            # to call init_db() explicitly for K-V operations.
            self._init_tables(conn)
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _init_tables(conn: sqlite3.Connection) -> None:
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                seat_model_id TEXT NOT NULL,
                type TEXT DEFAULT 'mvs',
                source TEXT NOT NULL DEFAULT '',
                enabled INTEGER DEFAULT 1,
                patchcore_model_path TEXT DEFAULT '',
                regions_json TEXT DEFAULT '[]',
                filter_classifier_path TEXT DEFAULT '',
                filter_classifier_enabled INTEGER DEFAULT 0,
                display_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (seat_model_id, camera_id),
                FOREIGN KEY (seat_model_id) REFERENCES seat_models(id)
            );
            CREATE TABLE IF NOT EXISTS model_files (
                id TEXT PRIMARY KEY,
                seat_model_id TEXT NOT NULL DEFAULT '',
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
        """)
        _ensure_camera_config_scoped_schema(conn)
        _ensure_camera_patchcore_column(conn)
        _ensure_camera_regions_column(conn)
        _ensure_model_file_seat_model_column(conn)
        _ensure_camera_indexes(conn)
        conn.commit()

    # ---------------------------------------------------------------- K-V config

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

    # ---------------------------------------------------------------- JSON sync

    def sync_json_to_db(self, json_path: str) -> None:
        """Parse all config from a JSON file and write into the SQLite K-V table."""
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
        """Export SQLite K-V config to a nested JSON file with atomic write."""
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

    # -------------------------------------------------------------- Seat models

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
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO seat_models (id, display_name, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (model_id, display_name, description, now, now),
            )
            conn.commit()

    def update_seat_model(self, model_id: str, **kwargs: Any) -> None:
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

    # ------------------------------------------------------------- Camera configs

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

    def get_camera(self, camera_id: str, seat_model_id: str | None = None) -> dict | None:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            if seat_model_id:
                row = conn.execute(
                    "SELECT * FROM camera_configs WHERE camera_id = ? AND seat_model_id = ?",
                    (camera_id, seat_model_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM camera_configs WHERE camera_id = ? ORDER BY seat_model_id",
                    (camera_id,),
                ).fetchone()
        return dict(row) if row else None

    def create_camera(self, camera: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO camera_configs
                   (camera_id, seat_model_id, type, source, enabled,
                    patchcore_model_path, regions_json, filter_classifier_path,
                    filter_classifier_enabled,
                    display_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    camera["camera_id"], camera["seat_model_id"],
                    camera.get("type", "mvs"), camera.get("source", ""),
                    camera.get("enabled", 1),
                    camera.get("patchcore_model_path", ""),
                    _regions_to_json(camera.get("regions_json", camera.get("regions"))),
                    camera.get("filter_classifier_path", ""),
                    camera.get("filter_classifier_enabled", 0),
                    camera.get("display_order", 0), now, now,
                ),
            )
            conn.commit()

    def update_camera(self, camera_id: str, seat_model_id: str | None = None, **kwargs: Any) -> None:
        allowed = {
            "type", "source", "enabled", "patchcore_model_path",
            "regions_json", "regions",
            "filter_classifier_path", "filter_classifier_enabled",
            "display_order",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        if "regions" in updates:
            updates["regions_json"] = _regions_to_json(updates.pop("regions"))
        if "regions_json" in updates:
            updates["regions_json"] = _regions_to_json(updates["regions_json"])
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        with self._get_conn() as conn:
            if seat_model_id:
                conn.execute(
                    f"UPDATE camera_configs SET {set_clause} WHERE camera_id = ? AND seat_model_id = ?",
                    values + [camera_id, seat_model_id],
                )
            else:
                conn.execute(
                    f"UPDATE camera_configs SET {set_clause} WHERE camera_id = ?",
                    values + [camera_id],
                )
            conn.commit()

    def delete_camera(self, camera_id: str, seat_model_id: str | None = None) -> None:
        with self._get_conn() as conn:
            if seat_model_id:
                conn.execute(
                    "DELETE FROM camera_configs WHERE camera_id = ? AND seat_model_id = ?",
                    (camera_id, seat_model_id),
                )
            else:
                conn.execute("DELETE FROM camera_configs WHERE camera_id = ?", (camera_id,))
            conn.commit()

    # ---------------------------------------------------------------- Model files

    def list_model_files(
        self,
        camera_id: str | None = None,
        model_type: str | None = None,
        seat_model_id: str | None = None,
    ) -> list[dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM model_files WHERE 1=1"
            params: list = []
            if seat_model_id is not None:
                sql += " AND seat_model_id = ?"
                params.append(seat_model_id)
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
                   (id, seat_model_id, camera_id, model_type, file_path, file_name, file_size,
                    sha256, source, platform_version, is_active, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mf["id"], mf.get("seat_model_id", ""), mf["camera_id"], mf["model_type"], mf["file_path"],
                    mf["file_name"], mf.get("file_size", 0),
                    mf.get("sha256", ""),
                    mf.get("source", "manual_import"),
                    mf.get("platform_version", ""),
                    mf.get("is_active", 1), mf["imported_at"],
                ),
            )
            conn.commit()

    def set_model_file_active(self, file_id: str, camera_id: str, model_type: str) -> None:
        with self._get_conn() as conn:
            # Verify the file_id exists and belongs to this camera+type
            row = conn.execute(
                "SELECT id, seat_model_id FROM model_files WHERE id = ? AND camera_id = ? AND model_type = ?",
                (file_id, camera_id, model_type),
            ).fetchone()
            if row is None:
                return  # silently ignore -- caller should validate
            seat_model_id = row[1] or ""
            conn.execute(
                "UPDATE model_files SET is_active = 0 WHERE seat_model_id = ? AND camera_id = ? AND model_type = ?",
                (seat_model_id, camera_id, model_type),
            )
            conn.execute(
                "UPDATE model_files SET is_active = 1 WHERE id = ?", (file_id,)
            )
            conn.commit()

    def delete_model_file(self, file_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM model_files WHERE id = ?", (file_id,))
            conn.commit()

    def get_active_model_path(self, camera_id: str, model_type: str, seat_model_id: str | None = None) -> str | None:
        with self._get_conn() as conn:
            if seat_model_id is not None:
                row = conn.execute(
                    "SELECT file_path FROM model_files "
                    "WHERE seat_model_id = ? AND camera_id = ? AND model_type = ? AND is_active = 1",
                    (seat_model_id, camera_id, model_type),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT file_path FROM model_files "
                    "WHERE camera_id = ? AND model_type = ? AND is_active = 1",
                    (camera_id, model_type),
                ).fetchone()
        return row[0] if row else None


# ------------------------------------------------------------------ Helpers

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


def _ensure_camera_patchcore_column(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(camera_configs)").fetchall()
    }
    if "patchcore_model_path" not in columns:
        conn.execute("ALTER TABLE camera_configs ADD COLUMN patchcore_model_path TEXT DEFAULT ''")


def _ensure_camera_config_scoped_schema(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(camera_configs)").fetchall()
    has_surrogate_id = any(row[1] == "id" for row in columns)
    camera_id_is_primary = any(row[1] == "camera_id" and row[5] for row in columns)
    if has_surrogate_id and not camera_id_is_primary:
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO seat_models "
        "(id, display_name, description, is_default, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        ("default", "默认型号", "旧相机配置自动迁移", now, now),
    )
    conn.execute("ALTER TABLE camera_configs RENAME TO camera_configs_legacy")
    conn.execute("""
        CREATE TABLE camera_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            seat_model_id TEXT NOT NULL,
            type TEXT DEFAULT 'mvs',
            source TEXT NOT NULL DEFAULT '',
            enabled INTEGER DEFAULT 1,
            patchcore_model_path TEXT DEFAULT '',
            regions_json TEXT DEFAULT '[]',
            filter_classifier_path TEXT DEFAULT '',
            filter_classifier_enabled INTEGER DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (seat_model_id, camera_id),
            FOREIGN KEY (seat_model_id) REFERENCES seat_models(id)
        )
    """)
    legacy_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(camera_configs_legacy)").fetchall()
    }
    if "seat_model_id" in legacy_columns:
        conn.execute(f"""
            INSERT OR IGNORE INTO seat_models
                (id, display_name, description, is_default, created_at, updated_at)
            SELECT DISTINCT
                COALESCE(NULLIF(seat_model_id, ''), 'default'),
                COALESCE(NULLIF(seat_model_id, ''), 'default'),
                '旧相机配置自动迁移',
                0,
                '{now}',
                '{now}'
            FROM camera_configs_legacy
        """)
    select_seat_model = "COALESCE(NULLIF(seat_model_id, ''), 'default')" if "seat_model_id" in legacy_columns else "'default'"
    select_type = "type" if "type" in legacy_columns else "'mvs'"
    select_source = "source" if "source" in legacy_columns else "''"
    select_enabled = "enabled" if "enabled" in legacy_columns else "1"
    select_regions = "regions_json" if "regions_json" in legacy_columns else "'[]'"
    select_patchcore = "patchcore_model_path" if "patchcore_model_path" in legacy_columns else "''"
    select_filter_path = "filter_classifier_path" if "filter_classifier_path" in legacy_columns else "''"
    select_filter_enabled = "filter_classifier_enabled" if "filter_classifier_enabled" in legacy_columns else "0"
    select_display_order = "display_order" if "display_order" in legacy_columns else "0"
    select_created_at = "created_at" if "created_at" in legacy_columns else f"'{now}'"
    select_updated_at = "updated_at" if "updated_at" in legacy_columns else f"'{now}'"
    conn.execute(f"""
        INSERT OR IGNORE INTO camera_configs (
            camera_id, seat_model_id, type, source, enabled,
            patchcore_model_path, regions_json, filter_classifier_path,
            filter_classifier_enabled, display_order, created_at, updated_at
        )
        SELECT
            camera_id, {select_seat_model}, {select_type}, {select_source}, {select_enabled},
            {select_patchcore}, {select_regions}, {select_filter_path},
            {select_filter_enabled}, {select_display_order}, {select_created_at}, {select_updated_at}
        FROM camera_configs_legacy
    """)
    conn.execute("DROP TABLE camera_configs_legacy")


def _ensure_camera_regions_column(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(camera_configs)").fetchall()
    }
    if "regions_json" not in columns:
        conn.execute("ALTER TABLE camera_configs ADD COLUMN regions_json TEXT DEFAULT '[]'")


def _ensure_model_file_seat_model_column(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(model_files)").fetchall()
    }
    if "seat_model_id" not in columns:
        conn.execute("ALTER TABLE model_files ADD COLUMN seat_model_id TEXT NOT NULL DEFAULT ''")
    conn.execute("DROP INDEX IF EXISTS idx_model_camera")
    conn.execute("DROP INDEX IF EXISTS idx_model_active")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model_camera ON model_files(seat_model_id, camera_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_model_active "
        "ON model_files(seat_model_id, camera_id, model_type, is_active)"
    )


def _ensure_camera_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_camera_seat ON camera_configs(seat_model_id)")


def _regions_to_json(value: Any) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value or "[]"
    return json.dumps(value, ensure_ascii=False)


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
    elif value.startswith("[") or value.startswith("{"):
        current[last] = json.loads(value)
    else:
        # Try int first (supports negatives), then float, fall back to string
        try:
            current[last] = int(value)
        except ValueError:
            try:
                current[last] = float(value)
            except ValueError:
                current[last] = value
