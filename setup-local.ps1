$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $projectRoot ".venv"
$localPython = Join-Path $venvRoot "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $localPython)) {
    Write-Host "Creating project-local Python environment in .venv"
    # PyThermoGIS 3 is a licensed package installed outside PyPI on this workstation.
    # Expose that verified installation without copying or redistributing its files.
    python -m venv --system-site-packages $venvRoot
}

Write-Host "Installing the DECODE API and PyThermoGIS engine"
& $localPython -m pip install --upgrade pip
& $localPython -m pip install -e "${projectRoot}[api]"
& $localPython -c "from importlib.metadata import version; import pythermogis; assert version('pythermogis').startswith('3.'), 'PyThermoGIS 3 is required'"

Write-Host "Installing website dependencies"
Push-Location (Join-Path $projectRoot "apps\web")
try {
    npm install
}
finally {
    Pop-Location
}

Write-Host "Setup complete. Start the full application with .\run-local.cmd"
