"""Model file management: import, SHA256 verify, activate, rollback."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from app.services.config_persistence import ConfigPersistenceService


class ModelFileService:
    """管理模型文件：导入、校验、激活、回滚。"""

    def __init__(self, persistence: ConfigPersistenceService, models_dir: str = "./models") -> None:
        self._p = persistence
        self._models_dir = models_dir
        Path(self._models_dir).mkdir(parents=True, exist_ok=True)

    def import_file(
        self,
        camera_id: str,
        model_type: str,
        src_path: str,
        *,
        seat_model_id: str | None = None,
    ) -> dict:
        src = _local_path(src_path)
        file_name = src.name
        model_scope = _model_scope(seat_model_id)
        dest_dir = Path(self._models_dir) / model_scope / camera_id / model_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name
        shutil.copy2(str(src), str(dest_path))

        sha = _sha256_file(str(dest_path))
        now = datetime.now(timezone.utc).isoformat()
        mf = {
            "id": str(uuid.uuid4()),
            "seat_model_id": seat_model_id or "",
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

    def register_synced(
        self,
        camera_id: str,
        model_type: str,
        file_path: str,
        version: str = "",
        *,
        seat_model_id: str | None = None,
    ) -> dict:
        fp = Path(file_path)
        sha = _sha256_file(file_path) if fp.exists() else ""
        now = datetime.now(timezone.utc).isoformat()
        mf = {
            "id": str(uuid.uuid4()),
            "seat_model_id": seat_model_id or "",
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

    def rollback_scoped(self, seat_model_id: str | None, camera_id: str, model_type: str) -> dict | None:
        history = self._p.list_model_files(
            camera_id=camera_id,
            model_type=model_type,
            seat_model_id=seat_model_id or "",
        )
        inactive = [m for m in history if m.get("is_active") != 1]
        if not inactive:
            return None
        prev = inactive[0]
        self._p.set_model_file_active(prev["id"], camera_id, model_type)
        return prev

    def get_active(self, camera_id: str, model_type: str, *, seat_model_id: str | None = None) -> dict | None:
        all_files = self._p.list_model_files(
            camera_id=camera_id,
            model_type=model_type,
            seat_model_id=seat_model_id if seat_model_id is not None else None,
        )
        for mf in all_files:
            if mf.get("is_active") == 1:
                return mf
        return None

    def list_history(
        self,
        camera_id: str | None,
        model_type: str | None,
        *,
        seat_model_id: str | None = None,
    ) -> list[dict]:
        return self._p.list_model_files(
            camera_id=camera_id,
            model_type=model_type,
            seat_model_id=seat_model_id if seat_model_id is not None else None,
        )

    def apply_active_files_to_cameras(self, cameras: list[dict], *, seat_model_id: str | None = None) -> list[dict]:
        """Return camera configs with active deployed files wired into runtime fields."""
        runtime_cameras = deepcopy(cameras)
        for camera in runtime_cameras:
            camera_id = camera.get("camera_id")
            if not camera_id:
                continue
            active_files = self._active_files_for_camera(camera_id, seat_model_id)
            for mf in active_files:
                file_path = mf.get("file_path", "")
                if not file_path:
                    continue
                model_type = _normalize_model_type(mf.get("model_type", ""))
                if model_type == "patchcore":
                    camera["patchcore_model_path"] = file_path
                elif model_type == "filter_classifier":
                    filter_classifier = dict(camera.get("filter_classifier") or {})
                    filter_classifier["enabled"] = True
                    filter_classifier["model_path"] = file_path
                    camera["filter_classifier"] = filter_classifier
                elif model_type == "rules":
                    rule_engine = dict(camera.get("rule_engine") or {})
                    rule_engine["enabled"] = True
                    rule_engine["deployed_rules_path"] = file_path
                    camera["rule_engine"] = rule_engine
        return runtime_cameras

    def active_runtime_versions(self, cameras: list[dict], *, seat_model_id: str | None = None) -> list[dict]:
        versions: list[dict] = []
        for camera in cameras:
            camera_id = camera.get("camera_id")
            if not camera_id:
                continue
            for mf in self._active_files_for_camera(camera_id, seat_model_id):
                versions.append(
                    {
                        "seat_model_id": mf.get("seat_model_id", ""),
                        "camera_id": camera_id,
                        "model_type": mf.get("model_type", ""),
                        "file_id": mf.get("id", ""),
                        "file_name": mf.get("file_name", ""),
                        "file_path": mf.get("file_path", ""),
                        "sha256": mf.get("sha256", ""),
                        "exists": Path(mf.get("file_path", "")).exists(),
                    }
                )
        return versions

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

    def _active_files_for_camera(self, camera_id: str, seat_model_id: str | None) -> list[dict]:
        scoped_files = [
            item
            for item in self._p.list_model_files(
                seat_model_id=seat_model_id or "",
                camera_id=camera_id,
            )
            if item.get("is_active") == 1
        ]
        if scoped_files or not seat_model_id:
            return scoped_files
        return [
            item
            for item in self._p.list_model_files(
                seat_model_id="",
                camera_id=camera_id,
            )
            if item.get("is_active") == 1
        ]


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _local_path(raw_path: str) -> Path:
    parsed = urlparse(raw_path)
    if parsed.scheme == "file":
        netloc = f"//{parsed.netloc}" if parsed.netloc else ""
        return Path(url2pathname(f"{netloc}{parsed.path}"))
    return Path(raw_path)


def _normalize_model_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"patchcore", "patch_core", "patchcore_model"}:
        return "patchcore"
    if normalized in {"filter", "classifier", "filter_classifier", "filter_clf"}:
        return "filter_classifier"
    if normalized in {"rule", "rules", "rule_engine"}:
        return "rules"
    return normalized


def _model_scope(seat_model_id: str | None) -> str:
    return seat_model_id.strip() if isinstance(seat_model_id, str) and seat_model_id.strip() else "__global__"
