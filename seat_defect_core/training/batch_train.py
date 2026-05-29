"""批量训练多机位 EfficientAD 模型。

从按机位组织的正常图像目录中，批量训练 EfficientAD 模型，
同时自动计算 CameraNormalizer + EmbeddingProjector 校准参数。

目录结构要求：
    <good_images_root>/
      <camera_id>/
        good/              # 全 ROI 正常图像
          *.jpg

用法：
    # CLI
    python -m seat_defect_core batch-train \\
      --config config.best.json \\
      --good-images-root ./training_data/ \\
      --output-root ./models/seat_model_a/

    # Python SDK
    from seat_defect_core.training.batch_train import batch_train_all
    batch_train_all("config.best.json", "./training_data/", "./models/")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from seat_defect_core.efficientad.engine import IMAGENET_MEAN, IMAGENET_STD

_logger = logging.getLogger(__name__)


def batch_train_all(
    config_path: str,
    good_images_root: str,
    output_root: str,
    *,
    cameras: Optional[list[str]] = None,
    mlflow_tracking_uri: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """批量为配置中的所有机位训练 EfficientAD 模型。

    Args:
        config_path: 检测配置文件路径。
        good_images_root: 正常图像根目录，按 camera_id/good/ 组织。
        output_root: 模型输出根目录。
        cameras: 限定要训练的机位列表，为 None 则训练全部。
        mlflow_tracking_uri: MLflow tracking URI。
        dry_run: True 时只打印训练计划，不实际训练。

    Returns:
        dict: {status, results: [{camera_id, status, artifact_path, image_threshold}]}
    """
    from seat_defect_core.config import InspectionConfig
    from seat_defect_core.api import resolve_config

    config = resolve_config(config_path) if isinstance(config_path, str) else config_path
    if not isinstance(config, InspectionConfig):
        raise TypeError(f"配置类型错误: {type(config)}")

    good_root = Path(good_images_root)
    if not good_root.is_dir():
        raise FileNotFoundError(f"正常图像根目录不存在: {good_images_root}")

    output_root_path = Path(output_root)
    output_root_path.mkdir(parents=True, exist_ok=True)

    # 收集所有待训练任务
    from seat_defect_core.training.efficientad import train_efficientad

    training_tasks: list[dict] = _build_training_tasks(config, good_root, output_root_path, cameras)

    if not training_tasks:
        raise RuntimeError("未找到可训练的机位——请检查 good-images-root 目录结构")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}发现 {len(training_tasks)} 个训练任务:")
    for task in training_tasks:
        print(f"  - camera={task['camera_id']}: {task['image_count']} 张正常图像")

    if dry_run:
        return {"status": "dry_run", "tasks": training_tasks}

    # 逐任务训练
    results: list[dict] = []
    total = len(training_tasks)
    for i, task in enumerate(training_tasks):
        camera_id = task["camera_id"]

        print(f"\n{'='*60}")
        print(f"[{i+1}/{total}] 训练 {camera_id} ({task['image_count']} 张图像)")
        print(f"{'='*60}")

        try:
            result = train_efficientad(
                config=config,
                camera_id=camera_id,
                good_image_paths=task["image_paths"],
                output_path=task["output_path"],
                mlflow_tracking_uri=mlflow_tracking_uri,
                mlflow_experiment="efficientad",
            )
            result["camera_id"] = camera_id
            results.append(result)
            print(f"  结果: {result['status']}, threshold={result['image_threshold']}")
        except Exception as e:
            print(f"  失败: {e}")
            results.append({
                "camera_id": camera_id,
                "status": "failed",
                "error": str(e),
            })

    # 汇总
    succeeded = [r for r in results if r.get("status") == "completed"]
    failed = [r for r in results if r.get("status") != "completed"]

    print(f"\n训练完成: {len(succeeded)} 成功, {len(failed)} 失败")
    if succeeded:
        print("成功模型:")
        for r in succeeded:
            print(f"  {r['camera_id']}: {r['artifact_path']}")
    if failed:
        print("失败任务:")
        for r in failed:
            print(f"  {r['camera_id']}: {r.get('error', 'unknown')}")

    # ── 自动计算 Calibration Stats ──
    calibration_result = {}
    if succeeded:
        try:
            calibration_result = _compute_calibration_stats(
                config=config,
                good_root=good_root,
                output_root=output_root_path,
                training_results={r["camera_id"]: r for r in succeeded},
            )
        except Exception:
            _logger.warning("calibration_compute_failed", exc_info=True)

    return {
        "status": "completed" if not failed else "partial",
        "results": results,
        "calibration": calibration_result,
    }


def _build_training_tasks(
    config,
    good_root: Path,
    output_root: Path,
    cameras: Optional[list[str]],
) -> list[dict]:
    """从配置和目录结构构建训练任务列表。"""
    tasks: list[dict] = []

    # 收集所有 camera config
    camera_configs: list = _collect_all_cameras(config)

    for cam in camera_configs:
        if not cam.enabled:
            continue
        if cameras and cam.camera_id not in cameras:
            continue

        cam_good_dir = good_root / cam.camera_id

        full_img_dir = cam_good_dir / "good"
        if not full_img_dir.is_dir():
            print(f"  跳过 {cam.camera_id}: 目录不存在 {full_img_dir}")
            continue

        image_paths = _collect_images(full_img_dir)
        if len(image_paths) < 2:
            print(f"  跳过 {cam.camera_id}: 图像不足 ({len(image_paths)} 张)")
            continue

        output_path = output_root / f"{cam.camera_id}_efficientad.pt"

        tasks.append({
            "camera_id": cam.camera_id,
            "image_paths": image_paths,
            "image_count": len(image_paths),
            "output_path": str(output_path),
        })

    return tasks


def _collect_images(directory: Path) -> list[str]:
    """收集目录中的所有图像文件路径。"""
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
    paths: list[str] = []
    for ext in extensions:
        for p in directory.glob(ext):
            paths.append(str(p))
    return sorted(paths)


def batch_train_cli() -> None:
    """CLI 入口：批量训练 EfficientAD 模型。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="批量训练多机位 EfficientAD 模型"
    )
    parser.add_argument("--config", required=True, help="检测配置文件路径 (JSON)")
    parser.add_argument(
        "--good-images-root",
        required=True,
        help="正常图像根目录（结构: <root>/<camera_id>/good/*.jpg）",
    )
    parser.add_argument("--output-root", required=True, help="模型输出根目录")
    parser.add_argument("--cameras", default=None, help="限定训练机位，逗号分隔，不传则全部训练")
    parser.add_argument("--mlflow-uri", default=None, help="MLflow tracking URI")
    parser.add_argument("--dry-run", action="store_true", help="只打印训练计划不执行")

    args = parser.parse_args()

    cameras_list = (
        [c.strip() for c in args.cameras.split(",") if c.strip()]
        if args.cameras
        else None
    )

    result = batch_train_all(
        config_path=args.config,
        good_images_root=args.good_images_root,
        output_root=args.output_root,
        cameras=cameras_list,
        mlflow_tracking_uri=args.mlflow_uri,
        dry_run=args.dry_run,
    )

    print("\n" + json.dumps(result, ensure_ascii=False, indent=2, default=str))


class _CalibrationDataset(Dataset):
    """标定特征提取用的图像 Dataset，完成 BGR→RGB、resize、ImageNet normalize。"""

    def __init__(self, image_paths: list[str], input_size: int) -> None:
        self.image_paths = image_paths
        self.input_size = input_size

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> torch.Tensor:
        img_path = self.image_paths[idx]
        img = cv2.imread(img_path)
        if img is None:
            return torch.zeros(3, self.input_size, self.input_size)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.input_size, self.input_size))
        img = img.astype(np.float32) / 255.0
        img = (img - IMAGENET_MEAN) / IMAGENET_STD
        return torch.from_numpy(img).permute(2, 0, 1)


def _compute_calibration_stats(
    config,
    good_root: Path,
    output_root: Path,
    training_results: dict[str, dict],
) -> dict:
    """在训练完成后自动计算 CameraNormalizer + EmbeddingProjector。

    使用同一批 good/*.jpg 正常图像，通过训练好的 EfficientAD 模型
    批量提取特征，拟合 per-camera 标准化参数和跨机位 PCA 投影矩阵。
    GPU 可用时自动使用 GPU 加速，比 CPU 逐张推理快 10-50×。
    """
    from seat_defect_core.efficientad import EfficientADService
    from seat_defect_core.efficientad.config import EfficientADConfig
    from seat_defect_core.calibration import CameraNormalizer, EmbeddingProjector

    # 构建 camera_id → (model_path, input_size) 映射
    camera_model_map: dict[str, tuple[str, int]] = {}
    for cam in _collect_all_cameras(config):
        if cam.camera_id in training_results:
            input_size = getattr(cam.efficientad, "input_size", 256) if cam.efficientad else 256
            camera_model_map[cam.camera_id] = (
                training_results[cam.camera_id]["artifact_path"],
                input_size,
            )

    if not camera_model_map:
        return {"status": "skipped", "reason": "no_trained_models"}

    device_str = "cuda" if torch.cuda.is_available() else "cpu"
    calib_batch_size = 32

    # GPU 性能优化
    if device_str == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    print(f"\n{'='*60}")
    print(f"计算 CameraNormalizer + EmbeddingProjector (device={device_str}, batch={calib_batch_size})...")
    print(f"{'='*60}")

    camera_features: dict[str, list[dict[str, np.ndarray]]] = {}
    camera_normalizers: dict[str, CameraNormalizer] = {}

    for camera_id, (model_path, input_size) in camera_model_map.items():
        cam_good_dir = good_root / camera_id / "good"
        if not cam_good_dir.is_dir():
            print(f"  跳过 {camera_id}: 目录不存在 {cam_good_dir}")
            continue

        image_paths = _collect_images(cam_good_dir)
        if len(image_paths) < 5:
            print(f"  跳过 {camera_id}: 图像不足 ({len(image_paths)} 张)")
            continue

        print(f"\n  处理 {camera_id} ({len(image_paths)} 张图像)...")

        # 加载训练好的模型（特征提取用 GPU 加速）
        ead_config = EfficientADConfig(model_path=model_path, device=device_str)
        service = EfficientADService(ead_config)

        if not service.has_features:
            print(f"  跳过 {camera_id}: 特征模型不可用")
            continue

        # torch.compile 加速特征提取（PyTorch 2.0+，减少 kernel launch 开销）
        if device_str == "cuda" and hasattr(torch, "compile"):
            try:
                service._feature_model = torch.compile(
                    service._feature_model,
                    mode="reduce-overhead",
                )
                print("    torch.compile 已启用 (mode=reduce-overhead)")
            except Exception:
                pass

        # DataLoader 批量加载 + 预处理
        dataset = _CalibrationDataset(image_paths, input_size)
        dataloader = DataLoader(
            dataset,
            batch_size=calib_batch_size,
            num_workers=4,
            pin_memory=(device_str == "cuda"),
        )

        # 增量拟合 CameraNormalizer（Welford 算法，无需在内存中累积全部特征）
        normalizer = CameraNormalizer()
        features_list: list[dict[str, np.ndarray]] = []
        processed = 0
        for batch in dataloader:
            batch = batch.to(service.device)
            try:
                batch_features = service.extract_features_batch(batch)
                if batch_features is not None:
                    for feats in batch_features:
                        normalizer.update(feats)  # 增量更新 mean/std
                    features_list.extend(batch_features)
            except Exception:
                _logger.warning("calibration_batch_extract_failed", exc_info=True)

            processed += batch.shape[0]
            if processed % 100 == 0 or processed >= len(image_paths):
                print(f"    已处理 {min(processed, len(image_paths))}/{len(image_paths)}...")

        if len(features_list) < 5:
            print(f"  跳过 {camera_id}: 有效特征不足 ({len(features_list)} 组)")
            continue

        camera_features[camera_id] = features_list
        camera_normalizers[camera_id] = normalizer

        norm_path = output_root / f"{camera_id}_norm.npz"
        normalizer.save(str(norm_path))
        print(f"  已保存: {norm_path}")

    if len(camera_features) < 1:
        return {"status": "skipped", "reason": "insufficient_features"}

    # 拟合 EmbeddingProjector（在归一化特征上）
    print(f"\n  拟合 EmbeddingProjector（跨 {len(camera_features)} 个机位）...")
    all_normalized: list[dict[str, np.ndarray]] = []
    for cam_id, feats_list in camera_features.items():
        normalizer = camera_normalizers[cam_id]
        for feats in feats_list:
            all_normalized.append(normalizer.normalize(feats))
        # 释放该机位的原始特征以节省内存，只保留归一化后的向量
        camera_features[cam_id] = []

    projector = EmbeddingProjector.fit(all_normalized, output_dim=384)
    projector_path = output_root / "projector.npz"
    projector.save(str(projector_path))
    print(f"  已保存: {projector_path}")

    norm_paths = {
        cam_id: str(output_root / f"{cam_id}_norm.npz")
        for cam_id in camera_normalizers
    }

    print("\n  Calibration stats 计算完成:")
    for cam_id, path in norm_paths.items():
        print(f"    {cam_id}: {path}")
    print(f"    projector: {projector_path}")

    return {
        "status": "completed",
        "camera_norms": norm_paths,
        "projector_path": str(projector_path),
    }


def _collect_all_cameras(config) -> list:
    """收集配置中所有 camera config。"""
    all_cameras: list = list(getattr(config, "cameras", []) or [])
    for sm in getattr(config, "seat_models", []) or []:
        all_cameras.extend(getattr(sm, "cameras", []) or [])
    return all_cameras


__all__ = ["batch_train_all", "batch_train_cli"]
