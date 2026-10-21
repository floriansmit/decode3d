@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-local.ps1"
if errorlevel 1 (
  echo.
  echo DECODE setup failed. Review the error above.
  exit /b 1
)
endlocal
