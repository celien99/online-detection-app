"""Collect a single field troubleshooting report for a deployed site."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import mvs_list
from app.camera_check import check_camera
from app.infrastructure.config_store import ConfigStore
from app.line_check import check_line_signal
from app.runtime_paths import chdir_to_config_dir, resolve_config_path
from app.services.diagnostics import ProductionDiagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect diagnostics, PLC/line signal, MVS, and camera checks into one JSON report."
    )
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--output", default="site_report.json", help="Output JSON report path")
    parser.add_argument("--camera-samples-dir", default="camera_samples", help="Directory for camera sample images")
    parser.add_argument("--camera-frames", type=int, default=1, help="Number of frames to grab per camera")
    parser.add_argument("--camera-timeout-ms", type=int, default=2000, help="Per-frame grab timeout")
    parser.add_argument("--skip-camera-check", action="store_true", help="Do not connect to configured cameras")
    parser.add_argument(
        "--camera-connect-only",
        action="store_true",
        help="Only connect cameras; do not wait for frames",
    )
    parser.add_argument("--skip-mvs-list", action="store_true", help="Do not enumerate Hikrobot MVS cameras")
    parser.add_argument("--wait-trigger", action="store_true", help="Wait for one line capture request")
    parser.add_argument("--line-timeout-s", type=float, default=5.0, help="Timeout when waiting for a line trigger")
    parser.add_argument("--line-poll-interval-s", type=float, default=0.05, help="Line trigger polling interval")
    parser.add_argument(
        "--send-test-result",
        choices=["OK", "NG", "REJECT"],
        default="",
        help="Send one test line result while collecting the report",
    )
    parser.add_argument("--defect-code", type=int, default=9001, help="Defect code used with --send-test-result")
    parser.add_argument("--json", action="store_true", help="Also print machine-readable JSON")
    args = parser.parse_args(argv)

    config_path = resolve_config_path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    original_cwd = Path.cwd()
    chdir_to_config_dir(config_path)
    try:
        resolved_config_path = config_path.resolve()
        config = ConfigStore(str(resolved_config_path))
        report = collect_site_report(
            config=config,
            config_path=resolved_config_path,
            camera_samples_dir=Path(args.camera_samples_dir),
            camera_frames=max(1, args.camera_frames),
            camera_timeout_ms=max(1, args.camera_timeout_ms),
            skip_camera_check=args.skip_camera_check,
            camera_connect_only=args.camera_connect_only,
            skip_mvs_list=args.skip_mvs_list,
            wait_trigger=args.wait_trigger,
            line_timeout_s=max(0.0, args.line_timeout_s),
            line_poll_interval_s=max(0.001, args.line_poll_interval_s),
            send_test_result=args.send_test_result,
            defect_code=max(0, args.defect_code),
        )
        output_path = _resolve_output_path(Path(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        os.chdir(original_cwd)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_summary(report, output_path))
    return 1 if report["status"] == "FAIL" else 0


def collect_site_report(
    *,
    config: ConfigStore,
    config_path: Path,
    camera_samples_dir: Path,
    camera_frames: int = 1,
    camera_timeout_ms: int = 2000,
    skip_camera_check: bool = False,
    camera_connect_only: bool = False,
    skip_mvs_list: bool = False,
    wait_trigger: bool = False,
    line_timeout_s: float = 5.0,
    line_poll_interval_s: float = 0.05,
    send_test_result: str = "",
    defect_code: int = 9001,
) -> dict[str, Any]:
    diagnostics = ProductionDiagnostics(config, config_path).run().to_dict()
    line_signal = asdict(
        check_line_signal(
            line_config=config.get("line_signal", default={}),
            plc_config=config.get_plc_config(),
            wait_trigger=wait_trigger,
            timeout_s=line_timeout_s,
            poll_interval_s=line_poll_interval_s,
            send_test_result=send_test_result,
            defect_code=defect_code,
        )
    )
    mvs_devices = _collect_mvs_devices(skip=skip_mvs_list)
    camera_items = _collect_camera_checks(
        config=config,
        samples_dir=camera_samples_dir,
        frames=camera_frames,
        timeout_ms=camera_timeout_ms,
        skip=skip_camera_check,
        connect_only=camera_connect_only,
    )
    statuses = [diagnostics["status"], line_signal["status"], mvs_devices["status"]]
    statuses.extend(item["status"] for item in camera_items["items"])
    return {
        "status": _overall_status(statuses),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "config_path": str(config_path),
        "runtime": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(Path.cwd()),
        },
        "diagnostics": diagnostics,
        "line_signal": line_signal,
        "mvs_devices": mvs_devices,
        "camera_check": camera_items,
    }


def _collect_mvs_devices(*, skip: bool) -> dict[str, Any]:
    candidates = mvs_list.describe_mvs_sdk_candidates(mvs_list._local_sdk_dll())
    if skip:
        return {"status": "SKIP", "message": "MVS device listing skipped", "sdk_candidates": candidates, "devices": []}
    try:
        devices = mvs_list.list_mvs_devices()
    except Exception as exc:
        return {"status": "FAIL", "message": str(exc), "sdk_candidates": candidates, "devices": []}
    return {
        "status": "OK",
        "message": f"Found {len(devices)} MVS camera(s)",
        "sdk_candidates": candidates,
        "devices": [asdict(device) | {"suggested_source": mvs_list._suggest_source(device)} for device in devices],
    }


def _collect_camera_checks(
    *,
    config: ConfigStore,
    samples_dir: Path,
    frames: int,
    timeout_ms: int,
    skip: bool,
    connect_only: bool,
) -> dict[str, Any]:
    camera_configs = config.get_camera_configs()
    if skip:
        return {"status": "SKIP", "message": "Camera check skipped", "items": []}
    if not camera_configs:
        return {
            "status": "FAIL",
            "message": "No enabled cameras in config",
            "items": [{"camera_id": "<none>", "status": "FAIL", "message": "No enabled cameras in config"}],
        }
    items = [
        asdict(
            check_camera(
                cam,
                frames=frames,
                timeout_ms=timeout_ms,
                save_dir=samples_dir,
                connect_only=connect_only,
            )
        )
        for cam in camera_configs
    ]
    return {
        "status": _overall_status([item["status"] for item in items]),
        "message": f"Checked {len(items)} camera(s)",
        "items": items,
    }


def _overall_status(statuses: list[str]) -> str:
    normalized = {status for status in statuses if status and status != "SKIP"}
    if "FAIL" in normalized:
        return "FAIL"
    if "WARN" in normalized:
        return "WARN"
    return "OK"


def _resolve_output_path(path: Path) -> Path:
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def _format_summary(report: dict[str, Any], output_path: Path) -> str:
    camera_items = report["camera_check"]["items"]
    ok_cameras = sum(1 for item in camera_items if item.get("status") == "OK")
    lines = [
        f"Site report: {report['status']}",
        f"Report: {output_path}",
        f"Diagnostics: {report['diagnostics']['status']}",
        f"Line signal: {report['line_signal']['status']} ({report['line_signal']['message']})",
        f"MVS devices: {report['mvs_devices']['status']} ({report['mvs_devices']['message']})",
        f"Cameras: {report['camera_check']['status']} ({ok_cameras}/{len(camera_items)} OK)",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
