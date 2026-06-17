"""ViewModel for SettingsScreen: read/write config via ConfigStore + persistence."""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.infrastructure.config_store import ConfigStore
from app.services.config_persistence import ConfigPersistenceService


class SettingsViewModel(QObject):
    """设置页 ViewModel。QML 侧通过 getValue/setValue/save 完成配置编辑。"""

    configChanged = Signal()
    reloaded = Signal()
    valueChanged = Signal(str)
    saved = Signal()
    saveFailed = Signal(str)
    importSucceeded = Signal()
    importFailed = Signal(str)

    def __init__(self, config_store: ConfigStore, persistence: ConfigPersistenceService) -> None:
        super().__init__()
        self._store = config_store
        self._persistence = persistence
        self._dirty_paths: set = set()

    def _get_data(self) -> dict:
        return self._store.data

    def _get_is_dirty(self) -> bool:
        return self._store.is_dirty

    data = Property(dict, _get_data, notify=configChanged)
    isDirty = Property(bool, _get_is_dirty, notify=configChanged)

    @Slot(str, result=str)
    def getValue(self, path: str) -> str:
        return self._store.get_value_by_path(path)

    @Slot(str, str)
    def setValue(self, path: str, value: str) -> None:
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = value
        self._store.set(path, parsed)
        self._dirty_paths.add(path)
        self.valueChanged.emit(path)
        self.configChanged.emit()

    @Slot()
    def save(self) -> None:
        try:
            self._store.save()
            self._dirty_paths.clear()
            self.saved.emit()
            self.configChanged.emit()
        except Exception as exc:
            self.saveFailed.emit(str(exc))

    @Slot()
    def reload(self) -> None:
        if self._store.reload():
            self._dirty_paths.clear()
            self.reloaded.emit()
            self.configChanged.emit()

    @Slot(str)
    def importConfig(self, file_path: str) -> None:
        try:
            self._persistence.import_from_json(file_path)
            self._store.reload()
            self._dirty_paths.clear()
            self.importSucceeded.emit()
            self.configChanged.emit()
        except Exception as exc:
            self.importFailed.emit(str(exc))

    @Slot(str)
    def exportConfig(self, file_path: str) -> None:
        self._store.save()
        self._persistence.export_to_json(file_path)

    @Slot(str)
    def resetToDefault(self, path: str) -> None:
        example_path = "config.example.json"
        try:
            with open(example_path, encoding="utf-8") as f:
                defaults = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        node = defaults
        for key in path.split("."):
            if isinstance(node, dict):
                node = node.get(key, "")
            else:
                return
        self.setValue(path, json.dumps(node, ensure_ascii=False) if not isinstance(node, str) else node)
