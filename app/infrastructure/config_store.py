"""JSON configuration store with hot-reload and write-back support."""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigStore:
    """JSON 配置文件的读写与热加载管理。"""

    def __init__(self, config_path: str) -> None:
        self._path = Path(config_path)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._mtime: float = 0.0
        self._persistence: Any = None  # ConfigPersistenceService, set later
        self._dirty: Dict[str, str] = {}
        self.reload()

    @property
    def data(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def set_persistence(self, svc: Any) -> None:
        self._persistence = svc

    def reload(self) -> bool:
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

    def set(self, path: str, value: Any) -> None:
        """在内存中设置值并标记 dirty（支持列表下标如 cameras.0.patchcore_model_path）。"""
        with self._lock:
            parts = path.split(".")
            node = self._data
            for part in parts[:-1]:
                if isinstance(node, dict):
                    if part not in node or not isinstance(node[part], (dict, list)):
                        node[part] = {}
                    node = node[part]
                elif isinstance(node, (list, tuple)):
                    try:
                        idx = int(part)
                        if 0 <= idx < len(node):
                            node = node[idx]
                        else:
                            return
                    except (ValueError, IndexError):
                        return
                else:
                    return
            last = parts[-1]
            if isinstance(node, dict):
                node[last] = value
            elif isinstance(node, (list, tuple)):
                try:
                    idx = int(last)
                    if 0 <= idx < len(node):
                        node[idx] = value
                    else:
                        return
                except (ValueError, IndexError):
                    return
            else:
                return
        self._dirty[path] = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

    def save(self) -> bool:
        """将内存中的配置持久化到 JSON 文件和 SQLite。"""
        with self._lock:
            data_copy = deepcopy(self._data)
        tmp_path = str(self._path) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data_copy, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(self._path))
        self._mtime = os.path.getmtime(str(self._path))
        if self._persistence is not None:
            for path, value in self._dirty.items():
                self._persistence.set(path, value)
        self._dirty.clear()
        return True

    @property
    def is_dirty(self) -> bool:
        return len(self._dirty) > 0

    def get_dirty_keys(self) -> list:
        return list(self._dirty.keys())

    def get_value_by_path(self, path: str) -> str:
        """按点号路径读取，返回 JSON 字符串（支持列表下标如 cameras.0.patchcore_model_path）。"""
        import json as _json
        with self._lock:
            node: Any = self._data
            for key in path.split("."):
                if isinstance(node, dict):
                    if key not in node:
                        return ""
                    node = node[key]
                elif isinstance(node, (list, tuple)):
                    try:
                        idx = int(key)
                        if 0 <= idx < len(node):
                            node = node[idx]
                        else:
                            return ""
                    except (ValueError, IndexError):
                        return ""
                else:
                    return ""
        return _json.dumps(node, ensure_ascii=False) if not isinstance(node, str) else node

    # ── Convenience accessors ──

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
