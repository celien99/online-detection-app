"""Generate a site-specific production config from the deployment template."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.runtime_paths import executable_dir


DEFAULT_TEMPLATE = "config.production.example.json"
DEFAULT_OUTPUT = "config.json"
DEFAULT_POINT_MAP = {
    "capture_request_coil": 10,
    "capture_ack_coil": 11,
    "busy_coil": 12,
    "done_coil": 13,
    "ok_coil": 14,
    "ng_coil": 15,
    "reject_coil": 16,
    "fault_coil": 17,
    "line_status_register": 0,
    "part_id_register": 20,
    "seat_model_register": 40,
    "defect_code_register": 60,
    "fault_code_register": 61,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a production config.json for a Hikrobot MVS camera and Modbus PLC site."
    )
    parser.add_argument("--template", default=None, help="Template JSON path")
    parser.add_argument("--output", default=None, help="Output config path")
    parser.add_argument("--camera-sn", action="append", default=[], help="Camera serial number; repeat for multiple cameras")
    parser.add_argument("--camera-id", action="append", default=[], help="Camera ID; repeat to match --camera-sn")
    parser.add_argument("--camera-source", action="append", default=[], help="Full camera source; overrides generated MVS source")
    parser.add_argument("--plc-host", default="", help="PLC Modbus TCP host")
    parser.add_argument("--plc-port", type=int, default=None, help="PLC Modbus TCP port")
    parser.add_argument("--line-id", default="", help="Production line ID")
    parser.add_argument("--station-id", default="", help="Station ID")
    parser.add_argument("--trigger-source", default="Line0", help="MVS hardware trigger input source")
    parser.add_argument("--trigger-activation", default="rising_edge", help="MVS hardware trigger activation")
    parser.add_argument("--timeout-ms", type=int, default=2000, help="MVS frame grab timeout")
    parser.add_argument("--exposure-time", type=float, default=6000.0, help="MVS exposure time in microseconds")
    parser.add_argument("--gain", type=float, default=8.0, help="MVS gain")
    parser.add_argument("--pixel-format", default="bgr8", help="MVS pixel format")
    parser.add_argument("--point", action="append", default=[], help="Override PLC point, for example ok_coil=14")
    parser.add_argument("--force", action="store_true", help="Overwrite output config if it already exists")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    args = parser.parse_args(argv)

    template_path = _resolve_path(args.template or DEFAULT_TEMPLATE)
    output_path = _resolve_path(args.output or DEFAULT_OUTPUT)
    if not template_path.exists():
        print(f"Template file not found: {template_path}", file=sys.stderr)
        return 2
    if output_path.exists() and not args.force:
        print(f"Output already exists, use --force to overwrite: {output_path}", file=sys.stderr)
        return 3

    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
        point_overrides = _parse_point_overrides(args.point)
        config = build_production_config(
            template,
            camera_serials=args.camera_sn,
            camera_ids=args.camera_id,
            camera_sources=args.camera_source,
            plc_host=args.plc_host,
            plc_port=args.plc_port,
            line_id=args.line_id,
            station_id=args.station_id,
            trigger_source=args.trigger_source,
            trigger_activation=args.trigger_activation,
            timeout_ms=max(1, args.timeout_ms),
            exposure_time=args.exposure_time,
            gain=args.gain,
            pixel_format=args.pixel_format,
            point_overrides=point_overrides,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "status": "OK",
        "output": str(output_path),
        "camera_count": len(config.get("cameras", [])),
        "plc_host": config.get("line_signal", {}).get("host", ""),
        "plc_port": config.get("line_signal", {}).get("port", 0),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(_format_summary(summary, config))
    return 0


def build_production_config(
    template: dict[str, Any],
    *,
    camera_serials: list[str],
    camera_ids: list[str],
    camera_sources: list[str],
    plc_host: str,
    plc_port: int | None,
    line_id: str,
    station_id: str,
    trigger_source: str,
    trigger_activation: str,
    timeout_ms: int,
    exposure_time: float,
    gain: float,
    pixel_format: str,
    point_overrides: dict[str, int] | None = None,
) -> dict[str, Any]:
    config = copy.deepcopy(template)
    _apply_app_config(config, line_id=line_id, station_id=station_id)
    _apply_line_signal_config(
        config,
        plc_host=plc_host,
        plc_port=plc_port,
        point_overrides=point_overrides or {},
    )
    _apply_camera_config(
        config,
        camera_serials=camera_serials,
        camera_ids=camera_ids,
        camera_sources=camera_sources,
        trigger_source=trigger_source,
        trigger_activation=trigger_activation,
        timeout_ms=timeout_ms,
        exposure_time=exposure_time,
        gain=gain,
        pixel_format=pixel_format,
    )
    return config


def _apply_app_config(config: dict[str, Any], *, line_id: str, station_id: str) -> None:
    app = config.setdefault("app", {})
    app["inspection_mode"] = "triggered"
    if line_id:
        app["line_id"] = line_id
    if station_id:
        app["station_id"] = station_id


def _apply_line_signal_config(
    config: dict[str, Any],
    *,
    plc_host: str,
    plc_port: int | None,
    point_overrides: dict[str, int],
) -> None:
    line_signal = config.setdefault("line_signal", {})
    line_signal["enabled"] = True
    line_signal["type"] = "modbus"
    if plc_host:
        line_signal["host"] = plc_host
    if plc_port is not None:
        line_signal["port"] = plc_port
    for key, value in DEFAULT_POINT_MAP.items():
        line_signal.setdefault(key, value)
    for key, value in point_overrides.items():
        if key not in DEFAULT_POINT_MAP:
            raise ValueError(f"Unsupported PLC point name: {key}")
        line_signal[key] = value


def _apply_camera_config(
    config: dict[str, Any],
    *,
    camera_serials: list[str],
    camera_ids: list[str],
    camera_sources: list[str],
    trigger_source: str,
    trigger_activation: str,
    timeout_ms: int,
    exposure_time: float,
    gain: float,
    pixel_format: str,
) -> None:
    cameras = config.get("cameras", [])
    if not cameras:
        raise ValueError("Template must contain at least one camera")
    requested_count = max(len(camera_serials), len(camera_sources), len(camera_ids), 1)
    base_camera = copy.deepcopy(cameras[0])
    normalized_cameras = []
    for index in range(requested_count):
        camera = copy.deepcopy(cameras[index] if index < len(cameras) else base_camera)
        camera_id = _indexed(camera_ids, index) or camera.get("camera_id") or f"CAM_{index + 1}"
        serial = _indexed(camera_serials, index)
        explicit_source = _indexed(camera_sources, index)
        camera["camera_id"] = camera_id
        camera["type"] = "mvs"
        camera["enabled"] = True
        camera["source"] = explicit_source or _build_mvs_source(
            serial=serial,
            trigger_source=trigger_source,
            trigger_activation=trigger_activation,
            timeout_ms=timeout_ms,
            exposure_time=exposure_time,
            gain=gain,
            pixel_format=pixel_format,
        )
        normalized_cameras.append(camera)
    config["cameras"] = normalized_cameras


def _build_mvs_source(
    *,
    serial: str,
    trigger_source: str,
    trigger_activation: str,
    timeout_ms: int,
    exposure_time: float,
    gain: float,
    pixel_format: str,
) -> str:
    if not serial:
        raise ValueError("Either --camera-sn or --camera-source is required for each generated camera")
    query = urlencode(
        {
            "trigger": "hardware",
            "trigger_source": trigger_source,
            "trigger_activation": trigger_activation,
            "timeout_ms": timeout_ms,
            "exposure_time": _format_number(exposure_time),
            "gain": _format_number(gain),
            "pixel_format": pixel_format,
        }
    )
    return f"mvs://sn/{serial}?{query}"


def _parse_point_overrides(values: list[str]) -> dict[str, int]:
    overrides: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --point value '{value}', expected name=value")
        key, raw_int = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --point value '{value}', missing name")
        try:
            overrides[key] = int(raw_int)
        except ValueError as exc:
            raise ValueError(f"Invalid integer for --point {key}: {raw_int}") from exc
    return overrides


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else executable_dir() / candidate


def _indexed(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index].strip()


def _format_number(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def _format_summary(summary: dict[str, Any], config: dict[str, Any]) -> str:
    lines = [
        "Production config generated:",
        f"  output={summary['output']}",
        f"  cameras={summary['camera_count']}",
        f"  plc={summary['plc_host']}:{summary['plc_port']}",
    ]
    for camera in config.get("cameras", []):
        lines.append(f"  camera {camera.get('camera_id', '')}: {camera.get('source', '')}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
