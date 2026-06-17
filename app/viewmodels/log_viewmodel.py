"""ViewModel for LogScreen."""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.log_engine import LogEngine


class LogViewModel(QObject):
    """日志页 ViewModel，管理筛选条件和查询结果。"""

    logsChanged = Signal()

    def __init__(self, log_engine: LogEngine) -> None:
        super().__init__()
        self._engine = log_engine
        self._logs: List[Dict[str, Any]] = []
        self._status_filter: str = ""
        self._camera_filter: str = ""

    def _get_logs(self) -> list:
        return self._logs

    logs = Property(list, _get_logs, notify=logsChanged)

    @Slot(str)
    def setStatusFilter(self, status: str) -> None:
        self._status_filter = status
        self.refresh()

    @Slot(str)
    def setCameraFilter(self, camera_id: str) -> None:
        self._camera_filter = camera_id
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        status = self._status_filter if self._status_filter else None
        camera = self._camera_filter if self._camera_filter else None
        self._logs = self._engine.query(status=status, camera_id=camera, limit=500)
        self.logsChanged.emit()

    @Slot(str)
    def exportCSV(self, path: str) -> None:
        self._engine.export_csv(path)

    @Slot()
    def clearOldLogs(self) -> None:
        self._engine.cleanup_old()
        self.refresh()
