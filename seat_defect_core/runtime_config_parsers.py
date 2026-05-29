"""Core inspect runtime configuration parsing."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from .calibration.config import (
    CalibrationConfig,
    CameraNormConfig,
    EMACenterConfig,
    ProjectionConfig,
    WhiteningConfig,
)
from .config import (
    AlignmentConfig,
    CameraConfig,
    DetectionConfig,
    FilterClassifierConfig,
    FusionConfig,
    InspectionConfig,
    QualityGuardConfig,
    RoiRefineConfig,
    RuleConfig,
    RuleEngineConfig,
    SeatModelConfig,
)
from .efficientad import EfficientADConfig
_LOCAL_PATH_SUFFIXES = {
    ".pt",
    ".pth",
    ".onnx",
    ".yaml",
    ".yml",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
}


# 主配置与座椅型号配置。
def _parse_inspection_config(payload: Dict[str, Any], config_dir: Path) -> InspectionConfig:
    scope = "InspectionConfig"
    _reject_unknown_keys(payload, _field_names(InspectionConfig), scope)

    cameras_payload = payload.get("cameras") or []
    seat_models_payload = payload.get("seat_models") or []
    if not cameras_payload and not seat_models_payload:
        raise ValueError("缺陷检测配置必须包含 `cameras` 或 `seat_models`")

    cameras = _parse_camera_list(
        cameras_payload,
        config_dir,
        scope=f"{scope}.cameras",
    )
    seat_models = [
        _parse_seat_model_config(item, config_dir, scope=f"{scope}.seat_models[{index}]")
        for index, item in enumerate(_ensure_list(seat_models_payload, f"{scope}.seat_models"))
    ]

    defaults = InspectionConfig()
    default_seat_model_id = _optional_string(payload.get("default_seat_model_id"))
    if default_seat_model_id is None and seat_models:
        default_seat_model_id = seat_models[0].seat_model_id

    return InspectionConfig(
        cameras=cameras,
        seat_models=seat_models,
        default_seat_model_id=default_seat_model_id,
        output_json_path=_resolve_local_path(
            config_dir,
            _string_or_default(payload.get("output_json_path"), defaults.output_json_path),
            force=True,
        ),
        debug_dir=_resolve_local_path(
            config_dir,
            _string_or_default(payload.get("debug_dir"), defaults.debug_dir),
            force=True,
        ),
        debug_artifacts_enabled=_bool_or_default(
            payload.get("debug_artifacts_enabled"),
            defaults.debug_artifacts_enabled,
        ),
        debug_artifact_names=_debug_artifact_names_or_default(
            payload.get("debug_artifact_names"),
            defaults.debug_artifact_names,
        ),
        part_id=_string_or_default(payload.get("part_id"), defaults.part_id),
        fusion=_parse_fusion_config(
            payload.get("fusion"),
            scope=f"{scope}.fusion",
        ),
        upload_base_url=_optional_string(payload.get("upload_base_url")),
        calibration=_parse_calibration_config(
            payload.get("calibration"),
            scope=f"{scope}.calibration",
        ),
    )


def _parse_seat_model_config(
    payload: Dict[str, Any],
    config_dir: Path,
    *,
    scope: str,
) -> SeatModelConfig:
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(SeatModelConfig), scope)

    seat_model_id = _require_string(payload, "seat_model_id", scope)
    cameras = _parse_camera_list(
        payload.get("cameras"),
        config_dir,
        scope=f"{scope}.cameras",
    )

    return SeatModelConfig(
        seat_model_id=seat_model_id,
        cameras=cameras,
        display_name=_optional_string(payload.get("display_name")),
    )


def _parse_camera_list(
    payload: Any,
    config_dir: Path,
    *,
    scope: str,
) -> List[CameraConfig]:
    items = _ensure_list(payload or [], scope)
    return [
        _parse_camera_config(item, config_dir, scope=f"{scope}[{index}]")
        for index, item in enumerate(items)
    ]


# 单机位及其子配置。
def _parse_camera_config(payload: Dict[str, Any], config_dir: Path, *, scope: str) -> CameraConfig:
    payload = _expect_dict(payload, scope)
    config_scope = f"CameraConfig {scope}"
    _reject_unknown_keys(payload, _field_names(CameraConfig), config_scope)

    return CameraConfig(
        camera_id=_require_string(payload, "camera_id", scope),
        efficientad_model_path=_resolve_local_path(
            config_dir,
            _require_string(payload, "efficientad_model_path", scope),
            force=True,
        ),
        source=_resolve_source_path(
            config_dir,
            _string_or_default(payload.get("source"), ""),
        ),
        enabled=_bool_or_default(payload.get("enabled"), True),
        quality=_parse_quality_guard_config(
            payload.get("quality"),
            scope=f"{scope}.quality",
        ),
        detection=_parse_detection_config(
            payload.get("detection"),
            config_dir,
            scope=f"{scope}.detection",
        ),
        roi=_parse_roi_refine_config(
            payload.get("roi"),
            scope=f"{scope}.roi",
        ),
        efficientad=_parse_efficientad_config(
            payload.get("efficientad"),
            scope=f"{scope}.efficientad",
        ),
        filter_classifier=_parse_filter_classifier_config(
            payload.get("filter_classifier"),
            config_dir,
            scope=f"{scope}.filter_classifier",
        ),
        rule_engine=_parse_rule_engine_config(
            payload.get("rule_engine"),
            scope=f"{scope}.rule_engine",
        ),
        calibration=_parse_calibration_config(
            payload.get("calibration"),
            scope=f"{scope}.calibration",
        ),
        color_insensitive_mode=_bool_or_default(
            payload.get("color_insensitive_mode"), True
        ),
    )


def _parse_fusion_config(payload: Any, *, scope: str) -> FusionConfig:
    defaults = FusionConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(FusionConfig), scope)
    return FusionConfig(
        reject_on_any_reject=_bool_or_default(
            payload.get("reject_on_any_reject"),
            defaults.reject_on_any_reject,
        ),
        ng_strategy=_string_or_default(payload.get("ng_strategy"), defaults.ng_strategy),
        defect_overrides_reject=_bool_or_default(
            payload.get("defect_overrides_reject"),
            defaults.defect_overrides_reject,
        ),
    )


def _parse_quality_guard_config(payload: Any, *, scope: str) -> QualityGuardConfig:
    defaults = QualityGuardConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(QualityGuardConfig), scope)
    return QualityGuardConfig(
        min_laplacian_variance=_float_or_default(
            payload.get("min_laplacian_variance"),
            defaults.min_laplacian_variance,
        ),
        min_brightness_mean=_float_or_default(
            payload.get("min_brightness_mean"),
            defaults.min_brightness_mean,
        ),
        max_brightness_mean=_float_or_default(
            payload.get("max_brightness_mean"),
            defaults.max_brightness_mean,
        ),
        max_overexposed_ratio=_float_or_default(
            payload.get("max_overexposed_ratio"),
            defaults.max_overexposed_ratio,
        ),
        max_underexposed_ratio=_float_or_default(
            payload.get("max_underexposed_ratio"),
            defaults.max_underexposed_ratio,
        ),
    )


def _parse_alignment_config(payload: Any, *, scope: str) -> AlignmentConfig:
    defaults = AlignmentConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(AlignmentConfig), scope)
    return AlignmentConfig(
        output_width=_int_or_default(payload.get("output_width"), defaults.output_width),
        output_height=_int_or_default(payload.get("output_height"), defaults.output_height),
    )


def _parse_roi_refine_config(payload: Any, *, scope: str) -> RoiRefineConfig:
    defaults = RoiRefineConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    if any(
        key in payload
        for key in (
            "keep_largest_component_only",
            "min_component_area_ratio",
            "min_component_area_pixels",
        )
    ):
        payload = dict(payload)
        payload.pop("keep_largest_component_only", None)
        payload.pop("min_component_area_ratio", None)
        payload.pop("min_component_area_pixels", None)
    _reject_unknown_keys(payload, _field_names(RoiRefineConfig), scope)
    return RoiRefineConfig(
        crop_expand_ratio=_float_or_default(
            payload.get("crop_expand_ratio"),
            defaults.crop_expand_ratio,
        ),
        crop_shrink_ratio=_float_or_default(
            payload.get("crop_shrink_ratio"),
            defaults.crop_shrink_ratio,
        ),
        mask_erode_pixels=_int_or_default(
            payload.get("mask_erode_pixels"),
            defaults.mask_erode_pixels,
        ),
        edge_ignore_pixels=_int_or_default(
            payload.get("edge_ignore_pixels"),
            defaults.edge_ignore_pixels,
        ),
        alignment=_parse_alignment_config(
            payload.get("alignment"),
            scope=f"{scope}.alignment",
        ),
    )


def _parse_detection_config(payload: Any, config_dir: Path, *, scope: str) -> DetectionConfig:
    defaults = DetectionConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(DetectionConfig), scope)
    return DetectionConfig(
        model_path=_resolve_optional_model_path(
            config_dir,
            _optional_string(payload.get("model_path")),
        ),
        target_class=_string_or_default(payload.get("target_class"), defaults.target_class),
        confidence=_float_or_default(payload.get("confidence"), defaults.confidence),
        iou=_float_or_default(payload.get("iou"), defaults.iou),
        device=_string_or_default(payload.get("device"), defaults.device),
        imgsz=_int_or_default(payload.get("imgsz"), defaults.imgsz),
        fill_segmentation_holes=_bool_or_default(
            payload.get("fill_segmentation_holes"),
            defaults.fill_segmentation_holes,
        ),
        segmentation_hole_fill_max_area_ratio=_float_or_default(
            payload.get("segmentation_hole_fill_max_area_ratio"),
            defaults.segmentation_hole_fill_max_area_ratio,
        ),
    )


def _parse_efficientad_config(payload: Any, *, scope: str) -> EfficientADConfig:
    defaults = EfficientADConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(EfficientADConfig), scope)
    return EfficientADConfig(
        model_path=_string_or_default(payload.get("model_path"), defaults.model_path),
        device=_string_or_default(payload.get("device"), defaults.device),
        input_size=_int_or_default(payload.get("input_size"), defaults.input_size),
        teacher_backbone=_string_or_default(
            payload.get("teacher_backbone"), defaults.teacher_backbone
        ),
        student_backbone=_string_or_default(
            payload.get("student_backbone"), defaults.student_backbone
        ),
        min_valid_pixel_ratio=_float_or_default(
            payload.get("min_valid_pixel_ratio"), defaults.min_valid_pixel_ratio
        ),
        image_threshold=_float_or_default(
            payload.get("image_threshold"), defaults.image_threshold
        ),
        pixel_threshold=_float_or_default(
            payload.get("pixel_threshold"), defaults.pixel_threshold
        ),
        epochs=_int_or_default(payload.get("epochs"), defaults.epochs),
        batch_size=_int_or_default(payload.get("batch_size"), defaults.batch_size),
        learning_rate=_float_or_default(
            payload.get("learning_rate"), defaults.learning_rate
        ),
        validation_split=_float_or_default(
            payload.get("validation_split"), defaults.validation_split
        ),
        early_stopping_patience=_int_or_default(
            payload.get("early_stopping_patience"), defaults.early_stopping_patience
        ),
    )


def _parse_filter_classifier_config(
    payload: Any, config_dir: Path, *, scope: str
) -> FilterClassifierConfig:
    defaults = FilterClassifierConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(FilterClassifierConfig), scope)
    raw_model_path = _optional_string(payload.get("model_path"))
    model_path: str | None = None
    if raw_model_path is not None:
        model_path = _resolve_local_path(config_dir, raw_model_path, force=False)
        if model_path is None:
            model_path = raw_model_path
    return FilterClassifierConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        model_path=model_path,
        device=_string_or_default(payload.get("device"), defaults.device),
        input_size=_int_or_default(payload.get("input_size"), defaults.input_size),
        confidence_threshold=_float_or_default(
            payload.get("confidence_threshold"), defaults.confidence_threshold
        ),
    )


def _parse_rule_engine_config(payload: Any, *, scope: str) -> RuleEngineConfig:
    defaults = RuleEngineConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(RuleEngineConfig), scope)
    rules_payload = payload.get("rules") or []
    return RuleEngineConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        deployed_rules_path=_optional_string(payload.get("deployed_rules_path")),
        rules=[
            _parse_rule_config(item, scope=f"{scope}.rules[{index}]")
            for index, item in enumerate(_ensure_list(rules_payload, f"{scope}.rules"))
        ],
    )


def _parse_rule_config(payload: Any, *, scope: str) -> RuleConfig:
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(RuleConfig), scope)
    return RuleConfig(
        name=_require_string(payload, "name", scope),
        enabled=_bool_or_default(payload.get("enabled"), True),
        # 阈值条件
        max_anomaly_score=_optional_float(payload.get("max_anomaly_score")),
        min_strong_patch_count=_optional_int(payload.get("min_strong_patch_count")),
        max_strong_patch_ratio=_optional_float(payload.get("max_strong_patch_ratio")),
        require_filter_false_alarm=_bool_or_default(
            payload.get("require_filter_false_alarm"), False
        ),
        require_filter_real_defect=_bool_or_default(
            payload.get("require_filter_real_defect"), False
        ),
        # 知识条件
        camera_id=_optional_string(payload.get("camera_id")),
        defect_type=_optional_string(payload.get("defect_type")),
        min_classifier_confidence=_optional_float(payload.get("min_classifier_confidence")),
        max_classifier_confidence=_optional_float(payload.get("max_classifier_confidence")),
        # 动作和元数据
        action=_string_or_default(payload.get("action"), "suppress_to_ok"),
        source=_string_or_default(payload.get("source"), "manual"),
        knowledge_entry_id=_optional_string(payload.get("knowledge_entry_id")),
        priority=_int_or_default(payload.get("priority"), 0),
    )


def _parse_calibration_config(payload: Any, *, scope: str) -> CalibrationConfig:
    """解析完整校准配置。返回默认值如果 payload 为 None。"""
    defaults = CalibrationConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(CalibrationConfig), scope)
    return CalibrationConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        camera_norm=_parse_camera_norm_config(
            payload.get("camera_norm"), scope=f"{scope}.camera_norm"
        ),
        projection=_parse_projection_config(
            payload.get("projection"), scope=f"{scope}.projection"
        ),
        whitening=_parse_whitening_config(
            payload.get("whitening"), scope=f"{scope}.whitening"
        ),
        ema_center=_parse_ema_center_config(
            payload.get("ema_center"), scope=f"{scope}.ema_center"
        ),
        camera_norm_paths=_string_dict_or_default(
            payload.get("camera_norm_paths"), defaults.camera_norm_paths
        ),
    )


def _parse_camera_norm_config(payload: Any, *, scope: str) -> CameraNormConfig:
    defaults = CameraNormConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(CameraNormConfig), scope)
    return CameraNormConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        stats_path=_string_or_default(payload.get("stats_path"), defaults.stats_path),
    )


def _parse_projection_config(payload: Any, *, scope: str) -> ProjectionConfig:
    defaults = ProjectionConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(ProjectionConfig), scope)
    return ProjectionConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        projector_path=_string_or_default(
            payload.get("projector_path"), defaults.projector_path
        ),
    )


def _parse_whitening_config(payload: Any, *, scope: str) -> WhiteningConfig:
    defaults = WhiteningConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(WhiteningConfig), scope)
    return WhiteningConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        method=_string_or_default(payload.get("method"), defaults.method),
        regularization=_float_or_default(
            payload.get("regularization"), defaults.regularization
        ),
        matrix_path=_string_or_default(payload.get("matrix_path"), defaults.matrix_path),
    )


def _parse_ema_center_config(payload: Any, *, scope: str) -> EMACenterConfig:
    defaults = EMACenterConfig()
    if payload is None:
        return defaults
    payload = _expect_dict(payload, scope)
    _reject_unknown_keys(payload, _field_names(EMACenterConfig), scope)
    return EMACenterConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        alpha=_float_or_default(payload.get("alpha"), defaults.alpha),
        min_samples=_int_or_default(payload.get("min_samples"), defaults.min_samples),
        novelty_threshold=_float_or_default(
            payload.get("novelty_threshold"), defaults.novelty_threshold
        ),
        centers_path=_string_or_default(payload.get("centers_path"), defaults.centers_path),
    )


# 通用字段读取与路径解析工具。
def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _field_names(cls: Type[Any]) -> Set[str]:
    return {field.name for field in dataclasses.fields(cls)}


def _reject_unknown_keys(payload: Dict[str, Any], allowed_keys: Set[str], scope: str) -> None:
    unexpected = sorted(key for key in payload if key not in allowed_keys)
    if not unexpected:
        return
    formatted = ", ".join(f"`{key}`" for key in unexpected)
    raise ValueError(f"{scope} 包含未知字段: {formatted}")


def _expect_dict(value: Any, scope: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{scope} 必须是对象")
    return value


def _ensure_list(value: Any, scope: str) -> List[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{scope} 必须是数组")
    return value


def _require_key(payload: Dict[str, Any], key: str, scope: str) -> Any:
    value = payload.get(key)
    if _is_missing(value):
        raise ValueError(f"{scope} 缺少 `{key}`")
    return value


def _require_string(payload: Dict[str, Any], key: str, scope: str) -> str:
    return str(_require_key(payload, key, scope))


def _optional_string(value: Any) -> Optional[str]:
    if _is_missing(value):
        return None
    return str(value)


def _string_or_default(value: Any, default: str) -> str:
    if _is_missing(value):
        return default
    return str(value)


def _bool_or_default(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise TypeError(f"布尔配置必须是 true/false，当前值: {value!r}")


def _int_or_default(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _float_or_default(value: Any, default: float) -> float:
    if value is None:
        return default
    return float(value)


def _optional_float(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None
    return float(value)


def _optional_int(value: Any) -> Optional[int]:
    if _is_missing(value):
        return None
    return int(value)


def _string_dict_or_default(value: Any, default: dict[str, str]) -> dict[str, str]:
    """解析字符串→字符串映射，用于 camera_norm_paths 等字段。"""
    if value is None or not isinstance(value, dict):
        return dict(default)
    return {str(k): str(v) for k, v in value.items()}


def _has_path_separator(value: str) -> bool:
    return os.sep in value or (os.altsep is not None and os.altsep in value)


def _string_list(value: Any, *, scope: str, default: List[str]) -> List[str]:
    if value is None:
        return list(default)
    return [str(item) for item in _ensure_list(value, scope)]


def _debug_artifact_names_or_default(value: Any, default: List[str]) -> List[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    else:
        items = [str(item).strip() for item in _ensure_list(value, "debug_artifact_names")]
    selected = [item for item in items if item]
    allowed = {"overlay"}
    unexpected = sorted(set(selected) - allowed)
    if unexpected:
        formatted = ", ".join(f"`{item}`" for item in unexpected)
        raise ValueError(f"debug_artifact_names 包含不支持的调试产物: {formatted}")
    return selected


def _resolve_source_path(config_dir: Path, value: str) -> str:
    if _is_missing(value):
        return ""
    if "://" in value or value.isdigit():
        return value
    return _resolve_local_path(config_dir, value, force=True)


def _resolve_optional_model_path(config_dir: Path, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _resolve_local_path(config_dir, value, force=False)


def _resolve_optional_local_path(config_dir: Path, value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    return _resolve_local_path(config_dir, value, force=True)


def _resolve_local_path(config_dir: Path, value: str, *, force: bool) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    if not force and not _looks_like_local_path(value):
        return value
    return str((config_dir / candidate).resolve())


def _looks_like_local_path(value: str) -> bool:
    if value.startswith(".") or _has_path_separator(value):
        return True
    return Path(value).suffix.lower() in _LOCAL_PATH_SUFFIXES
