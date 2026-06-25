@echo off
REM ===========================================================================
REM  LUNCH kiosk scan tester (standalone)
REM
REM  Double-click this on the kiosk PC to open a small window for testing card
REM  scans WITHOUT a USB reader. The kiosk app must be running (start.bat).
REM
REM  Needs only Python 3.x (the python.org install already on the kiosk).
REM  No project, no venv, no pip. Keep this file ASCII-only.
REM ===========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Find a Python launcher.
set "PY="
where pyw >nul 2>&1 && set "PY=pyw"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if not defined PY ( where pythonw >nul 2>&1 && set "PY=pythonw" )
if not defined PY ( where python >nul 2>&1 && set "PY=python" )

if not defined PY (
  echo [ERROR] Python was not found on PATH.
  echo         Install Python 3.11+ from https://www.python.org/downloads/
  echo         and check "Add Python to PATH" during install.
  pause
  exit /b 1
)

REM Launch the GUI tester. .pyw runs without a console window.
start "" %PY% "kiosk_tester.pyw"
endlocal
