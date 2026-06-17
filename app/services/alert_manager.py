"""NG alert orchestration."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class AlertAction(Enum):
    CONFIRM_DEFECT = "confirm_defect"
    MARK_REVIEW = "mark_review"
    FALSE_ALARM = "false_alarm"


@dataclass(slots=True)
class AlertState:
    alert_id: str
    response: Any  # InspectionResponse
    camera_images: Dict[str, Any] = field(default_factory=dict)
    action: AlertAction | None = None
    acknowledged: bool = False
    started_at: float = field(default_factory=time.time)
    timeout_seconds: float = 30.0

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.timeout_seconds - (time.time() - self.started_at))

    @property
    def is_timed_out(self) -> bool:
        return self.remaining_seconds <= 0.0


class AlertManager:
    """NG 告警状态管理。发出信号通知 QML 层显示/隐藏弹窗。"""

    def __init__(self, timeout_seconds: float = 30.0, default_action: str = "confirm_defect") -> None:
        self._current: Optional[AlertState] = None
        self._lock = threading.Lock()
        self._timeout_seconds = timeout_seconds
        self._default_action = AlertAction(default_action)
        self.on_alert_shown: Optional[Callable[[AlertState], None]] = None
        self.on_alert_dismissed: Optional[Callable[[AlertState], None]] = None

    @property
    def has_active_alert(self) -> bool:
        with self._lock:
            return self._current is not None and not self._current.acknowledged

    @property
    def current_alert(self) -> Optional[AlertState]:
        with self._lock:
            return self._current

    def trigger(self, response: Any, camera_images: Dict[str, Any] | None = None) -> None:
        """触发新告警。若已有未确认告警则忽略。"""
        with self._lock:
            if self._current is not None and not self._current.acknowledged:
                return
            self._current = AlertState(
                alert_id=f"ng-{int(time.time() * 1000)}",
                response=response,
                camera_images=camera_images or {},
                timeout_seconds=self._timeout_seconds,
            )
            alert = self._current
        if self.on_alert_shown is not None:
            self.on_alert_shown(alert)

    def acknowledge(self, action: AlertAction) -> None:
        """操作员确认告警。"""
        with self._lock:
            if self._current is None:
                return
            self._current.action = action
            self._current.acknowledged = True
            alert = self._current
        if self.on_alert_dismissed is not None:
            self.on_alert_dismissed(alert)

    def check_timeout(self) -> Optional[AlertState]:
        """检查当前告警是否超时。超时则自动按默认动作处理。"""
        with self._lock:
            if self._current is None or self._current.acknowledged:
                return None
            if self._current.is_timed_out:
                self._current.action = self._default_action
                self._current.acknowledged = True
                alert = self._current
                if self.on_alert_dismissed is not None:
                    self.on_alert_dismissed(alert)
                return alert
        return None

    def update_config(self, *, timeout_seconds: float, default_action: str) -> None:
        with self._lock:
            self._timeout_seconds = timeout_seconds
            self._default_action = AlertAction(default_action)
            if self._current is not None and not self._current.acknowledged:
                self._current.timeout_seconds = timeout_seconds
