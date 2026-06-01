"""Tests for packaged camera connectivity checks."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from app.camera_check import main as camera_check_main


def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_camera_check_grabs_file_watcher_frame_from_config_directory(tmp_path: Path, monkeypatch, capsys) -> None:
    site_dir = tmp_path / "site"
    input_dir = site_dir / "input" / "CAM_A"
    input_dir.mkdir(parents=True)
    frame_path = input_dir / "frame.jpg"
    assert cv2.imwrite(str(frame_path), np.zeros((8, 10, 3), dtype=np.uint8))
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

    exit_code = camera_check_main(["--config", str(config_path), "--frames", "1", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path.cwd() == tmp_path
    assert payload["items"][0]["status"] == "OK"
    assert payload["items"][0]["frames_grabbed"] == 1
    assert payload["items"][0]["width"] == 10
    assert payload["items"][0]["height"] == 8


def test_camera_check_returns_failure_for_missing_camera(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.json"
    _write_config(config_path, {"cameras": []})

    exit_code = camera_check_main(["--config", str(config_path), "--camera-id", "CAM_X", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["items"][0]["status"] == "FAIL"
