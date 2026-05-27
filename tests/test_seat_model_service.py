"""Tests for SeatModelService."""
from __future__ import annotations

from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService
from app.services.seat_model_service import SeatModelService


def _setup(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    persistence = ConfigPersistenceService(db_path)
    svc = SeatModelService(persistence)
    return svc


def test_create_and_list_models(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "型号A", "描述A")
    svc.create_model("m2", "型号B")
    models = svc.list_models()
    assert len(models) == 2
    # Ordered by created_at DESC, so m2 is first
    assert models[1]["id"] == "m1"
    assert models[1]["display_name"] == "型号A"


def test_set_default_model(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.create_model("m2", "B")
    svc.set_default("m2")
    models = svc.list_models()
    assert models[0]["id"] == "m2"
    assert models[0]["is_default"] == 1


def test_delete_model_without_cameras_succeeds(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    assert svc.delete_model("m1") is True
    assert len(svc.list_models()) == 0


def test_delete_model_with_cameras_fails(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
    assert svc.delete_model("m1") is False
    assert len(svc.list_models()) == 1


def test_add_camera_to_model(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {
        "camera_id": "cam1", "type": "rtsp", "source": "rtsp://10.0.0.1",
        "efficientad_model_path": "./models/cam1.pt",
    })
    cameras = svc.get_cameras("m1")
    assert len(cameras) == 1
    assert cameras[0]["camera_id"] == "cam1"
    assert cameras[0]["type"] == "rtsp"
    assert cameras[0]["efficientad_model_path"] == "./models/cam1.pt"


def test_get_cameras_as_config_list(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {
        "camera_id": "cam1", "type": "mvs", "source": "mvs://1",
        "filter_classifier_path": "./fc/", "filter_classifier_enabled": True,
        "calibration_normalizer": "./cal/norm.json", "calibration_projector": "./cal/proj.pt",
    })
    configs = svc.get_cameras_as_config_list("m1")
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg["camera_id"] == "cam1"
    assert cfg["filter_classifier"]["enabled"] is True
    assert cfg["filter_classifier"]["model_path"] == "./fc/"
    assert cfg["calibration"]["normalizer_path"] == "./cal/norm.json"
    assert cfg["calibration"]["projector_path"] == "./cal/proj.pt"


def test_remove_camera(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
    svc.remove_camera("cam1")
    assert len(svc.get_cameras("m1")) == 0


def test_update_camera(tmp_path: Path):
    svc = _setup(tmp_path)
    svc.create_model("m1", "A")
    svc.add_camera("m1", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
    svc.update_camera("cam1", efficientad_model_path="./models/new.pt", enabled=False)
    cam = svc.get_cameras("m1")[0]
    assert cam["efficientad_model_path"] == "./models/new.pt"
    assert cam["enabled"] == 0
