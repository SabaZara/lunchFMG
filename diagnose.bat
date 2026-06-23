@echo off
REM Create diagnose.txt with startup/environment details.
REM Keep this file ASCII-only.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "OUT=diagnose.txt"
echo LUNCH diagnose > "%OUT%"
echo Generated: %DATE% %TIME% >> "%OUT%"
echo Folder: %CD% >> "%OUT%"
echo. >> "%OUT%"

echo === Files === >> "%OUT%"
dir /b >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === Python discovery === >> "%OUT%"
where py >> "%OUT%" 2>&1
where python >> "%OUT%" 2>&1
py -3 --version >> "%OUT%" 2>&1
python --version >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === .env exists === >> "%OUT%"
if exist ".env" (
  echo YES >> "%OUT%"
) else (
  echo NO >> "%OUT%"
)
echo. >> "%OUT%"

echo === Existing venv === >> "%OUT%"
if exist ".venv\Scripts\python.exe" (
  echo YES >> "%OUT%"
  ".venv\Scripts\python.exe" --version >> "%OUT%" 2>&1
  ".venv\Scripts\python.exe" -m pip --version >> "%OUT%" 2>&1
) else (
  echo NO >> "%OUT%"
)
echo. >> "%OUT%"

echo === Port check 8000/8001 === >> "%OUT%"
netstat -ano | findstr ":8000" >> "%OUT%" 2>&1
netstat -ano | findstr ":8001" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === Startup prepare === >> "%OUT%"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\startup_prepare.py >> "%OUT%" 2>&1
) else (
  echo Cannot run startup_prepare: .venv missing >> "%OUT%"
)
echo. >> "%OUT%"

echo === Direct app import check === >> "%OUT%"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "from app.main import app; print('import ok')" >> "%OUT%" 2>&1
) else (
  echo Cannot import app: .venv missing >> "%OUT%"
)
echo. >> "%OUT%"

echo Diagnose written to %OUT%
echo Please send diagnose.txt
pause
endlocal
