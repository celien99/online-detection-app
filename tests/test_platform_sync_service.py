"""Tests for PlatformSyncService."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.platform_sync_service import PlatformSyncService


def test_check_health_online():
    svc = PlatformSyncService("http://localhost:8000")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status":"healthy"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        assert svc.check_health() is True


def test_check_health_offline():
    svc = PlatformSyncService("http://localhost:8000")
    with patch("urllib.request.urlopen", side_effect=OSError):
        assert svc.check_health() is False


def test_check_health_empty_url():
    svc = PlatformSyncService("")
    assert svc.check_health() is False


def test_set_base_url():
    svc = PlatformSyncService("")
    svc.set_base_url("http://192.168.1.200:8000")
    assert svc.base_url == "http://192.168.1.200:8000"


def test_list_deployed_models():
    svc = PlatformSyncService("http://localhost:8000")
    mock_data = [{"target": "line_a", "status": "active", "model_version": "v2.3.1"}]
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        models = svc.list_deployed_models()
        assert len(models) == 1
        assert models[0]["target"] == "line_a"


def test_download_model(tmp_path: Path):
    svc = PlatformSyncService("http://localhost:8000")
    dest = str(tmp_path / "downloaded.pt")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [b"model binary content", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = svc.download_model(
            "http://localhost:8000/api/hot-reload/download/model_123", dest
        )
        assert result == dest
        assert Path(dest).exists()
        assert Path(dest).read_bytes() == b"model binary content"


def test_download_model_http_error(tmp_path: Path):
    svc = PlatformSyncService("http://localhost:8000")
    dest = str(tmp_path / "fail.pt")
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        result = svc.download_model("http://bad/url", dest)
        assert result is None
