<h1 align="center">Online Detection App</h1>

<p align="center">
  <strong>工业座椅缺陷在线实时检测系统</strong><br />
  基于 PySide6/QML + seat_defect_core 的多相机、多模型、实时 ML 推理平台
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-架构设计">架构设计</a> ·
  <a href="#-检测管线">检测管线</a> ·
  <a href="#-屏幕截图">功能概览</a> ·
  <a href="#-配置说明">配置说明</a> ·
  <a href="#-项目结构">项目结构</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/PySide6-6.6+-41CD52?style=flat-square&logo=qt&logoColor=white" />
  <img src="https://img.shields.io/badge/QML-6.6+-41CD52?style=flat-square&logo=qt&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenCV-4.8+-5C3EE8?style=flat-square&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/arch-MVVM-7B3FE4?style=flat-square" />
</p>

---

## 功能特性

- **多相机实时采集** — 支持 Hikrobot MVS 工业相机、RTSP/RTMP 网络流、本地文件监听三种输入模式
- **ML 缺陷检测** — YOLO 区域分割 → EfficientAD 纹理异常检测 → Filter Classifier 误检过滤 → Rule Engine 后处理
- **PLC 联动控制** — Modbus TCP 协议下发缺陷/停线信号，支持产线自动化闭环
- **多座位模型管理** — 按车型/座位切换相机配置与模型文件，一键部署远端的模型
- **NG 弹窗与告警** — 实时缺陷弹窗、热力图叠加、超时自动确认、声音告警
- **检查记录与复盘** — SQLite 持久化存、状统计、历史趋势图、缺陷截图
- **模型热重载** — 监控模型文件变更，无需重启即可切换推理模型
- **平台同步** — 检测记录与模型文件可上传至离线训练平台形成数据闭环
- **工业风格 UI** — 暗色主题、状态角标、工位信息栏、全屏适配

## 检测管线

```
CameraFrame → YOLO Segmentation → ROI Crop/Align → EfficientAD (Texture Anomaly)
                                                                    ↓
                                                          Feature Calibration
                                                           (Normalize/Project/Whiten)
                                                                    ↓
                                                             Filter Classifier
                                                            (False-Positive Suppression)
                                                                    ↓
                                                               Rule Engine
                                                                    ↓
                                                         OK / NG → PLC / Alert
```

## 技术栈

| 层级          | 技术                                |
| ------------- | ----------------------------------- |
| 运行时        | Python 3.11+                        |
| UI 框架       | PySide6 (Qt 6.6+), QML              |
| 计算机视觉    | OpenCV, NumPy                       |
| ML 推理       | PyTorch (YOLO, EfficientAD)         |
| 工业通信      | pymodbus (Modbus TCP)               |
| 日志          | structlog + SQLite                  |
| 包管理        | uv                                  |
| 测试          | pytest, pytest-qt                   |

## 快速开始

### 环境要求

- Python 3.11+
- uv (推荐) 或 pip
- (可选) Hikrobot MVS SDK (如需连接海康工业相机)
- (可选) CUDA 兼容 GPU (如需 GPU 推理)

### 安装与运行

```bash
# 1. 克隆仓库
git clone <repo-url> && cd online-detection-app

# 2. 安装依赖
uv sync

# 3. 复制配置文件并根据实际环境编辑
cp config.example.json config.json

# 4. 启动应用
uv run python -m app.main
```

也可通过环境变量指定配置文件路径:

```bash
SEAT_INSPECTION_CONFIG=/path/to/my_config.json uv run python -m app.main
```

### 运行测试

```bash
uv run pytest                          # 全部测试
uv run pytest tests/test_integration.py -v  # 单文件
```

### 产线联机模式

正式连接 PLC 和海康相机时，建议从生产模板开始：

```bash
cp config.production.example.json config.json
uv run python -m app.diagnostics --config config.json
uv run python -m app.main
```

关键配置：

- `app.inspection_mode`: 生产联机使用 `triggered`，应用只在收到产线触发后检测一件产品。
- `line_signal.enabled`: 生产联机设为 `true`。
- `line_signal.type`: PLC Modbus TCP 使用 `modbus`。
- `line_signal.*_coil` / `*_register`: 必须按现场 PLC 点表填写，并确认地址是 0-based 还是 1-based。
- `cameras[].source`: 海康相机建议用序列号固定设备，例如 `mvs://sn/<SN>?trigger=hardware&trigger_source=Line0&trigger_activation=rising_edge`。

当前握手流程为：PLC 拉高 `capture_request_coil` → 应用检测上升沿 → 应用脉冲 `capture_ack_coil` → 应用置位 `busy_coil` → 抓图检测 → 写入 `ok_coil` / `ng_coil` / `reject_coil` 和 `defect_code_register` → 脉冲 `done_coil` → 清除 busy。异常时写入 `fault_code_register` 并脉冲 `fault_coil`。

如果现场需要沿用旧的单独缺陷/停线脉冲，可将 `plc.enabled=true` 且 `line_signal.also_send_legacy_plc_defect=true`。默认情况下，`triggered + line_signal` 会以 `line_signal` 结果握手为准，避免同一次 NG 重复写 PLC 点位。

### Windows 打包

测试电脑连接海康相机时，建议在 Windows 工控机或同等 Windows 环境打包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

输出目录为 `dist\OnlineDetectionApp`，同时生成 `dist\OnlineDetectionApp-<version>-<commit>.zip`。部署到测试电脑后：

1. 编辑 `dist\OnlineDetectionApp\config.json`，填写相机序列号、PLC IP/端口/点表、模型和标定路径。
2. 将模型放入 `models\`、`deployed_models\`、`deployed_rules\`、`calibration\` 等目录。
3. 确认测试电脑已安装 Hikrobot MVS 运行环境，且相机能在 MVS 工具中正常取流。
4. 先运行 `OnlineDetectionDiagnostics.exe --config config.json` 做配置、模型、系统环境自检。
5. 再运行 `OnlineDetectionLineCheck.exe --config config.json` 确认 PLC/产线信号连接；如需等待一次到位触发，运行 `OnlineDetectionLineCheck.exe --config config.json --wait-trigger --timeout-s 10`。
6. 如需确认相机序列号，运行 `OnlineDetectionMvsList.exe` 查看海康 SDK 可见设备和建议的 `mvs://sn/...` 配置。
7. 再运行 `OnlineDetectionCameraCheck.exe --config config.json --frames 1` 确认海康相机 SDK、相机选择和抓图链路。
8. 运行 `OnlineDetectionApp.exe`。

部署目录也会生成可双击的批处理脚本：`00_verify_deployment.bat`、`01_run_diagnostics.bat`、`02_check_line_signal.bat`、`03_list_mvs_cameras.bat`、`04_check_cameras.bat`、`05_start_app.bat`。

GUI 启动、后台线程异常和未捕获异常会写入 `logs\runtime.log`，现场排障时优先查看这个文件。

构建脚本会先安装依赖、运行测试、执行生产诊断，再调用 PyInstaller 生成可分发目录，写入 `BUILD_INFO.txt` 和 `MANIFEST.json`，压缩成 zip，并检查 GUI/诊断/相机检查/产线信号检查 exe、QML、MVS DLL、配置文件和部署目录是否齐全。需要跳过测试时可使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SkipTests
```

如需单独校验已有部署目录：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_deployment.ps1 -DistRoot dist\OnlineDetectionApp
```

## 架构设计

本应用采用 **MVVM (Model-View-ViewModel)** 架构，通过 PySide6 的 Signal/Slot 机制解耦检测线程与 UI 渲染:

```
┌─────────────────────────────────────────────────────────────┐
│  QML Layer (View)                                           │
│  main.qml · MainScreen · StatsScreen · LogScreen            │
│  SettingsScreen · ReviewScreen · SeatModelScreen            │
│  ModelDeployScreen · NGOverlay · StatusBar                  │
│  Components: ActionButton · InfoCard · StatusBadge · Toast  │
│                      ↕ Binding / Signal                      │
├─────────────────────────────────────────────────────────────┤
│  ViewModel Layer (PySide6 QObject)                          │
│  MainVM · LogVM · StatsVM · SettingsVM · ReviewVM           │
│  SeatModelVM · ModelDeployVM                                │
│                      ↕ Service Interface                     │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                              │
│  InspectionService · AlertManager · StatsCollector          │
│  LogEngine · HotReloadService · SeatModelService            │
│  ModelFileService · PlatformSyncService · ConfigPersistence │
│                      ↕ Adapter Interface                     │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                       │
│  Camera (MVS / RTSP / FileWatcher)                          │
│  PLC (Modbus TCP / Virtual)                                 │
│  CameraImageProvider (image://camera/<id>)                  │
│  ConfigStore                                                │
└─────────────────────────────────────────────────────────────┘
```

- **daemon 线程 `inspection-loop`** 负责 帧抓取 → ML 推理 → 结果分发，不阻塞 Qt 事件循环
- **QPixmap 通过 `CameraImageProvider`** 直接传递到 QML，零拷贝渲染
- **`ThreadPoolExecutor`** 将推理任务卸载到线程池，防止单帧慢推理拖慢整体帧率

## 配置说明

`config.json` 的结构 (完整示例见 `config.example.json`):

```jsonc
{
  "app": {
    "line_id": "A-03",         // 产线 ID
    "station_id": "seat_inspection",  // 工位 ID
    "language": "zh-CN",
    "fullscreen": true,
    "grid_layout": "2x2",      // 相机网格布局，如 2x2 / 1x1 / 3x1
    "inspection_mode": "triggered"
  },
  "cameras": [{
    "camera_id": "CAM_FRONT",
    "source": "mvs://0?exposure_time=6000&gain=8",
    "type": "mvs",             // mvs | rtsp | file_watcher
    "enabled": true,
    "efficientad_model_path": "./models/cam_front.pt",
    "filter_classifier": {
      "enabled": true,
      "model_path": "./deployed_models/filter_classifier/",
      "device": "cuda",
      "confidence_threshold": 0.5
    },
    "rule_engine": { "enabled": true, "deployed_rules_path": "./deployed_rules/rules.json" }
  }],
  "plc": {
    "enabled": false,
    "host": "192.168.1.100",
    "port": 502,
    "defect_coil": 100,
    "stop_coil": 101
  },
  "line_signal": {
    "enabled": true,
    "type": "modbus",
    "host": "192.168.1.100",
    "port": 502,
    "capture_request_coil": 10,
    "capture_ack_coil": 11,
    "busy_coil": 12,
    "done_coil": 13,
    "ok_coil": 14,
    "ng_coil": 15,
    "reject_coil": 16,
    "fault_coil": 17
  },
  "alert": {
    "ng_popup_timeout_seconds": 30,
    "ng_default_action": "confirm_defect",
    "sound_enabled": false
  },
  "storage": {
    "log_dir": "./logs",
    "log_retention_days": 30,
    "screenshot_dir": "./screenshots"
  }
}
```

### 相机类型

| type           | source 格式                                      | 说明                        |
| -------------- | ------------------------------------------------ | --------------------------- |
| `mvs`          | `mvs://<index>?exposure_time=6000&gain=8`        | Hikrobot MVS 工业相机 SDK   |
| `rtsp`         | `rtsp://192.168.1.50:554/stream`                 | RTSP/RTMP 网络流            |
| `file_watcher` | 使用 `watch_dir` 和 `pattern` 字段代替 `source`   | 本地文件目录监听 (开发调试) |

## 项目结构

```
online-detection-app/
├── app/                          # 应用层
│   ├── main.py                   # 入口点: 依赖注入, 启动循环, 生命周期管理
│   ├── qml/                      # QML 视图层
│   │   ├── main.qml              # 主窗口 + TabBar + StackLayout
│   │   ├── MainScreen.qml        # 检测监控页
│   │   ├── CameraGrid.qml        # 多相机网格容器
│   │   ├── CameraTile.qml        # 单相机画面卡片
│   │   ├── NGOverlay.qml         # NG 弹窗 & 热力图叠加层
│   │   ├── StatusBar.qml         # 底部状态栏 (产线/工位/时间/吞吐)
│   │   ├── StatsScreen.qml       # 统计仪表盘
│   │   ├── LogScreen.qml         # 检测记录列表
│   │   ├── ReviewScreen.qml      # 历史记录复盘
│   │   ├── SettingsScreen.qml    # 系统设置 & 配置管理
│   │   ├── SeatModelScreen.qml   # 座位模型管理
│   │   ├── ModelDeployScreen.qml # 模型部署上下架
│   │   └── components/           # 可复用 UI 组件
│   │       ├── ActionButton.qml
│   │       ├── IndustrialDialog.qml
│   │       ├── InfoCard.qml
│   │       ├── StatusBadge.qml
│   │       └── ToastNotification.qml
│   ├── viewmodels/               # ViewModel 层 (Signal/Slot 绑定)
│   │   ├── main_viewmodel.py     # 主监控页 VM
│   │   ├── stats_viewmodel.py    # 统计面板 VM
│   │   ├── log_viewmodel.py      # 检测日志 VM
│   │   ├── review_viewmodel.py   # 复盘审查 VM
│   │   ├── settings_viewmodel.py # 设置页 VM
│   │   ├── seat_model_viewmodel.py
│   │   └── model_deploy_viewmodel.py
│   ├── services/                 # 业务服务层 (无状态/轻状态)
│   │   ├── inspection_service.py     # ML 推理封装 (ThreadPoolExecutor)
│   │   ├── alert_manager.py          # NG 弹窗生命周期管理
│   │   ├── stats_collector.py        # 滚动统计 (计数/良率)
│   │   ├── log_engine.py             # SQLite 持久化
│   │   ├── hot_reload_service.py     # 模型文件 mtime 监控
│   │   ├── config_persistence.py     # 配置 CRUD + 迁移
│   │   ├── seat_model_service.py     # 座位模型切换逻辑
│   │   ├── model_file_service.py     # 模型文件管理
│   │   └── platform_sync_service.py  # 离线平台数据同步
│   ├── infrastructure/           # 基础设施适配器
│   │   ├── camera/               # CameraInterface Protocol 实现
│   │   │   ├── interface.py      # 抽象协议
│   │   │   ├── manager.py        # 多相机生命周期管理 + 看门狗
│   │   │   ├── mvs_adapter.py    # Hikrobot MVS SDK 适配
│   │   │   ├── rtsp_adapter.py   # RTSP/RTMP 流适配
│   │   │   └── file_watcher.py   # 文件目录监听适配
│   │   ├── plc/                  # PLCInterface Protocol 实现
│   │   │   ├── interface.py      # 抽象协议 (DefectSignal)
│   │   │   ├── modbus_adapter.py # Modbus TCP 适配器
│   │   │   └── virtual_plc.py    # 虚拟 PLC (开发调试用)
│   │   ├── config_store.py       # 线程安全 JSON 配置读写
│   │   └── image_provider.py     # QQuickImageProvider 实现
│   └── resources/                # QML 主题/资源
├── seat_defect_core/             # ML 推理核心库
│   ├── api.py                    # SeatDefectInspector 主入口
│   ├── yolo/                     # YOLO 分割模块
│   ├── efficientad/              # EfficientAD 异常检测模块
│   ├── calibration/              # 特征校准 (Normalize/Project/Whiten)
│   ├── classifier/               # Filter Classifier 误检过滤
│   ├── proposal/                 # 候选区域生成
│   ├── rule_engine.py            # 规则引擎后处理
│   ├── fusion.py                 # 多相机结果融合
│   └── training/                 # 训练脚本 & 工具
├── tests/                        # pytest 测试套件
├── config.example.json           # 配置模板
├── pyproject.toml                # 项目元数据 & 工具配置
└── CLAUDE.md                     # AI 助手指令
```

## 贡献

欢迎提交 Issue 和 Pull Request。在提交 PR 前请确保:

- 通过全部测试: `uv run pytest`
- 通过 lint 检查: `uv run ruff check .`
- 测试覆盖新功能或修复

## License

[Internal Use] — 本软件为工业内部检测系统，未经授权不得外部分发。
