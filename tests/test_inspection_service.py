"""Tests for InspectionService (without real GPU models)."""
from __future__ import annotations

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
