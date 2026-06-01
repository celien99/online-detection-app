"""Tests for packaged line signal connectivity checks."""
from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.line_signal import InspectionDecision
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


def test_line_check_sends_virtual_test_result(monkeypatch) -> None:
    adapters = []

    class CapturingVirtualAdapter:
        enabled = True

        def __init__(self) -> None:
            from app.infrastructure.line_signal import VirtualLineSignalAdapter

            self._inner = VirtualLineSignalAdapter()
            adapters.append(self._inner)

        @property
        def connected(self):
            return self._inner.connected

        def connect(self):
            self._inner.connect()

        def disconnect(self):
            self._inner.disconnect()

        def poll_capture_request(self):
            return self._inner.poll_capture_request()

        def send_busy(self, request, busy):
            self._inner.send_busy(request, busy)

        def send_result(self, result):
            self._inner.send_result(result)

        def send_fault(self, request, code, message):
            self._inner.send_fault(request, code, message)

        def read_line_status(self):
            return self._inner.read_line_status()

    monkeypatch.setattr("app.line_check.create_line_signal", lambda line_config, plc_config: CapturingVirtualAdapter())

    result = check_line_signal(
        line_config={"enabled": True, "type": "virtual"},
        plc_config={},
        send_test_result="NG",
        defect_code=42,
    )

    assert result.status == "OK"
    assert result.test_result_sent == "NG"
    assert result.defect_code == 42
    assert adapters[0].last_result is not None
    assert adapters[0].last_result.status == InspectionDecision.NG
    assert adapters[0].last_result.defect_code == 42


def test_line_check_fails_when_test_result_disconnects_adapter(monkeypatch) -> None:
    class DisconnectingAdapter:
        enabled = True

        def __init__(self) -> None:
            self._connected = False

        @property
        def connected(self):
            return self._connected

        def connect(self):
            self._connected = True

        def disconnect(self):
            self._connected = False

        def poll_capture_request(self):
            return None

        def send_busy(self, request, busy):
            pass

        def send_result(self, result):
            self._connected = False

        def send_fault(self, request, code, message):
            pass

        def read_line_status(self):
            from app.infrastructure.plc.interface import LineStatus

            return LineStatus.RUNNING

    monkeypatch.setattr("app.line_check.create_line_signal", lambda line_config, plc_config: DisconnectingAdapter())

    result = check_line_signal(
        line_config={"enabled": True, "type": "modbus"},
        plc_config={},
        send_test_result="NG",
        defect_code=42,
    )

    assert result.status == "FAIL"
    assert result.connected is False
    assert result.test_result_sent == "NG"
    assert "adapter disconnected" in result.message


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


def test_line_check_cli_sends_test_result(tmp_path: Path, monkeypatch, capsys) -> None:
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

    exit_code = line_check_main(
        [
            "--config",
            str(config_path),
            "--send-test-result",
            "REJECT",
            "--defect-code",
            "77",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert payload["status"] == "OK"
    assert payload["test_result_sent"] == "REJECT"
    assert payload["defect_code"] == 77


def test_line_check_cli_fails_for_missing_config(tmp_path: Path, capsys) -> None:
    exit_code = line_check_main(["--config", str(tmp_path / "missing.json")])

    assert exit_code == 2
    assert "Config file not found" in capsys.readouterr().err
