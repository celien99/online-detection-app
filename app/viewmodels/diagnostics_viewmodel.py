"""ViewModel for production diagnostics."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.infrastructure.config_store import ConfigStore
from app.services.diagnostics import ProductionDiagnostics
from app.site_report import collect_site_report


class DiagnosticsViewModel(QObject):
    reportChanged = Signal()

    def __init__(
        self,
        config_store: ConfigStore,
        config_path: str,
        *,
        camera_configs_provider: Callable[[], list[dict[str, Any]]] | None = None,
        seat_model_id_provider: Callable[[], str | None] | None = None,
    ) -> None:
        super().__init__()
        self._config = config_store
        self._config_path = config_path
        self._camera_configs_provider = camera_configs_provider
        self._seat_model_id_provider = seat_model_id_provider
        self._overall_status = "unknown"
        self._report_status = "idle"
        self._report_message = ""
        self._last_report_path = ""
        self._items: list[dict] = []

    def _get_overall_status(self) -> str:
        return self._overall_status

    def _get_report_status(self) -> str:
        return self._report_status

    def _get_report_message(self) -> str:
        return self._report_message

    def _get_last_report_path(self) -> str:
        return self._last_report_path

    def _get_items(self) -> list:
        return self._items

    overallStatus = Property(str, _get_overall_status, notify=reportChanged)
    reportStatus = Property(str, _get_report_status, notify=reportChanged)
    reportMessage = Property(str, _get_report_message, notify=reportChanged)
    lastReportPath = Property(str, _get_last_report_path, notify=reportChanged)
    items = Property(list, _get_items, notify=reportChanged)

    @Slot()
    def refresh(self) -> None:
        report = ProductionDiagnostics(
            self._config,
            Path(self._config_path),
            camera_configs=self._runtime_camera_configs(),
        ).run()
        self._overall_status = report.status
        self._items = report.to_dict()["items"]
        self.reportChanged.emit()

    @Slot(result=bool)
    def generateSiteReport(self) -> bool:
        self._report_status = "running"
        self._report_message = "正在生成现场验收报告"
        self.reportChanged.emit()
        try:
            config_path = Path(self._config_path).resolve()
            output_dir = self._report_output_dir(config_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = output_dir / f"site_report_{timestamp}.json"
            report = collect_site_report(
                config=self._config,
                config_path=config_path,
                camera_samples_dir=output_dir / f"camera_samples_{timestamp}",
                camera_configs=self._runtime_camera_configs(),
                seat_model_id=self._active_seat_model_id(),
            )
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self._overall_status = report["status"]
            self._items = report["diagnostics"]["items"]
            self._last_report_path = str(report_path)
            self._report_status = report["status"]
            self._report_message = f"验收报告已生成: {report_path}"
            self.reportChanged.emit()
            return report["status"] != "FAIL"
        except Exception as exc:
            self._report_status = "FAIL"
            self._report_message = f"生成验收报告失败: {exc}"
            self.reportChanged.emit()
            return False

    def _runtime_camera_configs(self) -> list[dict[str, Any]] | None:
        if self._camera_configs_provider is None:
            return None
        return self._camera_configs_provider()

    def _active_seat_model_id(self) -> str | None:
        if self._seat_model_id_provider is None:
            return None
        value = self._seat_model_id_provider()
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _report_output_dir(self, config_path: Path) -> Path:
        storage = self._config.get_storage_config()
        raw_log_dir = storage.get("log_dir", "./logs")
        output_dir = Path(raw_log_dir) / "site_reports"
        if output_dir.is_absolute():
            return output_dir
        return config_path.parent / output_dir
