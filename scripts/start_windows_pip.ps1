param(
    [string]$Config = "config.json",
    [string]$Venv = ".venv-pip",
    [switch]$Dev,
    [switch]$SkipDiagnostics,
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment not found: $Venv. Run scripts\setup_windows_pip.ps1 first."
}
if (-not (Test-Path -LiteralPath $Config)) {
    throw "Config file not found: $Config"
}

if (-not $SkipDiagnostics) {
    & $VenvPython -m app.diagnostics --config $Config
    if ($LASTEXITCODE -ne 0) {
        throw "Diagnostics failed for $Config. Fix the reported items or rerun with -SkipDiagnostics for UI-only debugging."
    }
}

$RunArgs = @("-m", "app.main", "--config", $Config)
if ($Dev) {
    $RunArgs += "--dev"
}
if ($ExtraArgs.Count -gt 0) {
    $RunArgs += $ExtraArgs
}

& $VenvPython @RunArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
