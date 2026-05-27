"""Log persistence engine using SQLite."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from app.services.stats_collector import InspectionRecord


class LogEngine:
    """将检测记录持久化到 SQLite。"""

    def __init__(self, db_path: str = "./logs/inspection.db", retention_days: int = 30) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._retention_days = retention_days
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inspection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    camera_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    defect_type TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    operator_action TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON inspection_log(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON inspection_log(status)")
            conn.commit()

    def insert(self, record: InspectionRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO inspection_log (timestamp, camera_id, status, reason, defect_type, confidence, operator_action) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record.timestamp, record.camera_id, record.status, record.reason, record.defect_type, record.confidence, record.operator_action),
            )
            conn.commit()

    def query(
        self,
        status: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[dict]:
        sql = "SELECT * FROM inspection_log WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if camera_id:
            sql += " AND camera_id = ?"
            params.append(camera_id)
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def cleanup_old(self) -> int:
        cutoff = time.time() - self._retention_days * 86400
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM inspection_log WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount

    def export_csv(self, output_path: str) -> None:
        import csv
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM inspection_log ORDER BY timestamp DESC").fetchall()
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "timestamp", "camera_id", "status", "reason", "defect_type", "confidence", "operator_action"])
            writer.writerows(rows)
