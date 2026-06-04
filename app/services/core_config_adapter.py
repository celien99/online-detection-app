"""Build seat_defect_core runtime configs from desktop app camera payloads."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_LOCAL_PATH_SUFFIXES = {
    ".json",
    ".jpeg",
    ".jpg",
    ".onnx",
    ".png",
    ".pt",
    ".pth",
    ".yaml",
    ".yml",
}


def build_core_inspection_config(
    *,
    cameras: list[dict[str, Any]],
    upload_base_url: str = "",
    part_id: str = "seat_demo",
    output_json_path: str = "outputs/seat_defect_inspection/results.json",
    debug_dir: str = "outputs/seat_defect_inspection/debug",
    debug_artifacts_enabled: bool = True,
    debug_artifact_names: list[str] | None = None,
    config_dir: Path | None = None,
) -> Any:
    """Create the offline PatchCore core InspectionConfig used by the app.

    The desktop config includes capture/UI fields such as ``type``,
    ``watch_dir`` and ``pattern``. The offline core does not know those keys,
    so the app owns this adapter instead of relying on a core-side shim.
    """
    from seat_defect_core.config import (
        InspectionConfig,
    )
    from seat_defect_core.runtime_config import validate_inspection_config

    root = (config_dir or Path.cwd()).resolve()
    config = InspectionConfig(
        cameras=[_camera_config(camera, root) for camera in cameras],
        output_json_path=_resolve_local_path(root, output_json_path, force=True),
        debug_dir=_resolve_local_path(root, debug_dir, force=True),
        debug_artifacts_enabled=bool(debug_artifacts_enabled),
        debug_artifact_names=list(debug_artifact_names or ["overlay"]),
        part_id=str(part_id or "seat_demo"),
        upload_base_url=str(upload_base_url) if upload_base_url else None,
    )
    validate_inspection_config(config)
    return config


def _camera_config(payload: dict[str, Any], config_dir: Path) -> Any:
    from seat_defect_core.config import CameraConfig

    regions_payload = _list_or_empty(payload.get("regions"))
    return CameraConfig(
        camera_id=_require_string(payload, "camera_id"),
        patchcore_model_path=_camera_patchcore_model_path(payload, regions_payload, config_dir),
        source=_resolve_source_path(config_dir, _string_or_default(payload.get("source"), "")),
        enabled=_bool_or_default(payload.get("enabled"), True),
        color_insensitive_mode=_bool_or_default(payload.get("color_insensitive_mode"), False),
        quality=_quality_config(payload.get("quality")),
        detection=_detection_config(payload.get("detection"), config_dir),
        roi=_roi_config(payload.get("roi")),
        patchcore=_patchcore_config(payload.get("patchcore"), config_dir),
        color_branch=_color_branch_config(payload.get("color_branch")),
        filter_classifier=_filter_classifier_config(payload.get("filter_classifier"), config_dir),
        rule_engine=_rule_engine_config(payload.get("rule_engine")),
        regions=_region_configs(regions_payload, config_dir),
    )


def _quality_config(payload: Any) -> Any:
    from seat_defect_core.config import QualityGuardConfig

    defaults = QualityGuardConfig()
    if not isinstance(payload, dict):
        return defaults
    return QualityGuardConfig(
        min_laplacian_variance=_float_or_default(
            payload.get("min_laplacian_variance"), defaults.min_laplacian_variance
        ),
        min_brightness_mean=_float_or_default(
            payload.get("min_brightness_mean"), defaults.min_brightness_mean
        ),
        max_brightness_mean=_float_or_default(
            payload.get("max_brightness_mean"), defaults.max_brightness_mean
        ),
        max_overexposed_ratio=_float_or_default(
            payload.get("max_overexposed_ratio"), defaults.max_overexposed_ratio
        ),
        max_underexposed_ratio=_float_or_default(
            payload.get("max_underexposed_ratio"), defaults.max_underexposed_ratio
        ),
    )


def _detection_config(payload: Any, config_dir: Path) -> Any:
    from seat_defect_core.config import DetectionConfig

    defaults = DetectionConfig()
    if not isinstance(payload, dict):
        return defaults
    return DetectionConfig(
        model_path=_resolve_optional_model_path(config_dir, _optional_string(payload.get("model_path"))),
        target_class=_string_or_default(payload.get("target_class"), defaults.target_class),
        confidence=_float_or_default(payload.get("confidence"), defaults.confidence),
        iou=_float_or_default(payload.get("iou"), defaults.iou),
        device=_string_or_default(payload.get("device"), defaults.device),
        imgsz=_int_or_default(payload.get("imgsz"), defaults.imgsz),
        fill_segmentation_holes=_bool_or_default(
            payload.get("fill_segmentation_holes"), defaults.fill_segmentation_holes
        ),
        segmentation_hole_fill_max_area_ratio=_float_or_default(
            payload.get("segmentation_hole_fill_max_area_ratio"),
            defaults.segmentation_hole_fill_max_area_ratio,
        ),
    )


def _roi_config(payload: Any) -> Any:
    from seat_defect_core.config import AlignmentConfig, RoiRefineConfig

    defaults = RoiRefineConfig()
    if not isinstance(payload, dict):
        return defaults
    alignment_payload = payload.get("alignment")
    alignment_defaults = AlignmentConfig()
    alignment = alignment_defaults
    if isinstance(alignment_payload, dict):
        alignment = AlignmentConfig(
            output_width=_int_or_default(
                alignment_payload.get("output_width"), alignment_defaults.output_width
            ),
            output_height=_int_or_default(
                alignment_payload.get("output_height"), alignment_defaults.output_height
            ),
        )
    return RoiRefineConfig(
        crop_expand_ratio=_float_or_default(payload.get("crop_expand_ratio"), defaults.crop_expand_ratio),
        crop_shrink_ratio=_float_or_default(payload.get("crop_shrink_ratio"), defaults.crop_shrink_ratio),
        mask_erode_pixels=_int_or_default(payload.get("mask_erode_pixels"), defaults.mask_erode_pixels),
        edge_ignore_pixels=_int_or_default(payload.get("edge_ignore_pixels"), defaults.edge_ignore_pixels),
        alignment=alignment,
    )


def _patchcore_config(payload: Any, config_dir: Path) -> Any:
    from seat_defect_core.config import PatchCoreConfig

    defaults = PatchCoreConfig()
    if not isinstance(payload, dict):
        return defaults
    return PatchCoreConfig(
        backend=_string_or_default(payload.get("backend"), defaults.backend),
        image_size=_int_or_default(payload.get("image_size"), defaults.image_size),
        patch_size=_int_or_default(payload.get("patch_size"), defaults.patch_size),
        stride=_int_or_default(payload.get("stride"), defaults.stride),
        max_memory=_int_or_default(payload.get("max_memory"), defaults.max_memory),
        threshold_quantile=_float_or_default(
            payload.get("threshold_quantile"), defaults.threshold_quantile
        ),
        texture_input=_string_or_default(payload.get("texture_input"), defaults.texture_input),
        min_target_coverage=_float_or_default(
            payload.get("min_target_coverage"), defaults.min_target_coverage
        ),
        max_ignore_overlap=_float_or_default(payload.get("max_ignore_overlap"), defaults.max_ignore_overlap),
        min_valid_patch_ratio=_float_or_default(
            payload.get("min_valid_patch_ratio"), defaults.min_valid_patch_ratio
        ),
        training_threshold_upper_quantile=_float_or_default(
            payload.get("training_threshold_upper_quantile"),
            defaults.training_threshold_upper_quantile,
        ),
        decision_score_margin=_float_or_default(
            payload.get("decision_score_margin"), defaults.decision_score_margin
        ),
        strong_patch_score_ratio=_float_or_default(
            payload.get("strong_patch_score_ratio"), defaults.strong_patch_score_ratio
        ),
        min_strong_patch_count=_int_or_default(
            payload.get("min_strong_patch_count"), defaults.min_strong_patch_count
        ),
        min_strong_component_count=_int_or_default(
            payload.get("min_strong_component_count"), defaults.min_strong_component_count
        ),
        min_strong_patch_ratio=_float_or_default(
            payload.get("min_strong_patch_ratio"), defaults.min_strong_patch_ratio
        ),
        min_strong_component_ratio=_float_or_default(
            payload.get("min_strong_component_ratio"), defaults.min_strong_component_ratio
        ),
        critical_score_margin=_float_or_default(
            payload.get("critical_score_margin"), defaults.critical_score_margin
        ),
        critical_peak_score_margin=_float_or_default(
            payload.get("critical_peak_score_margin"), defaults.critical_peak_score_margin
        ),
        critical_min_component_patch_count=_int_or_default(
            payload.get("critical_min_component_patch_count"),
            defaults.critical_min_component_patch_count,
        ),
        min_peak_component_patch_count=_int_or_default(
            payload.get("min_peak_component_patch_count"), defaults.min_peak_component_patch_count
        ),
        backbone_name=_string_or_default(payload.get("backbone_name"), defaults.backbone_name),
        feature_layers=_string_list(payload.get("feature_layers"), defaults.feature_layers),
        backbone_pretrained=_bool_or_default(payload.get("backbone_pretrained"), defaults.backbone_pretrained),
        backbone_weights_path=_resolve_optional_local_path(
            config_dir, _optional_string(payload.get("backbone_weights_path"))
        ),
        backbone_device=_string_or_default(payload.get("backbone_device"), defaults.backbone_device),
        feature_pool_kernel_size=_int_or_default(
            payload.get("feature_pool_kernel_size"), defaults.feature_pool_kernel_size
        ),
        coreset_sampling_ratio=_float_or_default(
            payload.get("coreset_sampling_ratio"), defaults.coreset_sampling_ratio
        ),
    )


def _color_branch_config(payload: Any) -> Any:
    from seat_defect_core.config import ColorBranchConfig

    defaults = ColorBranchConfig()
    if not isinstance(payload, dict):
        return defaults
    return ColorBranchConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        threshold_quantile=_float_or_default(
            payload.get("threshold_quantile"), defaults.threshold_quantile
        ),
        threshold=_optional_float(payload.get("threshold")),
        min_valid_pixel_ratio=_float_or_default(
            payload.get("min_valid_pixel_ratio"), defaults.min_valid_pixel_ratio
        ),
        training_threshold_upper_quantile=_float_or_default(
            payload.get("training_threshold_upper_quantile"),
            defaults.training_threshold_upper_quantile,
        ),
    )


def _filter_classifier_config(payload: Any, config_dir: Path) -> Any:
    from seat_defect_core.config import FilterClassifierConfig

    defaults = FilterClassifierConfig()
    if not isinstance(payload, dict):
        return defaults
    raw_model_path = _optional_string(payload.get("model_path"))
    model_path = _resolve_optional_model_path(config_dir, raw_model_path)
    return FilterClassifierConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        model_path=model_path,
        device=_string_or_default(payload.get("device"), defaults.device),
        input_size=_int_or_default(payload.get("input_size"), defaults.input_size),
        confidence_threshold=_float_or_default(
            payload.get("confidence_threshold"), defaults.confidence_threshold
        ),
    )


def _rule_engine_config(payload: Any) -> Any:
    from seat_defect_core.config import RuleEngineConfig

    defaults = RuleEngineConfig()
    if not isinstance(payload, dict):
        return defaults
    return RuleEngineConfig(
        enabled=_bool_or_default(payload.get("enabled"), defaults.enabled),
        deployed_rules_path=_optional_string(payload.get("deployed_rules_path")),
        rules=[_rule_config(item) for item in _list_or_empty(payload.get("rules"))],
    )


def _rule_config(payload: Any) -> Any:
    from seat_defect_core.config import RuleConfig

    if not isinstance(payload, dict):
        raise TypeError("rule_engine.rules items must be objects")
    return RuleConfig(
        name=_require_string(payload, "name"),
        enabled=_bool_or_default(payload.get("enabled"), True),
        max_anomaly_score=_optional_float(payload.get("max_anomaly_score")),
        min_strong_patch_count=_optional_int(payload.get("min_strong_patch_count")),
        max_strong_patch_ratio=_optional_float(payload.get("max_strong_patch_ratio")),
        require_filter_false_alarm=_bool_or_default(payload.get("require_filter_false_alarm"), False),
        require_filter_real_defect=_bool_or_default(payload.get("require_filter_real_defect"), False),
        camera_id=_optional_string(payload.get("camera_id")),
        defect_type=_optional_string(payload.get("defect_type")),
        min_classifier_confidence=_optional_float(payload.get("min_classifier_confidence")),
        max_classifier_confidence=_optional_float(payload.get("max_classifier_confidence")),
        action=_string_or_default(payload.get("action"), "suppress_to_ok"),
        source=_string_or_default(payload.get("source"), "manual"),
        knowledge_entry_id=_optional_string(payload.get("knowledge_entry_id")),
        priority=_int_or_default(payload.get("priority"), 0),
    )


def _region_configs(payload: Any, config_dir: Path) -> list[Any]:
    return [_region_config(item, config_dir) for item in _list_or_empty(payload)]


def _camera_patchcore_model_path(
    payload: dict[str, Any],
    regions_payload: list[Any],
    config_dir: Path,
) -> str:
    value = _optional_string(payload.get("patchcore_model_path"))
    if value is not None:
        return _resolve_local_path(config_dir, value, force=True)
    if _has_enabled_region_model(regions_payload):
        return ""
    raise ValueError("Missing required config key `patchcore_model_path`")


def _has_enabled_region_model(regions_payload: list[Any]) -> bool:
    for item in regions_payload:
        if not isinstance(item, dict):
            continue
        if item.get("enabled", True) is False:
            continue
        if not _is_missing(item.get("patchcore_model_path")):
            return True
    return False


def _region_config(payload: Any, config_dir: Path) -> Any:
    from seat_defect_core.config import RegionConfig

    if not isinstance(payload, dict):
        raise TypeError("regions items must be objects")
    if "patchcore" in payload:
        raise ValueError(
            "region-level patchcore config is not supported by the app; "
            "configure camera-level patchcore once per camera"
        )
    return RegionConfig(
        region_id=_require_string(payload, "region_id"),
        box=_region_box(payload.get("box")),
        patchcore_model_path=_resolve_local_path(
            config_dir,
            _require_string(payload, "patchcore_model_path"),
            force=True,
        ),
        enabled=_bool_or_default(payload.get("enabled"), True),
        patchcore=None,
    )


def _region_box(value: Any) -> list[float]:
    items = [float(item) for item in _ensure_list(value)]
    if len(items) != 4:
        raise ValueError("region box must contain four normalized coordinates")
    x1, y1, x2, y2 = items
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        raise ValueError("region box must satisfy 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1")
    return items


def _resolve_source_path(config_dir: Path, value: str) -> str:
    if _is_missing(value):
        return ""
    if "://" in value or value.isdigit():
        return value
    return _resolve_local_path(config_dir, value, force=True)


def _resolve_optional_model_path(config_dir: Path, value: str | None) -> str | None:
    if value is None:
        return None
    return _resolve_local_path(config_dir, value, force=False)


def _resolve_optional_local_path(config_dir: Path, value: str | None) -> str | None:
    if _is_missing(value):
        return None
    return _resolve_local_path(config_dir, str(value), force=True)


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


def _has_path_separator(value: str) -> bool:
    return os.sep in value or (os.altsep is not None and os.altsep in value)


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if _is_missing(value):
        raise ValueError(f"Missing required config key `{key}`")
    return str(value)


def _optional_string(value: Any) -> str | None:
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
    return bool(value)


def _int_or_default(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _float_or_default(value: Any, default: float) -> float:
    if value is None:
        return default
    return float(value)


def _optional_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    return int(value)


def _string_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    return [str(item) for item in _ensure_list(value)]


def _list_or_empty(value: Any) -> list[Any]:
    if value is None:
        return []
    return _ensure_list(value)


def _ensure_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("Config value must be a list")
    return value
