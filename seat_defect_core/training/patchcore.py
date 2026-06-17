"""PatchCore 模型训练。

复用 seat_defect_core 的核心模块（features.py, scoring.py, engine.py），
从正常参考图像中训练 PatchCore 异常检测模型并保存为 .npz 文件。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Sequence

import cv2
import numpy as np

try:
    import faiss
except ImportError:  # 回退：FAISS 不可用时降级为 numpy 暴力搜索
    faiss = None

PatchCoreInputMode = Literal["roi", "online"]


@dataclass(frozen=True)
class PatchCoreTrainingSample:
    """PatchCore 训练实际消费的一张样本。"""

    image: np.ndarray
    target_mask: np.ndarray
    ignore_mask: np.ndarray
    source_path: str
    region_id: str | None = None


def train_patchcore(
    config: object,
    camera_id: str,
    good_image_paths: Sequence[str | Path],
    output_path: str,
    *,
    input_mode: PatchCoreInputMode = "roi",
    region_id: str | None = None,
) -> dict:
    """训练 PatchCore 模型。

    Args:
        config: seat_defect_core 的 InspectionConfig 或 JSON 配置文件路径。
        camera_id: 目标相机 ID，从配置中提取对应相机的 PatchCore 参数。
        good_image_paths: 正常（无缺陷）参考图像路径列表。
        output_path: 输出 .npz 文件路径。
        input_mode: roi 表示样本已是标准 ROI；online 表示按线上 YOLO→ROI→mask 流程准备。
        region_id: online 模式下可指定训练某个局部区域模型。

    Returns:
        dict: {memory_bank_size, total_embeddings, threshold, artifact_path, skipped_by_reason}
    """
    from ..config import (
        InspectionConfig,
        PatchCoreConfig,
    )
    from ..config_file import resolve_config
    from ..patchcore.features import _TorchPatchFeatureExtractor
    from ..patchcore.scoring import _determine_memory_bank_size, coreset_subsample_indices

    # 解析配置
    if isinstance(config, (str, Path)):
        inspection_cfg = resolve_config(str(config))
    elif isinstance(config, InspectionConfig):
        inspection_cfg = config
    else:
        raise TypeError(f"config 类型不支持: {type(config)}")

    # 查找目标相机
    camera_config = _find_camera(inspection_cfg, camera_id)
    if camera_config is None:
        available = _list_camera_ids(inspection_cfg)
        raise ValueError(f"未找到相机 '{camera_id}'，可用相机: {available}")

    patchcore_cfg: PatchCoreConfig = camera_config.patchcore
    if patchcore_cfg is None:
        raise ValueError(f"相机 '{camera_id}' 未配置 patchcore 参数")
    region_config = _find_region(camera_config, region_id)
    if region_id is not None and region_config is None:
        available = ", ".join(region.region_id for region in camera_config.regions)
        raise ValueError(f"未找到区域 '{region_id}'，可用区域: {available or 'none'}")
    if region_config is not None and region_config.patchcore is not None:
        patchcore_cfg = region_config.patchcore

    # 构建特征提取器（复用 seat_defect_core 的核心实现）
    extractor = _TorchPatchFeatureExtractor(patchcore_cfg)

    # 逐张提取 embedding
    all_embeddings: list[np.ndarray] = []
    skipped_by_reason: Counter[str] = Counter()
    for img_path in good_image_paths:
        img_path = Path(img_path)
        if not img_path.exists():
            skipped_by_reason["image_missing"] += 1
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            skipped_by_reason["image_read_failed"] += 1
            continue
        samples, skipped_reason = prepare_patchcore_training_samples(
            img,
            camera_config,
            input_mode=input_mode,
            region_id=region_id,
            source_path=str(img_path),
        )
        if skipped_reason is not None:
            skipped_by_reason[skipped_reason] += 1
            continue
        for sample in samples:
            try:
                embeddings, _patch_batch = extractor.extract(
                    sample.image,
                    target_mask=sample.target_mask,
                    ignore_mask=sample.ignore_mask,
                )
                if embeddings.shape[0] > 0:
                    all_embeddings.append(embeddings)
                else:
                    skipped_by_reason["empty_embeddings"] += 1
            except Exception:
                skipped_by_reason["embedding_extract_failed"] += 1

    if not all_embeddings:
        raise RuntimeError(f"未能从参考图像中提取到有效 embedding: {len(good_image_paths)} 张图片")

    merged = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    total_embeddings = merged.shape[0]

    # coreset 子采样 → memory bank
    max_points = _determine_memory_bank_size(merged, patchcore_cfg)
    chosen = coreset_subsample_indices(merged, max_points)
    memory_bank = merged[chosen].copy()

    # 计算归一化统计量
    feature_mean = memory_bank.mean(axis=0).astype(np.float32)
    feature_std = memory_bank.std(axis=0).astype(np.float32)
    feature_std[feature_std < 1e-6] = 1.0

    # 构建 FAISS 索引，加速推理时的最近邻搜索
    faiss_index_bytes = b""
    if faiss is not None:
        normalized_bank = (memory_bank - feature_mean) / feature_std
        dim = int(normalized_bank.shape[1])
        index = faiss.IndexFlatL2(dim)
        index.add(normalized_bank.astype(np.float32))
        # 将 FAISS 索引序列化为 bytes，写入 npz
        try:
            faiss_index_bytes = faiss.serialize_index(index)
        except Exception:
            faiss_index_bytes = b""

    # 用每张正常图像的 image-level score 分布确定阈值
    # image-level score = 每张图所有有效 patch 距离的 99 分位
    image_scores: list[float] = []
    for img_embeddings in all_embeddings:
        if img_embeddings.shape[0] == 0:
            continue
        normalized = ((img_embeddings - feature_mean) / feature_std).astype(np.float32)
        patch_distances = _compute_min_distances(normalized, normalized)
        if len(patch_distances) > 0:
            image_score = float(np.percentile(patch_distances, 99))
            image_scores.append(image_score)

    if not image_scores:
        raise RuntimeError("无法计算图像级分数，训练样本不足以确定阈值")

    image_scores_arr = np.asarray(image_scores, dtype=np.float32)
    threshold = float(np.quantile(image_scores_arr, patchcore_cfg.threshold_quantile))
    # 鲁棒上界：防止阈值被个别极端正常样本拉高
    upper_quantile = float(
        np.clip(getattr(patchcore_cfg, "training_threshold_upper_quantile", 0.999), 0.9, 1.0)
    )
    threshold = max(
        threshold,
        float(np.quantile(image_scores_arr, upper_quantile)),
        float(image_scores_arr.mean() + 3.0 * image_scores_arr.std()),
    )

    # 保存 .npz（格式与 PatchCoreService.load_bundle 兼容）
    meta = {
        "backend": str(patchcore_cfg.backend),
        "backbone_name": str(patchcore_cfg.backbone_name),
        "backbone_device": str(patchcore_cfg.backbone_device),
        "backbone_pretrained": bool(patchcore_cfg.backbone_pretrained),
        "backbone_weights_path": patchcore_cfg.backbone_weights_path,
        "image_size": int(patchcore_cfg.image_size),
        "patch_size": int(patchcore_cfg.patch_size),
        "stride": int(patchcore_cfg.stride),
        "max_memory": int(patchcore_cfg.max_memory),
        "threshold": float(threshold),
        "threshold_quantile": float(patchcore_cfg.threshold_quantile),
        "training_threshold_upper_quantile": float(
            getattr(patchcore_cfg, "training_threshold_upper_quantile", 0.999)
        ),
        "texture_input": str(patchcore_cfg.texture_input),
        "input_mode": input_mode,
        "region_id": region_id,
        "feature_layers": list(patchcore_cfg.feature_layers),
        "feature_pool_kernel_size": int(patchcore_cfg.feature_pool_kernel_size),
        "coreset_sampling_ratio": float(patchcore_cfg.coreset_sampling_ratio),
        "min_target_coverage": float(patchcore_cfg.min_target_coverage),
        "max_ignore_overlap": float(patchcore_cfg.max_ignore_overlap),
        "min_valid_patch_ratio": float(patchcore_cfg.min_valid_patch_ratio),
        "decision_score_margin": float(patchcore_cfg.decision_score_margin),
        "strong_patch_score_ratio": float(patchcore_cfg.strong_patch_score_ratio),
        "min_strong_patch_count": int(patchcore_cfg.min_strong_patch_count),
        "min_strong_component_count": int(patchcore_cfg.min_strong_component_count),
        "min_strong_patch_ratio": float(patchcore_cfg.min_strong_patch_ratio),
        "min_strong_component_ratio": float(patchcore_cfg.min_strong_component_ratio),
        "critical_score_margin": float(patchcore_cfg.critical_score_margin),
        "critical_peak_score_margin": float(patchcore_cfg.critical_peak_score_margin),
        "critical_min_component_patch_count": int(patchcore_cfg.critical_min_component_patch_count),
        "min_peak_component_patch_count": int(patchcore_cfg.min_peak_component_patch_count),
        # 训练诊断信息
        "train_image_count": int(len(image_scores)),
        "skipped_by_reason": dict(skipped_by_reason),
        "threshold_image_score_mean": float(image_scores_arr.mean()),
        "threshold_image_score_std": float(image_scores_arr.std()),
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(output),
        meta_json=np.array([json.dumps(meta)], dtype=object),
        memory_bank=memory_bank,
        feature_mean=feature_mean,
        feature_std=feature_std,
        faiss_index=np.frombuffer(faiss_index_bytes, dtype=np.uint8),
        color_profile_json=np.array([""], dtype=object),
    )

    return {
        "memory_bank_size": int(memory_bank.shape[0]),
        "total_embeddings": int(total_embeddings),
        "threshold": float(threshold),
        "artifact_path": str(output),
        "input_mode": input_mode,
        "region_id": region_id,
        "skipped_by_reason": dict(skipped_by_reason),
    }


def prepare_patchcore_training_samples(
    image: np.ndarray,
    camera_config,
    *,
    input_mode: PatchCoreInputMode = "roi",
    region_id: str | None = None,
    detection_result=None,
    source_path: str = "",
) -> tuple[list[PatchCoreTrainingSample], str | None]:
    """把训练图准备成 PatchCore 与线上同源的 image/mask 输入。

    返回 `(samples, skipped_reason)`；当 `skipped_reason` 非空时表示整张图不可用于训练。
    """
    normalized_mode = input_mode.strip().lower()
    if normalized_mode == "roi":
        if region_id is not None:
            return [], "region_requires_online_mode"
        height, width = image.shape[:2]
        return [
            PatchCoreTrainingSample(
                image=image,
                target_mask=np.ones((height, width), dtype=np.uint8),
                ignore_mask=np.zeros((height, width), dtype=np.uint8),
                source_path=source_path,
            )
        ], None
    if normalized_mode != "online":
        return [], f"unsupported_input_mode:{input_mode}"

    from ..cvops import ImageQualityGuard, RoiRefineEngine, split_roi_regions
    from ..util import select_patchcore_input

    if detection_result is None:
        from ..yolo import DetectionService
        detection_result = DetectionService(camera_config.detection).detect(image)
    if detection_result.target is None:
        return [], "target_not_found"
    if detection_result.target.segmentation_mask is None:
        return [], "target_mask_missing"

    try:
        roi = RoiRefineEngine(camera_config.roi).refine(image, detection_result)
    except ValueError as exc:
        return [], str(exc)

    quality = ImageQualityGuard(camera_config.quality).evaluate(
        roi.aligned_roi_image,
        valid_mask=roi.valid_mask,
    )
    if not quality.accepted:
        return [], f"quality_{quality.reason or 'rejected'}"

    if region_id is not None:
        samples = [
            region_sample
            for region_sample in split_roi_regions(roi, camera_config.regions)
            if region_sample.region_id == region_id
        ]
        if not samples:
            return [], "region_empty"
        return [
            PatchCoreTrainingSample(
                image=sample.image,
                target_mask=sample.target_mask,
                ignore_mask=sample.ignore_mask,
                source_path=source_path,
                region_id=sample.region_id,
            )
            for sample in samples
        ], None

    patchcore_input = select_patchcore_input(roi)
    return [
        PatchCoreTrainingSample(
            image=patchcore_input,
            target_mask=roi.target_mask,
            ignore_mask=roi.ignore_mask,
            source_path=source_path,
        )
    ], None


def train_patchcore_cli() -> None:
    """CLI 入口：由 seat_defect_core.__main__ 调用。"""
    import argparse

    parser = argparse.ArgumentParser(description="训练 PatchCore 模型")
    parser.add_argument("--config", required=True, help="检测配置文件路径 (JSON/INI)")
    parser.add_argument("--camera-id", required=True, help="目标相机 ID")
    parser.add_argument("--good-images", required=True, help="正常参考图像目录")
    parser.add_argument("--output", required=True, help="输出 .npz 文件路径")
    parser.add_argument(
        "--input-mode",
        choices=("roi", "online"),
        default="roi",
        help="训练样本输入模式：roi=已裁标准ROI，online=复用线上YOLO/ROI/mask流程",
    )
    parser.add_argument("--region-id", default=None, help="online 模式下训练指定局部区域")

    args = parser.parse_args()

    img_dir = Path(args.good_images)
    if not img_dir.is_dir():
        raise FileNotFoundError(f"图像目录不存在: {args.good_images}")

    image_paths: list[str] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(str(p) for p in img_dir.glob(ext))
    if not image_paths:
        raise FileNotFoundError(f"目录中未找到图像文件: {args.good_images}")

    result = train_patchcore(
        config=args.config,
        camera_id=args.camera_id,
        good_image_paths=image_paths,
        output_path=args.output,
        input_mode=args.input_mode,
        region_id=args.region_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _find_camera(inspection_cfg, camera_id: str):
    """在配置中查找指定相机。"""

    # 直接相机列表
    for cam in getattr(inspection_cfg, "cameras", []) or []:
        if cam.camera_id == camera_id:
            return cam
    # 座椅型号下的相机列表
    seat_models: list = getattr(inspection_cfg, "seat_models", []) or []
    for sm in seat_models:
        for cam in getattr(sm, "cameras", []) or []:
            if cam.camera_id == camera_id:
                return cam
    return None


def _find_region(camera_config, region_id: str | None):
    if region_id is None:
        return None
    for region in getattr(camera_config, "regions", []) or []:
        if region.region_id == region_id:
            return region
    return None


def _list_camera_ids(inspection_cfg) -> list[str]:
    """列出配置中所有相机 ID。"""
    ids: list[str] = []
    for cam in getattr(inspection_cfg, "cameras", []) or []:
        ids.append(cam.camera_id)
    for sm in getattr(inspection_cfg, "seat_models", []) or []:
        for cam in getattr(sm, "cameras", []) or []:
            ids.append(cam.camera_id)
    return ids


def _compute_min_distances(embeddings: np.ndarray, bank: np.ndarray) -> np.ndarray:
    """计算每个 embedding 到 memory bank 的最小欧氏距离。"""
    dists: list[np.ndarray] = []
    chunk_size = 256
    for i in range(0, embeddings.shape[0], chunk_size):
        chunk = embeddings[i : i + chunk_size]
        diff = chunk[:, None, :] - bank[None, :, :]
        dists.append(np.sqrt((diff ** 2).sum(axis=2)).min(axis=1))
    return np.concatenate(dists)
