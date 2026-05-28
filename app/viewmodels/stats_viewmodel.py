"""ViewModel for StatsScreen."""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.stats_collector import StatsCollector


class StatsViewModel(QObject):
    """统计页 ViewModel，暴露当日统计摘要和缺陷分布。"""

    statsChanged = Signal()
    distributionChanged = Signal()

    def __init__(self, stats_collector: StatsCollector) -> None:
        super().__init__()
        self._stats = stats_collector
        self._total = 0
        self._ok = 0
        self._ng = 0
        self._ok_rate = 0.0
        self._defect_distribution: dict = {}

    def _get_total(self) -> int: return self._total
    def _get_ok(self) -> int: return self._ok
    def _get_ng(self) -> int: return self._ng
    def _get_ok_rate(self) -> float: return self._ok_rate
    def _get_defect_distribution(self) -> dict: return self._defect_distribution

    total = Property(int, _get_total, notify=statsChanged)
    ok = Property(int, _get_ok, notify=statsChanged)
    ng = Property(int, _get_ng, notify=statsChanged)
    okRate = Property(float, _get_ok_rate, notify=statsChanged)
    defectDistribution = Property(dict, _get_defect_distribution, notify=distributionChanged)

    @Slot()
    def refresh(self) -> None:
        today = self._stats.get_today_stats()
        self._total = today.total
        self._ok = today.ok + today.filter_suppressed
        self._ng = today.ng
        self._ok_rate = round(self._ok / max(self._total, 1) * 100, 2)
        self._defect_distribution = dict(today.defect_types)
        self.statsChanged.emit()
        self.distributionChanged.emit()

    @Slot(result="QVariantMap")
    def getDefectDistribution(self) -> dict:
        today = self._stats.get_today_stats()
        return dict(today.defect_types)
