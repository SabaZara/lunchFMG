@echo off
REM ===========================================================================
REM  OPTIONAL: build a true standalone kiosk_tester.exe (Windows only).
REM
REM  You do NOT need this to use the tester — run-tester.bat already works with
REM  the installed Python. Use this only if you want a single .exe with no
REM  Python needed on the machine that runs it.
REM
REM  This downloads PyInstaller into a throwaway venv and produces:
REM      dist\kiosk_tester.exe
REM  Needs internet once. Keep this file ASCII-only.
REM ===========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY ( where python >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo [ERROR] Python not found on PATH. Install Python 3.11+ first.
  pause
  exit /b 1
)

echo Creating build venv ...
%PY% -m venv .build-venv
set "BPY=.build-venv\Scripts\python.exe"

echo Installing PyInstaller ...
"%BPY%" -m pip install --upgrade pip
"%BPY%" -m pip install pyinstaller
if errorlevel 1 (
  echo [ERROR] Could not install PyInstaller. Check your internet connection.
  pause
  exit /b 1
)

echo Building kiosk_tester.exe ...
"%BPY%" -m PyInstaller --onefile --noconsole --name kiosk_tester kiosk_tester.pyw
if errorlevel 1 (
  echo [ERROR] Build failed.
  pause
  exit /b 1
)

echo.
echo ===========================================================================
echo  Done. Your standalone executable is:  dist\kiosk_tester.exe
echo  You can send that single file by itself; it needs no Python to run.
echo ===========================================================================
pause
endlocal
