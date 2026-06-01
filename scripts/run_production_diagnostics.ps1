param(
    [string]$Config = "config.json"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

uv run python -m app.diagnostics --config $Config
