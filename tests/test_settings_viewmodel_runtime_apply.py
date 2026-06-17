from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.services.config_persistence import ConfigPersistenceService
from app.services.runtime_config_apply import RuntimeConfigApplyResult
from app.viewmodels.settings_viewmodel import SettingsViewModel


def test_settings_save_applies_runtime_config_after_persist(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    db_path = tmp_path / "config.db"
    config_path.write_text(
        json.dumps({"app": {"line_id": "A"}, "plc": {"enabled": False}}),
        encoding="utf-8",
    )
    store = ConfigStore(str(config_path))
    persistence = ConfigPersistenceService(str(db_path))
    store.set_persistence(persistence)
    applied_paths: list[set[str]] = []

    def apply_runtime_config(paths: set[str]) -> RuntimeConfigApplyResult:
        applied_paths.append(paths)
        return RuntimeConfigApplyResult(applied=["ui"])

    vm = SettingsViewModel(store, persistence, apply_runtime_config)
    vm.setValue("app.line_id", '"B"')
    vm.save()

    assert applied_paths == [{"app.line_id"}]
    assert store.is_dirty is False
    assert json.loads(config_path.read_text(encoding="utf-8"))["app"]["line_id"] == "B"
