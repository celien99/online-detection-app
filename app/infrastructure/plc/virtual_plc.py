"""Virtual PLC for debugging without real hardware."""
from __future__ import annotations

from app.infrastructure.plc.interface import DefectSignal, LineStatus, PLCInterface


class VirtualPLC(PLCInterface):
    """虚拟 PLC，所有写操作记录在内存中，读操作返回预设状态。"""

    def __init__(self, initial_status: LineStatus = LineStatus.RUNNING) -> None:
        self._connected = False
        self._status = initial_status
        self._signals: list[DefectSignal] = []

    @property
    def enabled(self) -> bool: return True

    @property
    def connected(self) -> bool: return self._connected

    @property
    def last_signal(self) -> DefectSignal | None:
        return self._signals[-1] if self._signals else None

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def send_defect_signal(self, signal: DefectSignal) -> None:
        self._signals.append(signal)

    def read_line_status(self) -> LineStatus:
        return self._status

    def set_status(self, status: LineStatus) -> None:
        self._status = status
