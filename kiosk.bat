@echo off
REM Open the local kiosk scan screen. Run start.bat first if the app is not up.
REM Keep this file ASCII-only.

setlocal
cd /d "%~dp0"

set "PORT=8000"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="PORT" set "PORT=%%b"
  )
)

start "" "http://127.0.0.1:%PORT%/"
endlocal
