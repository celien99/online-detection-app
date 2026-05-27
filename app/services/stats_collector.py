"""Inspection statistics collector."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class InspectionRecord:
    timestamp: float
    camera_id: str
    status: str  # OK / NG / REJECT
    reason: str
    defect_type: str = ""
    confidence: float = 0.0
    operator_action: str = ""


@dataclass(slots=True)
class DailyStats:
    total: int = 0
    ok: int = 0
    ng: int = 0
    reject: int = 0
    filter_suppressed: int = 0
    by_camera: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    defect_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class StatsCollector:
    """收集检测统计数据，支持按天/周/月查询。"""

    def __init__(self, max_records: int = 100_000) -> None:
        self._lock = threading.Lock()
        self._records: List[InspectionRecord] = []
        self._max_records = max_records
        self._today = DailyStats()
        self._day_key = time.strftime("%Y-%m-%d")

    def record(self, record: InspectionRecord) -> None:
        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records // 2:]
            today = time.strftime("%Y-%m-%d")
            if today != self._day_key:
                self._today = DailyStats()
                self._day_key = today
            self._today.total += 1
            if record.status == "OK":
                self._today.ok += 1
            elif record.status == "NG":
                self._today.ng += 1
            elif record.status == "REJECT":
                self._today.reject += 1
            self._today.by_camera[record.camera_id][record.status] += 1
            if record.defect_type:
                self._today.defect_types[record.defect_type] += 1

    def get_today_stats(self) -> DailyStats:
        with self._lock:
            return self._today

    def get_records(self, limit: int = 200) -> List[InspectionRecord]:
        with self._lock:
            return list(self._records[-limit:])

    def get_records_filtered(
        self, status: str | None = None, camera_id: str | None = None, limit: int = 200
    ) -> List[InspectionRecord]:
        with self._lock:
            result = list(self._records)
        if status:
            result = [r for r in result if r.status == status]
        if camera_id:
            result = [r for r in result if r.camera_id == camera_id]
        return result[-limit:]
