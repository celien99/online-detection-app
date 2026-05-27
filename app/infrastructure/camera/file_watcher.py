"""File watcher camera adapter for debugging without real hardware."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.infrastructure.camera.interface import CameraInterface, CameraStatus


class FileWatcherCamera(CameraInterface):
    """监控目录中的最新图像文件，模拟相机取流（调试用）。"""

    def __init__(self, camera_id: str, watch_dir: str, pattern: str = "*.jpg") -> None:
        self._id = camera_id
        self._watch_dir = Path(watch_dir)
        self._pattern = pattern
        self._connected = False
        self._last_file: Optional[Path] = None
        self._width = 0
        self._height = 0
        self._frames_grabbed = 0
        self._last_frame_at = 0.0

    @property
    def camera_id(self) -> str: return self._id

    @property
    def is_connected(self) -> bool: return self._connected

    @property
    def width(self) -> int: return self._width

    @property
    def height(self) -> int: return self._height

    @property
    def fps(self) -> float: return 0.0

    def connect(self) -> None:
        self._watch_dir.mkdir(parents=True, exist_ok=True)
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def grab_frame(self, timeout_ms: int = 1000) -> np.ndarray | None:
        files = sorted(self._watch_dir.glob(self._pattern))
        if not files:
            return None
        newest = files[-1]
        if newest == self._last_file:
            return None
        self._last_file = newest
        frame = cv2.imread(str(newest), cv2.IMREAD_COLOR)
        if frame is not None:
            self._height, self._width = frame.shape[:2]
            self._frames_grabbed += 1
            self._last_frame_at = time.time()
        return frame

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id=self._id,
            connected=self._connected,
            width=self._width,
            height=self._height,
            frames_grabbed=self._frames_grabbed,
            last_frame_at=self._last_frame_at,
        )
