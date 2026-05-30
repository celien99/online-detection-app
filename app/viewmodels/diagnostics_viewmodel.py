"""ViewModel for production diagnostics."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.infrastructure.config_store import ConfigStore
from app.services.diagnostics import ProductionDiagnostics


class DiagnosticsViewModel(QObject):
    reportChanged = Signal()

    def __init__(self, config_store: ConfigStore, config_path: str) -> None:
        super().__init__()
        self._config = config_store
        self._config_path = config_path
        self._overall_status = "unknown"
        self._items: list[dict] = []

    def _get_overall_status(self) -> str:
        return self._overall_status

    def _get_items(self) -> list:
        return self._items

    overallStatus = Property(str, _get_overall_status, notify=reportChanged)
    items = Property(list, _get_items, notify=reportChanged)

    @Slot()
    def refresh(self) -> None:
        report = ProductionDiagnostics(self._config, Path(self._config_path)).run()
        self._overall_status = report.status
        self._items = report.to_dict()["items"]
        self.reportChanged.emit()
