"""ViewModel for MainScreen: camera grid, status bar, NG overlay control."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Property, Signal, Slot

from typing import TYPE_CHECKING

from app.services.alert_manager import AlertAction, AlertManager, AlertState
from app.services.inspection_service import InspectionService
from app.services.stats_collector import StatsCollector

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
    ngImageVersionChanged = Signal()
    cameraListChanged = Signal()
    remainingSecondsChanged = Signal()
    lineStatusChanged = Signal()
    lineConnectedChanged = Signal()
    lineBusyChanged = Signal()
    lastTriggerResultChanged = Signal()
    triggerErrorChanged = Signal()
    triggerErrorDisplayChanged = Signal()
    triggerEnabledChanged = Signal()
    gridLayoutChanged = Signal()

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
        self._ng_image_version = 0
        self._remaining_seconds = 0
        self._last_inspect_time = 0.0
        self._inspect_count = 0
        self._grid_layout = grid_layout
        self._last_ng_timestamp = 0.0
        self._trigger_service: Any | None = None
        self._line_status = "unknown"
        self._line_connected = False
        self._line_busy = False
        self._last_trigger_result = ""
        self._trigger_error = ""
        self._last_camera_emit = 0.0

        self._camera_list: List[Dict[str, Any]] = []
        self._camera_index: Dict[str, Dict[str, Any]] = {}
        for cid in (camera_ids or []):
            entry = {
                "cameraId": cid,
                "live": False,
                "status": "ok",
                "defectLabel": "",
                "frameVersion": 0,
            }
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
    def _get_ng_image_version(self) -> int: return self._ng_image_version
    def _get_camera_list(self) -> list: return self._camera_list
    def _get_remaining_seconds(self) -> int: return self._remaining_seconds
    def _get_line_status(self) -> str: return self._line_status
    def _get_line_connected(self) -> bool: return self._line_connected
    def _get_line_busy(self) -> bool: return self._line_busy
    def _get_last_trigger_result(self) -> str: return self._last_trigger_result
    def _get_trigger_error(self) -> str: return self._trigger_error
    def _get_trigger_error_display(self) -> str: return _trigger_error_display(self._trigger_error)
    def _get_trigger_enabled(self) -> bool: return self._trigger_service is not None
    def _get_grid_layout(self) -> str: return self._grid_layout

    lineId = Property(str, _get_line_id, notify=lineIdChanged)
    systemStatus = Property(str, _get_system_status, notify=systemStatusChanged)
    okCount = Property(int, _get_ok_count, notify=okCountChanged)
    ngCount = Property(int, _get_ng_count, notify=ngCountChanged)
    tactRate = Property(float, _get_tact_rate, notify=tactRateChanged)
    ngOverlayVisible = Property(bool, _get_ng_visible, notify=ngOverlayVisibleChanged)
    ngDefectType = Property(str, _get_ng_defect_type, notify=ngDefectTypeChanged)
    ngConfidence = Property(float, _get_ng_confidence, notify=ngConfidenceChanged)
    ngCameraId = Property(str, _get_ng_camera_id, notify=ngCameraIdChanged)
    ngImageVersion = Property(int, _get_ng_image_version, notify=ngImageVersionChanged)
    cameraList = Property(list, _get_camera_list, notify=cameraListChanged)
    remainingSeconds = Property(int, _get_remaining_seconds, notify=remainingSecondsChanged)
    lineStatus = Property(str, _get_line_status, notify=lineStatusChanged)
    lineConnected = Property(bool, _get_line_connected, notify=lineConnectedChanged)
    lineBusy = Property(bool, _get_line_busy, notify=lineBusyChanged)
    lastTriggerResult = Property(str, _get_last_trigger_result, notify=lastTriggerResultChanged)
    triggerError = Property(str, _get_trigger_error, notify=triggerErrorChanged)
    triggerErrorDisplay = Property(str, _get_trigger_error_display, notify=triggerErrorDisplayChanged)
    triggerEnabled = Property(bool, _get_trigger_enabled, notify=triggerEnabledChanged)
    gridLayout = Property(str, _get_grid_layout, notify=gridLayoutChanged)

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

    @Slot()
    def manualTrigger(self) -> None:
        if self._trigger_service is None:
            self._set_trigger_error("manual_trigger_disabled")
            return
        try:
            if self._trigger_service.manual_trigger():
                self._set_trigger_error("")
        except Exception as exc:
            self._set_trigger_error(str(exc))

    @Slot()
    def refreshTriggerState(self) -> None:
        self._sync_trigger_state()

    def set_trigger_service(self, trigger_service: Any) -> None:
        was_enabled = self._trigger_service is not None
        self._trigger_service = trigger_service
        self._system_status = "running"
        self.systemStatusChanged.emit()
        if not was_enabled:
            self.triggerEnabledChanged.emit()
        self._sync_trigger_state()

    def clear_trigger_service(self) -> None:
        was_enabled = self._trigger_service is not None
        self._trigger_service = None
        self._line_status = "unknown"
        self._line_connected = False
        self._line_busy = False
        self._last_trigger_result = ""
        self._trigger_error = ""
        self.lineStatusChanged.emit()
        self.lineConnectedChanged.emit()
        self.lineBusyChanged.emit()
        self.lastTriggerResultChanged.emit()
        self.triggerErrorChanged.emit()
        self.triggerErrorDisplayChanged.emit()
        if was_enabled:
            self.triggerEnabledChanged.emit()

    def apply_runtime_config(self, *, line_id: str, grid_layout: str, camera_ids: List[str]) -> None:
        if self._line_id != line_id:
            self._line_id = line_id
            self.lineIdChanged.emit()
        if self._grid_layout != grid_layout:
            self._grid_layout = grid_layout
            self.gridLayoutChanged.emit()

        old_by_id = {entry["cameraId"]: entry for entry in self._camera_list}
        new_list: List[Dict[str, Any]] = []
        new_index: Dict[str, Dict[str, Any]] = {}
        for cid in camera_ids:
            previous = old_by_id.get(cid, {})
            entry = {
                "cameraId": cid,
                "live": bool(previous.get("live", False)),
                "status": str(previous.get("status", "ok")),
                "defectLabel": str(previous.get("defectLabel", "")),
                "frameVersion": int(previous.get("frameVersion", 0)),
            }
            new_list.append(entry)
            new_index[cid] = entry
        self._camera_list = new_list
        self._camera_index = new_index
        self.cameraListChanged.emit()

    # ── Internal ──

    def mark_cameras_live(self, camera_ids: List[str]) -> None:
        """标记哪些相机当前有帧输入。"""
        changed = False
        now = time.time()
        for entry in self._camera_list:
            cid = entry["cameraId"]
            was_live = entry["live"]
            entry["live"] = cid in camera_ids
            if entry["live"]:
                entry["frameVersion"] = int(entry.get("frameVersion", 0)) + 1
            if entry["live"] != was_live:
                changed = True
        if changed or now - self._last_camera_emit >= 0.1:
            self._last_camera_emit = now
            self.cameraListChanged.emit()

    def update_from_result(self, response: Any, camera_images: Dict[str, Any] | None = None) -> None:
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
                    defect_label = _camera_defect_label(cr)
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
            self._alert.trigger(response, camera_images=camera_images)

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
            self._ng_defect_type = _camera_defect_label(ng_cam)
            self._ng_confidence = _camera_anomaly_score(ng_cam)
            self._ng_camera_id = ng_cam.camera_id
        self._ng_image_version += 1
        self._ng_visible = True
        self._remaining_seconds = int(alert.remaining_seconds)
        self.ngOverlayVisibleChanged.emit()
        self.ngDefectTypeChanged.emit()
        self.ngConfidenceChanged.emit()
        self.ngCameraIdChanged.emit()
        self.ngImageVersionChanged.emit()
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
        self._sync_trigger_state()
        current = self._alert.current_alert
        if current is not None and not current.acknowledged:
            secs = int(current.remaining_seconds)
            if secs != self._remaining_seconds:
                self._remaining_seconds = secs
                self.remainingSecondsChanged.emit()

    def _sync_trigger_state(self) -> None:
        if self._trigger_service is None:
            return
        state = self._trigger_service.get_state()
        if self._line_status != state.line_status:
            self._line_status = state.line_status
            self.lineStatusChanged.emit()
        if self._line_connected != state.connected:
            self._line_connected = state.connected
            self.lineConnectedChanged.emit()
        if self._line_busy != state.busy:
            self._line_busy = state.busy
            self.lineBusyChanged.emit()
        if self._last_trigger_result != state.last_result:
            self._last_trigger_result = state.last_result
            self.lastTriggerResultChanged.emit()
        if self._trigger_error != state.last_error:
            self._trigger_error = state.last_error
            self.triggerErrorChanged.emit()
            self.triggerErrorDisplayChanged.emit()

    def _set_trigger_error(self, message: str) -> None:
        if self._trigger_error == message:
            return
        self._trigger_error = message
        self.triggerErrorChanged.emit()
        self.triggerErrorDisplayChanged.emit()


def _camera_defect_label(camera_result: Any) -> str:
    filter_result = getattr(camera_result, "filter_result", None)
    class_name = getattr(filter_result, "class_name", "") if filter_result else ""
    if class_name:
        return str(class_name)
    region = _primary_ng_region(camera_result)
    if region is not None:
        return f"region:{getattr(region, 'region_id', '')}"
    return ""


def _camera_anomaly_score(camera_result: Any) -> float:
    texture_result = getattr(camera_result, "texture_result", None)
    if texture_result is not None:
        return float(getattr(texture_result, "score", 0.0) or 0.0)
    region = _primary_ng_region(camera_result)
    if region is None:
        return 0.0
    region_texture = getattr(region, "texture_result", None)
    if region_texture is None:
        return 0.0
    return float(getattr(region_texture, "score", 0.0) or 0.0)


def _primary_ng_region(camera_result: Any) -> Any:
    ng_regions = [
        region
        for region in getattr(camera_result, "region_results", []) or []
        if getattr(region, "status", "") == "NG"
    ]
    if not ng_regions:
        return None
    return max(
        ng_regions,
        key=lambda region: float(getattr(getattr(region, "texture_result", None), "score", 0.0) or 0.0),
    )


def _trigger_error_display(message: str) -> str:
    if not message:
        return ""
    return {
        "capture_timeout_no_frames": "取帧超时：未收到相机图像",
        "manual_trigger_disabled": "手动触发仅在触发模式可用",
        "trigger_service_not_started": "触发服务未启动",
    }.get(message, message)
