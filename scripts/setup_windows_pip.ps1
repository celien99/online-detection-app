param(
    [string]$Python = "",
    [string]$Venv = ".venv-pip",
    [switch]$Dev,
    [switch]$Ml,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Test-SupportedPython {
    param([string]$PythonExe)
    $Version = & $PythonExe -c "import sys; raise SystemExit(0 if ((3, 11) <= sys.version_info[:2] < (3, 13)) else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Resolve-Python {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        if (Test-Path -LiteralPath $RequestedPython) {
            $Resolved = (Resolve-Path -LiteralPath $RequestedPython).Path
            if (Test-SupportedPython $Resolved) {
                return $Resolved
            }
            throw "Python must be 3.11 or 3.12: $Resolved"
        }
        $Command = Get-Command $RequestedPython -ErrorAction SilentlyContinue
        if ($Command -and (Test-SupportedPython $Command.Source)) {
            return $Command.Source
        }
        throw "Python not found or unsupported: $RequestedPython"
    }

    $BundledCandidates = @(
        ".uv-python\cpython-3.12.13-windows-x86_64-none\python.exe",
        ".uv-python\cpython-3.11.14-windows-x86_64-none\python.exe"
    )
    foreach ($Candidate in $BundledCandidates) {
        if (Test-Path -LiteralPath $Candidate) {
            $Resolved = (Resolve-Path -LiteralPath $Candidate).Path
            if (Test-SupportedPython $Resolved) {
                return $Resolved
            }
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($Version in @("3.12", "3.11")) {
            $Resolved = & py "-$Version" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $Resolved -and (Test-SupportedPython $Resolved.Trim())) {
                return $Resolved.Trim()
            }
        }
    }

    foreach ($Name in @("python", "python3")) {
        $Command = Get-Command $Name -ErrorAction SilentlyContinue
        if ($Command -and (Test-SupportedPython $Command.Source)) {
            return $Command.Source
        }
    }

    throw "Python 3.11 or 3.12 not found. Install Python, or pass -Python C:\Path\To\python.exe."
}

$PythonExe = Resolve-Python $Python
Write-Host "Using Python: $PythonExe"

if ($Recreate -and (Test-Path -LiteralPath $Venv)) {
    Remove-Item -LiteralPath $Venv -Recurse -Force
}

if (-not (Test-Path -LiteralPath $Venv)) {
    & $PythonExe -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $VenvPython -m pip uninstall -y seat-defect-core
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$InstallTarget = ".[dev]"
if (-not $Dev) {
    $InstallTarget = "."
}
& $VenvPython -m pip install -e $InstallTarget
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Ml) {
    & $VenvPython -m pip install -e ".[ml]"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host "pip environment ready: $Venv"
Write-Host "Run with: powershell -ExecutionPolicy Bypass -File scripts\start_windows_pip.ps1 -Config config.local.example.json"
