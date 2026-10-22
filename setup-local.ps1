$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $projectRoot ".venv"
$localPython = Join-Path $venvRoot "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $localPython)) {
    Write-Host "Creating project-local Python environment in .venv"
    python -m venv $venvRoot
}

Write-Host "Installing DECODE and PyThermoGIS from the official TNO package index"
& $localPython -m pip install --upgrade pip
Push-Location $projectRoot
try {
    & $localPython -m pip install --upgrade -r (Join-Path $projectRoot "requirements.txt")
}
finally {
    Pop-Location
}

Write-Host "Preparing the bundled PyThermoGIS Java 17 runtime (first setup can take a few minutes)"
& $localPython -c "from importlib.metadata import version; from pythermogis.jvm import start_jvm; v = version('pythermogis'); assert v.startswith('3.'), 'PyThermoGIS 3 is required'; start_jvm(); print(f'PyThermoGIS {v} and Java 17 are ready')"

Write-Host "Installing website dependencies"
Push-Location (Join-Path $projectRoot "apps\web")
try {
    npm install
}
finally {
    Pop-Location
}

Write-Host "Setup complete. Start the full application with .\run-local.cmd"
