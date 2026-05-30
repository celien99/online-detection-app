"""Tests for triggered inspection orchestration."""
from __future__ import annotations

import json
import socket
import threading
import time

import numpy as np

from app.infrastructure.camera.interface import CameraStatus
from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.line_signal import InspectionDecision, LabVIEWTcpLineSignalAdapter, VirtualLineSignalAdapter
from app.services.trigger_service import TriggerService


class FakeCamera:
    def __init__(self) -> None:
        self._connected = False

    @property
    def camera_id(self) -> str:
        return "CAM_A"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def width(self) -> int:
        return 4

    @property
    def height(self) -> int:
        return 4

    @property
    def fps(self) -> float:
        return 30.0

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def grab_frame(self, timeout_ms: int = 1000):
        return np.zeros((4, 4, 3), dtype=np.uint8) if self._connected else None

    def get_status(self) -> CameraStatus:
        return CameraStatus(camera_id=self.camera_id, connected=self._connected)


class FakeResponse:
    status = "OK"
    decision_reason = "all_checks_passed"

    class Result:
        camera_results = []

    result = Result()


class FakeInspectionService:
    def __init__(self) -> None:
        self.calls = 0

    def inspect_sync(self, frames, *, seat_model_id=None, timeout_s=5.0):
        self.calls += 1
        assert "CAM_A" in frames
        return FakeResponse()


def test_trigger_service_runs_one_inspection_for_manual_request() -> None:
    camera_manager = CameraManager()
    camera = FakeCamera()
    camera_manager.register(camera)
    camera_manager.connect_all()
    adapter = VirtualLineSignalAdapter()
    adapter.connect()
    inspection = FakeInspectionService()
    handled = []

    svc = TriggerService(
        adapter=adapter,
        camera_manager=camera_manager,
        inspection_service=inspection,
        handle_response=lambda response, frames: handled.append((response, frames)),
        capture_timeout_s=0.2,
    )
    svc.start()
    try:
        assert svc.manual_trigger(part_id="P1") is True
        deadline = time.time() + 1.0
        while time.time() < deadline and adapter.last_result is None:
            time.sleep(0.01)
    finally:
        svc.stop()
        camera_manager.disconnect_all()

    assert inspection.calls == 1
    assert len(handled) == 1
    assert adapter.last_result is not None
    assert adapter.last_result.status == InspectionDecision.OK
    assert adapter.last_result.part_id == "P1"


def test_labview_tcp_adapter_parses_request_and_sends_result() -> None:
    received = []
    ready = threading.Event()

    def server() -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port_holder.append(srv.getsockname()[1])
        srv.listen(1)
        ready.set()
        conn, _addr = srv.accept()
        with conn:
            conn.sendall(
                json.dumps({
                    "type": "capture_request",
                    "request_id": "REQ1",
                    "part_id": "P100",
                    "seat_model_id": "MODEL_A",
                }).encode("utf-8") + b"\n"
            )
            conn.settimeout(1.0)
            buffer = b""
            while len(received) < 2:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        received.append(json.loads(line.decode("utf-8")))
        srv.close()

    port_holder: list[int] = []
    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=1.0)

    adapter = LabVIEWTcpLineSignalAdapter({
        "host": "127.0.0.1",
        "port": port_holder[0],
        "timeout_s": 0.2,
        "reconnect_interval_s": 0.01,
    })
    adapter.connect()
    request = None
    deadline = time.time() + 1.0
    while time.time() < deadline and request is None:
        request = adapter.poll_capture_request()
        time.sleep(0.01)

    assert request is not None
    assert request.request_id == "REQ1"
    assert request.part_id == "P100"
    assert request.seat_model_id == "MODEL_A"

    adapter.send_busy(request, True)
    from app.infrastructure.line_signal import InspectionResultSignal

    adapter.send_result(
        InspectionResultSignal(
            request_id=request.request_id,
            part_id=request.part_id,
            status=InspectionDecision.OK,
            reason="all_checks_passed",
        )
    )
    thread.join(timeout=1.0)
    adapter.disconnect()

    assert received[0]["type"] == "busy"
    assert received[0]["busy"] is True
    assert received[1]["type"] == "result"
    assert received[1]["status"] == "OK"
