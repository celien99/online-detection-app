"""Tests for production config generation."""
from __future__ import annotations

import json
from pathlib import Path

from app.production_config import build_production_config, main as production_config_main


def _template() -> dict:
    return {
        "app": {
            "line_id": "A-03",
            "station_id": "seat_inspection",
            "inspection_mode": "continuous",
        },
        "cameras": [
            {
                "camera_id": "CAM_FRONT",
                "source": "mvs://0",
                "type": "mvs",
                "enabled": True,
                "efficientad_model_path": "./models/cam_front.pt",
            }
        ],
        "line_signal": {
            "enabled": False,
            "type": "virtual",
            "host": "192.168.1.100",
            "port": 502,
        },
    }


def test_build_production_config_generates_hardware_trigger_mvs_source() -> None:
    config = build_production_config(
        _template(),
        camera_serials=["ABC123"],
        camera_ids=["CAM_A"],
        camera_sources=[],
        plc_host="10.1.2.3",
        plc_port=1502,
        line_id="L1",
        station_id="S1",
        trigger_source="Line1",
        trigger_activation="falling_edge",
        timeout_ms=2500,
        exposure_time=7000,
        gain=6,
        pixel_format="bgr8",
        point_overrides={"ok_coil": 24, "ng_coil": 25},
    )

    assert config["app"]["inspection_mode"] == "triggered"
    assert config["app"]["line_id"] == "L1"
    assert config["app"]["station_id"] == "S1"
    assert config["line_signal"]["enabled"] is True
    assert config["line_signal"]["type"] == "modbus"
    assert config["line_signal"]["host"] == "10.1.2.3"
    assert config["line_signal"]["port"] == 1502
    assert config["line_signal"]["ok_coil"] == 24
    assert config["line_signal"]["ng_coil"] == 25
    camera = config["cameras"][0]
    assert camera["camera_id"] == "CAM_A"
    assert camera["type"] == "mvs"
    assert camera["enabled"] is True
    assert camera["source"].startswith("mvs://sn/ABC123?")
    assert "trigger=hardware" in camera["source"]
    assert "trigger_source=Line1" in camera["source"]
    assert "trigger_activation=falling_edge" in camera["source"]
    assert "timeout_ms=2500" in camera["source"]


def test_build_production_config_supports_multiple_camera_serials() -> None:
    config = build_production_config(
        _template(),
        camera_serials=["ABC123", "DEF456"],
        camera_ids=["CAM_A", "CAM_B"],
        camera_sources=[],
        plc_host="10.1.2.3",
        plc_port=None,
        line_id="",
        station_id="",
        trigger_source="Line0",
        trigger_activation="rising_edge",
        timeout_ms=2000,
        exposure_time=6000,
        gain=8,
        pixel_format="bgr8",
        point_overrides={},
    )

    assert [camera["camera_id"] for camera in config["cameras"]] == ["CAM_A", "CAM_B"]
    assert config["cameras"][0]["source"].startswith("mvs://sn/ABC123?")
    assert config["cameras"][1]["source"].startswith("mvs://sn/DEF456?")


def test_production_config_cli_writes_output_and_requires_force(tmp_path: Path, monkeypatch, capsys) -> None:
    template_path = tmp_path / "config.production.example.json"
    output_path = tmp_path / "config.json"
    template_path.write_text(json.dumps(_template()), encoding="utf-8")
    output_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = production_config_main(["--template", str(template_path), "--output", str(output_path), "--camera-sn", "ABC123"])

    assert exit_code == 3
    assert "use --force" in capsys.readouterr().err

    exit_code = production_config_main(
        [
            "--template",
            str(template_path),
            "--output",
            str(output_path),
            "--camera-sn",
            "ABC123",
            "--plc-host",
            "10.1.2.3",
            "--force",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    config = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["status"] == "OK"
    assert payload["camera_count"] == 1
    assert config["cameras"][0]["source"].startswith("mvs://sn/ABC123?")
    assert config["line_signal"]["host"] == "10.1.2.3"


def test_production_config_cli_rejects_unknown_plc_point(tmp_path: Path, capsys) -> None:
    template_path = tmp_path / "config.production.example.json"
    output_path = tmp_path / "config.json"
    template_path.write_text(json.dumps(_template()), encoding="utf-8")

    exit_code = production_config_main(
        [
            "--template",
            str(template_path),
            "--output",
            str(output_path),
            "--camera-sn",
            "ABC123",
            "--point",
            "unknown=1",
        ]
    )

    assert exit_code == 2
    assert "Unsupported PLC point name" in capsys.readouterr().err
