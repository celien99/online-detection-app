"""QQuickImageProvider for streaming numpy frames to QML with zero copy."""
from __future__ import annotations

import threading
from typing import Dict, Optional

import numpy as np
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtQuick import QQuickImageProvider


class CameraImageProvider(QQuickImageProvider):
    """将 numpy BGR 帧零拷贝暴露给 QML Image 组件。

    QML 用法:
        Image {
            source: "image://camera/CAM_FRONT"
            cache: false
        }
    """

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._frames: Dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def update_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """更新指定相机的帧数据。frame 必须是 BGR numpy array。"""
        with self._lock:
            self._frames[camera_id] = frame.copy()

    def requestImage(self, image_id: str, size, requested_size):
        """QML 引擎调用此方法请求图像。"""
        with self._lock:
            frame = self._frames.get(image_id)
        if frame is None:
            empty = QImage(1, 1, QImage.Format.Format_RGB32)
            empty.fill(0)
            return empty

        h, w = frame.shape[:2]
        # BGR → RGB, using QImage zero-copy construction
        rgb = frame[:, :, ::-1].copy()
        qimage = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        qimage.rgb_data_holder = rgb
        return qimage
