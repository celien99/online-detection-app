"""Runtime path helpers for source and frozen deployments."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def executable_dir() -> Path:
    """Return the directory containing the frozen exe, or the project cwd in source runs."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_config_path() -> Path:
    env_path = os.environ.get("SEAT_INSPECTION_CONFIG")
    if env_path:
        return Path(env_path)
    return executable_dir() / "config.json"


def resolve_config_path(config_path: str | os.PathLike[str] | None = None) -> Path:
    if config_path:
        return Path(config_path)
    return default_config_path()


def chdir_to_config_dir(config_path: Path) -> None:
    """Make relative model/log paths resolve next to the active config file."""
    parent = config_path.resolve().parent
    os.chdir(parent)
