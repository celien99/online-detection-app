"""Integration tests for service wiring."""
from __future__ import annotations

import time

import numpy as np
import pytest

from app.infrastructure.camera.interface import CameraInterface, CameraStatus
from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.config_store import ConfigStore
from app.infrastructure.plc.virtual_plc import VirtualPLC
from app.infrastructure.plc.interface import DefectSignal, LineStatus, Severity
from app.services.alert_manager import AlertAction, AlertManager
from app.services.stats_collector import InspectionRecord, StatsCollector


class MockResponse:
    status = "NG"
    result = None
    decision_reason = "texture_anomaly"


class TestFullPipeline:
    def test_config_load(self) -> None:
        config = ConfigStore("config.example.json")
        assert config.get_app_config()["line_id"] == "A-03"
        assert len(config.get_camera_configs()) >= 1

    def test_camera_manager_multi_register(self) -> None:
        mgr = CameraManager()

        class FakeCam(CameraInterface):
            def __init__(self, cid): self._id = cid; self._c = False
            @property
            def camera_id(self): return self._id
            @property
            def is_connected(self): return self._c
            @property
            def width(self): return 640
            @property
            def height(self): return 480
            @property
            def fps(self): return 30.0
            def connect(self): self._c = True
            def disconnect(self): self._c = False
            def grab_frame(self, timeout_ms=1000): return np.zeros((480, 640, 3), dtype=np.uint8)
            def get_status(self): return CameraStatus(camera_id=self._id, connected=self._c)

        for i in range(4):
            mgr.register(FakeCam(f"CAM_{i}"))
        mgr.connect_all()
        frames = mgr.grab_all()
        assert len(frames) == 4
        assert all(f is not None for f in frames.values())
        mgr.disconnect_all()

    def test_alert_manager_lifecycle(self) -> None:
        mgr = AlertManager(timeout_seconds=1.0)
        assert not mgr.has_active_alert
        mgr.trigger(MockResponse())
        assert mgr.has_active_alert
        mgr.acknowledge(AlertAction.CONFIRM_DEFECT)
        assert not mgr.has_active_alert

    def test_alert_manager_timeout(self) -> None:
        mgr = AlertManager(timeout_seconds=0.1)
        mgr.trigger(MockResponse())
        time.sleep(0.2)
        result = mgr.check_timeout()
        assert result is not None
        assert result.action == AlertAction.CONFIRM_DEFECT

    def test_stats_collector_record(self) -> None:
        sc = StatsCollector()
        sc.record(InspectionRecord(time.time(), "CAM_A", "OK", "all_checks_passed"))
        sc.record(InspectionRecord(time.time(), "CAM_B", "NG", "texture_anomaly", defect_type="破洞", confidence=0.94))
        today = sc.get_today_stats()
        assert today.total == 2
        assert today.ok == 1
        assert today.ng == 1

    def test_virtual_plc(self) -> None:
        plc = VirtualPLC()
        plc.connect()
        assert plc.connected
        plc.send_defect_signal(DefectSignal(camera_id="CAM_A", severity=Severity.MINOR))
        assert plc.last_signal is not None
        assert plc.read_line_status() == LineStatus.RUNNING
        plc.disconnect()
        assert not plc.connected
