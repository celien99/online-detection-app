"""Seat model CRUD and camera association management."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.config_persistence import ConfigPersistenceService


class SeatModelService:
    """管理座椅型号及其关联的相机配置。"""

    def __init__(self, persistence: ConfigPersistenceService) -> None:
        self._p = persistence

    def list_models(self) -> list[dict]:
        return self._p.list_seat_models()

    def get_model(self, model_id: str) -> dict | None:
        return self._p.get_seat_model(model_id)

    def create_model(self, model_id: str, display_name: str, description: str = "") -> None:
        self._p.create_seat_model(model_id, display_name, description)

    def update_model(self, model_id: str, **kwargs: Any) -> None:
        self._p.update_seat_model(model_id, **kwargs)

    def delete_model(self, model_id: str) -> bool:
        return self._p.delete_seat_model(model_id)

    def set_default(self, model_id: str) -> None:
        self._p.set_default_seat_model(model_id)

    def get_default_model_id(self) -> str | None:
        models = self.list_models()
        for m in models:
            if m.get("is_default"):
                return m["id"]
        return models[0]["id"] if models else None

    def get_cameras(self, model_id: str) -> list[dict]:
        return self._p.list_cameras(seat_model_id=model_id)

    def add_camera(self, model_id: str, camera: dict) -> None:
        camera["seat_model_id"] = model_id
        self._p.create_camera(camera)

    def remove_camera(self, camera_id: str) -> None:
        self._p.delete_camera(camera_id)

    def update_camera(self, camera_id: str, **kwargs: Any) -> None:
        self._p.update_camera(camera_id, **kwargs)

    def get_cameras_as_config_list(self, model_id: str) -> List[Dict[str, Any]]:
        """将 SQLite 中的相机数据转回 seat_defect_core 期望的 config dict 格式。"""
        cameras = self.get_cameras(model_id)
        result: List[Dict[str, Any]] = []
        for cam in cameras:
            entry: Dict[str, Any] = {
                "camera_id": cam["camera_id"],
                "source": cam["source"],
                "type": cam["type"],
                "enabled": bool(cam["enabled"]),
                "patchcore_model_path": cam.get("patchcore_model_path", ""),
                "regions": _decode_regions(cam.get("regions_json")),
                "filter_classifier": {
                    "enabled": bool(cam.get("filter_classifier_enabled", False)),
                    "model_path": cam.get("filter_classifier_path", ""),
                },
            }
            result.append(entry)
        return result


def _decode_regions(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if not isinstance(value, str):
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]
