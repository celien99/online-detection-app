"""Production line trigger and result adapters."""
from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from app.infrastructure.plc.interface import LineStatus


class InspectionDecision(Enum):
    OK = "OK"
    NG = "NG"
    REJECT = "REJECT"


@dataclass(slots=True)
class CaptureRequest:
    request_id: str
    part_id: str = ""
    seat_model_id: str | None = None
    source: str = "manual"
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at <= 0:
            self.created_at = time.time()


@dataclass(slots=True)
class InspectionResultSignal:
    request_id: str
    status: InspectionDecision
    part_id: str = ""
    defect_code: int = 0
    defect_type: str = ""
    confidence: float = 0.0
    reason: str = ""


@runtime_checkable
class LineSignalAdapter(Protocol):
    """Adapter for production-line capture triggers and result handshakes."""

    @property
    def enabled(self) -> bool: ...

    @property
    def connected(self) -> bool: ...

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def poll_capture_request(self) -> CaptureRequest | None: ...
    def send_busy(self, request: CaptureRequest, busy: bool) -> None: ...
    def send_result(self, result: InspectionResultSignal) -> None: ...
    def send_fault(self, request: CaptureRequest | None, code: str, message: str) -> None: ...
    def read_line_status(self) -> LineStatus: ...


class VirtualLineSignalAdapter(LineSignalAdapter):
    """In-memory line signal adapter used for development and manual triggering."""

    def __init__(self, initial_status: LineStatus = LineStatus.RUNNING) -> None:
        self._connected = False
        self._status = initial_status
        self._pending: CaptureRequest | None = None
        self._busy = False
        self._results: list[InspectionResultSignal] = []
        self._faults: list[tuple[str, str]] = []

    @property
    def enabled(self) -> bool:
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def last_result(self) -> InspectionResultSignal | None:
        return self._results[-1] if self._results else None

    @property
    def last_fault(self) -> tuple[str, str] | None:
        return self._faults[-1] if self._faults else None

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def queue_capture_request(
        self,
        *,
        part_id: str = "",
        seat_model_id: str | None = None,
        source: str = "manual",
    ) -> CaptureRequest:
        request = CaptureRequest(
            request_id=f"{source}-{int(time.time() * 1000)}",
            part_id=part_id,
            seat_model_id=seat_model_id,
            source=source,
        )
        self._pending = request
        return request

    def poll_capture_request(self) -> CaptureRequest | None:
        if self._status != LineStatus.RUNNING:
            return None
        request = self._pending
        self._pending = None
        return request

    def send_busy(self, request: CaptureRequest, busy: bool) -> None:
        self._busy = busy

    def send_result(self, result: InspectionResultSignal) -> None:
        self._results.append(result)

    def send_fault(self, request: CaptureRequest | None, code: str, message: str) -> None:
        self._faults.append((code, message))

    def read_line_status(self) -> LineStatus:
        return self._status

    def set_status(self, status: LineStatus) -> None:
        self._status = status


class ModbusLineSignalAdapter(LineSignalAdapter):
    """Modbus TCP line handshake adapter.

    The default point map is intentionally small and can be overridden from
    config.json once the site PLC address table is known.
    """

    def __init__(self, config: dict) -> None:
        self._host = config.get("host", "192.168.1.100")
        self._port = int(config.get("port", 502))
        self._capture_request_coil = int(config.get("capture_request_coil", 10))
        self._capture_ack_coil = int(config.get("capture_ack_coil", 11))
        self._busy_coil = int(config.get("busy_coil", 12))
        self._done_coil = int(config.get("done_coil", 13))
        self._ok_coil = int(config.get("ok_coil", 14))
        self._ng_coil = int(config.get("ng_coil", 15))
        self._reject_coil = int(config.get("reject_coil", 16))
        self._fault_coil = int(config.get("fault_coil", 17))
        self._line_status_register = int(config.get("line_status_register", 0))
        self._part_id_register = int(config.get("part_id_register", 20))
        self._seat_model_register = int(config.get("seat_model_register", 40))
        self._defect_code_register = int(config.get("defect_code_register", 60))
        self._fault_code_register = int(config.get("fault_code_register", 61))
        self._clear_request_on_ack = bool(config.get("clear_request_on_ack", False))
        self._connected = False
        self._client = None
        self._last_request_state = False
        self._last_request_id = 0

    @property
    def enabled(self) -> bool:
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        from pymodbus.client import ModbusTcpClient

        self._client = ModbusTcpClient(self._host, port=self._port)
        self._connected = bool(self._client.connect())

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._connected = False

    def poll_capture_request(self) -> CaptureRequest | None:
        if self._client is None or not self._connected:
            return None
        result = self._client.read_coils(self._capture_request_coil, 1)
        if result.isError():
            return None
        current = bool(result.bits[0])
        rising_edge = current and not self._last_request_state
        self._last_request_state = current
        if not rising_edge:
            return None

        self._last_request_id += 1
        part_id = self._read_register_string(self._part_id_register, 8)
        seat_model_id = self._read_register_string(self._seat_model_register, 8) or None
        request = CaptureRequest(
            request_id=f"plc-{self._last_request_id}",
            part_id=part_id,
            seat_model_id=seat_model_id,
            source="plc",
        )
        self._pulse_coil(self._capture_ack_coil)
        if self._clear_request_on_ack:
            self._client.write_coil(self._capture_request_coil, False)
        return request

    def send_busy(self, request: CaptureRequest, busy: bool) -> None:
        if self._client is not None and self._connected:
            self._client.write_coil(self._busy_coil, busy)

    def send_result(self, result: InspectionResultSignal) -> None:
        if self._client is None or not self._connected:
            return
        self._client.write_register(self._defect_code_register, int(result.defect_code))
        self._client.write_coil(self._ok_coil, result.status == InspectionDecision.OK)
        self._client.write_coil(self._ng_coil, result.status == InspectionDecision.NG)
        self._client.write_coil(self._reject_coil, result.status == InspectionDecision.REJECT)
        self._pulse_coil(self._done_coil)

    def send_fault(self, request: CaptureRequest | None, code: str, message: str) -> None:
        if self._client is None or not self._connected:
            return
        self._client.write_register(self._fault_code_register, _fault_code_to_int(code))
        self._pulse_coil(self._fault_coil)

    def read_line_status(self) -> LineStatus:
        if self._client is None or not self._connected:
            return LineStatus.UNKNOWN
        result = self._client.read_holding_registers(self._line_status_register, 1)
        if result.isError():
            return LineStatus.UNKNOWN
        return {
            0: LineStatus.STOPPED,
            1: LineStatus.RUNNING,
            2: LineStatus.PAUSED,
        }.get(result.registers[0], LineStatus.UNKNOWN)

    def _pulse_coil(self, address: int) -> None:
        self._client.write_coil(address, True)
        self._client.write_coil(address, False)

    def _read_register_string(self, start: int, count: int) -> str:
        result = self._client.read_holding_registers(start, count)
        if result.isError():
            return ""
        raw = bytearray()
        for value in result.registers:
            raw.extend([(value >> 8) & 0xFF, value & 0xFF])
        return raw.rstrip(b"\x00").decode("ascii", errors="ignore").strip()


def _fault_code_to_int(code: str) -> int:
    return abs(hash(code)) % 32767 or 1


class LabVIEWTcpLineSignalAdapter(LineSignalAdapter):
    """TCP JSON-lines adapter for LabVIEW or other supervisory software.

    Expected inbound message:
        {"type":"capture_request","request_id":"1","part_id":"P1","seat_model_id":"A"}

    Outbound messages:
        {"type":"busy","request_id":"1","busy":true}
        {"type":"result","request_id":"1","status":"OK",...}
        {"type":"fault","request_id":"1","code":"inspection_failed","message":"..."}
    """

    def __init__(self, config: dict) -> None:
        self._host = config.get("host", "127.0.0.1")
        self._port = int(config.get("port", 9100))
        self._timeout_s = float(config.get("timeout_s", 0.1))
        self._reconnect_interval_s = float(config.get("reconnect_interval_s", 2.0))
        self._connected = False
        self._sock: socket.socket | None = None
        self._buffer = ""
        self._last_connect_attempt = 0.0

    @property
    def enabled(self) -> bool:
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._close_socket()
        sock = socket.create_connection((self._host, self._port), timeout=self._timeout_s)
        sock.settimeout(self._timeout_s)
        self._sock = sock
        self._connected = True

    def disconnect(self) -> None:
        self._close_socket()

    def poll_capture_request(self) -> CaptureRequest | None:
        if not self._ensure_connected():
            return None
        message = self._read_message()
        if message is None or message.get("type") != "capture_request":
            return None
        return CaptureRequest(
            request_id=str(message.get("request_id") or f"labview-{int(time.time() * 1000)}"),
            part_id=str(message.get("part_id", "")),
            seat_model_id=message.get("seat_model_id") or None,
            source="labview",
        )

    def send_busy(self, request: CaptureRequest, busy: bool) -> None:
        self._send({
            "type": "busy",
            "request_id": request.request_id,
            "part_id": request.part_id,
            "busy": busy,
        })

    def send_result(self, result: InspectionResultSignal) -> None:
        self._send({
            "type": "result",
            "request_id": result.request_id,
            "part_id": result.part_id,
            "status": result.status.value,
            "defect_code": result.defect_code,
            "defect_type": result.defect_type,
            "confidence": result.confidence,
            "reason": result.reason,
        })

    def send_fault(self, request: CaptureRequest | None, code: str, message: str) -> None:
        self._send({
            "type": "fault",
            "request_id": request.request_id if request is not None else "",
            "part_id": request.part_id if request is not None else "",
            "code": code,
            "message": message,
        })

    def read_line_status(self) -> LineStatus:
        return LineStatus.RUNNING if self._connected else LineStatus.UNKNOWN

    def _ensure_connected(self) -> bool:
        if self._connected:
            return True
        now = time.time()
        if now - self._last_connect_attempt < self._reconnect_interval_s:
            return False
        self._last_connect_attempt = now
        try:
            self.connect()
        except OSError:
            self._close_socket()
            return False
        return True

    def _read_message(self) -> dict | None:
        if self._sock is None:
            return None
        try:
            chunk = self._sock.recv(4096)
        except socket.timeout:
            return None
        except OSError:
            self._close_socket()
            return None
        if not chunk:
            self._close_socket()
            return None
        self._buffer += chunk.decode("utf-8", errors="ignore")
        if "\n" not in self._buffer:
            return None
        line, self._buffer = self._buffer.split("\n", 1)
        line = line.strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _send(self, payload: dict) -> None:
        if not self._ensure_connected() or self._sock is None:
            return
        try:
            data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8") + b"\n"
            self._sock.sendall(data)
        except OSError:
            self._close_socket()

    def _close_socket(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._connected = False
