"""批量训练多机位 EfficientAD 模型。

从按机位组织的正常图像目录中，批量训练 EfficientAD 模型。

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
from pathlib import Path
from typing import Optional


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

    return {"status": "completed" if not failed else "partial", "results": results}


def _build_training_tasks(
    config,
    good_root: Path,
    output_root: Path,
    cameras: Optional[list[str]],
) -> list[dict]:
    """从配置和目录结构构建训练任务列表。"""
    tasks: list[dict] = []

    # 收集所有 camera config
    camera_configs: list = []
    if config.cameras:
        camera_configs.extend(config.cameras)
    for sm in getattr(config, "seat_models", []) or []:
        camera_configs.extend(getattr(sm, "cameras", []) or [])

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


__all__ = ["batch_train_all", "batch_train_cli"]
