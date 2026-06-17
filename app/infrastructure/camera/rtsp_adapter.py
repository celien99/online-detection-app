"""RTSP camera adapter."""
from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np

from app.infrastructure.camera.interface import CameraInterface, CameraStatus


class RTSPCameraAdapter(CameraInterface):
    """通过 OpenCV VideoCapture 接入 RTSP 网络相机。"""

    def __init__(self, camera_id: str, rtsp_url: str) -> None:
        self._id = camera_id
        self._rtsp_url = rtsp_url
        self._cap: Optional[cv2.VideoCapture] = None
        self._frames_grabbed = 0
        self._last_frame_at = 0.0

    @property
    def camera_id(self) -> str: return self._id

    @property
    def is_connected(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def width(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self._cap is not None else 0

    @property
    def height(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self._cap is not None else 0

    @property
    def fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) if self._cap is not None else 0.0

    def connect(self) -> None:
        self._cap = cv2.VideoCapture(self._rtsp_url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP stream: {self._rtsp_url}")

    def disconnect(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def grab_frame(self, timeout_ms: int = 1000) -> np.ndarray | None:
        if self._cap is None:
            return None
        success, frame = self._cap.read()
        if success and frame is not None:
            self._frames_grabbed += 1
            self._last_frame_at = time.time()
            return frame
        return None

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id=self._id,
            connected=self.is_connected,
            width=self.width,
            height=self.height,
            fps=self.fps,
            frames_grabbed=self._frames_grabbed,
            last_frame_at=self._last_frame_at,
        )
