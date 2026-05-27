"""ViewModel for ModelDeployScreen: model file import/sync/activate/rollback."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.model_file_service import ModelFileService
from app.services.platform_sync_service import PlatformSyncService


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
    ) -> None:
        super().__init__()
        self._mfs = model_file_service
        self._platform = platform_sync
        self._sync_status = "offline"
        self._last_sync_time = ""
        self._filter_camera: str = ""
        self._filter_type: str = ""

    def _get_sync_status(self) -> str:
        return self._sync_status

    def _get_last_sync_time(self) -> str:
        return self._last_sync_time

    def _get_model_files(self) -> list:
        return self._mfs.list_history(
            camera_id=self._filter_camera or None,
            model_type=self._filter_type or None,
        )

    syncStatus = Property(str, _get_sync_status, notify=syncStatusChanged)
    lastSyncTime = Property(str, _get_last_sync_time, notify=syncStatusChanged)
    modelFiles = Property(list, _get_model_files, notify=modelFilesChanged)

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
            mf = self._mfs.import_file(camera_id, model_type, file_path)
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
                    model_type = dep.get("model_type", "efficientad")
                    download_url = dep.get("download_url", "")
                    if download_url:
                        dest = f"{tempfile.gettempdir()}/sync_{camera_id}_{model_type}.pt"
                        downloaded = self._platform.download_model(download_url, dest)
                        if downloaded:
                            self._mfs.register_synced(camera_id, model_type, downloaded, version)
                            imported += 1
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
        self._mfs.activate(file_id)
        self.modelFilesChanged.emit()
        self.toast.emit("模型版本已切换", "success")

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
        prev = self._mfs.rollback(camera_id, model_type)
        if prev:
            self.modelFilesChanged.emit()
            self.toast.emit(f"已回滚至 {prev['file_name']}", "success")
        else:
            self.toast.emit("没有可回滚的历史版本", "warning")
