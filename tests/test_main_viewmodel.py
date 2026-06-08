from __future__ import annotations

from types import SimpleNamespace

from app.services.alert_manager import AlertManager
from app.services.stats_collector import StatsCollector
from app.viewmodels.main_viewmodel import MainViewModel


class FakeInspectionService:
    pass


class FakeTriggerService:
    def __init__(self, state: SimpleNamespace) -> None:
        self._state = state
        self.manual_calls = 0

    def manual_trigger(self) -> bool:
        self.manual_calls += 1
        return True

    def get_state(self) -> SimpleNamespace:
        return self._state


def _make_vm() -> MainViewModel:
    return MainViewModel(
        FakeInspectionService(),
        AlertManager(),
        StatsCollector(),
    )


def test_manual_trigger_disabled_exposes_operator_message() -> None:
    vm = _make_vm()

    assert vm.triggerEnabled is False
    vm.manualTrigger()

    assert vm.triggerError == "manual_trigger_disabled"
    assert vm.triggerErrorDisplay == "手动触发仅在触发模式可用"


def test_capture_timeout_error_is_translated_for_display() -> None:
    vm = _make_vm()
    trigger = FakeTriggerService(
        SimpleNamespace(
            line_status="running",
            connected=True,
            busy=False,
            last_result="",
            last_error="capture_timeout_no_frames",
        )
    )

    vm.set_trigger_service(trigger)

    assert vm.triggerEnabled is True
    assert vm.triggerError == "capture_timeout_no_frames"
    assert vm.triggerErrorDisplay == "取帧超时：未收到相机图像"
