param(
    [string]$ConfigTemplate = "config.production.example.json",
    [string]$EnvName = "online-detection-app",
    [string]$PythonVersion = "3.12",
    [string]$Conda = "conda",
    [switch]$SkipTests,
    [switch]$SkipDiagnostics,
    [switch]$SkipArchive,
    [switch]$Clean,
    [switch]$RecreateEnv
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. "$PSScriptRoot\common_windows.ps1"

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
}

$script:CondaCommand = Resolve-CondaCommand $Conda

& "$PSScriptRoot\setup_windows_conda.ps1" `
    -EnvName $EnvName `
    -PythonVersion $PythonVersion `
    -Conda $script:CondaCommand `
    -Dev `
    -Ml `
    -Packaging `
    -Recreate:$RecreateEnv

if (-not $SkipTests) {
    Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("python", "-m", "pytest")
}

if (-not $SkipDiagnostics) {
    try {
        Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("python", "-m", "app.diagnostics", "--config", $ConfigTemplate)
    }
    catch {
        Write-Warning "Production diagnostics reported missing site assets or configuration issues. Packaging will continue; run diagnostics again on the test computer after editing config.json."
    }
}
Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("pyinstaller", "--noconfirm", "packaging/online_detection_app.spec")

$DistRoot = Join-Path $RepoRoot "dist/OnlineDetectionApp"
$ConfigTarget = Join-Path $DistRoot "config.json"
Copy-Item -Force $ConfigTemplate $ConfigTarget

foreach ($dir in @("models", "deployed_models", "deployed_rules", "logs", "screenshots")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistRoot $dir) | Out-Null
}

$RequiredPaths = Get-DeploymentRequiredPaths
Test-DeploymentPaths -DistRoot $DistRoot -Paths $RequiredPaths -MessagePrefix "Packaged output is missing required path"

$Version = (& $script:CondaCommand "run" "--no-capture-output" "-n" $EnvName "python" "-c" "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
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

$BatchFiles = @{
    "00_verify_deployment.bat" = New-DeploymentVerificationBatchContent -Paths (Get-DeploymentVerificationPaths)
    "00_create_production_config.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
set /p CAMERA_SN=Hikrobot camera serial number:
set /p PLC_HOST=PLC Modbus TCP host:
if "%CAMERA_SN%"=="" (
  echo Camera serial number is required.
  exit /b 1
)
if "%PLC_HOST%"=="" (
  echo PLC host is required.
  exit /b 1
)
OnlineDetectionConfigWizard.exe --template config.production.example.json --output config.json --camera-sn "%CAMERA_SN%" --plc-host "%PLC_HOST%" --force
"@
    "01_run_diagnostics.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionDiagnostics.exe --config config.json
"@
    "02_check_models.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionModelCheck.exe --config config.json
"@
    "03_check_line_signal.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionLineCheck.exe --config config.json
"@
    "04_send_plc_ng_test.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
echo This sends one NG test result to PLC/result points.
OnlineDetectionLineCheck.exe --config config.json --send-test-result NG --defect-code 9001
"@
    "05_list_mvs_cameras.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionMvsList.exe
"@
    "06_check_camera_connections.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionCameraCheck.exe --config config.json --connect-only
"@
    "07_grab_camera_samples.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionCameraCheck.exe --config config.json --frames 1 --save-dir camera_samples
"@
    "08_collect_site_report.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionSiteReport.exe --config config.json --output site_report.json --camera-samples-dir camera_samples --camera-connect-only
"@
    "09_start_app.bat" = @"
@echo off
setlocal
cd /d "%~dp0"
OnlineDetectionApp.exe
"@
}
foreach ($entry in $BatchFiles.GetEnumerator()) {
    $entry.Value | Set-Content -Encoding ASCII (Join-Path $DistRoot $entry.Key)
}

$Readme = @"
OnlineDetectionApp deployment

1. Edit config.json for the test computer:
   - camera source: prefer mvs://sn/<camera-serial>?trigger=hardware&trigger_source=Line0
   - line_signal.host/port and Modbus point table
   - PatchCore, YOLO, Filter, and rule paths
2. Or run 00_create_production_config.bat to generate config.json from camera serial and PLC host.
3. Install Hikrobot MVS runtime on the test computer if the bundled DLL is not enough for the camera model.
4. Put PatchCore, YOLO, Filter, and rule files under models/, deployed_models/, and deployed_rules/.
5. Run 00_verify_deployment.bat.
6. Run 01_run_diagnostics.bat.
7. Run 02_check_models.bat.
8. Run 03_check_line_signal.bat.
9. Run 04_send_plc_ng_test.bat with the PLC engineer watching ng_coil, done_coil, and defect_code_register.
10. Run 05_list_mvs_cameras.bat if camera serial numbers need to be confirmed.
11. Run 06_check_camera_connections.bat.
12. Run 07_grab_camera_samples.bat while providing camera trigger pulses if cameras are hardware-triggered.
13. Run 08_collect_site_report.bat and send site_report.json plus camera_samples\ if troubleshooting is needed. The report includes build info, manifest summary, runtime log tail, diagnostics, model runtime check, line signal, MVS listing, and camera status.
14. Run 09_start_app.bat.

Run diagnostics before production:
   OnlineDetectionDiagnostics.exe --config config.json

Check model runtime:
   OnlineDetectionModelCheck.exe --config config.json
   OnlineDetectionModelCheck.exe --config config.json --seat-model-id <seat-model-id>

Generate production config:
   OnlineDetectionConfigWizard.exe --template config.production.example.json --output config.json --camera-sn <camera-serial> --plc-host <plc-ip> --force

Check cameras:
   OnlineDetectionMvsList.exe
   OnlineDetectionCameraCheck.exe --config config.json --connect-only
   OnlineDetectionCameraCheck.exe --config config.json --frames 1 --save-dir camera_samples

Check PLC / line signal:
   OnlineDetectionLineCheck.exe --config config.json
   OnlineDetectionLineCheck.exe --config config.json --wait-trigger --timeout-s 10
   OnlineDetectionLineCheck.exe --config config.json --send-test-result NG --defect-code 9001

Collect site report:
   OnlineDetectionSiteReport.exe --config config.json --output site_report.json --camera-samples-dir camera_samples --camera-connect-only
   OnlineDetectionSiteReport.exe --config config.json --output site_report.json --skip-model-check --camera-connect-only

Main GUI:
   OnlineDetectionApp.exe

Runtime log:
   logs\runtime.log
"@
$Readme | Set-Content -Encoding UTF8 (Join-Path $DistRoot "DEPLOYMENT.txt")

$GeneratedFiles = Get-DeploymentGeneratedPaths
$ManifestItems = foreach ($relativePath in $RequiredPaths + $GeneratedFiles) {
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
