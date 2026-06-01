param(
    [string]$DistRoot = "dist/OnlineDetectionApp"
)

$ErrorActionPreference = "Stop"

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
    "screenshots",
    "BUILD_INFO.txt",
    "DEPLOYMENT.txt",
    "MANIFEST.json",
    "00_verify_deployment.bat",
    "01_run_diagnostics.bat",
    "02_check_line_signal.bat",
    "03_check_cameras.bat",
    "04_start_app.bat"
)

foreach ($relativePath in $RequiredPaths) {
    $fullPath = Join-Path $DistRoot $relativePath
    if (-not (Test-Path $fullPath)) {
        throw "Deployment is missing required path: $relativePath"
    }
}

Write-Host "Deployment verification passed: $DistRoot"
