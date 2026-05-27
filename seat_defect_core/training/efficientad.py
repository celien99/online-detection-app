"""EfficientAD 模型训练。

基于 anomalib 的 EfficientAD 实现，从正常参考图像训练异常检测模型。
训练完成后自动计算最优阈值并记录 MLflow 实验。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Sequence

import cv2
import numpy as np
import torch


def train_efficientad(
    config: object,
    camera_id: str,
    good_image_paths: Sequence[str | Path],
    output_path: str,
    *,
    mlflow_tracking_uri: Optional[str] = None,
    mlflow_experiment: str = "efficientad",
) -> dict:
    """训练 EfficientAD 模型并导出 TorchScript。

    Args:
        config: InspectionConfig 或 JSON 配置文件路径。
        camera_id: 目标相机 ID。
        good_image_paths: 正常参考图像路径列表。
        output_path: 输出 .pt 文件路径。
        mlflow_tracking_uri: MLflow tracking URI，为 None 则不记录。
        mlflow_experiment: MLflow 实验名称。

    Returns:
        dict: {status, artifact_path, image_threshold, pixel_threshold, train_image_count, mlflow_run_id}
    """
    from ..config import InspectionConfig
    from ..api import resolve_config

    # 解析配置
    if isinstance(config, (str, Path)):
        inspection_cfg = resolve_config(str(config))
    elif isinstance(config, InspectionConfig):
        inspection_cfg = config
    else:
        raise TypeError(f"config 类型不支持: {type(config)}")

    camera_config = _find_camera(inspection_cfg, camera_id)
    if camera_config is None:
        available = _list_camera_ids(inspection_cfg)
        raise ValueError(f"未找到相机 '{camera_id}'，可用相机: {available}")

    efficientad_cfg = camera_config.efficientad
    if efficientad_cfg is None:
        raise ValueError(f"相机 '{camera_id}' 未配置 efficientad 参数")

    # 加载正常图像
    images: list[np.ndarray] = []
    for img_path in good_image_paths:
        img_path = Path(img_path)
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is not None:
            images.append(img)

    if len(images) < 2:
        raise RuntimeError(f"正常参考图像不足 ({len(images)} 张)，至少需要 2 张")

    device = _resolve_train_device(efficientad_cfg.device)

    # 使用 anomalib 训练
    try:
        from anomalib.data import MVTec
        from anomalib.models import EfficientAd
        from anomalib.engine import Engine
    except ImportError:
        raise RuntimeError(
            "EfficientAD 训练依赖 anomalib 库，请安装: pip install anomalib"
        )

    import tempfile
    import shutil

    # MLflow 初始化
    mlflow_run_id: Optional[str] = None
    mlflow = _init_mlflow(mlflow_tracking_uri, mlflow_experiment)

    tmp_dir = Path(tempfile.mkdtemp(prefix="efficientad_train_"))
    t_start = time.monotonic()
    try:
        # anomalib MVTec 格式: {category}/train/good/ + {category}/test/good/ (用于阈值计算)
        category = camera_id.replace(" ", "_")
        good_dir = tmp_dir / category / "train" / "good"
        good_dir.mkdir(parents=True, exist_ok=True)

        # 划分训练集和阈值计算集 (90/10)
        split_idx = max(1, int(len(images) * (1.0 - efficientad_cfg.validation_split)))
        train_images = images[:split_idx]
        threshold_images = images[split_idx:] if split_idx < len(images) else images[:1]

        for i, img in enumerate(train_images):
            cv2.imwrite(str(good_dir / f"{i:04d}.png"), img)

        # 创建测试集目录用于 anomalib 验证
        test_good_dir = tmp_dir / category / "test" / "good"
        test_good_dir.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(threshold_images):
            cv2.imwrite(str(test_good_dir / f"{i:04d}.png"), img)

        # 配置 anomalib 模型
        model = EfficientAd(
            teacher_out_channels=384,
            model_size="medium",
        )

        # 训练
        engine = Engine(
            max_epochs=efficientad_cfg.epochs,
            devices=1 if device.type != "cpu" else 0,
            accelerator="gpu" if device.type == "cuda" else "cpu",
            default_root_dir=str(tmp_dir / "results"),
        )

        datamodule = MVTec(
            root=str(tmp_dir),
            category=category,
            image_size=(efficientad_cfg.input_size, efficientad_cfg.input_size),
            train_batch_size=efficientad_cfg.batch_size,
            eval_batch_size=efficientad_cfg.batch_size,
            num_workers=0,
        )

        engine.fit(model=model, datamodule=datamodule)

        # 计算最优阈值：在正常图像上推理，取分数的指定分位数作为阈值
        image_threshold = _compute_threshold(
            model=model,
            images=threshold_images,
            device=device,
            input_size=efficientad_cfg.input_size,
            percentile=99.7,
        )

        # 导出 TorchScript
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        model.eval()
        example_input = torch.randn(1, 3, efficientad_cfg.input_size, efficientad_cfg.input_size)
        traced = torch.jit.trace(model, example_input.to(device))
        traced.save(str(output))

        # 像素级阈值（取图像级阈值的 0.8 倍作为参考）
        pixel_threshold = round(image_threshold * 0.8, 6)

        train_time_s = round(time.monotonic() - t_start, 1)

        # 保存元数据
        meta = {
            "image_threshold": image_threshold,
            "pixel_threshold": pixel_threshold,
            "input_size": efficientad_cfg.input_size,
            "teacher_backbone": efficientad_cfg.teacher_backbone,
            "student_backbone": efficientad_cfg.student_backbone,
            "train_image_count": len(train_images),
            "threshold_image_count": len(threshold_images),
            "epochs": efficientad_cfg.epochs,
            "train_time_s": train_time_s,
            "camera_id": camera_id,
        }
        meta_path = output.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        # 记录 MLflow
        if mlflow is not None:
            try:
                mlflow.log_params({
                    "camera_id": camera_id,
                    "teacher_backbone": efficientad_cfg.teacher_backbone,
                    "student_backbone": efficientad_cfg.student_backbone,
                    "input_size": efficientad_cfg.input_size,
                    "epochs": efficientad_cfg.epochs,
                    "batch_size": efficientad_cfg.batch_size,
                    "learning_rate": efficientad_cfg.learning_rate,
                    "train_image_count": len(train_images),
                    "threshold_image_count": len(threshold_images),
                })
                mlflow.log_metrics({
                    "image_threshold": image_threshold,
                    "pixel_threshold": pixel_threshold,
                    "train_time_s": train_time_s,
                })
                mlflow.log_artifact(str(output))
                mlflow.log_artifact(str(meta_path))
                mlflow_run_id = mlflow.active_run().info.run_id
                mlflow.end_run()
            except Exception:
                pass  # MLflow 记录失败不阻塞训练流程

        return {
            "status": "completed",
            "artifact_path": str(output),
            "image_threshold": image_threshold,
            "pixel_threshold": pixel_threshold,
            "train_image_count": len(train_images),
            "train_time_s": train_time_s,
            "mlflow_run_id": mlflow_run_id,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _compute_threshold(
    model: object,
    images: list[np.ndarray],
    device: torch.device,
    input_size: int,
    percentile: float = 99.7,
) -> float:
    """在正常图像上计算异常分数阈值。

    对给定的正常图像集合逐一推理，收集 anomaly score，
    然后以指定分位数（默认 99.7%，对应 3-sigma）作为检测阈值。
    高于此阈值的图像将被判定为异常。
    """
    model.eval()
    scores: list[float] = []
    imagenet_mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    imagenet_std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)

    with torch.no_grad():
        for img in images:
            # BGR → RGB → resize → normalize → tensor
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_resized = cv2.resize(img_rgb, (input_size, input_size))
            tensor = (
                torch.from_numpy(img_resized).float().permute(2, 0, 1).to(device) / 255.0
            )
            tensor = (tensor - imagenet_mean) / imagenet_std
            tensor = tensor.unsqueeze(0)

            output = model(tensor)
            if isinstance(output, tuple):
                _, score = output
            elif isinstance(output, torch.Tensor):
                score = output
            else:
                continue

            if isinstance(score, torch.Tensor):
                score_val = float(score.detach().cpu().item())
            else:
                score_val = float(score)
            scores.append(score_val)

    if not scores:
        return 0.5

    threshold = float(np.percentile(scores, percentile))
    # 确保阈值不低于合理下限，避免正常波动被误检
    threshold = max(threshold, 1e-6)
    return round(threshold, 6)


def _init_mlflow(tracking_uri: Optional[str], experiment: str):
    """初始化 MLflow tracking。"""
    if tracking_uri is None:
        return None
    try:
        import mlflow

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
        mlflow.start_run()
        return mlflow
    except Exception:
        return None


def train_efficientad_cli() -> None:
    """CLI 入口：由 seat_defect_core.__main__ 调用。"""
    import argparse

    parser = argparse.ArgumentParser(description="训练 EfficientAD 模型")
    parser.add_argument("--config", required=True, help="检测配置文件路径 (JSON/INI)")
    parser.add_argument("--camera-id", required=True, help="目标相机 ID")
    parser.add_argument("--good-images", required=True, help="正常参考图像目录")
    parser.add_argument("--output", required=True, help="输出 .pt 文件路径")
    parser.add_argument("--mlflow-uri", default=None, help="MLflow tracking URI")
    parser.add_argument("--mlflow-experiment", default="efficientad", help="MLflow 实验名称")

    args = parser.parse_args()

    img_dir = Path(args.good_images)
    if not img_dir.is_dir():
        raise FileNotFoundError(f"图像目录不存在: {args.good_images}")

    image_paths: list[str] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(str(p) for p in img_dir.glob(ext))
    if not image_paths:
        raise FileNotFoundError(f"目录中未找到图像文件: {args.good_images}")

    result = train_efficientad(
        config=args.config,
        camera_id=args.camera_id,
        good_image_paths=image_paths,
        output_path=args.output,
        mlflow_tracking_uri=args.mlflow_uri,
        mlflow_experiment=args.mlflow_experiment,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _find_camera(inspection_cfg, camera_id: str):
    """在配置中查找指定相机。"""
    for cam in getattr(inspection_cfg, "cameras", []) or []:
        if cam.camera_id == camera_id:
            return cam
    seat_models: list = getattr(inspection_cfg, "seat_models", []) or []
    for sm in seat_models:
        for cam in getattr(sm, "cameras", []) or []:
            if cam.camera_id == camera_id:
                return cam
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


def _resolve_train_device(requested: str) -> torch.device:
    """解析训练设备。"""
    normalized = requested.strip().lower()
    if normalized.startswith("cuda") and torch.cuda.is_available():
        return torch.device("cuda")
    if normalized == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
