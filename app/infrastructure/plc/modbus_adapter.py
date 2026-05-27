"""Modbus TCP PLC adapter."""
from __future__ import annotations

from app.infrastructure.plc.interface import DefectSignal, LineStatus, PLCInterface, Severity


class ModbusTCPAdapter(PLCInterface):
    """通过 Modbus TCP 与 PLC 通信。"""

    def __init__(self, host: str, port: int = 502, defect_coil: int = 100, stop_coil: int = 101) -> None:
        self._host = host
        self._port = port
        self._defect_coil = defect_coil
        self._stop_coil = stop_coil
        self._connected = False
        self._client = None

    @property
    def enabled(self) -> bool: return True

    @property
    def connected(self) -> bool: return self._connected

    def connect(self) -> None:
        from pymodbus.client import ModbusTcpClient
        self._client = ModbusTcpClient(self._host, port=self._port)
        self._connected = self._client.connect()

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._connected = False

    def send_defect_signal(self, signal: DefectSignal) -> None:
        if self._client is None or not self._connected:
            return
        coil = self._defect_coil if signal.severity == Severity.MINOR else self._stop_coil
        self._client.write_coil(coil, True)
        self._client.write_coil(coil, False)  # 脉冲信号

    def read_line_status(self) -> LineStatus:
        if self._client is None or not self._connected:
            return LineStatus.UNKNOWN
        result = self._client.read_holding_registers(0, 1)
        if result.isError():
            return LineStatus.UNKNOWN
        status_map = {0: LineStatus.STOPPED, 1: LineStatus.RUNNING, 2: LineStatus.PAUSED}
        return status_map.get(result.registers[0], LineStatus.UNKNOWN)
