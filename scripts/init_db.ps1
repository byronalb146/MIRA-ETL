$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

if (-not (Test-Path .\.venv\Scripts\mira-etl.exe)) {
    throw "Missing .venv. Run scripts\install.ps1 first."
}

& .\.venv\Scripts\mira-etl.exe init-db
