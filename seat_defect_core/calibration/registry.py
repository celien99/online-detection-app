"""Unified calibration registry — per-camera indexed access to all calibration components."""

from __future__ import annotations

from typing import Optional

import numpy as np

from .._protocol import UnifiedEmbedding
from .camera_normalizer import CameraNormalizer
from .config import CalibrationConfig
from .feature_center import EMAFeatureCenter
from .projector import EmbeddingProjector
from .whitening import WhiteningTransform


class CalibrationRegistry:
    """按 camera_id 索引所有 calibration 组件。

    一个 camera 的完整校准链路：
        registry.normalize(camera_id, features)
        registry.project(features)
        registry.whiten(unified_emb)

    projector / whitening / ema_center 跨机位共享，
    normalizer 必须 per-camera。
    """

    def __init__(self, config: CalibrationConfig):
        self.config = config
        self._normalizers: dict[str, CameraNormalizer] = {}
        self._projector: Optional[EmbeddingProjector] = None
        self._whitening: Optional[WhiteningTransform] = None
        self._ema_center: Optional[EMAFeatureCenter] = None

        self._load_from_config()

    def _load_from_config(self) -> None:
        cfg = self.config
        # 加载 per-camera normalizers
        for camera_id, stats_path in cfg.camera_norm_paths.items():
            if stats_path:
                try:
                    self.load_camera_normalizer(camera_id, stats_path)
                except Exception:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.warning(
                        "calibration_normalizer_load_failed",
                        extra={"camera_id": camera_id, "path": stats_path},
                    )
        if cfg.projection.enabled and cfg.projection.projector_path:
            self._projector = EmbeddingProjector.load(cfg.projection.projector_path)
        if cfg.whitening.enabled and cfg.whitening.matrix_path:
            self._whitening = WhiteningTransform.load(cfg.whitening.matrix_path)
        if cfg.ema_center.enabled and cfg.ema_center.centers_path:
            self._ema_center = EMAFeatureCenter.load(cfg.ema_center.centers_path)
        elif cfg.ema_center.enabled:
            self._ema_center = EMAFeatureCenter(
                alpha=cfg.ema_center.alpha,
                dim=384,
            )

    def register_camera(self, camera_id: str, normalizer: CameraNormalizer) -> None:
        self._normalizers[camera_id] = normalizer

    def load_camera_normalizer(self, camera_id: str, path: str) -> CameraNormalizer:
        normalizer = CameraNormalizer.load(path)
        self._normalizers[camera_id] = normalizer
        return normalizer

    def get_normalizer(self, camera_id: str) -> Optional[CameraNormalizer]:
        return self._normalizers.get(camera_id)

    def normalize(self, camera_id: str, features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """机位级标准化。未注册 camera 则返回原值。"""
        normalizer = self._normalizers.get(camera_id)
        if normalizer is None:
            return features
        return normalizer.normalize(features)

    def project(self, features: dict[str, np.ndarray]) -> Optional[np.ndarray]:
        """投影到 384-dim。projector 未加载则返回 None。"""
        if self._projector is None:
            return None
        return self._projector.project(features)

    def whiten(self, embedding: np.ndarray) -> np.ndarray:
        """ZCA 白化。whitening 未加载则返回原值。"""
        if self._whitening is None:
            return embedding
        return self._whitening.whiten(embedding)

    def calibrate(
        self, camera_id: str, features: dict[str, np.ndarray]
    ) -> Optional[UnifiedEmbedding]:
        """执行完整校准链路：normalize → project → whiten → UnifiedEmbedding。

        注意：projector 必须在归一化后的特征上拟合，否则投影结果无效。
        如果 projector 已加载但对应 camera 的 normalizer 未注册，
        归一化会原样返回（无操作），此时 project 接收原始特征。

        Returns:
            UnifiedEmbedding 如果 projection 可用，否则 None
        """
        if not self.config.enabled:
            return None

        if self._projector is not None and camera_id not in self._normalizers:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(
                "calibration_projector_without_normalizer",
                extra={
                    "camera_id": camera_id,
                    "hint": "projector 应在归一化后的特征上拟合，"
                            "请为每个 camera 注册 CameraNormalizer",
                },
            )

        normalized = self.normalize(camera_id, features)
        vec = self.project(normalized)
        if vec is None:
            return None

        if self._whitening is not None:
            vec = self.whiten(vec)

        return UnifiedEmbedding(
            vector=vec.tolist(),
            contract_version="1.0.0",
            source="efficientad_projected",
        )

    def update_ema_center(self, defect_type: str, embedding: np.ndarray) -> None:
        """更新 EMA 中心。"""
        if self._ema_center is not None:
            self._ema_center.update(defect_type, embedding)

    def query_nearest(self, embedding: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        if self._ema_center is not None:
            return self._ema_center.query_nearest(embedding, top_k)
        return []

    def is_novel(self, embedding: np.ndarray) -> bool:
        if self._ema_center is None:
            return False
        return self._ema_center.is_novel(embedding, self.config.ema_center.novelty_threshold)

    @property
    def projector(self) -> Optional[EmbeddingProjector]:
        return self._projector

    @property
    def ema_center(self) -> Optional[EMAFeatureCenter]:
        return self._ema_center
