"""Offline platform API integration for model sync."""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path


class PlatformSyncService:
    """对接离线分析平台 API：健康检查、模型列表、文件下载。"""

    def __init__(self, base_url: str = "", timeout: int = 30) -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    def set_base_url(self, url: str) -> None:
        self._base_url = url.rstrip("/") if url else ""

    def check_health(self) -> bool:
        if not self._base_url:
            return False
        try:
            req = urllib.request.Request(f"{self._base_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_deployed_models(self) -> list[dict]:
        if not self._base_url:
            return []
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/hot-reload/targets", method="GET"
            )
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return []

    def download_model(
        self, download_url: str, dest_path: str
    ) -> str | None:
        try:
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(download_url, method="GET")
            with urllib.request.urlopen(
                req, timeout=self._timeout * 2
            ) as resp:
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(resp, f)
            return dest_path
        except Exception:
            return None
