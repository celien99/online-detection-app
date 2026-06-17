"""Tests for CameraManager."""
from __future__ import annotations

import numpy as np

from app.infrastructure.camera.interface import CameraInterface, CameraStatus
from app.infrastructure.camera.manager import CameraManager


class FakeCamera(CameraInterface):
    def __init__(self, camera_id: str) -> None:
        self._id = camera_id
        self._connected = False
        self._width = 1920
        self._height = 1080
        self._fps = 30.0
        self._frames = 0

    @property
    def camera_id(self) -> str: return self._id

    @property
    def is_connected(self) -> bool: return self._connected

    @property
    def width(self) -> int: return self._width

    @property
    def height(self) -> int: return self._height

    @property
    def fps(self) -> float: return self._fps

    def connect(self) -> None: self._connected = True

    def disconnect(self) -> None: self._connected = False

    def grab_frame(self, timeout_ms: int = 1000) -> np.ndarray | None:
        if not self._connected:
            return None
        self._frames += 1
        return np.zeros((self._height, self._width, 3), dtype=np.uint8)

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id=self._id,
            connected=self._connected,
            width=self._width,
            height=self._height,
            fps=self._fps,
            frames_grabbed=self._frames,
        )


class TestCameraManager:
    def test_register_and_connect(self) -> None:
        mgr = CameraManager()
        cam = FakeCamera("CAM_A")
        mgr.register(cam)
        mgr.connect_all()
        assert cam.is_connected is True

    def test_grab_all_returns_frames(self) -> None:
        mgr = CameraManager()
        cam = FakeCamera("CAM_A")
        mgr.register(cam)
        mgr.connect_all()
        frames = mgr.grab_all()
        assert "CAM_A" in frames
        assert frames["CAM_A"] is not None
        assert frames["CAM_A"].shape == (1080, 1920, 3)

    def test_grab_all_returns_none_when_disconnected(self) -> None:
        mgr = CameraManager()
        cam = FakeCamera("CAM_B")
        mgr.register(cam)
        frames = mgr.grab_all()
        assert frames["CAM_B"] is None

    def test_disconnect_all(self) -> None:
        mgr = CameraManager()
        cam = FakeCamera("CAM_C")
        mgr.register(cam)
        mgr.connect_all()
        mgr.disconnect_all()
        assert cam.is_connected is False

    def test_get_all_statuses(self) -> None:
        mgr = CameraManager()
        cam = FakeCamera("CAM_D")
        mgr.register(cam)
        mgr.connect_all()
        statuses = mgr.get_all_statuses()
        assert statuses["CAM_D"].connected is True

    def test_replace_all_disconnects_old_and_connects_new(self) -> None:
        mgr = CameraManager()
        old_cam = FakeCamera("CAM_OLD")
        new_cam = FakeCamera("CAM_NEW")
        mgr.register(old_cam)
        mgr.connect_all()

        mgr.replace_all([new_cam])

        assert old_cam.is_connected is False
        assert new_cam.is_connected is True
        frames = mgr.grab_all()
        assert set(frames) == {"CAM_NEW"}
