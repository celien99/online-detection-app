"""ViewModel for SeatModelScreen: model CRUD + hot-switch."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.seat_model_service import SeatModelService


class SeatModelViewModel(QObject):
    """座椅型号管理 ViewModel。"""

    modelListChanged = Signal()
    activeModelChanged = Signal(str)
    switchFailed = Signal(str)
    requestConfirmSwitch = Signal(str)  # QML shows confirmation dialog
    toast = Signal(str, str)  # message, level: "success"/"error"/"warning"

    def __init__(
        self,
        seat_model_service: SeatModelService,
        on_switch: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._svc = seat_model_service
        self._on_switch = on_switch
        self._active_id: str = seat_model_service.get_default_model_id() or ""

    def _get_models(self) -> list:
        models = self._svc.list_models()
        for m in models:
            cameras = self._svc.get_cameras(m["id"])
            m["camera_count"] = len(cameras)
            m["camera_ids"] = [c["camera_id"] for c in cameras]
        return models

    def _get_active_id(self) -> str:
        return self._active_id

    seatModels = Property(list, _get_models, notify=modelListChanged)
    activeModelId = Property(str, _get_active_id, notify=activeModelChanged)

    @Slot(str, str, str, result=bool)
    def createModel(self, model_id: str, name: str, description: str) -> bool:
        try:
            self._svc.create_model(model_id, name, description)
            self.modelListChanged.emit()
            self.toast.emit(f"型号 '{name}' 创建成功", "success")
            return True
        except Exception as exc:
            self.toast.emit(f"创建失败: {exc}", "error")
            return False

    @Slot(str, str, str)
    def updateModel(self, model_id: str, name: str, description: str) -> None:
        self._svc.update_model(model_id, display_name=name, description=description)
        self.modelListChanged.emit()
        self.toast.emit("型号已更新", "success")

    @Slot(str, result=bool)
    def deleteModel(self, model_id: str) -> bool:
        ok = self._svc.delete_model(model_id)
        if not ok:
            cameras = self._svc.get_cameras(model_id)
            self.toast.emit(f"该型号下还有 {len(cameras)} 台相机，请先解除关联", "error")
            return False
        self.modelListChanged.emit()
        self.toast.emit("型号已删除", "success")
        return True

    @Slot(str)
    def setActive(self, model_id: str) -> None:
        self.requestConfirmSwitch.emit(model_id)

    @Slot(str)
    def confirmSwitch(self, model_id: str) -> None:
        try:
            if self._on_switch:
                self._on_switch(model_id)
            self._active_id = model_id
            self.activeModelChanged.emit(model_id)
            model = self._svc.get_model(model_id)
            name = model["display_name"] if model else model_id
            self.toast.emit(f"已切换至：{name}", "success")
        except Exception as exc:
            self.switchFailed.emit(str(exc))
            self.toast.emit(f"切换失败: {exc}", "error")

    @Slot(str, str, str, str)
    def addCamera(self, model_id: str, camera_id: str, cam_type: str, source: str) -> None:
        self._svc.add_camera(model_id, {
            "camera_id": camera_id,
            "type": cam_type,
            "source": source,
        })
        self.modelListChanged.emit()
        self.toast.emit(f"相机 '{camera_id}' 已添加", "success")

    @Slot(str)
    def removeCamera(self, camera_id: str) -> None:
        self._svc.remove_camera(camera_id)
        self.modelListChanged.emit()
        self.toast.emit("相机已移除", "success")

    @Slot(str, str, str)
    def updateCamera(self, camera_id: str, key: str, value: str) -> None:
        self._svc.update_camera(camera_id, **{key: value})
        self.modelListChanged.emit()

    def refresh(self) -> None:
        self.modelListChanged.emit()
