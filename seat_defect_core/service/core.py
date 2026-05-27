"""Core runtime context and cached camera pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..calibration import CalibrationConfig, CalibrationRegistry
from ..classifier.engine import FilterClassifierService
from ..config import CameraConfig, InspectionConfig
from ..cvops import ImageQualityGuard, RoiRefineEngine
from ..efficientad import EfficientADService
from ..core_types import DetectionResult, ImageQualityDecision, RoiRefineResult, TextureAnomalyResult
from ..yolo import DetectionService


@dataclass
class PreparedCameraSample:
    """Shared intermediate data for one camera."""

    quality: Optional[ImageQualityDecision]
    detection: Optional[DetectionResult] = None
    roi: Optional[RoiRefineResult] = None
    rejection_reason: Optional[str] = None


@dataclass
class ResolvedInspectionContext:
    """Resolved camera set and pipelines for a model route."""

    seat_model_id: Optional[str]
    cameras: List[CameraConfig]
    pipelines: Dict[str, "CameraPipeline"]


class CameraPipeline:
    """Per-camera detection, ROI and quality pipeline."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self.quality_guard = ImageQualityGuard(config.quality)
        self.detection_service = DetectionService(config.detection)
        self.roi_refine_engine = RoiRefineEngine(config.roi)

    def prepare_image(self, image: Any) -> PreparedCameraSample:
        detection = self.detection_service.detect(image)
        return self.prepare_from_detection(image, detection)

    def prepare_from_detection(
        self,
        image: Any,
        detection: DetectionResult,
    ) -> PreparedCameraSample:
        """Run ROI refinement and quality checks from a precomputed detection."""
        if detection.target is None:
            return PreparedCameraSample(
                quality=None,
                detection=detection,
                rejection_reason="target_not_found",
            )

        if detection.target.segmentation_mask is None:
            return PreparedCameraSample(
                quality=None,
                detection=detection,
                rejection_reason="target_mask_missing",
            )

        try:
            roi = self.roi_refine_engine.refine(image, detection)
        except ValueError as exc:
            return PreparedCameraSample(
                quality=None,
                detection=detection,
                rejection_reason=str(exc),
            )
        quality = self.quality_guard.evaluate(
            roi.aligned_roi_image,
            valid_mask=roi.valid_mask,
        )
        if not quality.accepted:
            return PreparedCameraSample(
                quality=quality,
                detection=detection,
                roi=roi,
                rejection_reason=f"quality_{quality.reason}",
            )

        return PreparedCameraSample(
            quality=quality,
            detection=detection,
            roi=roi,
        )


class InspectionService:
    """Core inspection service without capture or training responsibilities."""

    def __init__(self, config: InspectionConfig) -> None:
        self.config = config
        self._pipeline_cache: Dict[str, Dict[str, CameraPipeline]] = {}
        self._model_cache = AnomalyModelCache(self)
        self._anomaly_predictor = EfficientADPredictor()
        self._trackers: Dict[str, Any] = {}
        self._calibration_registry = self._init_calibration()

    def _init_calibration(self) -> Optional[CalibrationRegistry]:
        """从配置中初始化 CalibrationRegistry。"""
        # 从 CameraConfig 中查找 calibration 配置
        for camera in self.config.cameras:
            if camera.calibration is not None:
                return CalibrationRegistry(camera.calibration)
        # 检查 seat_models 中的 camera 配置
        for seat_model in self.config.seat_models:
            for camera in seat_model.cameras:
                if camera.calibration is not None:
                    return CalibrationRegistry(camera.calibration)
        return CalibrationRegistry(CalibrationConfig())

    @property
    def calibration(self) -> Optional[CalibrationRegistry]:
        return self._calibration_registry

    def resolve_context(self, seat_model_id: Optional[str]) -> ResolvedInspectionContext:
        resolved_seat_model_id, cameras = self._resolve_active_cameras(seat_model_id)
        cache_key = resolved_seat_model_id or "__default__"
        pipelines = self._pipeline_cache.get(cache_key)
        if pipelines is None:
            pipelines = {
                camera.camera_id: CameraPipeline(camera)
                for camera in cameras
            }
            self._pipeline_cache[cache_key] = pipelines
        return ResolvedInspectionContext(
            seat_model_id=resolved_seat_model_id,
            cameras=cameras,
            pipelines=pipelines,
        )

    def _resolve_active_cameras(self, seat_model_id: Optional[str]) -> Tuple[Optional[str], List[CameraConfig]]:
        if self.config.seat_models:
            resolved_seat_model_id: Optional[str] = (
                seat_model_id
                or self.config.default_seat_model_id
                or self.config.seat_models[0].seat_model_id
            )
            for seat_model in self.config.seat_models:
                if seat_model.seat_model_id == resolved_seat_model_id:
                    return (
                        resolved_seat_model_id,
                        [camera for camera in seat_model.cameras if camera.enabled],
                    )
            available = ", ".join(item.seat_model_id for item in self.config.seat_models)
            raise ValueError(f"未知 seat_model_id `{resolved_seat_model_id}`，可选值：{available}")

        resolved_seat_model_id = seat_model_id or self.config.default_seat_model_id
        return resolved_seat_model_id, [camera for camera in self.config.cameras if camera.enabled]

    def load_model_bundle(
        self,
        camera: CameraConfig,
        seat_model_id: Optional[str],
    ) -> EfficientADService:
        return self._model_cache.load_camera_bundle(camera, seat_model_id)

    def load_filter_classifier(
        self,
        camera: CameraConfig,
        seat_model_id: Optional[str],
    ) -> Optional[FilterClassifierService]:
        return self._model_cache.load_filter_classifier(camera, seat_model_id)

    def predict_anomaly_batch(
        self,
        items: List[Tuple[EfficientADService, Any, Any, Any]],
    ) -> List[TextureAnomalyResult]:
        """Predict anomaly results, one model at a time."""
        return self._anomaly_predictor.predict_batch(items)

    def warmup(self, seat_model_id: Optional[str] = None) -> None:
        """Preload all models (detection, EfficientAD, filter classifier)."""
        context = self.resolve_context(seat_model_id)
        for camera in context.cameras:
            pipeline = context.pipelines[camera.camera_id]
            pipeline.detection_service.warmup()
            self.load_model_bundle(camera, context.seat_model_id)
            if camera.filter_classifier.enabled and camera.filter_classifier.model_path:
                self.load_filter_classifier(camera, context.seat_model_id)


class AnomalyModelCache:
    """Load and cache EfficientAD models by model file."""

    def __init__(self, service: InspectionService) -> None:
        self._service = service
        self._cache: Dict[Tuple[str, str, str, int], EfficientADService] = {}
        self._filter_cache: Dict[Tuple[str, str, str, int], FilterClassifierService] = {}

    def load_camera_bundle(
        self,
        camera: CameraConfig,
        seat_model_id: Optional[str],
    ) -> EfficientADService:
        cache_key = self._cache_key(
            seat_model_id=seat_model_id,
            camera_id=camera.camera_id,
            model_id="__full__",
            model_path=camera.efficientad_model_path,
        )
        bundle = self._cache.get(cache_key)
        if bundle is not None:
            return bundle

        loaded = EfficientADService.load_bundle(camera.efficientad_model_path)
        self._cache[cache_key] = loaded
        return loaded

    def load_filter_classifier(
        self,
        camera: CameraConfig,
        seat_model_id: Optional[str],
    ) -> Optional[FilterClassifierService]:
        """加载过滤器分类器模型，缓存复用。

        支持两种 model_path 形式：
        - 直接指向 model.pt 文件
        - 指向部署目录（自动发现目录中的 model.pt）
        """
        if not camera.filter_classifier.enabled:
            return None
        model_path = camera.filter_classifier.model_path
        if not model_path:
            return None
        # 解析 model_path：目录自动发现 model.pt，或直接使用文件路径
        path = Path(model_path)
        if path.is_dir():
            candidate = path / "model.pt"
            resolved = str(candidate) if candidate.is_file() else None
        elif path.is_file():
            resolved = str(path)
        else:
            resolved = None
        if resolved is None:
            return None
        cache_key = self._cache_key(
            seat_model_id=seat_model_id,
            camera_id=camera.camera_id,
            model_id="filter_clf",
            model_path=resolved,
        )
        cached = self._filter_cache.get(cache_key)
        if cached is not None:
            return cached

        import torch

        svc = FilterClassifierService(
            config=camera.filter_classifier,
            model=torch.jit.load(
                resolved,
                map_location=camera.filter_classifier.device,
            ),
        )
        self._filter_cache[cache_key] = svc
        return svc

    @staticmethod
    def _cache_key(
        *,
        seat_model_id: Optional[str],
        camera_id: str,
        model_id: str,
        model_path: str,
    ) -> Tuple[str, str, str, int]:
        model_mtime_ns = Path(model_path).stat().st_mtime_ns
        return (
            seat_model_id or "__default__",
            camera_id,
            model_id,
            model_mtime_ns,
        )


class EfficientADPredictor:
    """Predict anomaly results, one model at a time."""

    def predict_batch(
        self,
        items: List[Tuple[EfficientADService, Any, Any, Any]],
    ) -> List[TextureAnomalyResult]:
        """Predict anomaly results for each item independently."""
        return [
            service.predict(image, target_mask, ignore_mask)
            for service, image, target_mask, ignore_mask in items
        ]
