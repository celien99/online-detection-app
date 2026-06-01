"""Tests for source and frozen runtime path resolution."""
from __future__ import annotations

import sys
from pathlib import Path

from app.runtime_paths import default_config_path, executable_dir, resolve_config_path


def test_default_config_path_uses_cwd_in_source_runs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEAT_INSPECTION_CONFIG", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert executable_dir() == tmp_path
    assert default_config_path() == tmp_path / "config.json"


def test_default_config_path_uses_frozen_executable_dir(monkeypatch, tmp_path: Path) -> None:
    exe_path = tmp_path / "OnlineDetectionApp.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))
    monkeypatch.delenv("SEAT_INSPECTION_CONFIG", raising=False)

    assert executable_dir() == tmp_path
    assert default_config_path() == tmp_path / "config.json"


def test_env_config_overrides_default(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "site.json"
    monkeypatch.setenv("SEAT_INSPECTION_CONFIG", str(config_path))

    assert resolve_config_path() == config_path
