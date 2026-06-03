"""Tests for GUI entry-point CLI parsing."""
from __future__ import annotations

from app.main import _parse_args


def test_main_cli_parses_config_and_dev_without_passing_to_qt() -> None:
    args = _parse_args(["--config", "site.json", "--dev", "--platform", "offscreen"])

    assert args.config == "site.json"
    assert args.dev is True
    assert args.qt_args == ["--platform", "offscreen"]
