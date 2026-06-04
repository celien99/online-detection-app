"""Runtime mode normalization shared by GUI startup and diagnostics."""
from __future__ import annotations

from typing import Any


TRIGGERED_MODE = "triggered"
CONTINUOUS_MODE = "continuous"

_TRIGGERED_ALIASES = {
    "trigger",
    "triggered",
    "line_trigger",
    "line_triggered",
    "manual_trigger",
}
_CONTINUOUS_ALIASES = {
    "continuous",
    "stream",
    "streaming",
}


def normalize_inspection_mode(value: Any, default: str = CONTINUOUS_MODE) -> str:
    """Return the canonical inspection mode used internally by the app."""
    mode = str(value or default).strip().lower().replace("-", "_")
    if not mode:
        return default
    if mode in _TRIGGERED_ALIASES:
        return TRIGGERED_MODE
    if mode in _CONTINUOUS_ALIASES:
        return CONTINUOUS_MODE
    return mode


def is_triggered_mode(value: Any) -> bool:
    return normalize_inspection_mode(value) == TRIGGERED_MODE
