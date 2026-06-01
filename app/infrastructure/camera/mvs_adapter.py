"""mvsCamera adapter implementing CameraInterface."""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

from app.infrastructure.camera.interface import CameraInterface, CameraStatus
from app.infrastructure.camera.mvs.frame_source import (
    MvsCameraCapture,
    MvsCameraSourceConfig,
    parse_mvs_source,
)


class MvsCameraAdapter(CameraInterface):
    """将 mvsCamera 库的 MvsCameraCapture 适配为 CameraInterface。"""

    def __init__(self, camera_id: str, source_uri: str) -> None:
        self._id = camera_id
        self._source_uri = source_uri
        self._config: MvsCameraSourceConfig = parse_mvs_source(source_uri)
        self._capture: Optional[MvsCameraCapture] = None
        self._width = 0
        self._height = 0
        self._fps = 0.0
        self._frames_grabbed = 0

    @property
    def camera_id(self) -> str:
        return self._id

    @property
    def is_connected(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def fps(self) -> float:
        return self._fps

    def connect(self) -> None:
        self._capture = MvsCameraCapture(self._config)
        self._width = int(self._capture.get(3))
        self._height = int(self._capture.get(4))
        self._fps = self._capture.get(5)

    def disconnect(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def grab_frame(self, timeout_ms: int = 1000) -> np.ndarray | None:
        if self._capture is None:
            return None
        success, frame = self._capture.read(timeout_ms=timeout_ms)
        if success and frame is not None:
            self._frames_grabbed += 1
            return frame
        return None

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id=self._id,
            connected=self.is_connected,
            grabbing=self.is_connected,
            width=self._width,
            height=self._height,
            fps=self._fps,
            frames_grabbed=self._frames_grabbed,
            last_frame_at=time.time(),
        )
