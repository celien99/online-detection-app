"""ViewModel for ReviewScreen: pending review queue."""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.log_engine import LogEngine


class ReviewViewModel(QObject):
    """复核队列 ViewModel，管理待复核记录。"""

    reviewListChanged = Signal()

    def __init__(self, log_engine: LogEngine) -> None:
        super().__init__()
        self._engine = log_engine
        self._reviews: List[Dict[str, Any]] = []

    def _get_reviews(self) -> list:
        return self._reviews

    reviews = Property(list, _get_reviews, notify=reviewListChanged)

    @Slot()
    def refresh(self) -> None:
        self._reviews = self._engine.get_pending_reviews()
        self.reviewListChanged.emit()

    @Slot(int)
    def confirmAsDefect(self, record_id: int) -> None:
        self._engine.resolve_review(record_id, "confirmed_defect")
        self.refresh()

    @Slot(int)
    def dismissAsOK(self, record_id: int) -> None:
        self._engine.resolve_review(record_id, "dismissed_ok")
        self.refresh()
