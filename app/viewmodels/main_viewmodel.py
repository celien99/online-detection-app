"""ViewModel for MainScreen: camera grid, status bar, NG overlay control."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot

from typing import TYPE_CHECKING

from app.services.alert_manager import AlertAction, AlertManager, AlertState
from app.services.inspection_service import InspectionService
from app.services.stats_collector import DailyStats, InspectionRecord, StatsCollector

if TYPE_CHECKING:
    from app.services.log_engine import LogEngine


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
    - cameraList: list[dict] — 动态相机列表
    - remainingSeconds: int — NG 弹窗剩余倒计时
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
    cameraListChanged = Signal()
    remainingSecondsChanged = Signal()

    def __init__(
        self,
        inspection_service: InspectionService,
        alert_manager: AlertManager,
        stats_collector: StatsCollector,
        line_id: str = "",
        camera_ids: List[str] | None = None,
        grid_layout: str = "2x2",
        log_engine: "LogEngine | None" = None,
    ) -> None:
        super().__init__()
        self._inspection = inspection_service
        self._alert = alert_manager
        self._stats = stats_collector
        self._log_engine = log_engine
        self._line_id = line_id
        self._system_status = "running"
        self._ok_count = 0
        self._ng_count = 0
        self._tact_rate = 0.0
        self._ng_visible = False
        self._ng_defect_type = ""
        self._ng_confidence = 0.0
        self._ng_camera_id = ""
        self._remaining_seconds = 0
        self._last_inspect_time = 0.0
        self._inspect_count = 0
        self._grid_layout = grid_layout
        self._last_ng_timestamp = 0.0

        self._camera_list: List[Dict[str, Any]] = []
        self._camera_index: Dict[str, Dict[str, Any]] = {}
        for cid in (camera_ids or []):
            entry = {"cameraId": cid, "live": False, "status": "ok", "defectLabel": ""}
            self._camera_list.append(entry)
            self._camera_index[cid] = entry

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
    def _get_camera_list(self) -> list: return self._camera_list
    def _get_remaining_seconds(self) -> int: return self._remaining_seconds

    lineId = Property(str, _get_line_id, notify=lineIdChanged)
    systemStatus = Property(str, _get_system_status, notify=systemStatusChanged)
    okCount = Property(int, _get_ok_count, notify=okCountChanged)
    ngCount = Property(int, _get_ng_count, notify=ngCountChanged)
    tactRate = Property(float, _get_tact_rate, notify=tactRateChanged)
    ngOverlayVisible = Property(bool, _get_ng_visible, notify=ngOverlayVisibleChanged)
    ngDefectType = Property(str, _get_ng_defect_type, notify=ngDefectTypeChanged)
    ngConfidence = Property(float, _get_ng_confidence, notify=ngConfidenceChanged)
    ngCameraId = Property(str, _get_ng_camera_id, notify=ngCameraIdChanged)
    cameraList = Property(list, _get_camera_list, notify=cameraListChanged)
    remainingSeconds = Property(int, _get_remaining_seconds, notify=remainingSecondsChanged)

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

    def mark_cameras_live(self, camera_ids: List[str]) -> None:
        """标记哪些相机当前有帧输入。"""
        changed = False
        for entry in self._camera_list:
            cid = entry["cameraId"]
            was_live = entry["live"]
            entry["live"] = cid in camera_ids
            if entry["live"] != was_live:
                changed = True
        if changed:
            self.cameraListChanged.emit()

    def update_from_result(self, response: Any) -> None:
        """根据检测结果更新状态。"""
        self._last_inspect_time = time.time()
        self._inspect_count += 1
        if self._inspect_count >= 10:
            elapsed = time.time() - (self._last_inspect_time - 1.0)
            self._tact_rate = round(60.0 / max(elapsed / self._inspect_count, 0.001), 1)
            self._inspect_count = 0
            self.tactRateChanged.emit()

        # Update per-camera status from results
        camera_changed = False
        if hasattr(response, 'result') and hasattr(response.result, 'camera_results'):
            for cr in response.result.camera_results:
                entry = self._camera_index.get(cr.camera_id)
                if entry is None:
                    continue
                new_status = "ng" if cr.status == "NG" else ("warn" if cr.status == "REJECT" else "ok")
                defect_label = ""
                if cr.status == "NG":
                    defect_label = getattr(cr.filter_result, 'class_name', '') if hasattr(cr, 'filter_result') and cr.filter_result else ''
                if entry["status"] != new_status or entry["defectLabel"] != defect_label:
                    entry["status"] = new_status
                    entry["defectLabel"] = defect_label
                    camera_changed = True
        if camera_changed:
            self.cameraListChanged.emit()

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
        self._last_ng_timestamp = time.time()
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
        self._remaining_seconds = int(alert.remaining_seconds)
        self.ngOverlayVisibleChanged.emit()
        self.ngDefectTypeChanged.emit()
        self.ngConfidenceChanged.emit()
        self.ngCameraIdChanged.emit()
        self.remainingSecondsChanged.emit()

    def _on_alert_dismissed(self, alert: AlertState) -> None:
        self._ng_visible = False
        self._remaining_seconds = 0
        self.ngOverlayVisibleChanged.emit()
        self.remainingSecondsChanged.emit()
        if alert.action is not None and self._log_engine is not None:
            self._log_engine.update_operator_action(
                self._ng_camera_id, self._last_ng_timestamp, alert.action.value
            )
        self.update_stats_from_collector()

    def tick_countdown(self) -> None:
        """由 QML 定时器每秒调用，同步倒计时。"""
        current = self._alert.current_alert
        if current is not None and not current.acknowledged:
            secs = int(current.remaining_seconds)
            if secs != self._remaining_seconds:
                self._remaining_seconds = secs
                self.remainingSecondsChanged.emit()
