"""Tests for GUI entry-point CLI parsing."""
from __future__ import annotations

from app.main import _iter_patchcore_model_paths, _parse_args


def test_main_cli_parses_config_and_dev_without_passing_to_qt() -> None:
    args = _parse_args(["--config", "site.json", "--dev", "--platform", "offscreen"])

    assert args.config == "site.json"
    assert args.dev is True
    assert args.qt_args == ["--platform", "offscreen"]


def test_iter_patchcore_model_paths_includes_region_models() -> None:
    paths = _iter_patchcore_model_paths(
        [
            {
                "camera_id": "CAM_A",
                "patchcore_model_path": "./models/camera.pt",
                "regions": [
                    {"region_id": "upper", "patchcore_model_path": "./models/upper.pt"},
                    {"region_id": "lower", "patchcore_model_path": ""},
                    {
                        "region_id": "disabled",
                        "enabled": False,
                        "patchcore_model_path": "./models/disabled.pt",
                    },
                ],
            },
            {
                "camera_id": "CAM_B",
                "regions": [
                    {"region_id": "middle", "patchcore_model_path": "./models/middle.pt"},
                ],
            },
        ]
    )

    assert paths == ["./models/camera.pt", "./models/upper.pt", "./models/middle.pt"]
