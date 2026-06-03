"""Tests for Windows deployment script required-file coverage."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_verifier_requires_production_template() -> None:
    verify_script = (ROOT / "scripts" / "verify_deployment.ps1").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")

    assert '"config.production.example.json"' in verify_script
    assert '"config.production.example.json"' in build_script
    assert 'if not exist "config.production.example.json"' in build_script
    assert "OnlineDetectionConfigWizard.exe --template config.production.example.json" in build_script


def test_pyinstaller_spec_includes_runtime_hidden_imports() -> None:
    spec = (ROOT / "packaging" / "online_detection_app.spec").read_text(encoding="utf-8")

    for module_name in [
        "torch",
        "ultralytics",
        "anomalib.models.image.efficient_ad.torch_model",
        "seat_defect_core.api",
        "seat_defect_core.yolo.detection",
        "seat_defect_core.efficientad.engine",
        "seat_defect_core.classifier.engine",
    ]:
        assert f'"{module_name}"' in spec


def test_deployment_includes_model_check_executable_and_batch() -> None:
    verify_script = (ROOT / "scripts" / "verify_deployment.ps1").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    spec = (ROOT / "packaging" / "online_detection_app.spec").read_text(encoding="utf-8")

    assert "OnlineDetectionModelCheck.exe" in verify_script
    assert "OnlineDetectionModelCheck.exe" in build_script
    assert "OnlineDetectionModelCheck" in spec
    assert '"app/model_check.py"' in spec
    assert '"02_check_models.bat"' in verify_script
    assert '"02_check_models.bat"' in build_script
    assert "OnlineDetectionModelCheck.exe --config config.json" in build_script

def test_windows_pip_scripts_exist_and_use_local_venv() -> None:
    setup_script = (ROOT / "scripts" / "setup_windows_pip.ps1").read_text(encoding="utf-8")
    start_script = (ROOT / "scripts" / "start_windows_pip.ps1").read_text(encoding="utf-8")

    assert "function Resolve-Python" in setup_script
    assert "Python 3.11 or 3.12 not found" in setup_script
    assert '$VenvPython = Join-Path $Venv "Scripts\\python.exe"' in setup_script
    assert '$VenvPython = Join-Path $Venv "Scripts\\python.exe"' in start_script
    assert '"-m", "app.main", "--config", $Config' in start_script
    assert '[string[]]$ExtraArgs = @()' in start_script
    assert "pip install -e" in setup_script
