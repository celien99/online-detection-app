"""CLI entry point for seat_defect_core: python -m seat_defect_core [options].

Usage examples:
  python -m seat_defect_core inspect --config config.json --images cam1=img1.jpg
  python -m seat_defect_core train-efficientad --config config.json --camera-id cam_front --good-images ./good/ --output model.pt
  python -m seat_defect_core batch-train --config config.json --good-images-root ./training_data/ --output-root ./models/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seat_defect_core",
        description="Online real-time seat defect inspection core",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # inspect 子命令（默认）
    inspect_parser = subparsers.add_parser("inspect", help="执行检测")
    _add_inspect_args(inspect_parser)

    # train-efficientad 子命令
    train_parser = subparsers.add_parser("train-efficientad", help="训练 EfficientAD 模型")
    train_parser.add_argument("--config", type=str, required=True, help="检测配置文件路径 (JSON/INI)")
    train_parser.add_argument("--camera-id", type=str, required=True, help="目标相机 ID")
    train_parser.add_argument("--good-images", type=str, required=True, help="正常参考图像目录")
    train_parser.add_argument("--output", type=str, required=True, help="输出 .pt 文件路径")

    # batch-train 子命令
    batch_parser = subparsers.add_parser("batch-train", help="批量训练多机位 EfficientAD 模型")
    batch_parser.add_argument("--config", type=str, required=True, help="检测配置文件路径 (JSON)")
    batch_parser.add_argument("--good-images-root", type=str, required=True, help="正常图像根目录")
    batch_parser.add_argument("--output-root", type=str, required=True, help="模型输出根目录")
    batch_parser.add_argument("--cameras", type=str, default=None, help="限定训练机位，逗号分隔")
    batch_parser.add_argument("--mlflow-uri", type=str, default=None, help="MLflow tracking URI")
    batch_parser.add_argument("--dry-run", action="store_true", help="只打印训练计划")

    args = parser.parse_args(argv)

    if args.command == "train-efficientad":
        return _run_train_efficientad(args)

    if args.command == "batch-train":
        return _run_batch_train(args)

    # 默认：inspect（兼容旧的 --config --images 直接调用方式）
    if args.command is None:
        # 兼容老格式，用 inspect 子命令的参数重新解析
        return _run_inspect_legacy(argv)

    return _run_inspect(args)


def _add_inspect_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=str, required=True, help="JSON or INI inspection config file path")
    parser.add_argument("--images", type=str, action="append", default=[], help="Camera image paths as CAMERA_ID=PATH pairs (可重复指定)")
    parser.add_argument("--part-id", type=str, default=None, help="Part identifier for this inspection")
    parser.add_argument("--seat-model-id", type=str, default=None, help="Seat model identifier override")
    parser.add_argument("--upload", type=str, default=None, help="Override upload_base_url in config")
    parser.add_argument("--output", type=str, default=None, help="Write inspection response JSON to file")
    parser.add_argument("--warmup", action="store_true", default=False, help="Preload models before inspection")


def _run_inspect(args) -> int:
    image_paths: Dict[str, str] = {}
    for pair in args.images:
        if "=" not in pair:
            print(f"错误：--images 格式应为 CAMERA_ID=PATH，收到：{pair}", file=sys.stderr)
            return 1
        camera_id, path = pair.split("=", 1)
        image_paths[camera_id.strip()] = path.strip()

    try:
        from seat_defect_core.api import SeatDefectInspector

        inspector = SeatDefectInspector(args.config)
        if args.upload:
            # 显式 --upload 时禁用 config 中的自动上传（避免 daemon 线程与同步上传重复）
            inspector.config.upload_base_url = ""
        if args.warmup:
            print("预热模型中...")
            inspector.warmup(seat_model_id=args.seat_model_id)
            print("预热完成")

        if image_paths:
            response, camera_images = inspector.inspect_paths(
                image_paths, part_id=args.part_id, seat_model_id=args.seat_model_id,
            )
        else:
            print("错误：请通过 --images 指定至少一个机位图片", file=sys.stderr)
            return 1

        payload = response.to_dict()
        print(json.dumps({"status": response.status, "decision_reason": response.decision_reason}, ensure_ascii=False))
        for cam_result in response.result.camera_results:
            print(f"  [{cam_result.camera_id}] status={cam_result.status} reason={cam_result.reason}")

        if args.upload:
            from seat_defect_core.anomaly_uploader import upload_inspection_response
            print(f"上传检测结果到 {args.upload}...")
            results = upload_inspection_response(response, args.upload)
            for r in results:
                ids = r.get("anomaly_ids", [r.get("anomaly_id", "?")])
                count = r.get("count", len(ids) if isinstance(ids, list) else 1)
                print(f"  上传成功: anomaly_ids={ids} count={count}")
            if not results:
                print("  无异常需上传或上传失败（网络不通/后端未运行）")

        if args.output:
            import cv2
            output_path = Path(args.output)
            out_dir = output_path.parent
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            # 保存各机位叠加图像到输出目录
            for cam_id, overlay_bgr in camera_images.items():
                if overlay_bgr is not None:
                    overlay_path = out_dir / f"{cam_id}_overlay.jpg"
                    cv2.imwrite(str(overlay_path), overlay_bgr)
            print(f"结果已写入：{output_path}")

        return 0
    except Exception as exc:
        print(f"检测失败：{exc}", file=sys.stderr)
        return 1


def _run_inspect_legacy(argv: Optional[List[str]]) -> int:
    """兼容老格式：python -m seat_defect_core --config ... --images ..."""
    parser = argparse.ArgumentParser(prog="seat_defect_core")
    _add_inspect_args(parser)
    args = parser.parse_args(argv)
    return _run_inspect(args)


def _run_train_efficientad(args) -> int:
    img_dir = Path(args.good_images)
    if not img_dir.is_dir():
        print(f"错误：图像目录不存在: {args.good_images}", file=sys.stderr)
        return 1

    image_paths: list[str] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(str(p) for p in img_dir.glob(ext))
    if not image_paths:
        print(f"错误：目录中未找到图像文件: {args.good_images}", file=sys.stderr)
        return 1

    try:
        from seat_defect_core.training.efficientad import train_efficientad
        result = train_efficientad(
            config=args.config,
            camera_id=args.camera_id,
            good_image_paths=image_paths,
            output_path=args.output,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") == "completed" else 1
    except Exception as exc:
        print(f"训练失败：{exc}", file=sys.stderr)
        return 1


def _run_batch_train(args) -> int:
    try:
        from seat_defect_core.training.batch_train import batch_train_all

        cameras_list: Optional[list[str]] = None
        if args.cameras:
            cameras_list = [c.strip() for c in args.cameras.split(",") if c.strip()]

        result = batch_train_all(
            config_path=args.config,
            good_images_root=args.good_images_root,
            output_root=args.output_root,
            cameras=cameras_list,
            mlflow_tracking_uri=args.mlflow_uri,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result.get("status") in ("completed", "dry_run") else 1
    except Exception as exc:
        print(f"批量训练失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
