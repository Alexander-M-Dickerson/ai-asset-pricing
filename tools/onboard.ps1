param(
    [ValidateSet("auto", "yes", "no")]
    [string]$Wrds = "auto",
    [string]$WrdsUsername = "",
    [switch]$SkipWrdsTest,
    [switch]$NonInteractive,
    [switch]$DryRun,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Test-PythonVersion {
    param([string]$PythonPath)
    if (-not $PythonPath) { return $false }
    try {
        $version = & $PythonPath -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
    } catch {
        return $false
    }
    return [version]$version -ge [version]"3.11"
}

function Find-Python {
    $candidates = @()

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($spec in @("-3.13", "-3.12", "-3.11")) {
            try {
                $path = & py $spec -c "import sys; print(sys.executable)" 2>$null
            } catch {
                $path = ""
            }
            if ($path) { $candidates += $path.Trim() }
        }
    }

    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notmatch "WindowsApps") {
            $candidates += $cmd.Source
        }
    }

    foreach ($path in @(
        "$HOME\miniforge3\python.exe",
        "$HOME\miniconda3\python.exe",
        "$HOME\anaconda3\python.exe",
        "C:\ProgramData\miniforge3\python.exe",
        "C:\ProgramData\Miniforge3\python.exe"
    )) {
        if (Test-Path $path) {
            $candidates += $path
        }
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-PythonVersion $candidate) {
            return $candidate
        }
    }
    return $null
}

function Ensure-Python {
    $python = Find-Python
    if ($python) { return $python }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw @"
No Python 3.11+ interpreter found and winget is unavailable.
Options:
  1. Install Miniforge from https://conda-forge.org/miniforge/
  2. Install Python 3.11+ from https://python.org/downloads/
  3. Install winget (https://aka.ms/getwinget), then rerun this script.
After installing, rerun: tools\onboard.ps1
"@
    }

    & winget install --id CondaForge.Miniforge3 -e --source winget --accept-package-agreements --accept-source-agreements
    $python = Find-Python
    if (-not $python) {
        throw "Miniforge install did not yield a usable Python 3.11+ interpreter."
    }
    return $python
}

$python = Ensure-Python
$driverArgs = @("tools/onboard_driver.py", "--shell", "powershell", "--wrds", $Wrds)
if ($WrdsUsername) { $driverArgs += @("--wrds-username", $WrdsUsername) }
if ($SkipWrdsTest) { $driverArgs += "--skip-wrds-test" }
if ($NonInteractive) { $driverArgs += "--non-interactive" }
if ($DryRun) { $driverArgs += "--dry-run" }
if ($Json) { $driverArgs += "--json" }

& $python @driverArgs
exit $LASTEXITCODE
