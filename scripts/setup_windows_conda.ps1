param(
    [string]$EnvName = "online-detection-app",
    [string]$PythonVersion = "3.12",
    [switch]$Dev,
    [switch]$Ml,
    [switch]$Packaging,
    [switch]$Recreate,
    [string]$Conda = "conda"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. "$PSScriptRoot\common_windows.ps1"

$script:CondaCommand = Resolve-CondaCommand $Conda

if ($Recreate -and (Test-CondaEnv -CondaCommand $script:CondaCommand -EnvName $EnvName)) {
    Invoke-CondaCommand -CondaCommand $script:CondaCommand -Arguments @("env", "remove", "-y", "-n", $EnvName)
}

if (-not (Test-CondaEnv -CondaCommand $script:CondaCommand -EnvName $EnvName)) {
    Invoke-CondaCommand -CondaCommand $script:CondaCommand -Arguments @("create", "-y", "-n", $EnvName, "python=$PythonVersion", "pip")
}

Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @(
    "python",
    "-c",
    "import sys; raise SystemExit(0 if ((3, 11) <= sys.version_info[:2] < (3, 13)) else 1)"
)

Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("python", "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("python", "-m", "pip", "uninstall", "-y", "seat-defect-core")

$Extras = @()
if ($Dev) {
    $Extras += "dev"
}
if ($Ml) {
    $Extras += "ml"
}
if ($Packaging) {
    $Extras += "packaging"
}

$InstallTarget = "."
if ($Extras.Count -gt 0) {
    $InstallTarget = ".[{0}]" -f ($Extras -join ",")
}

Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("python", "-m", "pip", "install", "-e", $InstallTarget)

Write-Host "Conda environment ready: $EnvName"
Write-Host "Run local demo: powershell -ExecutionPolicy Bypass -File scripts\run_local_demo_windows_conda.ps1 -EnvName $EnvName"
Write-Host "Run production config: powershell -ExecutionPolicy Bypass -File scripts\start_windows_conda.ps1 -EnvName $EnvName -Config config.json"
