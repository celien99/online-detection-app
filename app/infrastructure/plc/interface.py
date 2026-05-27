"""PLC communication interface."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class LineStatus(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class Severity(Enum):
    MINOR = 0     # 标记踢料，产线继续
    CRITICAL = 1  # 紧急停线


@dataclass(slots=True)
class DefectSignal:
    camera_id: str
    severity: Severity
    defect_type: str = ""
    confidence: float = 0.0


@runtime_checkable
class PLCInterface(Protocol):
    """PLC 通讯接口。"""

    @property
    def enabled(self) -> bool: ...

    @property
    def connected(self) -> bool: ...

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def send_defect_signal(self, signal: DefectSignal) -> None:
        """向 PLC 寄存器写入缺陷信号。"""
        ...
    def read_line_status(self) -> LineStatus:
        """读取产线运行状态。"""
        ...
