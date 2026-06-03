"""Tests for InspectionService (without real GPU models)."""
from __future__ import annotations

import json
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
                            "efficientad_model_path": "",
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
                            "efficientad_model_path": "",
                            "filter_classifier": {"enabled": False},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        svc = InspectionService(ConfigStore(str(config_path)))
        response = svc.inspect_sync({"CAM_LOCAL": np.zeros((2, 2, 3), dtype=np.uint8)})

        assert response.result.status == "OK"
        assert response.result.decision_reason == "mock_runtime_no_models"
        svc.shutdown()
