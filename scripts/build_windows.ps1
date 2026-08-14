$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install ".[windows,voice,dev]"
& .venv\Scripts\python.exe -m pytest -q
& .venv\Scripts\python.exe main.py --doctor
& .venv\Scripts\pyinstaller.exe --noconfirm --clean NikkiOS.spec

if (-not (Test-Path "dist\NikkiOS\NikkiOS.exe")) {
    throw "Windows build did not produce dist\NikkiOS\NikkiOS.exe"
}
Write-Host "Built: $Root\dist\NikkiOS\NikkiOS.exe"
