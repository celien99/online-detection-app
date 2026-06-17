"""Application entry point."""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.camera.factory import create_camera
from app.infrastructure.config_store import ConfigStore
from app.infrastructure.image_provider import CameraImageProvider
from app.infrastructure.line_signal_factory import create_line_signal
from app.infrastructure.plc.interface import PLCInterface, DefectSignal, Severity
from app.infrastructure.plc.modbus_adapter import ModbusTCPAdapter
from app.infrastructure.plc.virtual_plc import VirtualPLC
from app.services.alert_manager import AlertManager
from app.services.hot_reload_service import HotReloadService
from app.services.inspection_service import InspectionRunOutput, InspectionService
from app.services.log_engine import LogEngine
from app.services.stats_collector import InspectionRecord, StatsCollector
from app.services.trigger_service import TriggerService
from app.viewmodels.log_viewmodel import LogViewModel
from app.viewmodels.main_viewmodel import MainViewModel
from app.viewmodels.review_viewmodel import ReviewViewModel
from app.viewmodels.settings_viewmodel import SettingsViewModel
from app.viewmodels.stats_viewmodel import StatsViewModel
from app.viewmodels.diagnostics_viewmodel import DiagnosticsViewModel
from app.services.config_persistence import ConfigPersistenceService
from app.services.seat_model_service import SeatModelService
from app.services.model_file_service import ModelFileService
from app.services.platform_sync_service import PlatformSyncService
from app.viewmodels.seat_model_viewmodel import SeatModelViewModel
from app.viewmodels.model_deploy_viewmodel import ModelDeployViewModel
from app.runtime_paths import chdir_to_config_dir, resolve_config_path
from app.runtime_logging import get_runtime_logger, setup_runtime_logging
from app.runtime_modes import TRIGGERED_MODE, normalize_inspection_mode


def _create_plc(plc_config: Dict[str, Any]) -> PLCInterface:
    if not plc_config.get("enabled", False):
        return VirtualPLC()
    return ModbusTCPAdapter(
        host=plc_config.get("host", "192.168.1.100"),
        port=plc_config.get("port", 502),
        defect_coil=plc_config.get("defect_coil", 100),
        stop_coil=plc_config.get("stop_coil", 101),
    )


def _should_send_legacy_plc_defect(runtime_mode: str, line_config: Dict[str, Any], plc_config: Dict[str, Any]) -> bool:
    """Keep the old defect pulse only when the line handshake is not authoritative."""
    if not plc_config.get("enabled", False):
        return False
    if normalize_inspection_mode(runtime_mode) == TRIGGERED_MODE and line_config.get("enabled", False):
        return bool(line_config.get("also_send_legacy_plc_defect", False))
    return True


def _iter_patchcore_model_paths(cameras: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for cam in cameras:
        patchcore_path = cam.get("patchcore_model_path", "")
        if patchcore_path:
            paths.append(str(patchcore_path))
        for region in cam.get("regions", []) or []:
            if not isinstance(region, dict):
                continue
            if region.get("enabled", True) is False:
                continue
            region_path = region.get("patchcore_model_path", "")
            if region_path:
                paths.append(str(region_path))
    return paths


def _iter_runtime_reload_paths(cameras: list[dict[str, Any]]) -> list[str]:
    paths = _iter_patchcore_model_paths(cameras)
    for cam in cameras:
        fc = cam.get("filter_classifier", {})
        if fc.get("enabled") and fc.get("model_path"):
            paths.append(str(fc["model_path"]))
        rule_engine = cam.get("rule_engine", {})
        if rule_engine.get("enabled") and rule_engine.get("deployed_rules_path"):
            paths.append(str(rule_engine["deployed_rules_path"]))
    return paths


class QmlHotReload:
    """Watches QML files and sets a flag when changes are detected.

    The flag is polled from the Qt main thread via QTimer, which then calls
    the reload callback — this keeps all QML engine operations on the correct thread.
    """

    def __init__(self, watch_dir: Path) -> None:
        self._dir = watch_dir
        self._running = False
        self._mtimes: dict[str, float] = {}
        self.reload_requested = False
        self._debounce_s = 0.3
        self._last_change = 0.0
        self._pending = False

    def start(self) -> None:
        self._running = True
        t = threading.Thread(target=self._poll, daemon=True, name="qml-watcher")
        t.start()

    def stop(self) -> None:
        self._running = False

    def _poll(self) -> None:
        while self._running:
            changed = self._scan()
            if changed:
                self._last_change = time.time()
                self._pending = True
            if self._pending and (time.time() - self._last_change) >= self._debounce_s:
                self._pending = False
                self.reload_requested = True
            time.sleep(0.5)

    def _scan(self) -> bool:
        changed = False
        for path in self._dir.rglob("*.qml"):
            key = str(path)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if key not in self._mtimes:
                self._mtimes[key] = mtime
            elif mtime != self._mtimes[key]:
                self._mtimes[key] = mtime
                changed = True
        return changed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the online detection GUI.")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--dev", action="store_true", help="Enable QML hot reload")
    args, qt_args = parser.parse_known_args(argv)
    args.qt_args = qt_args
    return args


def main(config_path: str | None = None, argv: list[str] | None = None) -> int:
    logger = get_runtime_logger()
    args = _parse_args(argv)
    if config_path is None:
        config_path = args.config
    dev_mode = args.dev
    if dev_mode:
        os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
        os.environ.setdefault("QT_QUICK_CONTROLS_CONF", "qtquickcontrols2.conf")

    config_file = resolve_config_path(config_path)
    if not config_file.exists():
        print(f"Config file not found: {config_file}", file=sys.stderr)
        return 1
    chdir_to_config_dir(config_file)

    config_path = str(config_file.resolve())
    config = ConfigStore(config_path)
    app_config = config.get_app_config()
    alert_config = config.get_alert_config()
    offline_config = config.get_offline_platform_config()
    raw_runtime_mode = app_config.get("inspection_mode", "continuous")
    runtime_mode = normalize_inspection_mode(raw_runtime_mode)

    # ── Persistence ──
    storage_cfg = config.get_storage_config()
    log_path = setup_runtime_logging(storage_cfg.get("log_dir", "./logs"))
    logger = get_runtime_logger()
    logger.info(
        "Starting application config=%s mode=%s raw_mode=%s runtime_log=%s",
        config_path,
        runtime_mode,
        raw_runtime_mode,
        log_path,
    )
    if raw_runtime_mode != runtime_mode:
        logger.warning("Normalized inspection_mode from %r to %r", raw_runtime_mode, runtime_mode)
    db_path = str(Path(storage_cfg.get("log_dir", "./logs")) / "inspection.db")
    persistence = ConfigPersistenceService(db_path)
    persistence.migrate_from_json(config_path)
    config.set_persistence(persistence)

    # ── New services ──
    seat_model_service = SeatModelService(persistence)
    model_file_service = ModelFileService(
        persistence,
        models_dir=storage_cfg.get("models_dir", "./models"),
    )
    platform_sync = PlatformSyncService(
        base_url=offline_config.get("upload_base_url", ""),
    )

    # ── Infrastructure ──
    camera_manager = CameraManager()
    plc_config = config.get_plc_config()
    line_config = config.get("line_signal", default={})
    plc = _create_plc(plc_config)
    line_signal = create_line_signal(line_config, plc_config)
    send_legacy_plc_defect = _should_send_legacy_plc_defect(runtime_mode, line_config, plc_config)
    log_engine = LogEngine(
        db_path=str(Path(config.get_storage_config().get("log_dir", "./logs")) / "inspection.db"),
        retention_days=config.get_storage_config().get("log_retention_days", 30),
    )
    image_provider = CameraImageProvider()

    # ── Services ──
    inspection_service = InspectionService(config)
    alert_manager = AlertManager(
        timeout_seconds=alert_config.get("ng_popup_timeout_seconds", 30),
        default_action=alert_config.get("ng_default_action", "confirm_defect"),
    )
    stats_collector = StatsCollector()
    hot_reload = HotReloadService(
        poll_seconds=offline_config.get("hot_reload_poll_seconds", 30),
    )
    active_seat_model_id = seat_model_service.get_default_model_id()

    current_runtime_base_cameras = config.get_camera_configs()

    def _base_camera_configs_for_model(seat_model_id: str | None) -> list[dict[str, Any]]:
        if seat_model_id and not current_runtime_base_cameras:
            cameras = seat_model_service.get_cameras_as_config_list(seat_model_id)
            if cameras:
                return cameras
        return current_runtime_base_cameras

    def _runtime_camera_configs_for_model(seat_model_id: str | None) -> list[dict[str, Any]]:
        return model_file_service.apply_active_files_to_cameras(
            _base_camera_configs_for_model(seat_model_id),
            seat_model_id=seat_model_id,
        )

    def _watch_runtime_paths(cameras: list[dict[str, Any]]) -> None:
        hot_reload.clear()
        for model_path in _iter_runtime_reload_paths(cameras):
            hot_reload.watch(model_path)

    def _apply_runtime_model_files(seat_model_id: str | None = None) -> list[dict[str, Any]]:
        resolved_seat_model_id = seat_model_id if seat_model_id is not None else inspection_service.active_seat_model_id()
        cameras = _runtime_camera_configs_for_model(resolved_seat_model_id)
        inspection_service.set_active_camera_configs(cameras, seat_model_id=resolved_seat_model_id)
        if offline_config.get("hot_reload_enabled", False):
            _watch_runtime_paths(cameras)
        return cameras

    active_camera_configs = _apply_runtime_model_files(active_seat_model_id)

    # ── Hot reload ──
    if offline_config.get("hot_reload_enabled", False):
        _watch_runtime_paths(active_camera_configs)
        hot_reload.on_change(inspection_service.reset_runtime)
        hot_reload.start()

    # ── Connect cameras ──
    camera_ids = []
    for cam_config in active_camera_configs:
        try:
            camera = create_camera(cam_config)
            camera_manager.register(camera)
            camera_ids.append(camera.camera_id)
        except Exception as exc:
            logger.exception("Failed to create camera %s", cam_config.get("camera_id", "?"))
            print(f"Failed to create camera {cam_config.get('camera_id', '?')}: {exc}", file=sys.stderr)

    camera_manager.connect_all()

    # ── PLC connect ──
    try:
        plc.connect()
    except Exception:
        logger.exception("PLC connection failed")
        pass
    try:
        line_signal.connect()
    except Exception:
        logger.exception("Line signal connection failed")
        pass

    # ── Start camera watchdog ──
    camera_manager.start_watchdog()

    # ── QML Application ──
    if dev_mode:
        from PySide6.QtCore import qputenv
        qputenv("QML_DISABLE_DISK_CACHE", b"1")

    qt_argv = [sys.argv[0], *args.qt_args]
    app = QGuiApplication(qt_argv)
    app.setApplicationDisplayName("座椅缺陷在线检测系统")

    engine = QQmlApplicationEngine()

    # Image provider
    engine.addImageProvider("camera", image_provider)

    # Theme import path
    theme_path = str(Path(__file__).parent / "resources")
    engine.addImportPath(theme_path)

    # Create ViewModels
    main_vm = MainViewModel(
        inspection_service, alert_manager, stats_collector,
        line_id=app_config.get("line_id", ""),
        camera_ids=camera_ids,
        grid_layout=app_config.get("grid_layout", "2x2"),
        log_engine=log_engine,
    )
    log_vm = LogViewModel(log_engine)
    stats_vm = StatsViewModel(stats_collector)
    settings_vm = SettingsViewModel(config, persistence)
    review_vm = ReviewViewModel(log_engine)
    diagnostics_vm = DiagnosticsViewModel(
        config,
        config_path,
        camera_configs_provider=lambda: _runtime_camera_configs_for_model(
            inspection_service.active_seat_model_id()
        ),
        seat_model_id_provider=inspection_service.active_seat_model_id,
    )

    def _on_deployed_models_changed(seat_model_id: str | None = None) -> list[dict[str, Any]]:
        current_model_id = inspection_service.active_seat_model_id()
        if seat_model_id and current_model_id and seat_model_id != current_model_id:
            return _runtime_camera_configs_for_model(seat_model_id)
        return _apply_runtime_model_files(seat_model_id)

    model_deploy_vm: ModelDeployViewModel | None = None

    def _on_seat_model_switch(new_model_id: str) -> None:
        nonlocal current_runtime_base_cameras
        current_runtime_base_cameras = seat_model_service.get_cameras_as_config_list(new_model_id)
        cameras = _apply_runtime_model_files(new_model_id)
        runtime_cameras = []
        for cam_cfg in cameras:
            camera = create_camera(cam_cfg)
            runtime_cameras.append(camera)
        camera_manager.replace_all(runtime_cameras)
        main_vm._camera_list.clear()
        main_vm._camera_index.clear()
        for cam_cfg in cameras:
            cid = cam_cfg["camera_id"]
            entry = {"cameraId": cid, "live": False, "status": "ok", "defectLabel": "", "frameVersion": 0}
            main_vm._camera_list.append(entry)
            main_vm._camera_index[cid] = entry
        main_vm.cameraListChanged.emit()
        if model_deploy_vm is not None:
            model_deploy_vm.setSeatModel(new_model_id)

    seat_model_vm = SeatModelViewModel(seat_model_service, on_switch=_on_seat_model_switch)
    model_deploy_vm = ModelDeployViewModel(
        model_file_service,
        platform_sync,
        seat_model_service,
        on_runtime_models_changed=_on_deployed_models_changed,
    )

    # Load QML
    qml_path = str(Path(__file__).parent / "qml" / "main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        logger.error("Failed to load QML from %s", qml_path)
        print("Failed to load QML", file=sys.stderr)
        return 1

    root = engine.rootObjects()[0]
    root.setProperty("mainViewModel", main_vm)
    root.setProperty("logViewModel", log_vm)
    root.setProperty("statsViewModel", stats_vm)
    root.setProperty("settingsViewModel", settings_vm)
    root.setProperty("reviewViewModel", review_vm)
    root.setProperty("seatModelViewModel", seat_model_vm)
    root.setProperty("modelDeployViewModel", model_deploy_vm)
    root.setProperty("diagnosticsViewModel", diagnostics_vm)

    # ── QML hot reload (dev mode) ──
    if dev_mode:
        _qml_dir = Path(__file__).parent / "qml"
        _qml_watcher = QmlHotReload(_qml_dir)

        def _hot_reload_tick() -> None:
            if not _qml_watcher.reload_requested:
                return
            _qml_watcher.reload_requested = False
            engine.clearComponentCache()
            engine.load(QUrl.fromLocalFile(qml_path))
            objs = engine.rootObjects()
            if not objs:
                logger.error("QML hot reload produced no root objects")
                print("[hot-reload] QML reload produced no root objects", file=sys.stderr)
                return
            new_root = objs[0]
            new_root.setProperty("mainViewModel", main_vm)
            new_root.setProperty("logViewModel", log_vm)
            new_root.setProperty("statsViewModel", stats_vm)
            new_root.setProperty("settingsViewModel", settings_vm)
            new_root.setProperty("reviewViewModel", review_vm)
            new_root.setProperty("seatModelViewModel", seat_model_vm)
            new_root.setProperty("modelDeployViewModel", model_deploy_vm)
            new_root.setProperty("diagnosticsViewModel", diagnostics_vm)
            print("[hot-reload] QML reloaded")

        _reload_timer = QTimer()
        _reload_timer.timeout.connect(_hot_reload_tick)
        _reload_timer.start(200)

        _qml_watcher.start()
        print(f"[hot-reload] Watching {_qml_dir} for QML changes...")
        logger.info("QML hot reload watching %s", _qml_dir)

    # ── Inspection Loop ──
    running = True
    trigger_service: TriggerService | None = None

    def _publish_live_frames(frames: dict) -> None:
        valid_frames = {cid: frame for cid, frame in frames.items() if frame is not None}
        if not valid_frames:
            return
        for cid, frame in valid_frames.items():
            image_provider.update_frame(cid, frame)
        main_vm.mark_cameras_live(list(valid_frames.keys()))

    def _handle_inspection_response(output: Any, frames: dict, *, publish_frames: bool = True) -> None:
        if isinstance(output, InspectionRunOutput):
            response = output.response
            camera_images = output.camera_images
        else:
            response = getattr(output, "response", output)
            camera_images = getattr(output, "camera_images", {})

        if publish_frames:
            _publish_live_frames(frames)
        for cid, overlay in camera_images.items():
            if overlay is not None:
                image_provider.update_overlay(cid, overlay)

        if hasattr(response, 'result') and hasattr(response.result, 'camera_results'):
            for cr in response.result.camera_results:
                record = InspectionRecord(
                    timestamp=time.time(),
                    camera_id=cr.camera_id,
                    status=cr.status,
                    reason=cr.reason or "",
                    defect_type=getattr(cr.filter_result, 'class_name', '') if hasattr(cr, 'filter_result') and cr.filter_result else '',
                    confidence=float(cr.texture_result.score) if hasattr(cr, 'texture_result') and cr.texture_result else 0.0,
                )
                stats_collector.record(record)
                log_engine.insert(record)
                if cr.status == "NG":
                    severity = Severity.CRITICAL if getattr(cr, 'severity', '') == 'critical' else Severity.MINOR
                    if send_legacy_plc_defect:
                        plc.send_defect_signal(DefectSignal(camera_id=cr.camera_id, severity=severity))
                    if hasattr(cr, 'texture_result') and cr.texture_result is not None:
                        amap = getattr(cr.texture_result, 'heatmap', None)
                        if amap is not None:
                            image_provider.update_heatmap(cr.camera_id, amap)

        main_vm.update_from_result(response, camera_images=camera_images)

    def inspection_loop() -> None:
        nonlocal running
        valid_frames: dict = {}
        while running:
            try:
                frames = camera_manager.grab_all()
                valid_frames = {cid: f for cid, f in frames.items() if f is not None}
                if not valid_frames:
                    time.sleep(0.01)
                    continue

                _publish_live_frames(valid_frames)
                future = inspection_service.inspect_async(valid_frames)
                output = future.result(timeout=5.0)
                _handle_inspection_response(output, valid_frames, publish_frames=False)

            except Exception:
                logger.exception("Inspection loop failed; marking frames as REJECT")
                # Fail-safe: treat inference failure as potential defect so no
                # real defect escapes detection due to a pipeline error.
                for cid in valid_frames:
                    record = InspectionRecord(
                        timestamp=time.time(),
                        camera_id=cid,
                        status="REJECT",
                        reason="pipeline_failed",
                    )
                    stats_collector.record(record)
                    log_engine.insert(record)
                    if send_legacy_plc_defect:
                        plc.send_defect_signal(DefectSignal(camera_id=cid, severity=Severity.MINOR))
                main_vm.update_stats_from_collector()
                time.sleep(0.1)

    if runtime_mode == TRIGGERED_MODE:
        trigger_service = TriggerService(
            adapter=line_signal,
            camera_manager=camera_manager,
            inspection_service=inspection_service,
            handle_response=lambda output, frames: _handle_inspection_response(
                output,
                frames,
                publish_frames=False,
            ),
            handle_frames=_publish_live_frames,
            mode=runtime_mode,
            poll_interval_s=float(app_config.get("trigger_poll_interval_s", 0.05)),
            capture_timeout_s=float(app_config.get("capture_timeout_s", 2.0)),
        )
        main_vm.set_trigger_service(trigger_service)
        trigger_service.start()
        logger.info("Started triggered inspection service")
    else:
        thread = threading.Thread(target=inspection_loop, daemon=True, name="inspection-loop")
        thread.start()
        logger.info("Started continuous inspection loop")

    # ── Timeout checker timer ──
    timer = QTimer()
    def _on_timer_tick() -> None:
        alert_manager.check_timeout()
        main_vm.tick_countdown()
    timer.timeout.connect(_on_timer_tick)
    timer.start(1000)

    # ── Clean shutdown ──
    def cleanup() -> None:
        nonlocal running
        logger.info("Application cleanup started")
        running = False
        if dev_mode:
            _qml_watcher.stop()
        camera_manager.stop_watchdog()
        hot_reload.stop()
        if trigger_service is not None:
            trigger_service.stop()
        camera_manager.disconnect_all()
        line_signal.disconnect()
        plc.disconnect()
        inspection_service.shutdown()
        logger.info("Application cleanup finished")

    signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), app.quit()))
    signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), app.quit()))

    result = app.exec()
    cleanup()
    logger.info("Application exited with code %s", result)
    return result


if __name__ == "__main__":
    sys.exit(main())
