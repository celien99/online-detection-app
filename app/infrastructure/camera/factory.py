"""Camera construction helpers shared by GUI and production tools."""
from __future__ import annotations

from typing import Any

from app.infrastructure.camera.file_watcher import FileWatcherCamera
from app.infrastructure.camera.interface import CameraInterface
from app.infrastructure.camera.mvs_adapter import MvsCameraAdapter
from app.infrastructure.camera.rtsp_adapter import RTSPCameraAdapter


def create_camera(camera_config: dict[str, Any]) -> CameraInterface:
    camera_id = camera_config["camera_id"]
    source = camera_config.get("source", "")
    cam_type = camera_config.get("type", "mvs")

    if cam_type == "mvs" and source.startswith("mvs://"):
        return MvsCameraAdapter(camera_id, source)
    if cam_type == "rtsp" and (source.startswith("rtsp://") or source.startswith("rtmp://")):
        return RTSPCameraAdapter(camera_id, source)
    if cam_type == "file_watcher":
        watch_dir = camera_config.get("watch_dir", f"./input/{camera_id}")
        pattern = camera_config.get("pattern", "*.jpg")
        return FileWatcherCamera(camera_id, watch_dir, pattern)
    raise ValueError(f"Unsupported camera type or source for {camera_id}: type={cam_type}, source={source}")
