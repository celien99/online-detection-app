$WindowsDeploymentRequiredPaths = @(
    "OnlineDetectionApp.exe",
    "OnlineDetectionDiagnostics.exe",
    "OnlineDetectionConfigWizard.exe",
    "OnlineDetectionCameraCheck.exe",
    "OnlineDetectionModelCheck.exe",
    "OnlineDetectionLineCheck.exe",
    "OnlineDetectionMvsList.exe",
    "OnlineDetectionSiteReport.exe",
    "config.json",
    "config.production.example.json",
    "app/qml/main.qml",
    "app/resources/styles/theme.qml",
    "app/infrastructure/camera/mvs/MvCameraControl.dll",
    "models",
    "deployed_models",
    "deployed_rules",
    "logs",
    "screenshots"
)

$WindowsDeploymentGeneratedPaths = @(
    "BUILD_INFO.txt",
    "DEPLOYMENT.txt",
    "00_create_production_config.bat",
    "00_verify_deployment.bat",
    "01_run_diagnostics.bat",
    "02_check_models.bat",
    "03_check_line_signal.bat",
    "04_send_plc_ng_test.bat",
    "05_list_mvs_cameras.bat",
    "06_check_camera_connections.bat",
    "07_grab_camera_samples.bat",
    "08_collect_site_report.bat",
    "09_start_app.bat"
)

function Resolve-CondaCommand {
    param([string]$CondaCommand)

    if (Test-Path -LiteralPath $CondaCommand) {
        return (Resolve-Path -LiteralPath $CondaCommand).Path
    }

    $Command = Get-Command $CondaCommand -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Command) {
        return $Command.Source
    }

    throw "conda executable not found. Install Miniconda/Anaconda first, or pass -Conda C:\Path\To\conda.bat."
}

function Invoke-CondaCommand {
    param(
        [string]$CondaCommand,
        [string[]]$Arguments
    )

    & $CondaCommand @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "conda command failed: conda $($Arguments -join ' ')"
    }
}

function Invoke-CondaRun {
    param(
        [string]$CondaCommand,
        [string]$EnvName,
        [string[]]$Arguments
    )

    $RunArguments = @("run", "--no-capture-output", "-n", $EnvName) + $Arguments
    Invoke-CondaCommand -CondaCommand $CondaCommand -Arguments $RunArguments
}

function Test-CondaEnv {
    param(
        [string]$CondaCommand,
        [string]$EnvName
    )

    $EnvList = & $CondaCommand "env" "list" "--json" | ConvertFrom-Json
    foreach ($EnvPath in $EnvList.envs) {
        if ((Split-Path $EnvPath -Leaf) -eq $EnvName) {
            return $true
        }
    }
    return $false
}

function Get-DeploymentRequiredPaths {
    return @($WindowsDeploymentRequiredPaths)
}

function Get-DeploymentGeneratedPaths {
    return @($WindowsDeploymentGeneratedPaths)
}

function Get-DeploymentVerificationPaths {
    return @(Get-DeploymentRequiredPaths) + @(Get-DeploymentGeneratedPaths) + @("MANIFEST.json")
}

function Test-DeploymentPaths {
    param(
        [string]$DistRoot,
        [string[]]$Paths,
        [string]$MessagePrefix = "Deployment is missing required path"
    )

    foreach ($RelativePath in $Paths) {
        $FullPath = Join-Path $DistRoot $RelativePath
        if (-not (Test-Path $FullPath)) {
            throw "${MessagePrefix}: $RelativePath"
        }
    }
}

function New-DeploymentVerificationBatchContent {
    param([string[]]$Paths)

    $Lines = @(
        "@echo off",
        "setlocal",
        'cd /d "%~dp0"'
    )
    foreach ($RelativePath in $Paths) {
        $BatchPath = $RelativePath -replace "/", "\"
        $Lines += "if not exist ""$BatchPath"" ("
        $Lines += "  echo Missing $BatchPath"
        $Lines += "  exit /b 1"
        $Lines += ")"
    }
    $Lines += "echo Deployment file check passed."
    return ($Lines -join "`r`n") + "`r`n"
}
