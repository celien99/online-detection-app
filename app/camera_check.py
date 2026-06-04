"""Command line camera connectivity and frame-grab check."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import cv2
import numpy as np

from app.infrastructure.camera.factory import create_camera
from app.infrastructure.config_store import ConfigStore
from app.runtime_paths import chdir_to_config_dir, resolve_config_path


@dataclass(slots=True)
class CameraCheckItem:
    camera_id: str
    status: str
    message: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frames_grabbed: int = 0
    elapsed_ms: int = 0
    sample_path: str = ""
    mean: float = 0.0
    std: float = 0.0
    min_value: int = 0
    max_value: int = 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check configured cameras without starting the GUI or ML pipeline.")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--camera-id", default="", help="Only check one configured camera")
    parser.add_argument("--frames", type=int, default=1, help="Number of frames to grab per camera")
    parser.add_argument("--timeout-ms", type=int, default=2000, help="Per-frame grab timeout")
    parser.add_argument("--save-dir", default="", help="Directory for saving the last grabbed frame per camera")
    parser.add_argument(
        "--mvs-trigger-mode",
        choices=["config", "continuous", "software", "hardware"],
        default="config",
        help="Override MVS trigger mode for this check without editing config.json",
    )
    parser.add_argument(
        "--connect-only",
        action="store_true",
        help="Only connect and read camera status; useful for hardware-triggered cameras without a PLC pulse",
    )
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
        camera_configs = config.get_camera_configs()
        if args.camera_id:
            camera_configs = [cam for cam in camera_configs if cam.get("camera_id") == args.camera_id]
        if not camera_configs:
            items = [CameraCheckItem(args.camera_id or "<none>", "FAIL", "No matching enabled cameras in config")]
        else:
            items = [
                check_camera(
                    cam,
                    frames=max(1, args.frames),
                    timeout_ms=max(1, args.timeout_ms),
                    save_dir=Path(args.save_dir) if args.save_dir else None,
                    connect_only=args.connect_only,
                    mvs_trigger_mode=args.mvs_trigger_mode,
                )
                for cam in camera_configs
            ]
    finally:
        os.chdir(original_cwd)

    if args.json:
        print(json.dumps({"items": [asdict(item) for item in items]}, ensure_ascii=False, indent=2))
    else:
        print(_format_items(items))
    return 1 if any(item.status == "FAIL" for item in items) else 0


def check_camera(
    camera_config: dict[str, Any],
    *,
    frames: int = 1,
    timeout_ms: int = 2000,
    save_dir: Path | None = None,
    connect_only: bool = False,
    mvs_trigger_mode: str = "config",
) -> CameraCheckItem:
    camera_config = _with_mvs_trigger_mode(camera_config, mvs_trigger_mode)
    camera_id = str(camera_config.get("camera_id", "<unknown>"))
    started = time.time()
    camera = None
    frames_grabbed = 0
    last_frame = None
    try:
        camera = create_camera(camera_config)
        camera.connect()
        if connect_only:
            status = camera.get_status()
            return CameraCheckItem(
                camera_id=camera_id,
                status="OK" if status.connected else "FAIL",
                message="Camera connected; frame grab skipped" if status.connected else "Camera did not report connected",
                width=status.width,
                height=status.height,
                fps=status.fps,
                frames_grabbed=0,
                elapsed_ms=int((time.time() - started) * 1000),
            )
        for _ in range(frames):
            frame = camera.grab_frame(timeout_ms=timeout_ms)
            if frame is not None:
                frames_grabbed += 1
                last_frame = frame
        status = camera.get_status()
        elapsed_ms = int((time.time() - started) * 1000)
        if frames_grabbed <= 0:
            return CameraCheckItem(
                camera_id=camera_id,
                status="FAIL",
                message=_no_frame_message(camera_config),
                width=status.width,
                height=status.height,
                fps=status.fps,
                frames_grabbed=frames_grabbed,
                elapsed_ms=elapsed_ms,
            )
        stats = _frame_stats(last_frame)
        sample_path = _save_sample(camera_id, last_frame, save_dir) if save_dir is not None else ""
        return CameraCheckItem(
            camera_id=camera_id,
            status="OK",
            message="Camera connected and frame grab succeeded",
            width=status.width,
            height=status.height,
            fps=status.fps,
            frames_grabbed=frames_grabbed,
            elapsed_ms=elapsed_ms,
            sample_path=sample_path,
            mean=stats["mean"],
            std=stats["std"],
            min_value=stats["min_value"],
            max_value=stats["max_value"],
        )
    except Exception as exc:
        return CameraCheckItem(
            camera_id=camera_id,
            status="FAIL",
            message=str(exc),
            frames_grabbed=frames_grabbed,
            elapsed_ms=int((time.time() - started) * 1000),
        )
    finally:
        if camera is not None:
            try:
                camera.disconnect()
            except Exception:
                pass


def _format_items(items: list[CameraCheckItem]) -> str:
    lines = ["Camera check:"]
    for item in items:
        lines.append(
            f"[{item.status}] {item.camera_id}: {item.message} "
            f"frames={item.frames_grabbed} size={item.width}x{item.height} fps={item.fps:.2f} "
            f"mean={item.mean:.2f} std={item.std:.2f} min={item.min_value} max={item.max_value} "
            f"sample={item.sample_path or '-'} elapsed_ms={item.elapsed_ms}"
        )
    return "\n".join(lines)


def _frame_stats(frame) -> dict[str, float | int]:
    if frame is None:
        return {"mean": 0.0, "std": 0.0, "min_value": 0, "max_value": 0}
    arr = np.asarray(frame)
    return {
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min_value": int(arr.min()),
        "max_value": int(arr.max()),
    }


def _save_sample(camera_id: str, frame, save_dir: Path) -> str:
    if frame is None:
        return ""
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_camera_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in camera_id)
    path = save_dir / f"{safe_camera_id}_sample.jpg"
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Failed to write camera sample: {path}")
    return str(path)


def _with_mvs_trigger_mode(camera_config: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized = (mode or "config").strip().lower()
    if normalized == "config":
        return camera_config
    if camera_config.get("type", "mvs") != "mvs":
        return camera_config
    source = str(camera_config.get("source", ""))
    if not source.startswith("mvs://"):
        return camera_config

    parsed = urlparse(source)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["trigger"] = normalized
    updated = parsed._replace(query=urlencode(query))
    cloned = dict(camera_config)
    cloned["source"] = urlunparse(updated)
    return cloned


def _no_frame_message(camera_config: dict[str, Any]) -> str:
    source = str(camera_config.get("source", ""))
    trigger_mode = _mvs_trigger_mode(source) if source.startswith("mvs://") else ""
    if trigger_mode == "hardware":
        return (
            "Connected but did not receive any frames before timeout; hardware trigger is enabled, "
            "so send a trigger pulse or rerun with --connect-only / --mvs-trigger-mode continuous"
        )
    if trigger_mode == "software":
        return "Connected and sent software triggers, but did not receive any frames before timeout"
    return "Connected but did not receive any frames before timeout"


def _mvs_trigger_mode(source: str) -> str:
    query = dict(parse_qsl(urlparse(source).query, keep_blank_values=True))
    return query.get("trigger", "continuous").strip().lower()


if __name__ == "__main__":
    raise SystemExit(main())
