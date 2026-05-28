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
        Image {
            source: "image://camera/CAM_FRONT_heatmap"
            cache: false
        }
    """

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._frames: Dict[str, np.ndarray] = {}
        self._heatmaps: Dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def update_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """更新指定相机的帧数据。frame 必须是 BGR numpy array。"""
        with self._lock:
            self._frames[camera_id] = frame.copy()

    def update_heatmap(self, camera_id: str, anomaly_map: np.ndarray) -> None:
        """更新指定相机的异常热力图。anomaly_map 是单通道 float32 数组。"""
        with self._lock:
            self._heatmaps[camera_id] = anomaly_map.copy()

    def requestImage(self, image_id: str, size, requested_size):
        """QML 引擎调用此方法请求图像。

        支持的后缀:
        - 无后缀: 原始相机帧
        - _original: 同原始帧（NG 弹窗原图面板）
        - _heatmap: 异常热力图覆盖层
        """
        base_id = image_id
        suffix = ""
        for s in ("_heatmap", "_original"):
            if image_id.endswith(s):
                base_id = image_id[: -len(s)]
                suffix = s
                break

        with self._lock:
            frame = self._frames.get(base_id)
            heatmap = self._heatmaps.get(base_id) if suffix == "_heatmap" else None
        if frame is None:
            empty = QImage(1, 1, QImage.Format.Format_RGB32)
            empty.fill(0)
            return empty

        if suffix == "_heatmap":
            return self._render_heatmap(frame, heatmap)

        h, w = frame.shape[:2]
        rgb = frame[:, :, ::-1].copy()
        qimage = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        qimage.rgb_data_holder = rgb
        return qimage

    def _render_heatmap(self, frame: np.ndarray, anomaly_map: np.ndarray | None) -> QImage:
        """将 BGR 原图与异常热力图叠加渲染。"""
        import cv2

        h, w = frame.shape[:2]

        if anomaly_map is not None:
            # 使用真实异常图：缩放到原图尺寸并叠加
            amap = anomaly_map.astype(np.float32)
            if amap.shape[:2] != (h, w):
                amap = cv2.resize(amap, (w, h), interpolation=cv2.INTER_LINEAR)
            # 归一化到 0-255
            amap = amap - amap.min()
            if amap.max() > 0:
                amap = (amap / amap.max() * 255).astype(np.uint8)
            else:
                amap = amap.astype(np.uint8)
            colored = cv2.applyColorMap(amap, cv2.COLORMAP_JET)
        else:
            # 回退：用边缘模糊模拟
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_blur = cv2.resize(gray, (w // 4, h // 4))
            gray_blur = cv2.resize(gray_blur, (w, h), interpolation=cv2.INTER_LINEAR)
            colored = cv2.applyColorMap(gray_blur, cv2.COLORMAP_JET)

        blended = cv2.addWeighted(frame, 0.4, colored, 0.6, 0)
        rgb = blended[:, :, ::-1].copy()
        qimage = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        qimage.rgb_data_holder = rgb
        return qimage
