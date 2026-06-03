"""Tests for Windows deployment script required-file coverage."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_verifier_requires_production_template() -> None:
    common_script = (ROOT / "scripts" / "common_windows.ps1").read_text(encoding="utf-8")
    verify_script = (ROOT / "scripts" / "verify_deployment.ps1").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")

    assert '"config.production.example.json"' in common_script
    assert '"config.production.example.json"' in build_script
    assert "New-DeploymentVerificationBatchContent" in build_script
    assert "OnlineDetectionConfigWizard.exe --template config.production.example.json" in build_script
    assert "Get-DeploymentVerificationPaths" in verify_script


def test_pyinstaller_spec_includes_runtime_hidden_imports() -> None:
    spec = (ROOT / "packaging" / "online_detection_app.spec").read_text(encoding="utf-8")

    for module_name in [
        "torch",
        "ultralytics",
        "faiss",
        "seat_defect_core.api",
        "seat_defect_core.yolo.detection",
        "seat_defect_core.patchcore.engine",
        "seat_defect_core.classifier.engine",
    ]:
        assert f'"{module_name}"' in spec


def test_deployment_includes_model_check_executable_and_batch() -> None:
    common_script = (ROOT / "scripts" / "common_windows.ps1").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    spec = (ROOT / "packaging" / "online_detection_app.spec").read_text(encoding="utf-8")

    assert "OnlineDetectionModelCheck.exe" in common_script
    assert "OnlineDetectionModelCheck.exe" in build_script
    assert "OnlineDetectionModelCheck" in spec
    assert '"app/model_check.py"' in spec
    assert '"02_check_models.bat"' in common_script
    assert '"02_check_models.bat"' in build_script
    assert "OnlineDetectionModelCheck.exe --config config.json" in build_script


def test_windows_conda_scripts_exist_and_use_conda_env() -> None:
    common_script = (ROOT / "scripts" / "common_windows.ps1").read_text(encoding="utf-8")
    setup_script = (ROOT / "scripts" / "setup_windows_conda.ps1").read_text(encoding="utf-8")
    start_script = (ROOT / "scripts" / "start_windows_conda.ps1").read_text(encoding="utf-8")
    demo_script = (ROOT / "scripts" / "run_local_demo_windows_conda.ps1").read_text(encoding="utf-8")

    assert '[string]$EnvName = "online-detection-app"' in setup_script
    assert '. "$PSScriptRoot\\common_windows.ps1"' in setup_script
    assert '. "$PSScriptRoot\\common_windows.ps1"' in start_script
    assert 'Resolve-CondaCommand $Conda' in setup_script
    assert 'Invoke-CondaCommand -CondaCommand $script:CondaCommand -Arguments @("create", "-y", "-n", $EnvName, "python=$PythonVersion", "pip")' in setup_script
    assert '"run", "--no-capture-output", "-n", $EnvName' in common_script
    assert '"python", "-m", "pip", "install", "-e", $InstallTarget' in setup_script
    assert 'throw "Conda environment not found: $EnvName. Run scripts\\setup_windows_conda.ps1 first."' in start_script
    assert '$RunArgs = @("python", "-m", "app.main", "--config", $Config)' in start_script
    assert '[string[]]$ExtraArgs = @()' in start_script
    assert 'start_windows_conda.ps1' in demo_script


def test_legacy_windows_scripts_are_removed() -> None:
    for script_name in [
        "run_production_diagnostics.ps1",
        "run_local_demo_windows_pip.ps1",
        "setup_windows_pip.ps1",
        "start_windows_pip.ps1",
    ]:
        assert not (ROOT / "scripts" / script_name).exists()
