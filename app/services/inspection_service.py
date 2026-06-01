"""Inspection service wrapping seat_defect_core with thread pool."""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.config_store import ConfigStore


class InspectionService:
    """封装 seat_defect_core 的 SeatDefectInspector，通过线程池执行推理。"""

    def __init__(self, config: ConfigStore) -> None:
        self._config = config
        self._inspector = None  # 延迟初始化，避免导入 GPU 库过早
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="inspection"
        )
        self._warmed_up = False

    def init_inspector(self) -> None:
        """首次调用或热重载后重新初始化 SeatDefectInspector。"""
        from seat_defect_core.api import SeatDefectInspector
        from seat_defect_core.config import InspectionConfig
        from seat_defect_core.runtime_config_parsers import build_inspection_config

        camera_configs = self._config.get_camera_configs()
        app_config = self._config.get_app_config()
        inspection_cfg = build_inspection_config(
            cameras=camera_configs,
            upload_base_url=self._config.get_offline_platform_config().get("upload_base_url", ""),
            part_id=app_config.get("station_id", "seat_demo"),
        )
        self._inspector = SeatDefectInspector(inspection_cfg)

    def warmup(self, *, seat_model_id: Optional[str] = None) -> None:
        if self._warmed_up:
            return
        if self._inspector is None:
            self.init_inspector()
        self._inspector.warmup(seat_model_id=seat_model_id)
        self._warmed_up = True

    def inspect_sync(
        self,
        frames: Dict[str, np.ndarray],
        *,
        seat_model_id: Optional[str] = None,
        timeout_s: float = 5.0,
    ) -> Any:
        """同步执行一次检测。返回 InspectionResponse。"""
        if self._inspector is None:
            self.init_inspector()
        from seat_defect_core.core_types import InspectionFrame

        inspection_frames = [
            InspectionFrame(camera_id=cid, image=frame, source=f"camera://{cid}")
            for cid, frame in frames.items()
            if frame is not None
        ]
        if not inspection_frames:
            from seat_defect_core.core_types import InspectionResponse, InspectionResult
            return InspectionResponse(
                result=InspectionResult(status="REJECT", decision_reason="no_frames"),
                status="REJECT",
                decision_reason="no_frames",
            )
        response, _ = self._inspector.inspect(inspection_frames, seat_model_id=seat_model_id)
        return response

    def inspect_async(
        self,
        frames: Dict[str, np.ndarray],
        *,
        seat_model_id: Optional[str] = None,
        timeout_s: float = 5.0,
    ) -> concurrent.futures.Future:
        """异步执行一次检测，返回 Future[InspectionResponse]。"""
        return self._executor.submit(
            self.inspect_sync, frames, seat_model_id=seat_model_id, timeout_s=timeout_s
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
