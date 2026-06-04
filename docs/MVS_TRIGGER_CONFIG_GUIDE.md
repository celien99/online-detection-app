# MVS 相机 Trigger 配置快速切换指南

本文用于快速调整 `config.json` 中 Hikrobot MVS 相机的触发方式。MVS 相机触发方式主要由 `cameras[].source` 的 `trigger` 参数决定；应用是否启用“手动触发/产线触发”由 `app.inspection_mode` 和 `line_signal` 决定。

## 快速选择

| 场景 | `source` 中的 `trigger` | `app.inspection_mode` | `line_signal.enabled` | 说明 |
| --- | --- | --- | --- | --- |
| 本机调试实时画面 | `continuous` | `continuous` | `false` | 相机连续出图，监控页持续刷新 |
| 本机测试“手动触发”按钮 | `software` | `triggered` | `true` | 点击按钮后应用向相机发送一次软件触发 |
| 产线 PLC/光电硬触发 | `hardware` | `triggered` | `true` | 外部 Line0 脉冲触发相机曝光 |

## 1. 连续采集 continuous

适用：本机调试、验证画面、验证相机连接，不依赖 PLC 或外部触发线。

相机 `source`：

```json
"source": "mvs://sn/DA9184658?trigger=continuous&timeout_ms=2000&pixel_format=bgr8"
```

应用配置：

```json
"app": {
  "inspection_mode": "continuous"
},
"line_signal": {
  "enabled": false,
  "type": "virtual"
}
```

注意：

- `trigger=continuous` 时，`trigger_source=Line0` 和 `trigger_activation=rising_edge` 不起作用，建议删除，避免误解。
- 监控页会由后台连续检测循环刷新。
- “手动触发”按钮不会生效，因为 `TriggerService` 只在 `inspection_mode=triggered` 时创建。

验证命令：

```powershell
conda run -n online-detection-app python -m app.camera_check --config config.json --camera-id CAM_0 --frames 1 --timeout-ms 2000 --mvs-trigger-mode continuous --save-dir camera_samples
```

## 2. 软件触发 software

适用：没有 PLC/光电硬件脉冲，但需要测试监控页“手动触发”按钮、触发检测流程和 NG 弹窗流程。

相机 `source`：

```json
"source": "mvs://sn/DA9184658?trigger=software&timeout_ms=2000&pixel_format=bgr8"
```

应用配置：

```json
"app": {
  "inspection_mode": "triggered",
  "trigger_poll_interval_s": 0.05,
  "capture_timeout_s": 2.0
},
"line_signal": {
  "enabled": true,
  "type": "virtual"
}
```

行为：

- 点击“手动触发”后，应用创建一次检测请求。
- MVS 适配器在取图时调用 `TriggerSoftware`，相机曝光并返回一帧。
- 不需要 Line0 外部脉冲。

验证命令：

```powershell
conda run -n online-detection-app python -m app.camera_check --config config.json --camera-id CAM_0 --frames 1 --timeout-ms 2000 --mvs-trigger-mode software --save-dir camera_samples
```

## 3. 硬件触发 hardware

适用：产线 PLC、光电、工装到位信号接入相机触发输入口，例如 Line0。

相机 `source`：

```json
"source": "mvs://sn/DA9184658?trigger=hardware&trigger_source=Line0&trigger_activation=rising_edge&timeout_ms=2000&pixel_format=bgr8"
```

应用配置：

```json
"app": {
  "inspection_mode": "triggered",
  "trigger_poll_interval_s": 0.05,
  "capture_timeout_s": 2.0
},
"line_signal": {
  "enabled": true,
  "type": "modbus",
  "host": "192.168.1.100",
  "port": 502
}
```

行为：

- PLC 或产线信号先通知应用有一次检测请求。
- 应用进入检测流程后调用相机取图。
- 相机只有收到外部 Line0 上升沿脉冲才会曝光并返回帧。

注意：

- `trigger=hardware` 时，点击软件“手动触发”只能创建检测请求，不能替代相机 Line0 硬件脉冲。
- 如果没有外部脉冲，相机会连接成功但一直取不到帧，界面可能显示“无信号”或触发错误 `capture_timeout_no_frames`。
- 多相机生产配置建议始终使用 `mvs://sn/<序列号>`，不要依赖 `mvs://0` 这类枚举顺序。

验证命令：

```powershell
conda run -n online-detection-app python -m app.camera_check --config config.json --camera-id CAM_0 --frames 1 --timeout-ms 5000 --mvs-trigger-mode hardware --save-dir camera_samples
```

运行该命令时必须给相机 Line0 一个真实触发脉冲。

## 推荐调试顺序

1. 先用 `continuous` 确认相机能连接并稳定出图。
2. 再切到 `software` 测试应用内“手动触发”和检测流程。
3. 最后切到 `hardware`，接入 PLC/光电后做产线联机测试。

## 常见问题

### 监控页一直显示“无信号”

可能原因：

- 相机未连接或序列号不匹配。
- 当前是 `hardware`，但 Line0 没有触发脉冲。
- 检测模型或规则路径不存在，检测流程失败后没有把相机标记为 live。
- 只是测试画面时未启用 mock runtime，或 `filter_classifier.enabled=true` 但模型目录不存在。

测试画面时可临时使用：

```json
"app": {
  "inspection_mode": "continuous",
  "mock_runtime_enabled": true
}
```

并把相机中的过滤分类器关闭：

```json
"filter_classifier": {
  "enabled": false
}
```

### 点击“手动触发”无反应

检查：

- `app.inspection_mode` 是否为 `triggered`。
- `line_signal.enabled` 是否为 `true`。
- 相机是否使用 `trigger=software`，或者硬件触发时是否有真实 Line0 脉冲。

### `trigger=continuous` 还能不能保留 `trigger_source=Line0`

不建议保留。连续采集模式下这些参数不会触发相机，只会让配置读起来像硬触发，容易误判现场问题。

