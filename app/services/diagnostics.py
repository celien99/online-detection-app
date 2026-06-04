"""Production readiness diagnostics."""
from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.infrastructure.config_store import ConfigStore

PLACEHOLDER_MARKERS = ("REPLACE_WITH", "<", ">")


@dataclass(slots=True)
class DiagnosticItem:
    name: str
    status: str
    message: str
    suggestion: str = ""


@dataclass(slots=True)
class DiagnosticReport:
    status: str
    items: list[DiagnosticItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "items": [asdict(item) for item in self.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ProductionDiagnostics:
    """Runs non-destructive checks useful before starting a production shift."""

    def __init__(self, config: ConfigStore, config_path: str | Path) -> None:
        self._config = config
        self._base_dir = Path(config_path).resolve().parent

    def run(self) -> DiagnosticReport:
        items: list[DiagnosticItem] = []
        items.extend(self._check_cameras())
        items.extend(self._check_model_files())
        items.extend(self._check_storage())
        items.extend(self._check_line_signal())
        items.extend(self._check_runtime())
        return DiagnosticReport(status=_overall_status(items), items=items)

    def _check_cameras(self) -> list[DiagnosticItem]:
        cameras = self._config.get_camera_configs()
        if not cameras:
            return [
                DiagnosticItem(
                    name="相机配置",
                    status="FAIL",
                    message="未配置启用的相机",
                    suggestion="在 config.json 的 cameras 中至少启用一个相机",
                )
            ]

        items = [
            DiagnosticItem(
                name="相机配置",
                status="OK",
                message=f"已启用 {len(cameras)} 个相机",
            )
        ]
        if any(cam.get("type") == "mvs" for cam in cameras):
            items.append(self._check_mvs_sdk())
        for cam in cameras:
            camera_id = cam.get("camera_id", "<unknown>")
            source = cam.get("source", "")
            if cam.get("type") != "file_watcher" and not source:
                items.append(
                    DiagnosticItem(
                        name=f"相机 {camera_id}",
                        status="FAIL",
                        message="缺少 source 配置",
                        suggestion="为相机配置 mvs://、rtsp:// 或 rtmp:// 输入源",
                    )
                )
            if source and _looks_like_placeholder(source):
                items.append(
                    DiagnosticItem(
                        name=f"相机 {camera_id} source",
                        status="FAIL",
                        message=f"source 仍包含模板占位符: {source}",
                        suggestion="使用 OnlineDetectionConfigWizard.exe 或手工替换为真实相机序列号/IP",
                    )
                )
            if cam.get("type") == "mvs":
                items.extend(self._check_mvs_camera_source(camera_id, source))
        return items

    def _check_mvs_camera_source(self, camera_id: str, source: str) -> list[DiagnosticItem]:
        app_cfg = self._config.get_app_config()
        if app_cfg.get("inspection_mode", "continuous") != "triggered" or not source.startswith("mvs://"):
            return []
        parsed = urlparse(source)
        query = parse_qs(parsed.query)
        items: list[DiagnosticItem] = []
        selector = (parsed.netloc or "").strip().lower()
        if selector not in {"sn", "serial"} and "sn" not in query and "serial" not in query:
            items.append(
                DiagnosticItem(
                    name=f"{camera_id} 相机选择",
                    status="WARN",
                    message="MVS 相机未使用序列号选择",
                    suggestion="生产电脑建议使用 mvs://sn/<序列号>，避免设备枚举顺序变化导致误选",
                )
            )
        trigger_mode = query.get("trigger", ["continuous"])[0].lower()
        if trigger_mode != "hardware":
            items.append(
                DiagnosticItem(
                    name=f"{camera_id} 触发模式",
                    status="WARN",
                    message=f"MVS 相机 trigger={trigger_mode}",
                    suggestion="连接 PLC 到位信号时建议使用 trigger=hardware&trigger_source=Line0",
                )
            )
        return items

    def _check_mvs_sdk(self) -> DiagnosticItem:
        dll_path = Path(__file__).resolve().parents[1] / "infrastructure" / "camera" / "mvs" / "MvCameraControl.dll"
        if not dll_path.exists():
            return DiagnosticItem(
                name="Hikrobot MVS SDK",
                status="FAIL",
                message="未找到 MvCameraControl.dll",
                suggestion="在 Windows 工控机安装 Hikrobot MVS SDK，并确认 SDK DLL 可被加载",
            )
        if platform.system() != "Windows":
            return DiagnosticItem(
                name="Hikrobot MVS SDK",
                status="WARN",
                message="检测到 MVS DLL，但当前不是 Windows 运行环境",
                suggestion="最终联机验收需在 Windows 工控机上执行",
            )
        return DiagnosticItem(name="Hikrobot MVS SDK", status="OK", message="检测到 MVS SDK DLL")

    def _check_model_files(self) -> list[DiagnosticItem]:
        items: list[DiagnosticItem] = []
        for cam in self._config.get_camera_configs():
            camera_id = cam.get("camera_id", "<unknown>")
            checks = [
                ("PatchCore 模型", cam.get("patchcore_model_path")),
                ("规则文件", cam.get("rule_engine", {}).get("deployed_rules_path") if cam.get("rule_engine", {}).get("enabled") else None),
            ]
            for region in cam.get("regions", []) or []:
                if not isinstance(region, dict):
                    continue
                if region.get("enabled", True) is False:
                    continue
                region_id = region.get("region_id", "<unknown>")
                checks.append(
                    (
                        f"region {region_id} PatchCore 模型",
                        region.get("patchcore_model_path"),
                    )
                )
            if cam.get("filter_classifier", {}).get("enabled"):
                checks.append(("过滤分类器", cam.get("filter_classifier", {}).get("model_path")))
            for label, raw_path in checks:
                if not raw_path:
                    continue
                if _looks_like_placeholder(str(raw_path)):
                    items.append(
                        DiagnosticItem(
                            name=f"{camera_id} {label}",
                            status="FAIL",
                            message=f"路径仍包含模板占位符: {raw_path}",
                            suggestion="替换为测试电脑上的真实模型或规则文件路径",
                        )
                    )
                    continue
                path = self._resolve_path(raw_path)
                if path.exists():
                    items.append(DiagnosticItem(name=f"{camera_id} {label}", status="OK", message=str(path)))
                else:
                    items.append(
                        DiagnosticItem(
                            name=f"{camera_id} {label}",
                            status="FAIL",
                            message=f"路径不存在: {path}",
                            suggestion="部署对应模型或规则文件后再启动生产检测",
                        )
                    )
        if not items:
            items.append(
                DiagnosticItem(
                    name="模型文件",
                    status="WARN",
                    message="未发现模型或规则文件配置",
                    suggestion="确认 config.json 中每个相机的 PatchCore、YOLO、Filter 与规则路径",
                )
            )
        return items

    def _check_storage(self) -> list[DiagnosticItem]:
        storage = self._config.get_storage_config()
        items: list[DiagnosticItem] = []
        for key, label in (("log_dir", "日志目录"), ("screenshot_dir", "截图目录")):
            raw_path = storage.get(key)
            if not raw_path:
                items.append(DiagnosticItem(name=label, status="WARN", message=f"未配置 {key}"))
                continue
            path = self._resolve_path(raw_path)
            if path.exists() and path.is_dir() and os.access(path, os.W_OK):
                items.append(DiagnosticItem(name=label, status="OK", message=str(path)))
            elif not path.exists() and os.access(path.parent, os.W_OK):
                items.append(
                    DiagnosticItem(
                        name=label,
                        status="WARN",
                        message=f"目录尚不存在: {path}",
                        suggestion="启动前创建目录，或确认应用账号有权限创建",
                    )
                )
            else:
                items.append(
                    DiagnosticItem(
                        name=label,
                        status="FAIL",
                        message=f"目录不可写: {path}",
                        suggestion="修正目录权限或改用可写路径",
                    )
                )
        return items

    def _check_line_signal(self) -> list[DiagnosticItem]:
        app_cfg = self._config.get_app_config()
        line_cfg = self._config.get("line_signal", default={})
        mode = app_cfg.get("inspection_mode", "continuous")
        if mode != "triggered":
            return [
                DiagnosticItem(
                    name="产线触发",
                    status="WARN",
                    message="当前为 continuous 连续检测模式",
                    suggestion="生产联机建议设置 app.inspection_mode 为 triggered",
                )
            ]
        if not line_cfg.get("enabled", False):
            return [
                DiagnosticItem(
                    name="产线触发",
                    status="FAIL",
                    message="triggered 模式下 line_signal 未启用",
                    suggestion="启用 line_signal 并配置 modbus PLC 点表",
                )
            ]
        adapter_type = line_cfg.get("type", "")
        if adapter_type == "modbus":
            host = str(line_cfg.get("host", "192.168.1.100"))
            if _looks_like_placeholder(host):
                return [
                    DiagnosticItem(
                        name="产线触发",
                        status="FAIL",
                        message=f"PLC host 仍包含模板占位符: {host}",
                        suggestion="使用 OnlineDetectionConfigWizard.exe 或手工替换为真实 PLC IP",
                    )
                ]
            return [
                DiagnosticItem(
                    name="产线触发",
                    status="OK",
                    message=f"Modbus PLC {host}:{line_cfg.get('port', 502)}",
                )
            ]
        if adapter_type == "labview_tcp":
            return [
                DiagnosticItem(
                    name="产线触发",
                    status="WARN",
                    message="使用 LabVIEW TCP 上位机触发",
                    suggestion="高速产线建议使用 PLC 硬触发作为权威到位信号",
                )
            ]
        return [
            DiagnosticItem(
                name="产线触发",
                status="WARN",
                message=f"使用 {adapter_type or 'unknown'} 触发适配器",
                suggestion="生产默认推荐 line_signal.type=modbus",
            )
        ]

    def _check_runtime(self) -> list[DiagnosticItem]:
        items = [
            DiagnosticItem(
                name="运行系统",
                status="OK" if platform.system() == "Windows" else "WARN",
                message=f"{platform.system()} {platform.release()}",
                suggestion="最终部署目标为 Windows 工控机" if platform.system() != "Windows" else "",
            )
        ]
        python_version = sys.version_info
        python_status = "OK" if (python_version.major, python_version.minor) in {(3, 11), (3, 12)} else "FAIL"
        items.append(
            DiagnosticItem(
                name="Python 版本",
                status=python_status,
                message=f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                suggestion=(
                    "请使用 Python 3.11 或 3.12 运行；Windows 上的 PyTorch/Anomalib/PySide6 环境不建议使用 3.13+"
                    if python_status == "FAIL"
                    else ""
                ),
            )
        )
        try:
            import torch  # type: ignore

            cuda_available = bool(torch.cuda.is_available())
            items.append(
                DiagnosticItem(
                    name="PyTorch/CUDA",
                    status="OK" if cuda_available else "WARN",
                    message="CUDA 可用" if cuda_available else "CUDA 不可用，将使用 CPU 或模型回退路径",
                    suggestion="如需 GPU 推理，请安装匹配的 NVIDIA 驱动与 CUDA 版 PyTorch" if not cuda_available else "",
                )
            )
        except Exception as exc:
            items.append(
                DiagnosticItem(
                    name="PyTorch/CUDA",
                    status="WARN",
                    message=f"无法导入 torch: {exc}",
                    suggestion="如生产模型依赖 PyTorch，请检查运行环境依赖",
                )
            )
        return items

    def _resolve_path(self, raw_path: str | os.PathLike[str]) -> Path:
        path = Path(raw_path)
        return path if path.is_absolute() else self._base_dir / path


def _overall_status(items: list[DiagnosticItem]) -> str:
    statuses = {item.status for item in items}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "OK"


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)
