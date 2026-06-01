# Seat Defect Core V3.1

## 多机位频闪汽车座椅缺陷检测系统架构设计规范

Version: 3.1

Status: Production Ready Architecture

Classification: Industrial Surface Understanding Platform

---

# 1. 项目定位

Seat Defect Core 不是：

- AOI软件
- YOLO项目
- EfficientAD项目
- 缺陷分类器

---

Seat Defect Core 是：

Industrial Surface Understanding Platform

工业表面理解平台

---

目标：

理解：

- 表面结构
- 表面材质
- 表面缺陷

最终实现：

- 缺陷检测
- 缺陷解释
- 缺陷知识积累
- 持续学习

---

# 2. 核心设计哲学

优先级：

Surface Understanding

>

Geometry Understanding

>

Defect Detection

>

Model Selection

---

禁止：

不断替换模型

却不提升成像质量

---

必须：

优先优化：

光学

几何

表征空间

---

# 3. V3.1总体架构

PLC
│
▼

Trigger Service
│
▼

Capture Service
│
▼

ROI Builder
│
▼

ROI Confidence Monitor
│
▼

Geometry Builder
│
▼

Geometry Cache
│
▼

Feature Fusion Engine
│
▼

Unified Embedding
│
▼

Multi-Modal Anomaly Detection
│
▼

Proposal Aggregation
│
▼

Rule Engine
│
▼

Decision Engine
│
▼

OK / NG / REVIEW

---

# 4. 系统数据流

RAW Images
│
▼

ROI Composite
│
▼

Geometry Context
│
▼

Unified Embedding
│
▼

Anomaly Proposal
│
▼

Decision

---

# 5. Capture Layer

职责：

控制：

Cam1 Top

Cam2 Left

Cam3 Right

Cam4 Rear

---

采集：

19张频闪图像

---

输出：

CaptureContext

cam1:
  dome
  dark0
  dark90
  dark180
  dark270
  grazing_left
  grazing_right
  backlight

cam2:
  dark0
  dark90
  grazing_left
  polar

cam3:
  dark0
  dark90
  grazing_right
  polar

cam4:
  dome
  backlight
  side_dark

---

# 6. ROI Builder

V3.1新增

---

问题：

单独使用Dome图像

在：

- 黑色真皮
- Alcantara
- 吸光材质

容易失效

---

禁止：

Dome
↓
YOLO

---

采用：

Multi-Light ROI Composite

---

输入：

Dome

Grazing Left

Grazing Right

---

输出：

ROI Composite

---

推荐融合：

Composite

=

0.5 Dome

-

0.25 Grazing Left

-

0.25 Grazing Right

---

或者：

Edge Enhanced Composite

---

输出：

ROI定位图

---

# 7. ROI Confidence Monitor

V3.1新增

---

职责：

监控：

ROI质量

---

输出：

ROI Score

---

规则：

ROI Score ≥ 0.9

正常流程

---

ROI Score < 0.9

触发：

Fallback Strategy

---

Fallback：

Multi-Light Composite ROI

重新定位

---

ROI Score < 0.7

进入：

Review Mode

---

# 8. Geometry Builder

系统核心层

---

禁止：

写死：

Photometric Stereo

---

原因：

未来可替换

---

采用：

Geometry Builder抽象

---

支持：

Mode A

Photometric Stereo

---

Mode B

Photometric Stereo
+
Learned Geometry Encoder

---

Mode C

Multi-Light Transformer

---

输入：

ROI Multi-Light Images

---

输出：

GeometryContext

---

包含：

Normal Map

Height Map

Reflectance Map

Curvature Map

---

# 9. Geometry Cache

目的：

解决显存与吞吐量

---

禁止：

RAW Images长期驻留

---

Photometric Stereo结束后：

立即释放：

Raw Images

---

保留：

Normal

Height

Reflectance

Curvature

---

缓存结构：

GeometryCache

SeatID

ROI_ID

Normal

Height

Reflectance

Timestamp

---

# 10. Ring Buffer Architecture

目的：

控制显存

---

采用：

Current Seat

Previous Seat

Next Seat

---

仅保留：

3工件上下文

---

禁止：

无限缓存

---

# 11. Light Calibration Service

系统关键服务

---

职责：

监控：

Light Vector

Light Intensity

Normal Distribution

---

检测：

Light Drift

---

输出：

Calibration Matrix

---

# 12. Dual Calibration Strategy

Level 1

Reference Board

---

每班次：

自动标定

---

输出：

Light Matrix

---

Level 2

Online Self Calibration

---

监控：

Geometry Distribution

Reflectance Distribution

Normal Distribution

---

漂移超阈值：

自动报警

自动重标定

---

# 13. Feature Fusion Engine

V3.1重大升级

---

问题：

简单Concat

会导致：

Geometry Feature Dilution

特征稀释

---

禁止：

RGB

-

Geometry

↓

Concat

---

# 14. Dual Encoder Architecture

Branch A

RGB Encoder

输入：

RGB

---

输出：

RGB Embedding

---

Branch B

Geometry Encoder

输入：

Normal

Height

Reflectance

Curvature

---

输出：

Geometry Embedding

---

# 15. Attention Budget Rules

重要性能规范

---

禁止：

Full Resolution Attention

---

原因：

Attention Complexity

≈ O(N²)

---

容易突破：

50ms预算

---

允许：

Strategy A

Pooling + Attention

---

Strategy B

FlashAttention-2

---

Strategy C

Linear Attention

---

Strategy D

Perceiver IO

推荐

---

要求：

Attention Token ≤ 256

---

Feature Fusion预算：

≤ 50ms

---

# 16. Unified Embedding Space

输入：

RGB Embedding

Geometry Embedding

Lighting Embedding

---

输出：

Unified Embedding

---

用途：

异常检测

聚类

检索

持续学习

VLM解释

---

# 17. Multi-Modal Anomaly Detection

Phase 1

YOLO
+
EfficientAD

---

Phase 2

YOLO
+
DINO
+
Memory Bank

---

Phase 3

Foundation Vision Model

---

输出：

Texture Score

Geometry Score

Lighting Score

---

禁止：

Single Score

---

# 18. Proposal Aggregation

输入：

Texture Score

Geometry Score

Lighting Score

Heatmap

Geometry Evidence

---

输出：

Final Proposal

---

采用：

Weighted Fusion

Spatial Consistency

Confidence Fusion

---

# 19. Rule Engine

输入：

Proposal

---

规则：

面积

长度

深度

位置

客户规则

MES规则

工艺规则

---

输出：

OK

NG

REVIEW

---

# 20. Continuous Learning Service

长期稳定核心

---

职责：

监控：

Embedding Drift

Material Drift

Lighting Drift

Geometry Drift

---

来源：

供应商变化

颜色变化

材料变化

设备老化

---

输出：

Calibration Alert

Retraining Dataset

Model Update Request

---

# 21. GPU架构规范

必须支持：

CUDA

TensorRT

---

必须支持：

Pinned Memory

Zero Copy

CUDA Stream

---

推荐：

Capture Stream

Geometry Stream

Inference Stream

并行执行

---

禁止：

串行流水线

---

# 22. 性能预算

采集：

80ms

---

ROI：

30ms

---

Geometry：

100ms

---

Feature Fusion：

≤50ms

---

Anomaly：

100ms

---

Aggregation：

20ms

---

Rule Engine：

10ms

---

AI链路：

<500ms

---

整机节拍：

<2s

---

# 23. System Visualization Specification

V3.1新增

---

目标：

统一：

AI

光学

机械

自动化

软件

团队认知

---

Level 1

Physical Layout

展示：

Camera

Light

Seat

PLC

布局关系

---

Level 2

Exploded View

采用：

工业产品拆解图风格

---

展示：

Cam1

对应光场

对应ROI

对应数据流

---

Cam2

对应光场

对应ROI

对应数据流

---

Cam3

对应光场

对应ROI

对应数据流

---

Cam4

对应光场

对应ROI

对应数据流

---

Level 3

Data Flow

RAW

↓

ROI

↓

Geometry

↓

Embedding

↓

Decision

---

Level 4

Calibration Flow

Reference Board

↓

Calibration Service

↓

Light Matrix

↓

Geometry Builder

---

推荐工具：

Figma

---

协同内容：

接口协议

任务板

标定规范

缺陷定义

统一管理

---

# 24. AI Agent开发规则

所有LLM Agent必须遵守：

Rule 1

优先优化：

成像

几何

表征空间

---

Rule 2

禁止删除：

Geometry Builder

Geometry Cache

Calibration Service

Continuous Learning

---

Rule 3

新增模型必须说明：

输入

输出

延迟

显存

吞吐量

部署方式

---

Rule 4

必须兼容：

Unified Embedding

---

Rule 5

必须保留：

Image Evidence

Geometry Evidence

Decision Evidence

---

# 25. 最终演进路线

Phase 1

YOLO
+
EfficientAD

---

Phase 2

Photometric Stereo
+
Unified Embedding

---

Phase 3

DINO
+
Memory Bank

---

Phase 4

Multi-Light Transformer

---

Phase 5

Foundation Vision Model

---

Phase 6

Industrial Defect Understanding System

---

最终目标：

从缺陷检测

演进到

工业表面理解

工业缺陷解释

工业知识积累

工业持续学习

形成企业级工业缺陷知识库。
