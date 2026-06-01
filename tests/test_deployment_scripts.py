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
