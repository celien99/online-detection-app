# Online Detection App — 全功能管理端扩展设计

> 2026-05-27 · 方案 A：全功能 QML 管理端 + 离线平台可选集成

## 背景

当前在线检测 App（PySide6 + QML）定位为工业现场的**只读监视终端**。配置修改和模型管理必须离线操作（手动编辑 config.json、手动放置模型文件到磁盘）。seat_defect_core 引擎已支持座椅型号、多机位关联等概念，App 层未暴露。

离线分析平台（offline-analysis-platform，FastAPI + React）实现了完整的 NG 样本分析 → 聚类 → 复核 → 训练 → 部署闭环。App 需要能接收平台部署的模型，同时不依赖平台也能独立运行。

## 目标

将 App 从"只读监视终端"升级为"全功能管理 + 监视终端"：

1. **UI 可编辑配置** — 所有设置项在 QML 界面中直接修改并持久化
2. **模型文件管理** — 支持手动导入 + 离线平台同步两种方式，SHA256 校验
3. **座椅型号管理** — CRUD 座椅型号，型号下关联相机和模型，运行时热切换

## 架构概览

```
QML UI (7 tabs)
├─ 📷 监视 (MainScreen)          — 现有
├─ 📊 统计 (StatsScreen)         — 现有
├─ 📋 日志 (LogScreen)           — 现有
├─ 🔍 复核 (ReviewScreen)        — 现有
├─ ⚙ 设置 (SettingsScreen)       — 改造：只读 → 可编辑表单
├─ 🪑 型号 (SeatModelScreen)     — 新增
└─ 📦 模型 (ModelDeployScreen)   — 新增

ViewModels (Python QObject)
├─ SettingsViewModel    — 改造：+setValue, +save, +导入导出
├─ SeatModelViewModel   — 新增：型号 CRUD + 热切换
└─ ModelDeployViewModel — 新增：模型导入/同步/版本管理

Services (Python)
├─ ConfigPersistenceService — 新增：JSON ↔ SQLite 双写
├─ SeatModelService         — 新增：型号 CRUD + 相机关联
├─ ModelFileService         — 新增：文件管理 + SHA256 + 版本回滚
└─ PlatformSyncService      — 新增：离线平台 API 对接
```

## 数据模型

### SQLite 新增表

所有表使用现有 `inspection.db`（LogEngine 同库）。

**seat_models** — 座椅型号

| 列 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | seat_model_001 |
| display_name | TEXT NOT NULL | "座椅型号A" |
| description | TEXT | 备注 |
| is_default | INTEGER DEFAULT 0 | 默认型号 |
| created_at | TEXT NOT NULL | ISO timestamp |
| updated_at | TEXT NOT NULL | ISO timestamp |

**camera_configs** — 相机配置（从 config.json cameras[] 迁移）

| 列 | 类型 | 说明 |
|---|---|---|
| camera_id | TEXT PK | cam_front |
| seat_model_id | TEXT NOT NULL | FK→seat_models |
| type | TEXT DEFAULT 'mvs' | mvs/rtsp/file_watcher |
| source | TEXT NOT NULL | mvs://... / rtsp://... |
| enabled | INTEGER DEFAULT 1 | |
| efficientad_model_path | TEXT | 模型文件路径 |
| filter_classifier_path | TEXT | |
| filter_classifier_enabled | INTEGER | |
| calibration_normalizer | TEXT | |
| calibration_projector | TEXT | |
| display_order | INTEGER | 大屏排序 |
| created_at / updated_at | TEXT | |

**model_files** — 模型文件注册表

| 列 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID |
| camera_id | TEXT | 关联相机 |
| model_type | TEXT | efficientad / filter_classifier / calibration_normalizer / calibration_projector |
| file_path | TEXT | 存储路径 |
| file_name | TEXT | 原始文件名 |
| file_size | INTEGER | 字节数 |
| sha256 | TEXT | SHA256 校验和 |
| source | TEXT | local_upload / platform_sync / manual_import |
| platform_version | TEXT | 离线平台模型版本号 |
| is_active | INTEGER DEFAULT 1 | 当前是否激活 |
| imported_at | TEXT | |

**system_config** — 通用 K-V 配置

| 列 | 类型 | 说明 |
|---|---|---|
| key | TEXT PK | "app.line_id", "plc.host" |
| value | TEXT NOT NULL | |

### JSON ↔ SQLite 同步策略

- **启动时**：JSON 文件 mtime > SQLite 记录的 last_sync → 解析 JSON → 写入 SQLite
- **修改时**：UI 操作 → 写入 SQLite（事务） → 全量导出 JSON（先写 .tmp 再 rename）
- **冲突处理**：SQLite 为准
- **手动 reload**：触发 JSON → SQLite 覆盖同步

## 服务设计

### ConfigPersistenceService

- `init_db()` — 首次建表 / schema 迁移
- `sync_json_to_db()` / `sync_db_to_json()` — 双向同步
- `get(key)` / `set(key, value)` — K-V 读写
- `save()` — 原子写入 JSON（tmp → rename）
- 依赖：sqlite3（标准库）

### SeatModelService

- `list_models()` → list[SeatModel]
- `create_model(id, display_name, description)`
- `update_model(id, **kwargs)`
- `delete_model(id)` — 有关联相机时拒绝
- `set_default(id)` — 切换默认型号
- `get_cameras_for_model(id)` → list[CameraConfig]
- `add_camera_to_model(model_id, camera)`
- `remove_camera(camera_id)`
- `update_camera(camera_id, **kwargs)`

### ModelFileService

- `import_file(camera_id, model_type, src_path)` — 复制到 models/ 目录，计算 SHA256，注册入库
- `register_synced(camera_id, model_type, path, version)` — 离线平台同步来的文件注册
- `verify_checksum(id)` → bool
- `activate(id)` — 将指定版本设为激活（同时更新 camera_configs 的路径字段）
- `rollback(camera_id, model_type)` — 激活上一个版本
- `get_active(camera_id, model_type)` → ModelFile
- `list_history(camera_id, model_type)` → list[ModelFile]

### PlatformSyncService

- `check_health()` → bool
- `list_deployed_models()` — 调用 GET /api/hot-reload/targets
- `download_model(model_id, target_dir)` — 下载模型文件
- `get_deploy_targets()` → list[str]
- `set_base_url(url)` — 动态修改离线平台地址

## ViewModel 设计

### SettingsViewModel（改造）

新增：
- `@Slot(str, str) setValue(path, value)` — 在内存中设置配置值，标记 isDirty
- `@Slot() save()` — 批量持久化所有 dirty 字段
- `@Slot(str) resetToDefault(path)` — 恢复单个配置到默认值
- `@Slot(str) importConfig(filePath)` — 从指定 JSON 文件导入配置
- `@Slot(str) exportConfig(filePath)` — 导出当前配置到 JSON

Property/Signal：
- `isDirty` (bool) — 是否有未保存的修改
- `valueChanged(str path)` — 单个配置值改变
- `saved()` — 保存成功
- `importSucceeded()` / `importFailed(str error)`

### SeatModelViewModel（新增）

Property：
- `seatModels` (QVariantList) — 所有型号列表
- `activeModelId` (str) — 当前激活型号 ID

Slot：
- `createModel(id, name, desc)`
- `updateModel(id, **kwargs)`
- `deleteModel(id)`
- `setActive(modelId)` — 切换型号（含确认弹窗 + 检测引擎重初始化）
- `addCamera(modelId, cameraConfig)`
- `removeCamera(cameraId)`
- `updateCamera(cameraId, **kwargs)`

Signal：
- `modelListChanged()`
- `activeModelChanged(str newId)`
- `switchFailed(str error)`

### ModelDeployViewModel（新增）

Property：
- `modelFiles` (QVariantList) — 可按相机/类型筛选
- `syncStatus` (str) — "online" / "offline" / "syncing"
- `lastSyncTime` (str)

Slot：
- `importModelFile(cameraId, modelType, filePath)` — 手动导入（打开 FileDialog）
- `syncFromPlatform()` — 从离线平台拉取可部署模型列表
- `downloadAndActivate(fileId)` — 下载并激活指定版本
- `activateVersion(fileId)` — 激活本地已有版本
- `rollback(cameraId, modelType)` — 回滚到上一版本
- `deleteModelFile(fileId)` — 删除非激活版本

Signal：
- `modelFileAdded()`
- `syncCompleted(int newCount)`
- `syncFailed(str error)`

## QML UI 设计

### 视觉语言

| 属性 | 值 |
|---|---|
| 主题 | 暗色工业 HMI |
| 卡片风格 | 玻璃拟态：`background: rgba(255,255,255,0.04)` + `backdrop-filter: blur` |
| 圆角体系 | 4 / 8 / 12 / 20 px 四档 |
| 间距栅格 | 4px 基准 |
| 主色调 | `#00ff88` 绿色强调 |
| 按钮 | 主操作渐变绿，次要操作半透明 |
| 状态指示 | 发光脉冲光点（绿=正常，黄=警告，红=异常） |
| 过渡动画 | 200-300ms ease-out |

### 交互动效

| 场景 | 动效 | 时长 |
|---|---|---|
| 侧边栏/内容切换 | crossfade | 200ms |
| 卡片展开/折叠 | height + opacity ease-out | 300ms |
| Toast 通知 | slide-up + fade，自动消失 | 3s |
| 按钮 hover | scale(1.02) + 阴影增强 | 150ms |
| 状态指示灯 | 脉冲呼吸动画 | 2s 循环 |
| 开关 toggle | 滑块平滑滑动 | 200ms |
| 列表新增/删除 | slide-fade in/out | 250ms |

### 改造页面：SettingsScreen

- 左侧边栏保留 7 个分类
- 每个分类的 Text 标签 → `TextField` / `ComboBox` / `Switch`
- 相机卡片：默认折叠显示名称+类型+状态，点击展开编辑模型路径
- 底部操作栏：重新加载 / **保存所有更改** / 导入配置 / 导出配置 / 恢复默认

### 新增页面：SeatModelScreen

- 顶部：当前型号下拉选择器 + 型号计数 + 新增按钮
- 列表：每个型号卡片（名称、描述、关联相机数、是否默认）
- 操作：编辑 / 设为默认 / 删除
- 切换型号时弹出确认对话框

### 新增页面：ModelDeployScreen

- 顶部状态卡片：平台连接状态 / 本地模型总数 / 最近同步时间
- 筛选栏：按相机 / 按模型类型
- 操作栏：从离线平台同步 / 手动导入
- 文件列表：文件名、相机、类型、版本、SHA256 缩写、大小、时间
- 激活版本高亮（绿色左边框），非激活版本可激活或删除

### TabBar 变更

从 4 个 Tab → 7 个 Tab：
监视 / 统计 / 日志 / 复核 / **设置** / **型号** / **模型**

（设置移到型号和模型前面，因为使用频率更高）

## 数据流

### 配置修改
```
QML TextField → viewModel.setValue() → isDirty=true
→ 用户点"保存" → viewModel.save()
→ ConfigPersistenceService: SQLite 事务写入 → JSON 原子写入
→ ConfigStore.reload() → 通知各服务
→ Toast "配置已保存"
```

### 型号切换
```
QML ComboBox → viewModel.setActive(newId)
→ 确认弹窗
→ SeatModelService.get_cameras_for_model(newId)
→ InspectionService.switch_seat_model(newId)
→ MainViewModel.cameraList 更新 → CameraGrid 重绘
→ HotReloadService 重新注册模型路径
→ Toast "已切换至：座椅型号B"
```

### 模型同步
```
QML "从离线平台同步" → PlatformSyncService.check_health()
→ 不可达 → 显示"离线" + 手动导入仍可用
→ 可达 → GET /api/hot-reload/targets → 显示可部署模型列表
→ 用户选择 → download_model() → SHA256 校验
→ ModelFileService.register_synced() → 更新 camera_configs
→ Toast "已同步 3 个模型"
```

## 错误处理

| 场景 | 处理 |
|---|---|
| JSON 文件损坏 | 回退 SQLite 数据 → Toast 告警 → 自动修复 JSON |
| SQLite 写入失败 | 直接写 JSON 兜底 → 红色告警 → 提示清理磁盘 |
| 模型文件不存在 | 路径旁 ⚠ 图标 → 该相机降级为"仅采集不检测" |
| SHA256 校验失败 | 拒绝激活 → Toast "校验失败，请重新导入" |
| 离线平台不可达 | 静默降级 → 显示"离线"状态 → 手动导入仍可用 |
| 切换型号时检测运行中 | 等待当前帧完成 → 切换 → 恢复 |
| 删除有关联相机的型号 | 阻止 → Toast "该型号下还有 N 台相机" |

## 测试策略

| 类型 | 覆盖 |
|---|---|
| 单元测试 | SeatModelService CRUD、ModelFileService 校验/激活/回滚、ConfigPersistenceService 同步逻辑、PlatformSyncService API mock |
| 集成测试 | 型号切换→引擎重初始化、配置保存→JSON+SQLite 双写一致性、文件导入→SHA256→注册 |
| ViewModel 测试 | setValue/getValue 往返、save→reload 一致性、Signal 发射 |
| 人工验证 | QML UI 交互流畅度、暗色主题一致性、Toast 可读性、动画效果 |

## 约定

- **模型文件目录**：`./models/`（相对于 App 工作目录），可通过配置项 `storage.models_dir` 修改
- **默认值来源**：`config.example.json` 作为默认值模板，"恢复默认"按钮将对应字段重置为此模板中的值
- **JSON 同步时间戳**：SQLite 表 `system_config` 中记录 `key="_meta.last_json_sync"` 存储上次同步的 JSON mtime

## 兼容性

- 启动时检测：若 SQLite 表不存在，从 config.json 初始化（首次迁移）
- 启动时检测：若 config.json 不存在，从 SQLite 导出（恢复）
- CameraManager / InspectionService / HotReloadService 的现有接口保持兼容
- 不强制要求离线平台存在 — `offline_platform.upload_base_url` 为空时跳过所有同步逻辑

## 不包含

- 离线平台自身的功能修改（React 前端、API、Worker）
- 在线检测引擎 seat_defect_core 的推理逻辑修改
- 用户权限/登录系统（当前为单用户场景）
- 远程 OTA 固件升级
