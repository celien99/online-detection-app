"""Camera manager: lifecycle, health checks, auto-reconnect."""
from __future__ import annotations

import threading
import time
from typing import Any, Dict

from app.runtime_logging import get_runtime_logger
from app.infrastructure.camera.interface import CameraInterface, CameraStatus


class CameraManager:
    """管理所有相机的生命周期、健康检查和自动重连。"""

    def __init__(self) -> None:
        self._cameras: Dict[str, CameraInterface] = {}
        self._lock = threading.RLock()
        self._running = False
        self._watchdog_threads: Dict[str, threading.Thread] = {}
        self._last_heartbeat: Dict[str, float] = {}
        self._watchdog_interval = 5.0
        self._max_heartbeat_gap = 15.0

    def register(self, camera: CameraInterface) -> None:
        with self._lock:
            self._cameras[camera.camera_id] = camera
            self._last_heartbeat[camera.camera_id] = time.time()

    def unregister(self, camera_id: str) -> None:
        with self._lock:
            self._cameras.pop(camera_id, None)
            self._last_heartbeat.pop(camera_id, None)

    def connect_all(self) -> None:
        for camera in list(self._cameras.values()):
            try:
                camera.connect()
                self._last_heartbeat[camera.camera_id] = time.time()
            except Exception:
                get_runtime_logger().exception("Camera connection failed camera_id=%s", camera.camera_id)
                pass

    def disconnect_all(self) -> None:
        self._running = False
        for camera in list(self._cameras.values()):
            try:
                camera.disconnect()
            except Exception:
                pass

    def replace_all(self, cameras: list[CameraInterface]) -> None:
        """Replace managed cameras and connect the new set."""
        was_running = self._running
        self.stop_watchdog()
        self.disconnect_all()
        with self._lock:
            self._cameras.clear()
            self._last_heartbeat.clear()
            self._watchdog_threads.clear()
            for camera in cameras:
                self._cameras[camera.camera_id] = camera
                self._last_heartbeat[camera.camera_id] = time.time()
        self.connect_all()
        if was_running:
            self.start_watchdog()

    def grab_all(self, timeout_ms: int = 1000) -> Dict[str, Any]:
        """从所有已连接相机采集一帧。返回 {camera_id: np.ndarray | None}。"""
        frames: Dict[str, Any] = {}
        with self._lock:
            cameras = list(self._cameras.values())
        for camera in cameras:
            if not camera.is_connected:
                frames[camera.camera_id] = None
                continue
            try:
                frame = camera.grab_frame(timeout_ms=timeout_ms)
                frames[camera.camera_id] = frame
                self._last_heartbeat[camera.camera_id] = time.time()
            except Exception:
                frames[camera.camera_id] = None
        return frames

    def start_watchdog(self) -> None:
        self._running = True
        for camera_id in list(self._cameras.keys()):
            thread = threading.Thread(
                target=self._watchdog_loop,
                args=(camera_id,),
                daemon=True,
                name=f"watchdog-{camera_id}",
            )
            self._watchdog_threads[camera_id] = thread
            thread.start()

    def stop_watchdog(self) -> None:
        self._running = False

    def _watchdog_loop(self, camera_id: str) -> None:
        while self._running:
            time.sleep(self._watchdog_interval)
            with self._lock:
                camera = self._cameras.get(camera_id)
                last = self._last_heartbeat.get(camera_id, 0)
            if camera is None:
                return
            gap = time.time() - last
            if gap > self._max_heartbeat_gap:
                try:
                    camera.disconnect()
                    camera.connect()
                    self._last_heartbeat[camera_id] = time.time()
                except Exception:
                    pass

    def get_all_statuses(self) -> Dict[str, CameraStatus]:
        with self._lock:
            return {cid: cam.get_status() for cid, cam in self._cameras.items()}
