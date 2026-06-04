"""Tests for app-owned conversion into seat_defect_core configs."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.core_config_adapter import build_core_inspection_config


def test_build_core_config_ignores_capture_fields_and_resolves_paths(tmp_path: Path) -> None:
    config = build_core_inspection_config(
        cameras=[
            {
                "camera_id": "CAM_A",
                "type": "file_watcher",
                "watch_dir": "./input/CAM_A",
                "pattern": "*.jpg",
                "source": "./input/CAM_A",
                "patchcore_model_path": "./models/cam_a_patchcore.npz",
                "detection": {"model_path": "./models/yolo.pt", "device": "cpu"},
                "patchcore": {
                    "backend": "full",
                    "backbone_device": "cpu",
                    "backbone_weights_path": "./models/backbone.pth",
                    "feature_layers": ["layer2", "layer3"],
                },
                "filter_classifier": {
                    "enabled": True,
                    "model_path": "./models/filter",
                    "confidence_threshold": 0.6,
                },
                "rule_engine": {
                    "enabled": True,
                    "deployed_rules_path": "./rules/rules.json",
                    "rules": [{"name": "small-score", "max_anomaly_score": 0.2}],
                },
            }
        ],
        upload_base_url="https://offline.example.test",
        part_id="station-a",
        config_dir=tmp_path,
    )

    camera = config.cameras[0]

    assert config.part_id == "station-a"
    assert config.upload_base_url == "https://offline.example.test"
    assert camera.camera_id == "CAM_A"
    assert camera.source == str((tmp_path / "input/CAM_A").resolve())
    assert camera.patchcore_model_path == str((tmp_path / "models/cam_a_patchcore.npz").resolve())
    assert camera.detection.model_path == str((tmp_path / "models/yolo.pt").resolve())
    assert camera.patchcore.backbone_weights_path == str((tmp_path / "models/backbone.pth").resolve())
    assert camera.filter_classifier.enabled is True
    assert camera.filter_classifier.model_path == str((tmp_path / "models/filter").resolve())
    assert camera.rule_engine.enabled is True
    assert camera.rule_engine.deployed_rules_path == "./rules/rules.json"
    assert camera.rule_engine.rules[0].name == "small-score"
    assert camera.regions == []


def test_build_core_config_rejects_region_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="regions mode is not supported by online detection app"):
        build_core_inspection_config(
            cameras=[
                {
                    "camera_id": "CAM_A",
                    "source": "./input/CAM_A",
                    "patchcore_model_path": "./models/cam_a_patchcore.npz",
                    "regions": [
                        {
                            "region_id": "upper",
                            "box": [0.0, 0.0, 1.0, 0.5],
                            "patchcore_model_path": "./models/upper_patchcore.npz",
                        }
                    ],
                }
            ],
            config_dir=tmp_path,
        )
