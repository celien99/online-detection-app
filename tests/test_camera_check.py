"""Tests for packaged camera connectivity checks."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import app.camera_check as camera_check
from app.camera_check import main as camera_check_main
from app.infrastructure.camera.interface import CameraStatus


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_camera_check_grabs_file_watcher_frame_from_config_directory(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    input_dir = site_dir / "input" / "CAM_A"
    input_dir.mkdir(parents=True)
    frame_path = input_dir / "frame.jpg"
    image = np.zeros((8, 10, 3), dtype=np.uint8)
    image[:, :, 1] = 32
    assert cv2.imwrite(str(frame_path), image)
    config_path = site_dir / "config.json"
    _write_config(
        config_path,
        {
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": "./input/CAM_A",
                    "pattern": "*.jpg",
                }
            ]
        },
    )
    monkeypatch.chdir(tmp_path)

    exit_code = camera_check_main([
        "--config",
        str(config_path),
        "--frames",
        "1",
        "--save-dir",
        "camera_samples",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    item = payload["items"][0]

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert item["status"] == "OK"
    assert item["frames_grabbed"] == 1
    assert item["width"] == 10
    assert item["height"] == 8
    assert item["mean"] > 0
    assert item["max_value"] == 32
    sample_path = site_dir / item["sample_path"]
    assert sample_path.exists()
    sample = cv2.imread(str(sample_path), cv2.IMREAD_COLOR)
    assert sample is not None
    assert sample.shape[:2] == (8, 10)


def test_camera_check_returns_failure_for_missing_camera(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.json"
    _write_config(config_path, {"cameras": []})

    exit_code = camera_check_main(["--config", str(config_path), "--camera-id", "CAM_X", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["items"][0]["status"] == "FAIL"


def test_camera_check_connect_only_skips_frame_requirement(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    input_dir = site_dir / "input" / "CAM_A"
    input_dir.mkdir(parents=True)
    config_path = site_dir / "config.json"
    _write_config(
        config_path,
        {
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "file_watcher",
                    "enabled": True,
                    "watch_dir": "./input/CAM_A",
                    "pattern": "*.jpg",
                }
            ]
        },
    )
    monkeypatch.chdir(tmp_path)

    exit_code = camera_check_main([
        "--config",
        str(config_path),
        "--connect-only",
        "--save-dir",
        "camera_samples",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    item = payload["items"][0]

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert item["status"] == "OK"
    assert item["frames_grabbed"] == 0
    assert item["sample_path"] == ""
    assert not (site_dir / "camera_samples").exists()


def test_camera_check_hardware_trigger_timeout_suggests_trigger_options(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "mvs",
                    "enabled": True,
                    "source": "mvs://0?trigger=hardware&trigger_source=Line0",
                }
            ]
        },
    )

    class FakeCamera:
        camera_id = "CAM_A"
        is_connected = True
        width = 4096
        height = 3072
        fps = 9.5

        def connect(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        def grab_frame(self, timeout_ms: int = 1000):
            return None

        def get_status(self):
            return CameraStatus(camera_id="CAM_A", connected=True, width=4096, height=3072, fps=9.5)

    monkeypatch.setattr(camera_check, "create_camera", lambda camera_config: FakeCamera())

    exit_code = camera_check_main(["--config", str(config_path), "--frames", "1", "--json"])
    payload = json.loads(capsys.readouterr().out)
    item = payload["items"][0]

    assert exit_code == 1
    assert item["status"] == "FAIL"
    assert "hardware trigger is enabled" in item["message"]
    assert "--mvs-trigger-mode continuous" in item["message"]


def test_camera_check_can_override_mvs_trigger_mode_for_diagnostics(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / "config.json"
    _write_config(
        config_path,
        {
            "cameras": [
                {
                    "camera_id": "CAM_A",
                    "type": "mvs",
                    "enabled": True,
                    "source": "mvs://0?trigger=hardware&trigger_source=Line0&timeout_ms=2000",
                }
            ]
        },
    )
    seen_sources: list[str] = []

    class FakeCamera:
        camera_id = "CAM_A"
        is_connected = True
        width = 10
        height = 8
        fps = 10.0

        def __init__(self, source: str) -> None:
            self._source = source

        def connect(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        def grab_frame(self, timeout_ms: int = 1000):
            if "trigger=continuous" in self._source:
                return np.zeros((8, 10, 3), dtype=np.uint8)
            return None

        def get_status(self):
            return CameraStatus(camera_id="CAM_A", connected=True, width=10, height=8, fps=10.0)

    def fake_create_camera(camera_config):
        seen_sources.append(camera_config["source"])
        return FakeCamera(camera_config["source"])

    monkeypatch.setattr(camera_check, "create_camera", fake_create_camera)

    exit_code = camera_check_main([
        "--config",
        str(config_path),
        "--frames",
        "1",
        "--mvs-trigger-mode",
        "continuous",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    item = payload["items"][0]

    assert exit_code == 0
    assert item["status"] == "OK"
    assert item["frames_grabbed"] == 1
    assert "trigger=continuous" in seen_sources[0]
