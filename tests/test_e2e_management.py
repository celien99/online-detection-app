"""End-to-end smoke test for management features."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.services.config_persistence import ConfigPersistenceService
from app.services.seat_model_service import SeatModelService
from app.services.model_file_service import ModelFileService


def test_full_config_edit_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        json_path = Path(tmp) / "config.json"
        json_path.write_text(json.dumps({
            "app": {"line_id": "TEST-LINE"},
            "plc": {"host": "192.168.1.1", "port": 502},
        }), encoding="utf-8")

        db_path = str(Path(tmp) / "test.db")
        persistence = ConfigPersistenceService(db_path)
        persistence.migrate_from_json(str(json_path))

        config = ConfigStore(str(json_path))
        config.set_persistence(persistence)

        config.set("plc.host", "10.0.0.99")
        config.save()

        assert persistence.get("plc.host") == "10.0.0.99"

        with open(json_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["plc"]["host"] == "10.0.0.99"


def test_seat_model_camera_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        persistence = ConfigPersistenceService(db_path)
        svc = SeatModelService(persistence)

        svc.create_model("seat_a", "座椅型号A")
        assert len(svc.list_models()) == 1

        svc.add_camera("seat_a", {"camera_id": "cam1", "type": "mvs", "source": "mvs://1"})
        svc.add_camera("seat_a", {"camera_id": "cam2", "type": "rtsp", "source": "rtsp://10.0.0.1"})
        assert len(svc.get_cameras("seat_a")) == 2

        configs = svc.get_cameras_as_config_list("seat_a")
        assert configs[0]["camera_id"] == "cam1"
        assert configs[0]["filter_classifier"]["enabled"] is False


def test_model_file_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        models_dir = str(Path(tmp) / "models")
        persistence = ConfigPersistenceService(db_path)
        mfs = ModelFileService(persistence, models_dir=models_dir)

        src = Path(tmp) / "test_model.pt"
        src.write_bytes(b"model weights")
        mf = mfs.import_file("cam1", "efficientad", str(src))

        assert mfs.verify_checksum(mf["id"]) is True

        active = mfs.get_active("cam1", "efficientad")
        assert active is not None

        src2 = Path(tmp) / "test_model_v2.pt"
        src2.write_bytes(b"model weights v2")
        mf2 = mfs.import_file("cam1", "efficientad", str(src2))
        mfs.activate(mf["id"])
        active = mfs.get_active("cam1", "efficientad")
        assert active["id"] == mf["id"]
