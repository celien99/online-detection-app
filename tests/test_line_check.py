"""Tests for packaged line signal connectivity checks."""
from __future__ import annotations

import json
from pathlib import Path

from app.line_check import check_line_signal, main as line_check_main


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_line_check_connects_virtual_line_signal() -> None:
    result = check_line_signal(
        line_config={"enabled": True, "type": "virtual"},
        plc_config={},
    )

    assert result.status == "OK"
    assert result.connected is True
    assert result.line_status == "running"


def test_line_check_times_out_waiting_for_trigger() -> None:
    result = check_line_signal(
        line_config={"enabled": True, "type": "virtual"},
        plc_config={},
        wait_trigger=True,
        timeout_s=0.001,
        poll_interval_s=0.001,
    )

    assert result.status == "FAIL"
    assert "Timed out" in result.message


def test_line_check_cli_reads_config_and_restores_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    config_path = site_dir / "config.json"
    _write_config(
        config_path,
        {
            "line_signal": {"enabled": True, "type": "virtual"},
            "plc": {"enabled": False},
        },
    )
    monkeypatch.chdir(tmp_path)

    exit_code = line_check_main(["--config", str(config_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert payload["status"] == "OK"
    assert payload["connected"] is True


def test_line_check_cli_fails_for_missing_config(tmp_path: Path, capsys) -> None:
    exit_code = line_check_main(["--config", str(tmp_path / "missing.json")])

    assert exit_code == 2
    assert "Config file not found" in capsys.readouterr().err
