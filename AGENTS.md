# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the app (requires config.json)
uv run python -m app.main

# Run in dev mode with QML hot reload
uv run python -m app.main --dev

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_inspection_service.py

# Run a single test
uv run pytest tests/test_integration.py::TestFullPipeline::test_config_load -v

# Lint
uv run ruff check .
```

## Architecture

This is an industrial seat defect online detection desktop app. It captures frames from industrial cameras, runs ML-based anomaly detection via `seat_defect_core`, and displays results in a PySide6/QML UI.

**Startup flow** (`app/main.py`): `main()` loads `config.json` → wires ConfigStore, CameraManager, PLC adapter, InspectionService, AlertManager, StatsCollector, HotReloadService → creates QGuiApplication + QQmlApplicationEngine → pushes ViewModels as QML context properties → starts a background `inspection_loop` thread that grabs frames and runs inference → enters Qt event loop.

**Layers:**
- **`app/qml/`** — QML views. `main.qml` is the ApplicationWindow with a TabBar + StackLayout switching between MainScreen, StatsScreen, LogScreen, SettingsScreen. `components/` has shared elements (ActionButton, InfoCard, StatusBadge).
- **`app/viewmodels/`** — PySide6 `QObject` subclasses exposing `Property` + `Signal` + `Slot` to QML. Created in `main()` and attached to the QML root object as context properties. `MainViewModel` handles the monitor tab: camera grid data, NG overlay visibility, acknowledge/review/dismiss actions.
- **`app/services/`** — Stateless (mostly) service classes. `InspectionService` wraps `seat_defect_core.SeatDefectInspector` in a `ThreadPoolExecutor` for async inference. `AlertManager` manages NG popup lifecycle with timeout. `StatsCollector` keeps in-memory rolling stats. `LogEngine` persists records to SQLite. `HotReloadService` watches model file mtimes for live-update.
- **`app/infrastructure/`** — `camera/` adapters for MVS (Hikrobot SDK), RTSP streams, and directory-based file watching, all implementing the `CameraInterface` Protocol. `plc/` adapters for Modbus TCP or a no-op VirtualPLC, implementing `PLCInterface`. `CameraImageProvider` streams numpy frames to QML via `image://camera/<id>`. `ConfigStore` wraps JSON config with thread-safe reads and mtime-based reload.

**Inspection loop** (runs on daemon thread `inspection-loop`): `camera_manager.grab_all()` → filter non-None frames → update `CameraImageProvider` for QML display → `inspection_service.inspect_async()` (offloaded to thread pool) → record results in `StatsCollector` → call `main_vm.update_from_result()` which emits QML signals → if NG, trigger `AlertManager` and send PLC defect signal.

**`seat_defect_core/`** — Local package providing the ML runtime. The detection pipeline per camera: YOLO segmentation → ROI crop/align → PatchCore texture anomaly detection → Filter Classifier (false-positive suppression) → Rule Engine post-processing. Multi-camera fusion combines per-camera results. Entry points: `SeatDefectInspector` class for programmatic use, `python -m seat_defect_core` for CLI.

**Testing:** pytest with `pytest-qt`. Tests live in `tests/`. `test_integration.py` verifies service wiring with mock cameras and PLC. Config is loaded from `config.example.json` (the committed example) — `config.json` is gitignored and created by copying the example.
