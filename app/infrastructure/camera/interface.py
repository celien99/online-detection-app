"""Camera abstraction interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(slots=True)
class CameraStatus:
    camera_id: str
    connected: bool = False
    grabbing: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frames_grabbed: int = 0
    last_frame_at: float = 0.0
    last_error: str | None = None


@runtime_checkable
class CameraInterface(Protocol):
    """工业相机统一采集接口。所有相机适配器必须实现此接口。"""

    @property
    def camera_id(self) -> str: ...

    @property
    def is_connected(self) -> bool: ...

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    @property
    def fps(self) -> float: ...

    def connect(self) -> None:
        """建立连接并开始取流。"""
        ...

    def disconnect(self) -> None:
        """停止取流并关闭连接。"""
        ...

    def grab_frame(self, timeout_ms: int = 1000) -> np.ndarray | None:
        """采集一帧 BGR 图像。返回 None 表示超时。"""
        ...

    def get_status(self) -> CameraStatus:
        """返回当前相机状态。"""
        ...
