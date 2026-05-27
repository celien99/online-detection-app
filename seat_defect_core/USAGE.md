# seat_defect_core 使用说明

本文档描述 `seat_defect_core` 作为外部 Python 项目检测 SDK 时的接入方式。`core` 只负责检测运行时，不负责相机采集、模型训练或 UI 展示。

## 适用边界

`seat_defect_core` 支持的能力：

- 加载检测配置文件。
- 加载训练好的 YOLO 分割模型和 EfficientAD 模型。
- 接收外部项目传入的多机位图像。
- 执行 YOLO、ROI 对齐、EfficientAD 和多机位融合。
- 返回结构化检测结果、错误码、耗时和报告路径。

`seat_defect_core` 不负责的能力：

- 不直接控制工业相机。
- 不负责模型训练数据采集。
- 不负责长期结果数据库存储。

## 安装和交付

`seat_defect_core` 已将共享协议库（`defect_protocol`）嵌入为 `_protocol` 子模块，零外部 Python 包依赖。部署时只需安装 `seat_defect_core` 自身及其 PyPI 依赖。

### 从源码安装

```bash
pip install ./seat_defect_core
```

### 从预构建 wheel 安装

```bash
cd seat_defect_core && python -m build -w
pip install seat_defect_core/dist/seat_defect_core-*.whl
```

### 离线安装

先在联网机器上准备 wheel：

```bash
python -m pip download --only-binary=:all: -r requirements-core-py38-cpu.txt -d wheelhouse
python -m pip wheel --no-deps ./seat_defect_core -w wheelhouse
```

拷贝 `wheelhouse` 到目标机器后：

```bash
python -m pip install --no-index --find-links wheelhouse -r requirements-core-py38-cpu.txt
python -m pip install --no-index --find-links wheelhouse seat-defect-core
```

### 开发时使用（monorepo 内）

在 workspace 内直接 `uv sync --all-packages`，所有依赖自动解析。

不建议长期依赖手工复制目录作为正式交付方式。手工复制可以用于临时验证，但容易遗漏依赖、版本和包数据。

## 最小调用示例

外部项目传入每个机位对应的图片路径：

```python
from seat_defect_core import SeatDefectInspector

inspector = SeatDefectInspector("/path/to/inspection_config.json")

response = inspector.inspect_paths(
    {
        "cam_front": "/data/current/cam_front.png",
        "cam_left": "/data/current/cam_left.png",
    },
    part_id="part_20260509_0001",
    seat_model_id="seat_model_a",
    frame_id="frame_0001",
    timestamp="2026-05-09T10:00:00+08:00",
)

payload = response.to_dict()
print(payload["status"])
print(payload["decision_reason"])
```

如果只运行一次，也可以使用函数入口：

```python
from seat_defect_core import inspect_paths_once

response = inspect_paths_once(
    "/path/to/inspection_config.json",
    {
        "cam_front": "/data/current/cam_front.png",
    },
    part_id="part_20260509_0001",
    seat_model_id="seat_model_a",
)
```

如果外部项目已经拿到了 `numpy.ndarray` 图像，可以直接传 frame：

```python
from seat_defect_core import SeatDefectInspector

inspector = SeatDefectInspector("/path/to/inspection_config.json")

response = inspector.inspect(
    [
        {
            "camera_id": "cam_front",
            "image": image_bgr,
            "source": "external://cam_front",
            "source_kind": "external_image",
            "frame_id": "frame_0001",
            "timestamp": "2026-05-09T10:00:00+08:00",
        }
    ],
    part_id="part_20260509_0001",
    seat_model_id="seat_model_a",
)
```

图像数组要求：

- OpenCV BGR 格式优先。
- 类型通常为 `uint8`。
- 不要传已经被外部裁剪、旋转或压缩破坏的图像，除非模型训练时使用的就是同样流程。

## 配置文件

配置文件支持 JSON 和 INI。JSON 可以直接是检测配置对象，也可以包在 `seat_defect_inspection` 顶层字段下。路径类字段会按配置文件所在目录解析相对路径。

INI 用于兼容 LabVIEW 和现场工具，核心流程仍会先把 INI 转成同一份配置 payload，再走统一校验。常用 section 约定如下：

- `[seat_defect_inspection]`：顶层路径、开关、默认工件等字段
- `[fusion]`：整件融合策略
- `[camera.<camera_id>]`：顶层单机位
- `[camera.<camera_id>.detection]`、`roi`、`roi.alignment`、`efficientad`、`filter_classifier`、`rule_engine`
- `[seat_model.<seat_model_id>]` 和 `[seat_model.<seat_model_id>.camera.<camera_id>]`：多型号配置

示例：

```json
{
  "seat_defect_inspection": {
    "part_id": "seat_demo",
    "default_seat_model_id": "seat_model_a",
    "output_json_path": "../outputs/seat_defect_inspection/results.json",
    "debug_dir": "../outputs/seat_defect_inspection/debug",
    "debug_artifacts_enabled": false,
    "fusion": {
      "reject_on_any_reject": true,
      "ng_strategy": "any",
      "defect_overrides_reject": true
    },
    "seat_models": [
      {
        "seat_model_id": "seat_model_a",
        "display_name": "座椅型号A",
        "cameras": [
          {
            "camera_id": "cam_front",
            "efficientad_model_path": "../models/seat_model_a/cam_front_efficientad.pt",
            "detection": {
              "model_path": "../models/yolo/seat_model_a_best.pt",
              "target_class": "seat",
              "confidence": 0.25,
              "iou": 0.45,
              "imgsz": 960
            },
            "roi": {
              "crop_expand_ratio": 0.02,
              "mask_erode_pixels": 1,
              "edge_ignore_pixels": 4,
              "alignment": {
                "output_width": 256,
                "output_height": 256
              }
            },
            "efficientad": {
              "teacher_backbone": "wide_resnet50_2",
              "student_backbone": "resnet18",
              "device": "cpu",
              "input_size": 256,
              "min_valid_pixel_ratio": 0.3
            }
          }
        ]
      }
    ]
  }
}
```

### Feature Calibration 配置

在 `CameraConfig` 中增加 `calibration` 字段启用跨机位特征校准：

```json
{
  "camera_id": "cam_front",
  "calibration": {
    "enabled": true,
    "camera_norm": {
      "enabled": true,
      "stats_path": "./calibration/cam_front_norm_stats.npz"
    },
    "projection": {
      "enabled": true,
      "projector_path": "./calibration/projector.npz"
    },
    "whitening": {
      "enabled": true,
      "method": "zca",
      "regularization": 0.0001,
      "matrix_path": "./calibration/whitening_matrix.npz"
    },
    "ema_center": {
      "enabled": true,
      "alpha": 0.99,
      "min_samples": 10,
      "novelty_threshold": 0.3,
      "centers_path": "./calibration/defect_centers.json"
    }
  }
}
```

校准链路：`EAD features → CameraNormalizer (per-camera per-channel 标准化) → EmbeddingProjector (PCA 投影至 384-dim) → WhiteningTransform (ZCA 白化去相关) → UnifiedEmbedding`。

### Cascading Budget 配置

预算配置已内嵌于 `ProposalConfig` 的 `budget` 字段。如需启用两级预算（Proposal + Filter 级联），设置：

```json
{
  "proposal": {
    "budget": {
      "enabled": true,
      "scope": "proposal_and_filter",
      "target_latency_ms": 15.0,
      "hard_limit_ms": 20.0,
      "max_cc_before_emergency": 50,
      "avg_filter_latency_ms": 3.0,
      "window_size": 100,
      "threshold_multiplier_step": 0.5,
      "threshold_multiplier_max": 3.0,
      "recovery_rate": 0.01
    }
  }
}
```

`CascadingBudgetController` 会根据剩余预算动态调度 Filter：`full` (全部推理) / `partial` (按优先级裁剪) / `skip_all` / `emergency` (紧急熔断)。

生产环境建议：

- `debug_artifacts_enabled` 设置为 `false`，避免保存大量调试图片拖慢检测。
- `output_json_path` 和 `debug_dir` 放到外部项目可写目录。
- `device` 根据现场硬件设为 `cpu`、`cuda:0` 或 `mps`。

## 输入格式

### `inspect_paths`

```python
inspect_paths(
    image_paths: Dict[str, str],
    *,
    part_id: Optional[str] = None,
    seat_model_id: Optional[str] = None,
    frame_id: Optional[str] = None,
    timestamp: Optional[str] = None,
)
```

`image_paths` 是 `{camera_id: image_path}`。

- `camera_id` 必须和配置中启用的机位一致。
- 缺少某个启用机位时，该机位返回 `REJECT`，错误码为 `missing_external_frame`。
- 图片读取失败时，该机位返回 `REJECT`，错误码为 `image_read_failed`。
- 传入未配置或未启用的 `camera_id` 会抛出 `ValueError`。
- 重复 `camera_id` 会抛出 `ValueError`。

### `inspect`

```python
inspect(
    frames: List[Union[InspectionFrame, Dict]],
    *,
    part_id: Optional[str] = None,
    seat_model_id: Optional[str] = None,
)
```

dict frame 必填字段：

- `camera_id`
- `image`

dict frame 可选字段：

- `source`
- `source_kind`
- `frame_id`
- `timestamp`
- `error_reason`

## 输出格式

`InspectionResponse.to_dict()` 返回适合 JSON 序列化的字典：

```json
{
  "part_id": "part_20260509_0001",
  "frame_id": "frame_0001",
  "timestamp": "2026-05-09T10:00:00+08:00",
  "status": "OK",
  "decision_reason": "all_checks_passed",
  "seat_model_id": "seat_model_a",
  "timings_ms": {
    "context": 0.1,
    "frames": 0.1,
    "cameras": 120.0,
    "fusion": 0.1,
    "total": 120.3
  },
  "report_path": "../outputs/seat_defect_inspection/results.json",
  "artifact_paths": {},
  "camera_results": [
    {
      "camera_id": "cam_front",
      "frame_id": "frame_0001",
      "source": "/data/current/cam_front.png",
      "source_kind": "image_path",
      "status": "OK",
      "reason": "all_checks_passed",
      "seat_model_id": "seat_model_a",
      "timings_ms": {
        "prepare": 30.0,
        "anomaly": 80.0,
        "debug_artifacts": 0.0,
        "total": 111.0
      },
      "error": null,
      "artifact_paths": {}
    }
  ]
}
```

状态含义：

- `OK`：检测通过。
- `NG`：检测到缺陷。
- `REJECT`：本次输入或中间流程不满足检测条件，不能作为合格/缺陷结论使用。

常见 `reason`：

- `all_checks_passed`
- `texture_anomaly`
- `target_not_found`
- `target_mask_missing`
- `low_valid_pixel_ratio`
- `missing_external_frame`
- `image_read_failed`
- `pipeline_failed`

结构化错误字段：

```json
{
  "code": "image_read_failed",
  "message": "image_read_failed",
  "stage": "input"
}
```

外部系统应优先使用 `status`、`reason`、`error.code` 和 `error.stage` 做逻辑判断，不建议解析中文异常文本。

## 检测流程

单机位检测流程：

1. YOLO 检测目标座椅。
2. 根据分割 mask 做 ROI 裁剪和对齐。
3. 做图像质量检查。
4. 执行完整 ROI EfficientAD 纹理异常检测。
5. 异常帧进入 Feature Calibration（Normalize → Project → Whiten → EMA Center）。
6. Proposal 生成 defect patch 候选。
8. Identity Linking 跨帧关联。
9. Cascading Budget 调度 Filter 推理（full/partial/skip_all/emergency）。
10. Filter Classifier 三模态推理 + Proposal Aggregation。
11. 规则引擎后处理。
12. 汇总单机位结果。

多机位流程：

1. 校验外部传入机位。
2. 逐机位检测。
3. 按 fusion 配置汇总整件状态。
4. 写出 latest report。

## 模型和配置一致性

EfficientAD 模型中保存了训练时的上游 pipeline signature。运行时如果修改了会影响 ROI 或特征输入的关键配置，core 会拒绝使用旧模型，并提示重新训练。

常见需要重新训练 EfficientAD 的改动：

- YOLO 模型路径或目标类别发生变化。
- ROI 裁剪、mask、alignment 配置变化。
- EfficientAD 的 backbone、image_size、teacher/student 或 feature_layers 变化。

运行时可以调整部分判定阈值类配置，但不能用配置去掩盖训练数据不足的问题。

## 现场排查顺序

当结果为 `REJECT` 时，优先查看：

1. `camera_results[].error.code`
2. `camera_results[].error.stage`
3. `camera_results[].reason`
4. `camera_results[].timings_ms`
5. `report_path` 对应 JSON 报告

当速度偏慢时，优先检查：

1. `debug_artifacts_enabled` 是否为 `false`。
2. `timings_ms.cameras` 和各机位 `timings_ms.anomaly`。
3. `device` 是否符合现场硬件。
5. 是否每次请求都重新创建 `SeatDefectInspector`。

## 最佳检测效果配置

要发挥 `seat_defect_core` 最强检测效果，需同时启用以下特性：

| 特性 | 作用 | 效果提升 |
|------|------|----------|
| **Calibration** | 跨机位特征校准（Normalize→Project→Whiten） | 消除机位间特征分布差异，Filter Classifier 跨机位泛化能力提升 |
| **Cascading Budget** | 自适应提案+过滤预算调度 | 保证实时性（<20ms/帧），同时在正常帧上做完整推理 |
| **Tracking** | 缺陷跨帧身份关联（IoU+Kalman+Cosine） | 消除单帧误报，Mature 缺陷自动升级告警等级 |
| **Filter Classifier** | 三模态（图像+EAD特征+统一嵌入）误报抑制 | 误报率降低 50-80% |
| **Rule Engine** | 知识库规则后处理 | 针对已知缺陷类型/机位做定向压制或升级 |
| **Proposal Aggregation** | 加权置信度 ROI 级聚合 | 多 patch 联合判定，避免碎片化误检 |

### 推荐配置文件

使用 `config.best.json`（位于 seat_defect_core 目录）作为起点，按现场环境调整设备（`cpu`/`cuda`/`mps`）和模型路径。

### 特性启用顺序

1. **基础链路**：YOLO + EfficientAD（必须，最小可用）
2. **精度提升**：Filter Classifier + Rule Engine
3. **鲁棒性提升**：Calibration + Tracking + Proposal Aggregation
4. **性能保障**：Cascading Budget（实时性要求高时启用）

### 关键参数调优指南

#### EfficientAD 阈值

训练完成后自动计算 `image_threshold`（正常图像 anomaly score 的 99.7% 分位数）。现场调优时：

- **漏检多**：降低 `image_threshold`（当前值 × 0.7-0.8）
- **误报多**：提高 `image_threshold`（当前值 × 1.2-1.5）
- 阈值保存在模型 `.meta.json` 中，修改后重新加载即可生效

#### Filter Classifier 置信度

- `confidence_threshold: 0.5` 为平衡点
- 产线容忍误报率低时提高到 `0.7-0.8`
- 产线不容忍漏检时降低到 `0.3-0.4`

#### Cascading Budget 延迟目标

- `target_latency_ms: 15.0` 适合大多数产线节拍
- 高速产线（<100ms/件）设 `target_latency_ms: 8.0`, `hard_limit_ms: 12.0`
- 低速产线（>500ms/件）可关闭 budget 做完整推理

#### Calibration 数据准备

Calibration 需要离线拟合参数，训练脚本位于 `ml/alignment/trainer.py`：

1. 收集各机位正常图像 100+ 张
2. 用已训练的 EfficientAD 模型提取特征
3. 运行 AlignmentTrainer 拟合 CameraNormalizer + Projector + Whitening
4. 将输出的 `.npz` 文件路径填入 calibration 配置

## 训练工作流

### 准备训练数据

按机位组织正常图像，每个机位一个 `good/` 目录：

```
training_data/
  cam_back/
    good/        # 正常图像（各 50-200 张）
      0001.jpg
      0002.jpg
      ...
  cam_front/
    good/
      0001.jpg
      0002.jpg
      ...
  cam_left/
    good/
      ...
```

**数据要求：**
- 只包含正常（无缺陷）座椅图像
- 覆盖产线正常波动（光照变化、座椅颜色/材质差异、轻微位置偏移）
- 每个机位至少 50 张，推荐 100-200 张
- 图像应为 ROI 对齐后的裁剪（256×256 或与 `input_size` 一致）

### 单机位训练

```bash
python -m seat_defect_core train-efficientad \
  --config config.best.json \
  --camera-id cam_back \
  --good-images ./training_data/cam_back/good/ \
  --output ./models/seat_model_a/cam_back_efficientad.pt
```

### 批量训练全部机位

```bash
# 预览训练计划（不实际执行）
python -m seat_defect_core batch-train \
  --config config.best.json \
  --good-images-root ./training_data/ \
  --output-root ./models/seat_model_a/ \
  --dry-run

# 执行训练
python -m seat_defect_core batch-train \
  --config config.best.json \
  --good-images-root ./training_data/ \
  --output-root ./models/seat_model_a/

# 仅训练指定机位
python -m seat_defect_core batch-train \
  --config config.best.json \
  --good-images-root ./training_data/ \
  --output-root ./models/seat_model_a/ \
  --cameras cam_back,cam_front
```

### 训练流程

1. 自动将图像转换为 MVTec 格式
2. 划分训练集/阈值计算集（90/10）
3. 使用 anomalib `EfficientAd(teacher_out_channels=384, model_size="medium")` 训练
4. 在阈值集上计算 anomaly score 的 99.7% 分位数作为 `image_threshold`
5. 导出 TorchScript `.pt` 模型 + `.meta.json` 阈值元数据
6. 记录 MLflow 实验（params/metrics/artifacts）

### 训练参数建议

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `epochs` | 200 | 更多轮数有利于 teacher-student 收敛 |
| `batch_size` | 16 | GPU 显存充足可设 32 |
| `learning_rate` | 1e-4 | EfficientAD 官方推荐 |
| `validation_split` | 0.1 | 10% 用于阈值计算 |
| `early_stopping_patience` | 20 | 避免过拟合 |

## 生产部署检查清单

- [ ] `debug_artifacts_enabled` 设为 `false`
- [ ] 所有 `device` 字段与现场硬件一致（`cpu`/`cuda`/`mps`）
- [ ] YOLO 模型路径和分类名确认正确
- [ ] 每个机位的 EfficientAD 模型已训练并路径正确
- [ ] Filter Classifier 已部署且路径正确
- [ ] 规则引擎 deployed_rules_path 指向最新部署规则
- [ ] Calibration `.npz` 文件已拟合并路径正确
- [ ] `upload_base_url` 指向正确的离线平台后端
- [ ] 使用 `SeatDefectInspector` 单例，避免重复加载模型
- [ ] 预热调用 `inspector.warmup()` 在首次检测前执行
- [ ] 固定依赖版本（torch, torchvision, anomalib, ultralytics）
- [ ] 离线样本集回归验证通过

## 版本稳定性建议

外部项目接入时，建议固定以下内容：

- `seat-defect-core` 包版本。
- 配置文件版本。
- YOLO 模型文件。
- EfficientAD 模型文件。
- Python、torch、torchvision、ultralytics 版本。

LabVIEW 公共机建议固定 Python `3.8.5`，使用 CPU 版依赖，并在配置中设置 `device = cpu`。如果后续改用 GPU/CUDA，需要单独验证对应的 torch、torchvision 和驱动版本。

上线后不要直接替换模型或配置。任何模型或 ROI 配置调整，都应先在离线样本集上回归验证。
