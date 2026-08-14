param(
    [int]$SpriteAliveSeconds = 10,
    [int]$Live2DAliveSeconds = 15
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ReportPath = Join-Path $Root "qa\windows-validation-latest.json"
Set-Location $Root

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )
    Write-Host "[windows-validation] $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Test-AppAlive {
    param(
        [string]$Renderer,
        [int]$Seconds
    )
    $Process = $null
    $PreviousRenderer = $env:SOULPET_RENDERER
    $PreviousKey = $env:DASHSCOPE_API_KEY
    try {
        $env:SOULPET_RENDERER = $Renderer
        $env:DASHSCOPE_API_KEY = ""
        $Process = Start-Process -FilePath ".\dist\NikkiOS\NikkiOS.exe" -PassThru
        Start-Sleep -Seconds $Seconds
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "Packaged $Renderer renderer exited before $Seconds seconds (exit $($Process.ExitCode))"
        }
        return $true
    }
    finally {
        if ($Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $Process.Id -Timeout 10 -ErrorAction SilentlyContinue
        }
        $env:SOULPET_RENDERER = $PreviousRenderer
        $env:DASHSCOPE_API_KEY = $PreviousKey
    }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}
$Python = ".venv\Scripts\python.exe"

Invoke-Checked "install dependencies" { & $Python -m pip install --upgrade pip }
Invoke-Checked "install project" { & $Python -m pip install ".[windows,voice,dev]" }
Invoke-Checked "ruff" { & $Python -m ruff check . }
$env:QT_QPA_PLATFORM = "offscreen"
Write-Host "[windows-validation] pytest"
$PytestOutput = @(& $Python -m pytest -q 2>&1)
$PytestExitCode = $LASTEXITCODE
$PytestOutput | ForEach-Object { Write-Host $_ }
if ($PytestExitCode -ne 0) {
    throw "pytest failed with exit code $PytestExitCode"
}
$PytestSummary = ($PytestOutput | Select-String -Pattern "\d+ passed(?: in [\d.]+s)?" -AllMatches | ForEach-Object {
    $_.Matches.Value
} | Select-Object -Last 1)
if (-not $PytestSummary) {
    throw "pytest passed but its summary could not be parsed"
}
Invoke-Checked "source doctor" { & $Python main.py --doctor }
Invoke-Checked "PyInstaller" { & $Python -m PyInstaller --noconfirm --clean NikkiOS.spec }

$Executable = Join-Path $Root "dist\NikkiOS\NikkiOS.exe"
if (-not (Test-Path $Executable)) {
    throw "PyInstaller did not produce $Executable"
}

Invoke-Checked "packaged doctor" { & $Executable --doctor }
$null = Test-AppAlive -Renderer "sprite" -Seconds $SpriteAliveSeconds
$null = Test-AppAlive -Renderer "live2d" -Seconds $Live2DAliveSeconds

$Commit = (& git rev-parse HEAD).Trim()
$Os = Get-CimInstance Win32_OperatingSystem
$PackageHash = (Get-FileHash -Algorithm SHA256 $Executable).Hash.ToLowerInvariant()
$Report = [ordered]@{
    validated_at = (Get-Date).ToString("o")
    platform = "$($Os.Caption) $($Os.Version) $env:PROCESSOR_ARCHITECTURE"
    python = (& $Python --version 2>&1).ToString().Trim()
    commit = $Commit
    checks = [ordered]@{
        ruff = "pass"
        pytest = $PytestSummary
        doctor_source = "pass"
        doctor_packaged = "pass"
        packaged_sprite_alive_after_seconds = $SpriteAliveSeconds
        packaged_live2d_alive_after_seconds = $Live2DAliveSeconds
    }
    package = [ordered]@{
        type = "PyInstaller onedir"
        executable = "dist/NikkiOS/NikkiOS.exe"
        sha256 = $PackageHash
        size_bytes = (Get-Item $Executable).Length
    }
    notes = @(
        "Cloud AI calls were not exercised; no API key was placed on the Windows validation host.",
        "The report intentionally omits host address, account name, and credentials."
    )
}
$Report | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host "[windows-validation] passed: $ReportPath"
Write-Host "[windows-validation] executable sha256: $PackageHash"
