"""Command line production line signal connectivity check."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.infrastructure.line_signal_factory import create_line_signal
from app.runtime_paths import chdir_to_config_dir, resolve_config_path


@dataclass(slots=True)
class LineCheckResult:
    status: str
    message: str
    adapter_type: str
    connected: bool
    line_status: str = "unknown"
    request_id: str = ""
    part_id: str = ""
    seat_model_id: str = ""
    elapsed_ms: int = 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check PLC or line-trigger connectivity without starting the GUI.")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--wait-trigger", action="store_true", help="Wait for one capture request")
    parser.add_argument("--timeout-s", type=float, default=5.0, help="Timeout when waiting for a trigger")
    parser.add_argument("--poll-interval-s", type=float, default=0.05, help="Polling interval while waiting for a trigger")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    config_path = resolve_config_path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    original_cwd = Path.cwd()
    chdir_to_config_dir(config_path)
    try:
        config = ConfigStore(str(config_path.resolve()))
        result = check_line_signal(
            line_config=config.get("line_signal", default={}),
            plc_config=config.get_plc_config(),
            wait_trigger=args.wait_trigger,
            timeout_s=max(0.0, args.timeout_s),
            poll_interval_s=max(0.001, args.poll_interval_s),
        )
    finally:
        os.chdir(original_cwd)

    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(_format_result(result))
    return 1 if result.status == "FAIL" else 0


def check_line_signal(
    *,
    line_config: dict,
    plc_config: dict,
    wait_trigger: bool = False,
    timeout_s: float = 5.0,
    poll_interval_s: float = 0.05,
) -> LineCheckResult:
    started = time.time()
    adapter_type = str(line_config.get("type", "virtual" if not line_config.get("enabled", False) else "modbus"))
    adapter = None
    try:
        adapter = create_line_signal(line_config, plc_config)
        adapter.connect()
        line_status = adapter.read_line_status().value
        if not adapter.connected:
            return LineCheckResult(
                status="FAIL",
                message="Line signal adapter did not connect",
                adapter_type=adapter_type,
                connected=False,
                line_status=line_status,
                elapsed_ms=_elapsed_ms(started),
            )
        if not wait_trigger:
            return LineCheckResult(
                status="OK",
                message="Line signal adapter connected",
                adapter_type=adapter_type,
                connected=True,
                line_status=line_status,
                elapsed_ms=_elapsed_ms(started),
            )
        deadline = time.time() + timeout_s
        request = None
        while time.time() <= deadline:
            request = adapter.poll_capture_request()
            if request is not None:
                break
            time.sleep(poll_interval_s)
        if request is None:
            return LineCheckResult(
                status="FAIL",
                message="Timed out waiting for capture request",
                adapter_type=adapter_type,
                connected=adapter.connected,
                line_status=line_status,
                elapsed_ms=_elapsed_ms(started),
            )
        return LineCheckResult(
            status="OK",
            message="Received capture request",
            adapter_type=adapter_type,
            connected=adapter.connected,
            line_status=line_status,
            request_id=request.request_id,
            part_id=request.part_id,
            seat_model_id=request.seat_model_id or "",
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:
        return LineCheckResult(
            status="FAIL",
            message=str(exc),
            adapter_type=adapter_type,
            connected=False,
            elapsed_ms=_elapsed_ms(started),
        )
    finally:
        if adapter is not None:
            try:
                adapter.disconnect()
            except Exception:
                pass


def _elapsed_ms(started: float) -> int:
    return int((time.time() - started) * 1000)


def _format_result(result: LineCheckResult) -> str:
    fields = [
        f"[{result.status}] {result.message}",
        f"adapter={result.adapter_type}",
        f"connected={result.connected}",
        f"line_status={result.line_status}",
    ]
    if result.request_id:
        fields.append(f"request_id={result.request_id}")
        fields.append(f"part_id={result.part_id}")
        fields.append(f"seat_model_id={result.seat_model_id}")
    fields.append(f"elapsed_ms={result.elapsed_ms}")
    return "Line signal check: " + " ".join(fields)


if __name__ == "__main__":
    raise SystemExit(main())
