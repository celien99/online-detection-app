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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check configured cameras without starting the GUI or ML pipeline.")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--camera-id", default="", help="Only check one configured camera")
    parser.add_argument("--frames", type=int, default=1, help="Number of frames to grab per camera")
    parser.add_argument("--timeout-ms", type=int, default=2000, help="Per-frame grab timeout")
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
                check_camera(cam, frames=max(1, args.frames), timeout_ms=max(1, args.timeout_ms))
                for cam in camera_configs
            ]
    finally:
        os.chdir(original_cwd)

    if args.json:
        print(json.dumps({"items": [asdict(item) for item in items]}, ensure_ascii=False, indent=2))
    else:
        print(_format_items(items))
    return 1 if any(item.status == "FAIL" for item in items) else 0


def check_camera(camera_config: dict[str, Any], *, frames: int = 1, timeout_ms: int = 2000) -> CameraCheckItem:
    camera_id = str(camera_config.get("camera_id", "<unknown>"))
    started = time.time()
    camera = None
    frames_grabbed = 0
    try:
        camera = create_camera(camera_config)
        camera.connect()
        for _ in range(frames):
            frame = camera.grab_frame(timeout_ms=timeout_ms)
            if frame is not None:
                frames_grabbed += 1
        status = camera.get_status()
        elapsed_ms = int((time.time() - started) * 1000)
        if frames_grabbed <= 0:
            return CameraCheckItem(
                camera_id=camera_id,
                status="FAIL",
                message="Connected but did not receive any frames before timeout",
                width=status.width,
                height=status.height,
                fps=status.fps,
                frames_grabbed=frames_grabbed,
                elapsed_ms=elapsed_ms,
            )
        return CameraCheckItem(
            camera_id=camera_id,
            status="OK",
            message="Camera connected and frame grab succeeded",
            width=status.width,
            height=status.height,
            fps=status.fps,
            frames_grabbed=frames_grabbed,
            elapsed_ms=elapsed_ms,
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
            f"elapsed_ms={item.elapsed_ms}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
