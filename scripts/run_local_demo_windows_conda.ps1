param(
    [string]$EnvName = "online-detection-app",
    [string[]]$ExtraArgs = @(),
    [string]$Conda = "conda"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& "$PSScriptRoot\start_windows_conda.ps1" `
    -Config "config.local.example.json" `
    -EnvName $EnvName `
    -Conda $Conda `
    -SkipDiagnostics `
    -ExtraArgs $ExtraArgs
