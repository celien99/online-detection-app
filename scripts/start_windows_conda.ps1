param(
    [string]$Config = "config.json",
    [string]$EnvName = "online-detection-app",
    [switch]$Dev,
    [switch]$SkipDiagnostics,
    [string[]]$ExtraArgs = @(),
    [string]$Conda = "conda"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. "$PSScriptRoot\common_windows.ps1"

$script:CondaCommand = Resolve-CondaCommand $Conda
if (-not (Test-CondaEnv -CondaCommand $script:CondaCommand -EnvName $EnvName)) {
    throw "Conda environment not found: $EnvName. Run scripts\setup_windows_conda.ps1 first."
}
if (-not (Test-Path -LiteralPath $Config)) {
    throw "Config file not found: $Config"
}

if (-not $SkipDiagnostics) {
    Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments @("python", "-m", "app.diagnostics", "--config", $Config)
}

$RunArgs = @("python", "-m", "app.main", "--config", $Config)
if ($Dev) {
    $RunArgs += "--dev"
}
if ($ExtraArgs.Count -gt 0) {
    $RunArgs += $ExtraArgs
}

Invoke-CondaRun -CondaCommand $script:CondaCommand -EnvName $EnvName -Arguments $RunArgs
