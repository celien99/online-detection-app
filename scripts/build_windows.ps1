param(
    [string]$ConfigTemplate = "config.production.example.json",
    [switch]$SkipTests,
    [switch]$SkipDiagnostics,
    [switch]$SkipArchive,
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

$RequiredPaths = @(
    "OnlineDetectionApp.exe",
    "OnlineDetectionDiagnostics.exe",
    "OnlineDetectionCameraCheck.exe",
    "OnlineDetectionLineCheck.exe",
    "config.json",
    "app/qml/main.qml",
    "app/resources/styles/theme.qml",
    "app/infrastructure/camera/mvs/MvCameraControl.dll",
    "models",
    "deployed_models",
    "deployed_rules",
    "calibration",
    "logs",
    "screenshots"
)
foreach ($relativePath in $RequiredPaths) {
    $fullPath = Join-Path $DistRoot $relativePath
    if (-not (Test-Path $fullPath)) {
        throw "Packaged output is missing required path: $relativePath"
    }
}

$Version = (uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
$Commit = (git rev-parse --short HEAD).Trim()
$BuiltAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$BuildInfo = @"
name=OnlineDetectionApp
version=$Version
commit=$Commit
built_at_utc=$BuiltAt
config_template=$ConfigTemplate
"@
$BuildInfo | Set-Content -Encoding UTF8 (Join-Path $DistRoot "BUILD_INFO.txt")

$Readme = @"
OnlineDetectionApp deployment

1. Edit config.json for the test computer:
   - camera source: prefer mvs://sn/<camera-serial>?trigger=hardware&trigger_source=Line0
   - line_signal.host/port and Modbus point table
   - model, rule, and calibration paths
2. Install Hikrobot MVS runtime on the test computer if the bundled DLL is not enough for the camera model.
3. Put model files under models/, deployed_models/, deployed_rules/, and calibration/.
4. Run OnlineDetectionLineCheck.exe --config config.json before starting production.
5. Run OnlineDetectionCameraCheck.exe --config config.json --frames 1 before starting production.
6. Run OnlineDetectionApp.exe.

Run diagnostics before production:
   OnlineDetectionDiagnostics.exe --config config.json

Check cameras:
   OnlineDetectionCameraCheck.exe --config config.json --frames 1

Check PLC / line signal:
   OnlineDetectionLineCheck.exe --config config.json
   OnlineDetectionLineCheck.exe --config config.json --wait-trigger --timeout-s 10

Main GUI:
   OnlineDetectionApp.exe
"@
$Readme | Set-Content -Encoding UTF8 (Join-Path $DistRoot "DEPLOYMENT.txt")

$ManifestItems = foreach ($relativePath in $RequiredPaths + @("BUILD_INFO.txt", "DEPLOYMENT.txt")) {
    $fullPath = Join-Path $DistRoot $relativePath
    [pscustomobject]@{
        path = $relativePath
        exists = Test-Path $fullPath
        type = if (Test-Path $fullPath -PathType Container) { "directory" } else { "file" }
        size = if (Test-Path $fullPath -PathType Leaf) { (Get-Item $fullPath).Length } else { 0 }
    }
}
[pscustomobject]@{
    name = "OnlineDetectionApp"
    version = $Version
    commit = $Commit
    built_at_utc = $BuiltAt
    items = $ManifestItems
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $DistRoot "MANIFEST.json")

& (Join-Path $PSScriptRoot "verify_deployment.ps1") -DistRoot $DistRoot

if (-not $SkipArchive) {
    $ArchivePath = Join-Path (Join-Path $RepoRoot "dist") "OnlineDetectionApp-$Version-$Commit.zip"
    if (Test-Path $ArchivePath) {
        Remove-Item -Force $ArchivePath
    }
    Compress-Archive -Path (Join-Path $DistRoot "*") -DestinationPath $ArchivePath -Force
    Write-Host "Archive complete: $ArchivePath"
}

Write-Host "Build complete: $DistRoot"
