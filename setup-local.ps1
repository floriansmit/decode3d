$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $projectRoot ".venv"
$localPython = Join-Path $venvRoot "Scripts\python.exe"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvRunner = $uvCommand.Source
    $uvPrefix = @()
}
else {
    Write-Host "uv was not found; installing the dependency manager"
    python -m pip install --user --upgrade "uv>=0.12.5"
    $uvRunner = "python"
    $uvPrefix = @("-m", "uv")
}

Write-Host "Synchronising the locked DECODE, API, test, and PyThermoGIS environment with uv"
Push-Location $projectRoot
try {
    $syncArguments = $uvPrefix + @("sync", "--extra", "api", "--extra", "thermogis", "--extra", "test")
    & $uvRunner @syncArguments
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
