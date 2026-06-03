"""Tests for ModelFileService."""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService
from app.services.model_file_service import ModelFileService


def _setup(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    models_dir = str(tmp_path / "models")
    persistence = ConfigPersistenceService(db_path)
    svc = ModelFileService(persistence, models_dir=models_dir)
    return svc, tmp_path


def test_import_file(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "source.pt"
    src.write_bytes(b"fake model content")

    mf = svc.import_file("cam1", "patchcore", str(src))
    assert mf["camera_id"] == "cam1"
    assert mf["model_type"] == "patchcore"
    assert mf["source"] == "local_upload"
    assert mf["is_active"] == 1
    assert mf["file_name"] == "source.pt"
    assert Path(mf["file_path"]).exists()
    assert mf["file_size"] == 18


def test_sha256_calculated_on_import(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    content = b"deterministic content for sha256"
    src.write_bytes(content)

    mf = svc.import_file("cam2", "filter_classifier", str(src))
    expected_sha = hashlib.sha256(content).hexdigest()
    assert mf["sha256"] == expected_sha


def test_verify_checksum_pass(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    src.write_bytes(b"test")
    mf = svc.import_file("cam1", "patchcore", str(src))
    assert svc.verify_checksum(mf["id"]) is True


def test_verify_checksum_fail_on_tampered_file(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    src.write_bytes(b"original")
    mf = svc.import_file("cam1", "patchcore", str(src))
    Path(mf["file_path"]).write_bytes(b"tampered")
    assert svc.verify_checksum(mf["id"]) is False


def test_activate_deactivates_others(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src1 = base / "v1.pt"
    src1.write_bytes(b"v1")
    src2 = base / "v2.pt"
    src2.write_bytes(b"v2")

    mf1 = svc.import_file("cam1", "patchcore", str(src1))
    mf2 = svc.import_file("cam1", "patchcore", str(src2))

    svc.activate(mf1["id"])
    history = svc.list_history("cam1", "patchcore")
    active = [m for m in history if m["is_active"] == 1]
    assert len(active) == 1
    assert active[0]["id"] == mf1["id"]


def test_rollback_to_previous(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src1 = base / "v1.pt"
    src1.write_bytes(b"v1")
    src2 = base / "v2.pt"
    src2.write_bytes(b"v2")

    mf1 = svc.import_file("cam1", "patchcore", str(src1))
    mf2 = svc.import_file("cam1", "patchcore", str(src2))

    rolled = svc.rollback("cam1", "patchcore")
    assert rolled is not None
    assert rolled["id"] == mf1["id"]

    history = svc.list_history("cam1", "patchcore")
    active = [m for m in history if m["is_active"] == 1]
    assert len(active) == 1
    assert active[0]["id"] == mf1["id"]


def test_get_active(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src = base / "model.pt"
    src.write_bytes(b"test")
    svc.import_file("cam1", "patchcore", str(src))
    active = svc.get_active("cam1", "patchcore")
    assert active is not None
    assert active["camera_id"] == "cam1"


def test_delete_non_active(tmp_path: Path):
    svc, base = _setup(tmp_path)
    src1 = base / "v1.pt"
    src1.write_bytes(b"v1")
    src2 = base / "v2.pt"
    src2.write_bytes(b"v2")

    mf1 = svc.import_file("cam1", "patchcore", str(src1))
    mf2 = svc.import_file("cam1", "patchcore", str(src2))
    svc.activate(mf1["id"])
    svc.delete_file(mf2["id"])
    history = svc.list_history("cam1", "patchcore")
    assert len(history) == 1
