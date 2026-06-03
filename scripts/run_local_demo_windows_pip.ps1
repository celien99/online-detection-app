param(
    [string]$Venv = ".venv-pip",
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& "$PSScriptRoot\start_windows_pip.ps1" -Config "config.local.example.json" -Venv $Venv -SkipDiagnostics -ExtraArgs $ExtraArgs
