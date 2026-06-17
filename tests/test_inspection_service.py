"""Tests for InspectionService (without real GPU models)."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from app.infrastructure.config_store import ConfigStore


@pytest.fixture
def config() -> ConfigStore:
    return ConfigStore("config.example.json")


class TestInspectionService:
    def test_init_does_not_import_gpu(self, config: ConfigStore) -> None:
        from app.services.inspection_service import InspectionService
        svc = InspectionService(config)
        assert svc._inspector is None
        svc.shutdown()

    def test_import_ok(self, config: ConfigStore) -> None:
        from app.services.inspection_service import InspectionService
        svc = InspectionService(config)
        assert svc._warmed_up is False
        svc.shutdown()

    def test_warmup_forwards_seat_model_id(self, config: ConfigStore) -> None:
        from app.services.inspection_service import InspectionService

        class FakeInspector:
            def __init__(self) -> None:
                self.seat_model_id = None

            def warmup(self, *, seat_model_id=None) -> None:
                self.seat_model_id = seat_model_id

        svc = InspectionService(config)
        inspector = FakeInspector()
        svc._inspector = inspector

        svc.warmup(seat_model_id="MODEL_A")

        assert inspector.seat_model_id == "MODEL_A"
        assert svc._warmed_up is True
        svc.shutdown()

    def test_mock_runtime_requires_explicit_app_flag(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"inspection_mode": "continuous"},
                    "cameras": [
                        {
                            "camera_id": "CAM_LOCAL",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "filter_classifier": {"enabled": False},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))
        assert svc._can_use_mock_runtime() is False
        svc.shutdown()

    def test_mock_runtime_returns_ok_when_explicitly_enabled(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"inspection_mode": "continuous", "mock_runtime_enabled": True},
                    "cameras": [
                        {
                            "camera_id": "CAM_LOCAL",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "filter_classifier": {"enabled": False},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))
        output = svc.inspect_sync({"CAM_LOCAL": np.zeros((2, 2, 3), dtype=np.uint8)})
        response = output.response

        assert response.result.status == "OK"
        assert response.result.decision_reason == "mock_runtime_no_models"
        assert set(output.camera_images) == {"CAM_LOCAL"}
        assert output.camera_images["CAM_LOCAL"].shape == (2, 2, 3)
        svc.shutdown()

    def test_mock_runtime_uses_active_seat_model_by_default(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"inspection_mode": "continuous", "mock_runtime_enabled": True},
                    "cameras": [
                        {
                            "camera_id": "CAM_LOCAL",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "filter_classifier": {"enabled": False},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))
        svc.set_active_seat_model("MODEL_A")
        output = svc.inspect_sync({"CAM_LOCAL": np.zeros((2, 2, 3), dtype=np.uint8)})
        response = output.response

        assert response.result.seat_model_id == "MODEL_A"
        assert response.result.camera_results[0].seat_model_id == "MODEL_A"
        svc.shutdown()

    def test_explicit_seat_model_overrides_active_default(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"inspection_mode": "continuous", "mock_runtime_enabled": True},
                    "cameras": [
                        {
                            "camera_id": "CAM_LOCAL",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "filter_classifier": {"enabled": False},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))
        svc.set_active_seat_model("MODEL_A")
        output = svc.inspect_sync(
            {"CAM_LOCAL": np.zeros((2, 2, 3), dtype=np.uint8)},
            seat_model_id="MODEL_B",
        )
        response = output.response

        assert response.result.seat_model_id == "MODEL_B"
        svc.shutdown()

    def test_inspect_sync_keeps_core_camera_images(self, config: ConfigStore) -> None:
        from app.services.inspection_service import InspectionService
        from seat_defect_core.core_types import InspectionResponse, InspectionResult

        overlay = np.full((2, 2, 3), 127, dtype=np.uint8)

        class FakeInspector:
            def inspect(self, frames, *, seat_model_id=None):
                response = InspectionResponse(
                    result=InspectionResult(
                        part_id="station",
                        frame_id="frame-1",
                        timestamp="2026-06-04T00:00:00Z",
                        status="OK",
                        decision_reason="all_checks_passed",
                        seat_model_id=seat_model_id,
                    ),
                    report_path="",
                    artifact_paths={},
                )
                return response, {"CAM_LOCAL": overlay}

        svc = InspectionService(config)
        svc._inspector = FakeInspector()

        output = svc.inspect_sync(
            {"CAM_LOCAL": np.zeros((2, 2, 3), dtype=np.uint8)},
            seat_model_id="MODEL_A",
        )

        assert output.response.result.seat_model_id == "MODEL_A"
        assert np.array_equal(output.camera_images["CAM_LOCAL"], overlay)
        svc.shutdown()

    def test_active_camera_configs_override_json_cameras(self, tmp_path: Path, monkeypatch) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"inspection_mode": "continuous"},
                    "cameras": [
                        {
                            "camera_id": "CAM_JSON",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "./json_model.npz",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        captured = {}

        class FakeInspector:
            def __init__(self, config) -> None:
                captured["camera_ids"] = [camera.camera_id for camera in config.cameras]
                captured["seat_model_id"] = config.default_seat_model_id

        fake_api = types.ModuleType("seat_defect_core.api")
        fake_api.SeatDefectInspector = FakeInspector
        monkeypatch.setitem(sys.modules, "seat_defect_core.api", fake_api)

        svc = InspectionService(ConfigStore(str(config_path)))
        svc.set_active_camera_configs(
            [
                {
                    "camera_id": "CAM_MODEL",
                    "type": "file_watcher",
                    "enabled": True,
                    "patchcore_model_path": "./model_specific.npz",
                }
            ],
            seat_model_id="MODEL_A",
        )
        svc.init_inspector()

        assert captured["camera_ids"] == ["CAM_MODEL"]
        assert svc.active_seat_model_id() == "MODEL_A"
        svc.shutdown()

    def test_region_models_disable_mock_runtime(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"mock_runtime_enabled": True},
                    "cameras": [
                        {
                            "camera_id": "CAM_REGION",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "regions": [
                                {
                                    "region_id": "upper",
                                    "box": [0.0, 0.0, 1.0, 0.5],
                                    "patchcore_model_path": "./region_model.npz",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))

        assert svc._can_use_mock_runtime() is False
        svc.shutdown()

    def test_disabled_region_models_do_not_disable_mock_runtime(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"mock_runtime_enabled": True},
                    "cameras": [
                        {
                            "camera_id": "CAM_REGION",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "filter_classifier": {"enabled": False},
                            "regions": [
                                {
                                    "region_id": "upper",
                                    "box": [0.0, 0.0, 1.0, 0.5],
                                    "patchcore_model_path": "./region_model.npz",
                                    "enabled": False,
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))

        assert svc._can_use_mock_runtime() is True
        svc.shutdown()

    def test_mock_runtime_checks_active_camera_configs(self, tmp_path: Path) -> None:
        from app.services.inspection_service import InspectionService

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "app": {"mock_runtime_enabled": True},
                    "cameras": [
                        {
                            "camera_id": "CAM_LOCAL",
                            "type": "file_watcher",
                            "enabled": True,
                            "patchcore_model_path": "",
                            "filter_classifier": {"enabled": False},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))
        assert svc._can_use_mock_runtime() is True

        svc.set_active_camera_configs(
            [
                {
                    "camera_id": "CAM_LOCAL",
                    "type": "file_watcher",
                    "enabled": True,
                    "patchcore_model_path": "./active_model.npz",
                    "filter_classifier": {"enabled": False},
                }
            ],
            seat_model_id="MODEL_A",
        )

        assert svc._can_use_mock_runtime() is False
        svc.shutdown()
