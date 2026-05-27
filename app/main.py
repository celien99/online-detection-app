"""Application entry point."""
from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from app.infrastructure.camera.file_watcher import FileWatcherCamera
from app.infrastructure.camera.interface import CameraInterface
from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.camera.mvs_adapter import MvsCameraAdapter
from app.infrastructure.camera.rtsp_adapter import RTSPCameraAdapter
from app.infrastructure.config_store import ConfigStore
from app.infrastructure.image_provider import CameraImageProvider
from app.infrastructure.plc.interface import PLCInterface, DefectSignal, Severity
from app.infrastructure.plc.modbus_adapter import ModbusTCPAdapter
from app.infrastructure.plc.virtual_plc import VirtualPLC
from app.services.alert_manager import AlertManager
from app.services.hot_reload_service import HotReloadService
from app.services.inspection_service import InspectionService
from app.services.log_engine import LogEngine
from app.services.stats_collector import InspectionRecord, StatsCollector
from app.viewmodels.log_viewmodel import LogViewModel
from app.viewmodels.main_viewmodel import MainViewModel
from app.viewmodels.review_viewmodel import ReviewViewModel
from app.viewmodels.settings_viewmodel import SettingsViewModel
from app.viewmodels.stats_viewmodel import StatsViewModel
from app.services.config_persistence import ConfigPersistenceService
from app.services.seat_model_service import SeatModelService
from app.services.model_file_service import ModelFileService
from app.services.platform_sync_service import PlatformSyncService
from app.viewmodels.seat_model_viewmodel import SeatModelViewModel
from app.viewmodels.model_deploy_viewmodel import ModelDeployViewModel


def _create_camera(camera_config: Dict[str, Any]) -> CameraInterface:
    camera_id = camera_config["camera_id"]
    source = camera_config.get("source", "")
    cam_type = camera_config.get("type", "mvs")

    if cam_type == "mvs" and source.startswith("mvs://"):
        return MvsCameraAdapter(camera_id, source)
    elif cam_type == "rtsp" and (source.startswith("rtsp://") or source.startswith("rtmp://")):
        return RTSPCameraAdapter(camera_id, source)
    elif cam_type == "file_watcher":
        watch_dir = camera_config.get("watch_dir", f"./input/{camera_id}")
        pattern = camera_config.get("pattern", "*.jpg")
        return FileWatcherCamera(camera_id, watch_dir, pattern)
    else:
        raise ValueError(f"Unsupported camera type or source for {camera_id}: type={cam_type}, source={source}")


def _create_plc(plc_config: Dict[str, Any]) -> PLCInterface:
    if not plc_config.get("enabled", False):
        return VirtualPLC()
    return ModbusTCPAdapter(
        host=plc_config.get("host", "192.168.1.100"),
        port=plc_config.get("port", 502),
        defect_coil=plc_config.get("defect_coil", 100),
        stop_coil=plc_config.get("stop_coil", 101),
    )


def main(config_path: str | None = None) -> int:
    if config_path is None:
        config_path = os.environ.get("SEAT_INSPECTION_CONFIG", "config.json")
    if not Path(config_path).exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 1

    config = ConfigStore(config_path)
    app_config = config.get_app_config()
    alert_config = config.get_alert_config()
    offline_config = config.get_offline_platform_config()

    # ── Persistence ──
    storage_cfg = config.get_storage_config()
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
    plc = _create_plc(config.get_plc_config())
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

    # ── Hot reload ──
    if offline_config.get("hot_reload_enabled", False):
        for cam in config.get_camera_configs():
            fc = cam.get("filter_classifier", {})
            if fc.get("enabled") and fc.get("model_path"):
                hot_reload.watch(fc["model_path"])
            ead_path = cam.get("efficientad_model_path", "")
            if ead_path:
                hot_reload.watch(ead_path)
        hot_reload.on_change(lambda: setattr(inspection_service, '_inspector', None))
        hot_reload.start()

    # ── Connect cameras ──
    camera_ids = []
    for cam_config in config.get_camera_configs():
        try:
            camera = _create_camera(cam_config)
            camera_manager.register(camera)
            camera_ids.append(camera.camera_id)
        except Exception as exc:
            print(f"Failed to create camera {cam_config.get('camera_id', '?')}: {exc}", file=sys.stderr)

    camera_manager.connect_all()

    # ── PLC connect ──
    try:
        plc.connect()
    except Exception:
        pass

    # ── Start camera watchdog ──
    camera_manager.start_watchdog()

    # ── QML Application ──
    app = QGuiApplication(sys.argv)
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

    def _on_seat_model_switch(new_model_id: str) -> None:
        cameras = seat_model_service.get_cameras_as_config_list(new_model_id)
        inspection_service._inspector = None  # force re-init with new model
        main_vm._camera_list.clear()
        main_vm._camera_index.clear()
        for idx, cam_cfg in enumerate(cameras):
            cid = cam_cfg["camera_id"]
            entry = {"cameraId": cid, "live": False, "status": "ok", "defectLabel": ""}
            main_vm._camera_list.append(entry)
            main_vm._camera_index[cid] = entry
        main_vm.cameraListChanged.emit()
        hot_reload._paths.clear()
        for cam in cameras:
            fc = cam.get("filter_classifier", {})
            if fc.get("enabled") and fc.get("model_path"):
                hot_reload.watch(fc["model_path"])
            ead_path = cam.get("efficientad_model_path", "")
            if ead_path:
                hot_reload.watch(ead_path)

    seat_model_vm = SeatModelViewModel(seat_model_service, on_switch=_on_seat_model_switch)
    model_deploy_vm = ModelDeployViewModel(model_file_service, platform_sync)

    # Load QML
    qml_path = str(Path(__file__).parent / "qml" / "main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
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

    # ── Inspection Loop ──
    running = True

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

                for cid, frame in valid_frames.items():
                    image_provider.update_frame(cid, frame)

                main_vm.mark_cameras_live(list(valid_frames.keys()))

                future = inspection_service.inspect_async(valid_frames)
                response = future.result(timeout=5.0)

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
                            plc.send_defect_signal(DefectSignal(camera_id=cr.camera_id, severity=severity))
                            # 存储异常热力图到 ImageProvider 供 NGOverlay 使用
                            if hasattr(cr, 'texture_result') and cr.texture_result is not None:
                                amap = getattr(cr.texture_result, 'anomaly_map', None)
                                if amap is not None:
                                    image_provider.update_heatmap(cr.camera_id, amap)

                main_vm.update_from_result(response)

            except Exception as exc:
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
                    plc.send_defect_signal(DefectSignal(camera_id=cid, severity=Severity.MINOR))
                main_vm.update_stats_from_collector()
                time.sleep(0.1)

    thread = threading.Thread(target=inspection_loop, daemon=True, name="inspection-loop")
    thread.start()

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
        running = False
        camera_manager.stop_watchdog()
        hot_reload.stop()
        camera_manager.disconnect_all()
        plc.disconnect()
        inspection_service.shutdown()

    signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), app.quit()))
    signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), app.quit()))

    result = app.exec()
    cleanup()
    return result


if __name__ == "__main__":
    sys.exit(main())
