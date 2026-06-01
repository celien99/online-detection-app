"""List visible Hikrobot MVS cameras and SDK search paths."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.infrastructure.camera.mvs.camera_controller import CameraLocator, HikCamera, MvsDeviceInfo
from app.infrastructure.camera.mvs.sdk.sdk_loader import describe_mvs_sdk_candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List Hikrobot MVS cameras visible to the SDK.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    candidates = describe_mvs_sdk_candidates(_local_sdk_dll())
    try:
        devices = list_mvs_devices()
    except Exception as exc:
        payload = {"status": "FAIL", "message": str(exc), "sdk_candidates": candidates, "devices": []}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(_format_failure(payload), file=sys.stderr)
        return 1

    payload = {
        "status": "OK",
        "message": f"Found {len(devices)} MVS camera(s)",
        "sdk_candidates": candidates,
        "devices": [asdict(device) | {"suggested_source": _suggest_source(device)} for device in devices],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_success(payload))
    return 0


def list_mvs_devices() -> list[MvsDeviceInfo]:
    camera = HikCamera(locator=CameraLocator(device_index=0))
    try:
        return camera.enumerate_devices()
    finally:
        camera.close()


def _local_sdk_dll() -> Path:
    return Path(__file__).resolve().parent / "infrastructure" / "camera" / "mvs" / "MvCameraControl.dll"


def _suggest_source(device: MvsDeviceInfo) -> str:
    if device.serial_number:
        return (
            f"mvs://sn/{device.serial_number}"
            "?trigger=hardware&trigger_source=Line0&trigger_activation=rising_edge"
            "&timeout_ms=2000&pixel_format=bgr8"
        )
    if device.ip_address:
        return (
            f"mvs://ip/{device.ip_address}"
            "?trigger=hardware&trigger_source=Line0&trigger_activation=rising_edge"
            "&timeout_ms=2000&pixel_format=bgr8"
        )
    return (
        f"mvs://{device.index}"
        "?trigger=hardware&trigger_source=Line0&trigger_activation=rising_edge"
        "&timeout_ms=2000&pixel_format=bgr8"
    )


def _format_success(payload: dict) -> str:
    lines = [payload["message"], "", "SDK candidates:"]
    lines.extend(f"- {candidate}" for candidate in payload["sdk_candidates"])
    lines.append("")
    lines.append("Devices:")
    for device in payload["devices"]:
        lines.append(
            " - index={index} sn={serial_number} ip={ip_address} mac={mac_address} "
            "model={model_name} name={user_defined_name}".format(**device)
        )
        lines.append(f"   source: {device['suggested_source']}")
    return "\n".join(lines)


def _format_failure(payload: dict) -> str:
    lines = ["MVS device listing failed:", payload["message"], "", "SDK candidates:"]
    lines.extend(f"- {candidate}" for candidate in payload["sdk_candidates"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
