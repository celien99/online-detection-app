"""Command line model runtime and warmup check."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.infrastructure.config_store import ConfigStore
from app.runtime_paths import chdir_to_config_dir, resolve_config_path
from app.services.inspection_service import InspectionService


@dataclass(slots=True)
class ModuleCheck:
    name: str
    status: str
    message: str
    version: str = ""


@dataclass(slots=True)
class ModelCheckResult:
    status: str
    message: str
    config_path: str
    camera_count: int
    seat_model_id: str
    warmup_skipped: bool
    elapsed_ms: int
    runtime_modules: list[ModuleCheck]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check ML runtime imports and preload configured models without starting the GUI or cameras."
    )
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--seat-model-id", default="", help="Optional seat model ID to warm up")
    parser.add_argument("--skip-warmup", action="store_true", help="Only check imports and config parsing")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    config_path = resolve_config_path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    original_cwd = Path.cwd()
    chdir_to_config_dir(config_path)
    try:
        result = check_models(
            config_path=config_path.resolve(),
            seat_model_id=args.seat_model_id.strip() or None,
            skip_warmup=args.skip_warmup,
        )
    finally:
        os.chdir(original_cwd)

    if args.json:
        print(_to_json(result))
    else:
        print(_format_result(result))
    return 1 if result.status == "FAIL" else 0


def check_models(
    *,
    config_path: Path,
    seat_model_id: str | None = None,
    skip_warmup: bool = False,
) -> ModelCheckResult:
    started = time.time()
    modules = _check_runtime_modules()
    camera_count = 0
    service: InspectionService | None = None
    try:
        config = ConfigStore(str(config_path))
        camera_count = len(config.get_camera_configs())
        failed_imports = [item for item in modules if item.status == "FAIL"]
        if failed_imports:
            return _result(
                status="FAIL",
                message="Required ML runtime modules failed to import",
                config_path=config_path,
                camera_count=camera_count,
                seat_model_id=seat_model_id,
                warmup_skipped=skip_warmup,
                modules=modules,
                started=started,
            )
        if camera_count <= 0:
            return _result(
                status="FAIL",
                message="No enabled cameras in config",
                config_path=config_path,
                camera_count=camera_count,
                seat_model_id=seat_model_id,
                warmup_skipped=skip_warmup,
                modules=modules,
                started=started,
            )
        if skip_warmup:
            return _result(
                status="OK",
                message="Runtime modules imported and config parsed; model warmup skipped",
                config_path=config_path,
                camera_count=camera_count,
                seat_model_id=seat_model_id,
                warmup_skipped=True,
                modules=modules,
                started=started,
            )
        service = InspectionService(config)
        service.warmup(seat_model_id=seat_model_id)
        return _result(
            status="OK",
            message="Model runtime warmup succeeded",
            config_path=config_path,
            camera_count=camera_count,
            seat_model_id=seat_model_id,
            warmup_skipped=False,
            modules=modules,
            started=started,
        )
    except Exception as exc:
        return _result(
            status="FAIL",
            message=f"Model runtime warmup failed: {exc}",
            config_path=config_path,
            camera_count=camera_count,
            seat_model_id=seat_model_id,
            warmup_skipped=skip_warmup,
            modules=modules,
            started=started,
        )
    finally:
        if service is not None:
            service.shutdown()


def _check_runtime_modules() -> list[ModuleCheck]:
    module_names = [
        "numpy",
        "cv2",
        "torch",
        "torchvision",
        "ultralytics",
        "anomalib",
        "seat_defect_core",
    ]
    return [_check_module(name) for name in module_names]


def _check_module(name: str) -> ModuleCheck:
    try:
        module = importlib.import_module(name)
    except Exception as exc:
        return ModuleCheck(name=name, status="FAIL", message=str(exc))
    version = str(getattr(module, "__version__", ""))
    if name == "torch":
        version = _torch_version(module)
    return ModuleCheck(name=name, status="OK", message="imported", version=version)


def _torch_version(module: Any) -> str:
    version = str(getattr(module, "__version__", ""))
    try:
        cuda = "cuda" if bool(module.cuda.is_available()) else "cpu"
    except Exception:
        cuda = "cuda_unknown"
    return f"{version} ({cuda})" if version else cuda


def _result(
    *,
    status: str,
    message: str,
    config_path: Path,
    camera_count: int,
    seat_model_id: str | None,
    warmup_skipped: bool,
    modules: list[ModuleCheck],
    started: float,
) -> ModelCheckResult:
    return ModelCheckResult(
        status=status,
        message=message,
        config_path=str(config_path),
        camera_count=camera_count,
        seat_model_id=seat_model_id or "",
        warmup_skipped=warmup_skipped,
        elapsed_ms=int((time.time() - started) * 1000),
        runtime_modules=modules,
    )


def _format_result(result: ModelCheckResult) -> str:
    lines = [
        f"Model runtime check: {result.status}",
        f"Message: {result.message}",
        f"Config: {result.config_path}",
        f"Cameras: {result.camera_count}",
        f"Seat model: {result.seat_model_id or '-'}",
        f"Warmup skipped: {str(result.warmup_skipped).lower()}",
        f"Platform: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"Elapsed ms: {result.elapsed_ms}",
        "Runtime modules:",
    ]
    for item in result.runtime_modules:
        version = f" {item.version}" if item.version else ""
        lines.append(f"[{item.status}] {item.name}{version}: {item.message}")
    return "\n".join(lines)


def _to_json(result: ModelCheckResult) -> str:
    payload = asdict(result)
    payload["runtime"] = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cwd": str(Path.cwd()),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
