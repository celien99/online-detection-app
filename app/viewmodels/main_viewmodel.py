"""ViewModel for MainScreen: camera grid, status bar, NG overlay control."""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.alert_manager import AlertAction, AlertManager, AlertState
from app.services.inspection_service import InspectionService
from app.services.stats_collector import DailyStats, InspectionRecord, StatsCollector


class MainViewModel(QObject):
    """MainScreen 的 ViewModel，管理实时监控页面的所有状态。

    暴露给 QML 的 property:
    - lineId: str
    - systemStatus: str (running/paused/stopped)
    - okCount: int
    - ngCount: int
    - tactRate: float (节拍/分钟)
    - ngOverlayVisible: bool
    - ngDefectType: str
    - ngConfidence: float
    - ngCameraId: str
    """

    lineIdChanged = Signal()
    systemStatusChanged = Signal()
    okCountChanged = Signal()
    ngCountChanged = Signal()
    tactRateChanged = Signal()
    ngOverlayVisibleChanged = Signal()
    ngDefectTypeChanged = Signal()
    ngConfidenceChanged = Signal()
    ngCameraIdChanged = Signal()

    def __init__(
        self,
        inspection_service: InspectionService,
        alert_manager: AlertManager,
        stats_collector: StatsCollector,
        line_id: str = "",
    ) -> None:
        super().__init__()
        self._inspection = inspection_service
        self._alert = alert_manager
        self._stats = stats_collector
        self._line_id = line_id
        self._system_status = "stopped"
        self._ok_count = 0
        self._ng_count = 0
        self._tact_rate = 0.0
        self._ng_visible = False
        self._ng_defect_type = ""
        self._ng_confidence = 0.0
        self._ng_camera_id = ""
        self._last_inspect_time = 0.0
        self._inspect_count = 0

        # 连接告警回调
        self._alert.on_alert_shown = self._on_alert_shown
        self._alert.on_alert_dismissed = self._on_alert_dismissed

    # ── QML Properties ──

    def _get_line_id(self) -> str: return self._line_id
    def _get_system_status(self) -> str: return self._system_status
    def _get_ok_count(self) -> int: return self._ok_count
    def _get_ng_count(self) -> int: return self._ng_count
    def _get_tact_rate(self) -> float: return self._tact_rate
    def _get_ng_visible(self) -> bool: return self._ng_visible
    def _get_ng_defect_type(self) -> str: return self._ng_defect_type
    def _get_ng_confidence(self) -> float: return self._ng_confidence
    def _get_ng_camera_id(self) -> str: return self._ng_camera_id

    lineId = Property(str, _get_line_id, notify=lineIdChanged)
    systemStatus = Property(str, _get_system_status, notify=systemStatusChanged)
    okCount = Property(int, _get_ok_count, notify=okCountChanged)
    ngCount = Property(int, _get_ng_count, notify=ngCountChanged)
    tactRate = Property(float, _get_tact_rate, notify=tactRateChanged)
    ngOverlayVisible = Property(bool, _get_ng_visible, notify=ngOverlayVisibleChanged)
    ngDefectType = Property(str, _get_ng_defect_type, notify=ngDefectTypeChanged)
    ngConfidence = Property(float, _get_ng_confidence, notify=ngConfidenceChanged)
    ngCameraId = Property(str, _get_ng_camera_id, notify=ngCameraIdChanged)

    # ── Slots ──

    @Slot()
    def acknowledgeNG(self) -> None:
        self._alert.acknowledge(AlertAction.CONFIRM_DEFECT)

    @Slot()
    def markReview(self) -> None:
        self._alert.acknowledge(AlertAction.MARK_REVIEW)

    @Slot()
    def dismissFalseAlarm(self) -> None:
        self._alert.acknowledge(AlertAction.FALSE_ALARM)

    # ── Internal ──

    def update_from_result(self, response: Any) -> None:
        """根据检测结果更新状态。"""
        self._last_inspect_time = time.time()
        self._inspect_count += 1
        if self._inspect_count >= 10:
            elapsed = time.time() - (self._last_inspect_time - 1.0)
            self._tact_rate = round(60.0 / max(elapsed / self._inspect_count, 0.001), 1)
            self._inspect_count = 0
            self.tactRateChanged.emit()

        stats = self._stats.get_today_stats()
        self._ok_count = stats.ok + stats.filter_suppressed
        self._ng_count = stats.ng
        self.okCountChanged.emit()
        self.ngCountChanged.emit()

        if response.status == "NG":
            self._alert.trigger(response)

    def update_stats_from_collector(self) -> None:
        stats = self._stats.get_today_stats()
        self._ok_count = stats.ok + stats.filter_suppressed
        self._ng_count = stats.ng
        self.okCountChanged.emit()
        self.ngCountChanged.emit()

    # ── Alert callbacks ──

    def _on_alert_shown(self, alert: AlertState) -> None:
        """AlertManager 触发告警时回调，设置 NG overlay 数据。"""
        result = alert.response
        ng_cam = None
        if hasattr(result, 'result') and hasattr(result.result, 'camera_results'):
            for cr in result.result.camera_results:
                if cr.status == "NG":
                    ng_cam = cr
                    break
        if ng_cam is not None:
            self._ng_defect_type = getattr(ng_cam.filter_result, 'class_name', '') if hasattr(ng_cam, 'filter_result') and ng_cam.filter_result else ''
            self._ng_confidence = float(ng_cam.texture_result.score) if hasattr(ng_cam, 'texture_result') and ng_cam.texture_result else 0.0
            self._ng_camera_id = ng_cam.camera_id
        self._ng_visible = True
        self.ngOverlayVisibleChanged.emit()
        self.ngDefectTypeChanged.emit()
        self.ngConfidenceChanged.emit()
        self.ngCameraIdChanged.emit()

    def _on_alert_dismissed(self, alert: AlertState) -> None:
        self._ng_visible = False
        self.ngOverlayVisibleChanged.emit()
        if alert.action is not None:
            record = InspectionRecord(
                timestamp=time.time(),
                camera_id=self._ng_camera_id,
                status="NG",
                reason=alert.action.value,
                defect_type=self._ng_defect_type,
                confidence=self._ng_confidence,
                operator_action=alert.action.value,
            )
            self._stats.record(record)
        self.update_stats_from_collector()
