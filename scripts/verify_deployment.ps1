param(
    [string]$DistRoot = "dist/OnlineDetectionApp"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common_windows.ps1"

Test-DeploymentPaths -DistRoot $DistRoot -Paths (Get-DeploymentVerificationPaths)

Write-Host "Deployment verification passed: $DistRoot"
