"""Tests for triggered inspection orchestration."""
from __future__ import annotations

import json
import socket
import threading
import time

import numpy as np

from app.infrastructure.camera.interface import CameraStatus
from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.line_signal import (
    InspectionDecision,
    InspectionResultSignal,
    LabVIEWTcpLineSignalAdapter,
    ModbusLineSignalAdapter,
    VirtualLineSignalAdapter,
)
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


class EmptyCamera(FakeCamera):
    def grab_frame(self, timeout_ms: int = 1000):
        return None


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


def test_trigger_service_sends_one_request_fault_on_capture_timeout() -> None:
    camera_manager = CameraManager()
    camera = EmptyCamera()
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
        poll_interval_s=0.01,
        capture_timeout_s=0.03,
    )
    svc.start()
    try:
        assert svc.manual_trigger(part_id="P_TIMEOUT") is True
        deadline = time.time() + 1.0
        while time.time() < deadline and adapter.last_fault is None:
            time.sleep(0.01)
    finally:
        svc.stop()
        camera_manager.disconnect_all()

    assert inspection.calls == 0
    assert handled == []
    assert adapter.last_result is None
    assert adapter.last_fault is not None
    assert adapter.last_fault[0] == "inspection_failed"
    assert adapter.last_fault[1] == "capture_timeout_no_frames"
    assert len(adapter._faults) == 1


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


class FakeModbusResult:
    def __init__(self, *, bits=None, registers=None, error: bool = False) -> None:
        self.bits = bits or []
        self.registers = registers or []
        self._error = error

    def isError(self) -> bool:
        return self._error


class FakeModbusClient:
    connect_calls = 0
    instances: list["FakeModbusClient"] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.connected = False
        self.coils: dict[int, bool] = {}
        self.registers: dict[int, int] = {0: 1}
        self.writes: list[tuple[str, int, int | bool]] = []
        FakeModbusClient.instances.append(self)

    def connect(self) -> bool:
        FakeModbusClient.connect_calls += 1
        self.connected = True
        return True

    def close(self) -> None:
        self.connected = False

    def read_coils(self, address: int, count: int):
        return FakeModbusResult(bits=[self.coils.get(address + offset, False) for offset in range(count)])

    def read_holding_registers(self, address: int, count: int):
        return FakeModbusResult(registers=[self.registers.get(address + offset, 0) for offset in range(count)])

    def write_coil(self, address: int, value: bool) -> None:
        self.coils[address] = value
        self.writes.append(("coil", address, value))

    def write_register(self, address: int, value: int) -> None:
        self.registers[address] = value
        self.writes.append(("register", address, value))


def _ascii_registers(value: str, count: int = 8) -> list[int]:
    raw = value.encode("ascii")[: count * 2]
    raw = raw + b"\x00" * (count * 2 - len(raw))
    return [(raw[i] << 8) | raw[i + 1] for i in range(0, len(raw), 2)]


def test_modbus_adapter_uses_rising_edge_and_result_handshake() -> None:
    FakeModbusClient.connect_calls = 0
    FakeModbusClient.instances = []
    adapter = ModbusLineSignalAdapter(
        {
            "host": "10.0.0.10",
            "port": 502,
            "pulse_width_s": 0,
            "capture_request_coil": 10,
            "capture_ack_coil": 11,
            "busy_coil": 12,
            "done_coil": 13,
            "ok_coil": 14,
            "ng_coil": 15,
            "reject_coil": 16,
            "defect_code_register": 60,
            "part_id_register": 20,
            "seat_model_register": 40,
        },
        client_factory=FakeModbusClient,
    )
    adapter.connect()
    client = FakeModbusClient.instances[-1]
    for offset, value in enumerate(_ascii_registers("P100")):
        client.registers[20 + offset] = value
    for offset, value in enumerate(_ascii_registers("MODEL_A")):
        client.registers[40 + offset] = value

    assert adapter.poll_capture_request() is None
    client.coils[10] = True
    request = adapter.poll_capture_request()
    assert request is not None
    assert request.part_id == "P100"
    assert request.seat_model_id == "MODEL_A"
    assert adapter.poll_capture_request() is None

    adapter.send_busy(request, True)
    adapter.send_result(
        InspectionResultSignal(
            request_id=request.request_id,
            status=InspectionDecision.NG,
            part_id=request.part_id,
            defect_code=7,
        )
    )

    assert client.coils[12] is True
    assert client.registers[60] == 7
    assert client.coils[14] is False
    assert client.coils[15] is True
    assert client.coils[16] is False
    assert ("coil", 13, True) in client.writes
    assert client.writes[-1] == ("coil", 13, False)


def test_modbus_adapter_reconnects_after_write_failure() -> None:
    class FailingWriteClient(FakeModbusClient):
        def write_coil(self, address: int, value: bool) -> None:
            raise OSError("connection lost")

    FakeModbusClient.connect_calls = 0
    FakeModbusClient.instances = []
    adapter = ModbusLineSignalAdapter(
        {"reconnect_interval_s": 0, "pulse_width_s": 0},
        client_factory=FailingWriteClient,
    )
    adapter.connect()
    request = type("Request", (), {"request_id": "REQ1", "part_id": ""})()
    adapter.send_busy(request, True)
    assert not adapter.connected

    status = adapter.read_line_status()
    assert status.value == "running"
    assert adapter.connected
    assert FakeModbusClient.connect_calls >= 2


def test_modbus_adapter_records_error_response_on_result_write() -> None:
    class ErrorResponseClient(FakeModbusClient):
        def write_register(self, address: int, value: int):
            return FakeModbusResult(error=True)

    FakeModbusClient.connect_calls = 0
    FakeModbusClient.instances = []
    adapter = ModbusLineSignalAdapter(
        {"reconnect_interval_s": 0, "pulse_width_s": 0, "defect_code_register": 60},
        client_factory=ErrorResponseClient,
    )
    adapter.connect()
    adapter.send_result(
        InspectionResultSignal(
            request_id="REQ1",
            status=InspectionDecision.NG,
            defect_code=7,
        )
    )

    assert not adapter.connected
    assert "write_register failed address=60" in adapter.last_error
