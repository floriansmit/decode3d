$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$webRoot = Join-Path $projectRoot "apps\web"
$localPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $localPython)) {
    throw "Local environment not found. Run .\setup-local.ps1 once, then retry."
}

Write-Host "Starting DECODE PyThermoGIS API at http://127.0.0.1:8000"
$api = Start-Process -FilePath $localPython -ArgumentList @("-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru

try {
    $env:NEXT_PUBLIC_PYTHERMOGIS_API = "http://127.0.0.1:8000"
    Write-Host "Starting DECODE website at http://localhost:5173"
    Set-Location $webRoot
    npm run dev -- --host 127.0.0.1
}
finally {
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id }
}
