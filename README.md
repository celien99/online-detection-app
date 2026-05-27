# Online Detection Program

工业座椅缺陷在线实时检测程序。基于 seat_defect_core + PySide6/QML。

## 快速开始

```bash
# 安装依赖
uv sync

# 复制并编辑配置
cp config.example.json config.json

# 运行
uv run python -m app.main
```

## 目录结构

- `app/main.py` — 应用入口
- `app/qml/` — QML 界面文件
- `app/viewmodels/` — ViewModel 层 (PySide6 Signal/Slot)
- `app/services/` — 业务服务层
- `app/infrastructure/camera/` — 相机适配器 (mvs/RTSP/FileWatcher)
- `app/infrastructure/plc/` — PLC 适配器 (Modbus TCP/Virtual)
- `tests/` — 单元和集成测试
