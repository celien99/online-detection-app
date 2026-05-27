"""JSON configuration store with hot-reload support."""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


class ConfigStore:
    """JSON 配置文件的读写与热加载管理。"""

    def __init__(self, config_path: str) -> None:
        self._path = Path(config_path)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._mtime: float = 0.0
        self.reload()

    @property
    def data(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def reload(self) -> bool:
        """若文件有变化则重新加载，返回 True 表示已重载。"""
        try:
            stat = self._path.stat()
        except FileNotFoundError:
            return False
        if stat.st_mtime <= self._mtime:
            return False
        raw = self._path.read_text(encoding="utf-8")
        new_data = json.loads(raw)
        with self._lock:
            self._data = new_data
            self._mtime = stat.st_mtime
        return True

    def get(self, *keys: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for key in keys:
                if isinstance(node, dict):
                    node = node.get(key)
                else:
                    return default
            return node if node is not None else default

    def get_app_config(self) -> Dict[str, Any]:
        return self.get("app", default={})

    def get_camera_configs(self) -> list[Dict[str, Any]]:
        cameras = self.get("cameras", default=[])
        return [c for c in cameras if c.get("enabled", True)]

    def get_plc_config(self) -> Dict[str, Any]:
        return self.get("plc", default={})

    def get_alert_config(self) -> Dict[str, Any]:
        return self.get("alert", default={})

    def get_offline_platform_config(self) -> Dict[str, Any]:
        return self.get("offline_platform", default={})

    def get_storage_config(self) -> Dict[str, Any]:
        return self.get("storage", default={})
