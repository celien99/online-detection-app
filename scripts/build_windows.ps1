param(
    [string]$ConfigTemplate = "config.production.example.json",
    [switch]$SkipTests,
    [switch]$SkipDiagnostics,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install uv first, then rerun this script."
}

uv sync --extra dev --extra packaging

if (-not $SkipTests) {
    uv run pytest
}

if (-not $SkipDiagnostics) {
    uv run python -m app.diagnostics --config $ConfigTemplate
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Production diagnostics reported missing site assets or configuration issues. Packaging will continue; run diagnostics again on the test computer after editing config.json."
    }
}
uv run pyinstaller --noconfirm packaging/online_detection_app.spec

$DistRoot = Join-Path $RepoRoot "dist/OnlineDetectionApp"
$ConfigTarget = Join-Path $DistRoot "config.json"
Copy-Item -Force $ConfigTemplate $ConfigTarget

foreach ($dir in @("models", "deployed_models", "deployed_rules", "calibration", "logs", "screenshots")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistRoot $dir) | Out-Null
}

$Readme = @"
OnlineDetectionApp deployment

1. Edit config.json for the test computer:
   - camera source: prefer mvs://sn/<camera-serial>?trigger=hardware&trigger_source=Line0
   - line_signal.host/port and Modbus point table
   - model, rule, and calibration paths
2. Install Hikrobot MVS runtime on the test computer if the bundled DLL is not enough for the camera model.
3. Put model files under models/, deployed_models/, deployed_rules/, and calibration/.
4. Run OnlineDetectionApp.exe.

Run diagnostics before production:
   OnlineDetectionApp.exe is the GUI entry. For diagnostics, use the source checkout command:
   uv run python -m app.diagnostics --config config.json
"@
$Readme | Set-Content -Encoding UTF8 (Join-Path $DistRoot "DEPLOYMENT.txt")

Write-Host "Build complete: $DistRoot"
