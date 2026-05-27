"""Model file management: import, SHA256 verify, activate, rollback."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.services.config_persistence import ConfigPersistenceService


class ModelFileService:
    """管理模型文件：导入、校验、激活、回滚。"""

    def __init__(self, persistence: ConfigPersistenceService, models_dir: str = "./models") -> None:
        self._p = persistence
        self._models_dir = models_dir
        Path(self._models_dir).mkdir(parents=True, exist_ok=True)

    def import_file(self, camera_id: str, model_type: str, src_path: str) -> dict:
        src = Path(src_path)
        file_name = src.name
        dest_dir = Path(self._models_dir) / camera_id / model_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name
        shutil.copy2(str(src), str(dest_path))

        sha = _sha256_file(str(dest_path))
        now = datetime.now(timezone.utc).isoformat()
        mf = {
            "id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "model_type": model_type,
            "file_path": str(dest_path),
            "file_name": file_name,
            "file_size": dest_path.stat().st_size,
            "sha256": sha,
            "source": "local_upload",
            "platform_version": "",
            "is_active": 1,
            "imported_at": now,
        }
        self._p.insert_model_file(mf)
        self._p.set_model_file_active(mf["id"], camera_id, model_type)
        return mf

    def register_synced(self, camera_id: str, model_type: str, file_path: str, version: str = "") -> dict:
        fp = Path(file_path)
        sha = _sha256_file(file_path) if fp.exists() else ""
        now = datetime.now(timezone.utc).isoformat()
        mf = {
            "id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "model_type": model_type,
            "file_path": str(fp),
            "file_name": fp.name,
            "file_size": fp.stat().st_size if fp.exists() else 0,
            "sha256": sha,
            "source": "platform_sync",
            "platform_version": version,
            "is_active": 1,
            "imported_at": now,
        }
        self._p.insert_model_file(mf)
        self._p.set_model_file_active(mf["id"], camera_id, model_type)
        return mf

    def verify_checksum(self, file_id: str) -> bool:
        mf = self._p.get_model_file(file_id)
        if mf is None:
            return False
        fp = Path(mf["file_path"])
        if not fp.exists():
            return False
        return _sha256_file(str(fp)) == mf["sha256"]

    def activate(self, file_id: str) -> None:
        mf = self._p.get_model_file(file_id)
        if mf is None:
            return
        self._p.set_model_file_active(file_id, mf["camera_id"], mf["model_type"])

    def rollback(self, camera_id: str, model_type: str) -> dict | None:
        history = self._p.list_model_files(camera_id=camera_id, model_type=model_type)
        inactive = [m for m in history if m.get("is_active") != 1]
        if not inactive:
            return None
        prev = inactive[0]
        self._p.set_model_file_active(prev["id"], camera_id, model_type)
        return prev

    def get_active(self, camera_id: str, model_type: str) -> dict | None:
        all_files = self._p.list_model_files(camera_id=camera_id, model_type=model_type)
        for mf in all_files:
            if mf.get("is_active") == 1:
                return mf
        return None

    def list_history(self, camera_id: str, model_type: str) -> list[dict]:
        return self._p.list_model_files(camera_id=camera_id, model_type=model_type)

    def delete_file(self, file_id: str) -> bool:
        mf = self._p.get_model_file(file_id)
        if mf is None:
            return False
        if mf.get("is_active") == 1:
            return False
        fp = Path(mf["file_path"])
        if fp.exists():
            fp.unlink()
        self._p.delete_model_file(file_id)
        return True


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
