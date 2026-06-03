"""将 seat_defect_core 检测结果上传到离线分析平台。

此模块填补在线→离线数据闭环的关键缺口：
将实时检测中发现的异常（NG 结果）及其关联图片（ROI、热力图等）
上传到后端 API，供后续 embedding 提取、聚类分析和分类器训练使用。
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import requests

from .core_types import CameraInspectionResult, InspectionResponse, RegionPatchCoreResult

logger = logging.getLogger(__name__)

# 在线端期望的 schema 版本，与后端 app/schemas/__init__.py 中的 CURRENT_SCHEMA_VERSION 对齐
EXPECTED_SCHEMA_VERSION = "1.0"


def upload_camera_result(
    result: CameraInspectionResult,
    base_url: str,
    *,
    date_folder: Optional[str] = None,
    timeout: float = 30.0,
    include_ok_suppressed: bool = False,
) -> Optional[Dict[str, Any]]:
    """将单机位检测结果上传到离线平台。

    Args:
        result: 单机位检测结果。
        base_url: 后端 API 基础地址，如 "http://localhost:8000"。
        date_folder: 日期文件夹名，默认用当天日期 YYYY-MM-DD。
        timeout: HTTP 请求超时秒数。
        include_ok_suppressed: 是否也上传被分类器抑制的 OK 结果（用于反馈统计）。

    Returns:
        后端返回的 JSON 响应，包含 anomaly_id；不上传时返回 None。
    """
    is_ng = result.status == "NG"
    is_suppressed = (
        result.status == "OK"
        and result.filter_result is not None
        and "filter_classifier_suppressed" in (result.reason or "")
    )

    if not is_ng and not (include_ok_suppressed and is_suppressed):
        return None

    if date_folder is None:
        date_folder = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    data: Dict[str, Any] = {
        "camera_id": result.camera_id,
        "source": "patchcore",
        "date_folder": date_folder,
        "detected_at": datetime.now(tz=timezone.utc).isoformat(),
        "decision_reason": result.reason,
    }
    if result.seat_model_id:
        data["seat_model_id"] = result.seat_model_id

    # 传递过滤器分类器决策元数据
    if result.filter_result is not None:
        fr = result.filter_result
        data["filter_confidence"] = float(fr.confidence)
        data["filter_real_defect_score"] = float(fr.real_defect_score)
        data["filter_false_alarm_score"] = float(fr.false_alarm_score)
        data["filter_class_id"] = int(fr.class_id)
        if is_ng and fr.is_real_defect:
            data["filter_action"] = "confirmed_ng"
        elif is_suppressed and not fr.is_real_defect:
            data["filter_action"] = "suppressed_to_ok"
        elif fr.is_real_defect:
            data["filter_action"] = "confirmed_ng"
        else:
            data["filter_action"] = "not_applied"

    # regions 模式下每个 NG region 单独上传，避免离线 embedding/cluster 跨 region 混合。
    if result.region_results and is_ng:
        uploaded: list[dict[str, Any]] = []
        for region in _uploadable_regions(result):
            region_data = dict(data)
            region_data["region_id"] = region.region_id
            if region.texture_result is not None:
                region_data["anomaly_score"] = float(region.texture_result.score)
            region_files = _build_region_files(result, region)
            response_json = _post_anomaly(
                base_url=base_url,
                data=region_data,
                files=region_files,
                timeout=timeout,
            )
            if response_json is not None:
                uploaded.append(response_json)

        if not uploaded:
            return None
        if len(uploaded) == 1:
            return uploaded[0]

        anomaly_ids: list[str] = []
        total_count = 0
        for item in uploaded:
            anomaly_ids.extend(str(aid) for aid in item.get("anomaly_ids", []))
            total_count += int(item.get("count", 0))
        return {
            "anomaly_ids": anomaly_ids,
            "count": total_count,
            "status": "received",
            "message": "Region anomalies queued for processing",
            "schema_version": uploaded[0].get("schema_version", EXPECTED_SCHEMA_VERSION),
            "region_count": len(uploaded),
        }

    # 异常分数
    if result.texture_result is not None:
        data["anomaly_score"] = float(result.texture_result.score)
    elif result.region_results:
        # 区域模式下从 region_results 收集最高异常分数
        region_scores = [
            r.texture_result.score
            for r in result.region_results
            if r.texture_result is not None
        ]
        if region_scores:
            data["anomaly_score"] = float(max(region_scores))

    files = _build_camera_files(result)
    return _post_anomaly(base_url=base_url, data=data, files=files, timeout=timeout)


def upload_inspection_response(
    response: InspectionResponse,
    base_url: str,
    *,
    date_folder: Optional[str] = None,
    timeout: float = 30.0,
    include_ok_suppressed: bool = False,
) -> List[Dict[str, Any]]:
    """遍历 InspectionResponse 中的所有相机结果，上传异常到离线平台。

    Args:
        response: 整件检测响应。
        base_url: 后端 API 基础地址。
        date_folder: 日期文件夹名。
        timeout: HTTP 请求超时秒数。
        include_ok_suppressed: 是否也上传被分类器抑制的 OK 结果。

    Returns:
        成功上传的异常记录列表（每项包含 backend 返回的 anomaly_id）。
    """
    results: List[Dict[str, Any]] = []
    for camera_result in response.result.camera_results:
        uploaded = upload_camera_result(
            camera_result,
            base_url,
            date_folder=date_folder,
            timeout=timeout,
            include_ok_suppressed=include_ok_suppressed,
        )
        if uploaded is not None:
            results.append(uploaded)
    return results


def _post_anomaly(
    *,
    base_url: str,
    data: Dict[str, Any],
    files: list[tuple[str, tuple]],
    timeout: float,
) -> Optional[Dict[str, Any]]:
    try:
        url = f"{base_url.rstrip('/')}/api/anomaly/upload-with-files"
        response = requests.post(
            url,
            data=data,
            files=files,
            timeout=timeout,
        )
        response.raise_for_status()
        resp_json = response.json()
        # 校验后端 schema 版本兼容性
        backend_version = resp_json.get("schema_version")
        if backend_version and backend_version != EXPECTED_SCHEMA_VERSION:
            logger.warning(
                "Schema version mismatch: seat_defect_core expects %s, backend returns %s",
                EXPECTED_SCHEMA_VERSION,
                backend_version,
            )
        return resp_json
    except requests.RequestException:
        return None


def _uploadable_regions(result: CameraInspectionResult) -> list[RegionPatchCoreResult]:
    return [
        region
        for region in result.region_results
        if region.status == "NG"
        and region.texture_result is not None
        and region.texture_result.heatmap is not None
    ]


def _build_camera_files(result: CameraInspectionResult) -> list[tuple[str, tuple]]:
    files: list[tuple[str, tuple]] = []

    # 原图：用户/产线上传到 inspection 的原始大图，不含热力图叠加。
    if result.original_image is not None:
        files.append(("original_file", (
            "original.jpg",
            _encode_bgr_image(result.original_image, ".jpg"),
            "image/jpeg",
        )))

    # Crop：利用热力图裁剪异常高响应区域，供离线平台 embedding 提取使用。
    # 一张图可能存在多处异常 → 提取全部连通域，每张 crop 单独上传。
    anomaly_crops = _extract_anomaly_crop(result)
    if anomaly_crops:
        for i, crop_img in enumerate(anomaly_crops):
            files.append(("crop_files", (
                f"crop_{i}.jpg",
                _encode_bgr_image(crop_img, ".jpg"),
                "image/jpeg",
            )))
    elif result.roi_aligned_image is not None:
        files.append(("crop_files", (
            "crop_0.jpg",
            _encode_bgr_image(result.roi_aligned_image, ".jpg"),
            "image/jpeg",
        )))
    elif result.roi_image is not None:
        files.append(("crop_files", (
            "crop_0.jpg",
            _encode_bgr_image(result.roi_image, ".jpg"),
            "image/jpeg",
        )))

    # Heatmap：Inspection 页面输出的检测叠加图。它已经把完整 ROI 或 region
    # PatchCore 的热力图统一映射回原图坐标系。
    if result.overlay_image is not None:
        files.append(("heatmap_file", (
            "heatmap.jpg",
            _encode_bgr_image(result.overlay_image, ".jpg"),
            "image/jpeg",
        )))
    else:
        heatmap = _extract_heatmap_for_upload(result)
        if heatmap is not None:
            files.append(("heatmap_file", ("heatmap.png", _encode_heatmap(heatmap), "image/png")))

    return files


def _build_region_files(
    result: CameraInspectionResult,
    region: RegionPatchCoreResult,
) -> list[tuple[str, tuple]]:
    files: list[tuple[str, tuple]] = []

    if result.original_image is not None:
        files.append(("original_file", (
            "original.jpg",
            _encode_bgr_image(result.original_image, ".jpg"),
            "image/jpeg",
        )))

    crop_base = _region_crop_base(result, region)
    if crop_base is not None and region.texture_result is not None:
        crops = _crop_by_heatmap(np.asarray(region.texture_result.heatmap, dtype=np.float32), crop_base)
        if crops:
            for i, crop_img in enumerate(crops):
                files.append(("crop_files", (
                    f"{region.region_id}_crop_{i}.jpg",
                    _encode_bgr_image(crop_img, ".jpg"),
                    "image/jpeg",
                )))
        else:
            files.append(("crop_files", (
                f"{region.region_id}_crop_0.jpg",
                _encode_bgr_image(crop_base, ".jpg"),
                "image/jpeg",
            )))

    if region.texture_result is not None and region.texture_result.heatmap is not None:
        files.append(("heatmap_file", (
            f"{region.region_id}_heatmap.png",
            _encode_heatmap(np.asarray(region.texture_result.heatmap, dtype=np.float32)),
            "image/png",
        )))
    elif result.overlay_image is not None:
        files.append(("heatmap_file", (
            "heatmap.jpg",
            _encode_bgr_image(result.overlay_image, ".jpg"),
            "image/jpeg",
        )))

    return files


def _region_crop_base(
    result: CameraInspectionResult,
    region: RegionPatchCoreResult,
) -> np.ndarray | None:
    if region.sample is not None and region.sample.image is not None:
        return np.asarray(region.sample.image)
    if result.roi_aligned_image is not None:
        return result.roi_aligned_image
    return result.roi_image


def _extract_heatmap_for_upload(result: CameraInspectionResult) -> np.ndarray | None:
    """从检测结果中提取原始热力图，作为无 overlay 时的兼容兜底。"""
    if result.texture_result is not None and result.texture_result.heatmap is not None:
        return result.texture_result.heatmap
    return None


def _extract_anomaly_crop(result: CameraInspectionResult) -> list[np.ndarray]:
    """利用热力图定位异常高响应区域，从 ROI 图中裁剪出异常部位。

    一张图可能存在多处缺陷 → 提取热力图中所有显著连通域，
    按面积降序排列。regions 模式下遍历所有 NG region 各自裁剪。

    Returns:
        异常区域 BGR 裁剪图列表（按面积降序，跨 region 合并）。
    """
    all_crops: list[np.ndarray] = []

    # 完整 ROI 模式：heatmap + roi_aligned_image 同坐标系
    if (
        result.texture_result is not None
        and result.texture_result.heatmap is not None
    ):
        heatmap = np.asarray(result.texture_result.heatmap, dtype=np.float32)
        crop_base = (
            result.roi_aligned_image
            if result.roi_aligned_image is not None
            else result.roi_image
        )
        if crop_base is not None:
            all_crops.extend(_crop_by_heatmap(heatmap, crop_base))

    # regions 模式：遍历所有 NG region，各自从其热力图和局部图像中裁剪
    elif result.region_results:
        ng_regions = [
            r for r in result.region_results
            if r.status == "NG" and r.texture_result is not None and r.texture_result.heatmap is not None
        ]
        for region in ng_regions:
            heatmap = np.asarray(region.texture_result.heatmap, dtype=np.float32)
            crop_base = (
                np.asarray(region.sample.image)
                if region.sample is not None and region.sample.image is not None
                else (
                    result.roi_aligned_image
                    if result.roi_aligned_image is not None
                    else result.roi_image
                )
            )
            if heatmap is not None and crop_base is not None:
                all_crops.extend(_crop_by_heatmap(heatmap, crop_base))

    return all_crops


def _crop_by_heatmap(
    heatmap: np.ndarray,
    image: np.ndarray,
    *,
    threshold_ratio: float = 0.2,
    padding_ratio: float = 0.1,
    min_crop_size: int = 20,
    min_component_area: int = 4,
) -> list[np.ndarray]:
    """按热力图高响应连通域裁剪图像，支持多异常区域。

    PatchCore 热力图通常是高度局部化的尖锐热点，阈值取 max*0.2 保留
    高响应区域，配合 10% 外扩兼顾精度与 embedding 模型所需的上下文。

    Args:
        heatmap: 浮点热力图 (H, W)
        image: BGR 图像 (H, W, 3)，与 heatmap 同坐标系
        threshold_ratio: 阈值 = max * ratio（默认 0.2）
        padding_ratio: 裁剪框外扩比例（默认 0.1）
        min_crop_size: 最小裁剪边长 (px)
        min_component_area: 连通域最小面积 (px)

    Returns:
        裁剪后的 BGR 图像列表（按连通域面积降序）；热力图无明显热点时返回空列表
    """
    # 归一化到 0-1
    h_min = float(heatmap.min())
    h_max = float(heatmap.max())
    if h_max - h_min < 1e-8:
        return []

    normalized = (heatmap - h_min) / (h_max - h_min)

    # 对齐 heatmap 与 image 尺寸
    if normalized.shape[:2] != image.shape[:2]:
        normalized = cv2.resize(
            normalized,
            (image.shape[1], image.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )

    components = _find_components(normalized, threshold_ratio, min_component_area)
    # 若标准阈值没有结果，用更宽松的阈值重试
    if not components:
        components = _find_components(normalized, threshold_ratio * 0.5, max(2, min_component_area // 2))

    # 裁剪每个分量
    crops: list[np.ndarray] = []
    img_h, img_w = image.shape[:2]
    for _area, x, y, w, h in components:
        pad_w = max(1, int(w * padding_ratio))
        pad_h = max(1, int(h * padding_ratio))

        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(img_w, x + w + pad_w)
        y2 = min(img_h, y + h + pad_h)

        if (x2 - x1) < min_crop_size or (y2 - y1) < min_crop_size:
            continue

        crops.append(image[y1:y2, x1:x2])

    return crops


def _find_components(
    normalized: np.ndarray,
    threshold_ratio: float,
    min_area: int,
) -> list[tuple[int, int, int, int, int]]:
    """在归一化热力图中查找所有显著连通域，返回 (area, x, y, w, h) 列表。"""
    threshold = max(float(normalized.max()) * threshold_ratio, 0.03)
    binary = (normalized >= threshold).astype(np.uint8)

    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if num_labels <= 1:
        return []

    components: list[tuple[int, int, int, int, int]] = []
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if area < min_area:
            continue
        components.append((int(area), int(x), int(y), int(w), int(h)))

    components.sort(key=lambda c: c[0], reverse=True)
    return components


def _encode_heatmap(heatmap: np.ndarray) -> bytes:
    """将 2D 热力图 float 数组编码为伪彩色 PNG。"""
    normalized = np.zeros_like(heatmap, dtype=np.float32)
    h_min = float(heatmap.min())
    h_max = float(heatmap.max())
    if h_max - h_min > 1e-8:
        normalized = ((heatmap - h_min) / (h_max - h_min) * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(heatmap, dtype=np.uint8)
    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    success, encoded = cv2.imencode(".png", colored)
    if not success:
        raise ValueError("热力图编码失败")
    return encoded.tobytes()


def _encode_bgr_image(image: np.ndarray, ext: str = ".jpg") -> bytes:
    """将 BGR numpy 图像编码为 JPEG/PNG 字节。"""
    normalized = _normalize_bgr_image(image)
    success, encoded = cv2.imencode(ext, normalized)
    if not success:
        raise ValueError("图像编码失败")
    return encoded.tobytes()


def _normalize_bgr_image(image: np.ndarray) -> np.ndarray:
    """Normalize grayscale/BGRA arrays to BGR before storage."""
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


__all__ = [
    "upload_camera_result",
    "upload_inspection_response",
]
