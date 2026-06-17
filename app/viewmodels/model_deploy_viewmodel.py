"""ViewModel for ModelDeployScreen: model file import/sync/activate/rollback."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from typing import Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.model_file_service import ModelFileService
from app.services.platform_sync_service import PlatformSyncService
from app.services.seat_model_service import SeatModelService


class ModelDeployViewModel(QObject):
    """模型部署管理 ViewModel。"""

    modelFilesChanged = Signal()
    syncStatusChanged = Signal()
    syncCompleted = Signal(int)
    syncFailed = Signal(str)
    toast = Signal(str, str)

    def __init__(
        self,
        model_file_service: ModelFileService,
        platform_sync: PlatformSyncService,
        seat_model_service: SeatModelService | None = None,
        on_runtime_models_changed: Callable[[str | None], None] | None = None,
    ) -> None:
        super().__init__()
        self._mfs = model_file_service
        self._platform = platform_sync
        self._seat_models = seat_model_service
        self._on_runtime_models_changed = on_runtime_models_changed
        self._sync_status = "offline"
        self._last_sync_time = ""
        self._selected_seat_model_id = (
            seat_model_service.get_default_model_id() if seat_model_service is not None else ""
        ) or ""
        self._filter_camera: str = ""
        self._filter_type: str = ""

    def _refresh_runtime_models(self) -> None:
        if self._on_runtime_models_changed is not None:
            self._on_runtime_models_changed(self._selected_seat_model_id or None)

    def _get_sync_status(self) -> str:
        return self._sync_status

    def _get_last_sync_time(self) -> str:
        return self._last_sync_time

    def _get_selected_seat_model_id(self) -> str:
        return self._selected_seat_model_id

    def _get_seat_model_options(self) -> list:
        if self._seat_models is None:
            return []
        return [
            {
                "id": model["id"],
                "label": model.get("display_name") or model["id"],
            }
            for model in self._seat_models.list_models()
        ]

    def _camera_ids_for_selected_model(self) -> list[str]:
        if self._seat_models is None or not self._selected_seat_model_id:
            return []
        return [
            camera["camera_id"]
            for camera in self._seat_models.get_cameras(self._selected_seat_model_id)
        ]

    def _get_camera_options(self) -> list:
        return [{"id": "", "label": "全部相机"}] + [
            {"id": camera_id, "label": camera_id}
            for camera_id in self._camera_ids_for_selected_model()
        ]

    def _get_model_files(self) -> list:
        return self._mfs.list_history(
            camera_id=self._filter_camera or None,
            model_type=self._filter_type or None,
            seat_model_id=self._selected_seat_model_id,
        )

    def _get_runtime_versions(self) -> list:
        if self._seat_models is None or not self._selected_seat_model_id:
            return []
        cameras = self._seat_models.get_cameras_as_config_list(self._selected_seat_model_id)
        return self._mfs.active_runtime_versions(
            cameras,
            seat_model_id=self._selected_seat_model_id,
        )

    def _get_runtime_status(self) -> str:
        versions = self._get_runtime_versions()
        if not versions:
            return "未激活"
        if any(not item.get("exists", False) for item in versions):
            return "文件缺失"
        return "已应用"

    syncStatus = Property(str, _get_sync_status, notify=syncStatusChanged)
    lastSyncTime = Property(str, _get_last_sync_time, notify=syncStatusChanged)
    selectedSeatModelId = Property(str, _get_selected_seat_model_id, notify=modelFilesChanged)
    seatModelOptions = Property(list, _get_seat_model_options, notify=modelFilesChanged)
    cameraOptions = Property(list, _get_camera_options, notify=modelFilesChanged)
    modelFiles = Property(list, _get_model_files, notify=modelFilesChanged)
    activeRuntimeVersions = Property(list, _get_runtime_versions, notify=modelFilesChanged)
    runtimeStatus = Property(str, _get_runtime_status, notify=modelFilesChanged)

    @Slot(str)
    def setSeatModel(self, model_id: str) -> None:
        self._selected_seat_model_id = model_id.strip()
        self._filter_camera = ""
        self.modelFilesChanged.emit()

    @Slot(str)
    def setFilterCamera(self, camera_id: str) -> None:
        self._filter_camera = camera_id
        self.modelFilesChanged.emit()

    @Slot(str)
    def setFilterType(self, model_type: str) -> None:
        self._filter_type = model_type
        self.modelFilesChanged.emit()

    @Slot(str, str, str)
    def importModelFile(self, camera_id: str, model_type: str, file_path: str) -> None:
        try:
            mf = self._mfs.import_file(
                camera_id,
                model_type,
                file_path,
                seat_model_id=self._selected_seat_model_id,
            )
            self._refresh_runtime_models()
            self.modelFilesChanged.emit()
            self.toast.emit(f"模型 '{mf['file_name']}' 导入成功", "success")
        except Exception as exc:
            self.toast.emit(f"导入失败: {exc}", "error")

    @Slot()
    def checkPlatformHealth(self) -> None:
        if self._platform.check_health():
            self._sync_status = "online"
        else:
            self._sync_status = "offline"
        self.syncStatusChanged.emit()

    @Slot()
    def syncFromPlatform(self) -> None:
        self._sync_status = "syncing"
        self.syncStatusChanged.emit()
        try:
            models = self._platform.list_deployed_models()
            imported = 0
            for model in models:
                target = model.get("target", "")
                version = model.get("model_version", "")
                for dep in model.get("deployments", []):
                    camera_id = dep.get("camera_id", target)
                    model_type = dep.get("model_type", "patchcore")
                    download_url = dep.get("download_url", "")
                    if download_url:
                        dest = f"{tempfile.gettempdir()}/sync_{camera_id}_{model_type}.pt"
                        downloaded = self._platform.download_model(download_url, dest)
                        if downloaded:
                            self._mfs.register_synced(
                                camera_id,
                                model_type,
                                downloaded,
                                version,
                                seat_model_id=dep.get("seat_model_id") or self._selected_seat_model_id,
                            )
                            imported += 1
            if imported > 0:
                self._refresh_runtime_models()
            self._last_sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            self._sync_status = "online"
            self.modelFilesChanged.emit()
            self.syncCompleted.emit(imported)
            self.toast.emit(f"已同步 {imported} 个模型", "success")
        except Exception as exc:
            self._sync_status = "offline"
            self.syncFailed.emit(str(exc))
            self.toast.emit(f"同步失败: {exc}", "error")
        self.syncStatusChanged.emit()

    @Slot(str)
    def activateVersion(self, file_id: str) -> None:
        try:
            self._mfs.activate(file_id)
            self._refresh_runtime_models()
            self.modelFilesChanged.emit()
            self.toast.emit("模型版本已切换", "success")
        except Exception as exc:
            self.modelFilesChanged.emit()
            self.toast.emit(f"运行时切换失败: {exc}", "error")

    @Slot(str)
    def deleteModelFile(self, file_id: str) -> None:
        ok = self._mfs.delete_file(file_id)
        if ok:
            self.modelFilesChanged.emit()
            self.toast.emit("文件已删除", "success")
        else:
            self.toast.emit("无法删除激活版本", "error")

    @Slot(str, str)
    def rollback(self, camera_id: str, model_type: str) -> None:
        prev = self._mfs.rollback_scoped(self._selected_seat_model_id, camera_id, model_type)
        if prev:
            try:
                self._refresh_runtime_models()
                self.modelFilesChanged.emit()
                self.toast.emit(f"已回滚至 {prev['file_name']}", "success")
            except Exception as exc:
                self.modelFilesChanged.emit()
                self.toast.emit(f"回滚后运行时切换失败: {exc}", "error")
        else:
            self.toast.emit("没有可回滚的历史版本", "warning")

    @Slot(result=bool)
    def verifyActiveVersions(self) -> bool:
        versions = self._get_runtime_versions()
        if not versions:
            self.toast.emit("当前型号没有激活模型", "warning")
            return False
        missing = [item for item in versions if not item.get("exists", False)]
        if missing:
            names = ", ".join(item.get("file_name", "") for item in missing[:3])
            self.toast.emit(f"激活文件缺失: {names}", "error")
            return False
        failed = []
        for item in versions:
            file_id = item.get("file_id", "")
            if file_id and not self._mfs.verify_checksum(file_id):
                failed.append(item.get("file_name", file_id))
        if failed:
            self.toast.emit(f"校验失败: {', '.join(failed[:3])}", "error")
            return False
        self.toast.emit("激活版本校验通过", "success")
        self.modelFilesChanged.emit()
        return True
