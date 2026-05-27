"""ViewModel for SettingsScreen: read/edit config via ConfigStore."""
from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.infrastructure.config_store import ConfigStore


class SettingsViewModel(QObject):
    """设置页 ViewModel。QML 侧通过 getValue/setValue 读写配置。"""

    configChanged = Signal()
    reloaded = Signal()

    def __init__(self, config_store: ConfigStore) -> None:
        super().__init__()
        self._store = config_store
        self._data = config_store.data

    def _get_data(self) -> dict:
        return self._data

    data = Property(dict, _get_data, notify=configChanged)

    @Slot(str, result=str)
    def getValue(self, path: str) -> str:
        """按点号分隔的路径读取值，如 'app.line_id'。"""
        node: Any = self._data
        for key in path.split("."):
            if isinstance(node, dict):
                node = node.get(key, "")
            else:
                return ""
        return json.dumps(node, ensure_ascii=False) if not isinstance(node, str) else node

    @Slot()
    def reload(self) -> None:
        if self._store.reload():
            self._data = self._store.data
            self.reloaded.emit()
            self.configChanged.emit()
