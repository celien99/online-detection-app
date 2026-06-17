"""Runtime config change classification for online settings apply."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


RESTART_REQUIRED_PATHS = {
    "app.inspection_mode",
}

CAMERA_PREFIXES = (
    "cameras",
)

PLC_PREFIXES = (
    "plc",
    "line_signal",
)

TRIGGER_PREFIXES = (
    "app.trigger_poll_interval_s",
    "app.capture_timeout_s",
)

ALERT_PREFIXES = (
    "alert",
)

INSPECTION_PREFIXES = (
    "cameras",
    "offline_platform.upload_base_url",
    "app.station_id",
    "app.mock_runtime_enabled",
)

HOT_RELOAD_PREFIXES = (
    "cameras",
    "offline_platform.hot_reload_enabled",
    "offline_platform.hot_reload_poll_seconds",
)

UI_PREFIXES = (
    "app.line_id",
    "app.grid_layout",
)


@dataclass(slots=True)
class RuntimeConfigChanges:
    """Grouped dirty paths that can be applied to live runtime objects."""

    ui: set[str] = field(default_factory=set)
    cameras: set[str] = field(default_factory=set)
    plc: set[str] = field(default_factory=set)
    trigger: set[str] = field(default_factory=set)
    inspection: set[str] = field(default_factory=set)
    alert: set[str] = field(default_factory=set)
    hot_reload: set[str] = field(default_factory=set)
    restart_required: set[str] = field(default_factory=set)
    ignored: set[str] = field(default_factory=set)

    @property
    def has_runtime_changes(self) -> bool:
        return bool(
            self.ui
            or self.cameras
            or self.plc
            or self.trigger
            or self.inspection
            or self.alert
            or self.hot_reload
        )


@dataclass(slots=True)
class RuntimeConfigApplyResult:
    """Outcome returned by a runtime config apply callback."""

    applied: list[str] = field(default_factory=list)
    restart_required: list[str] = field(default_factory=list)

    def applied_message(self) -> str:
        if not self.applied:
            return ""
        return "Runtime config applied: " + ", ".join(self.applied)

    def restart_message(self) -> str:
        if not self.restart_required:
            return ""
        return "Restart required for: " + ", ".join(self.restart_required)


def classify_runtime_config_changes(paths: Iterable[str]) -> RuntimeConfigChanges:
    changes = RuntimeConfigChanges()
    for path in sorted(set(paths)):
        if path in RESTART_REQUIRED_PATHS:
            changes.restart_required.add(path)
            continue
        matched = False
        if _matches_any(path, UI_PREFIXES):
            changes.ui.add(path)
            matched = True
        if _matches_any(path, CAMERA_PREFIXES):
            changes.cameras.add(path)
            matched = True
        if _matches_any(path, PLC_PREFIXES):
            changes.plc.add(path)
            matched = True
        if _matches_any(path, TRIGGER_PREFIXES):
            changes.trigger.add(path)
            matched = True
        if _matches_any(path, INSPECTION_PREFIXES):
            changes.inspection.add(path)
            matched = True
        if _matches_any(path, ALERT_PREFIXES):
            changes.alert.add(path)
            matched = True
        if _matches_any(path, HOT_RELOAD_PREFIXES):
            changes.hot_reload.add(path)
            matched = True
        if not matched:
            changes.ignored.add(path)
    return changes


def _matches_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}.") for prefix in prefixes)
