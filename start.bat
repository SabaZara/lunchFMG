@echo off
REM ===========================================================================
REM  LUNCH meal-access  --  one-click start for Windows
REM
REM  First run (needs internet ONCE):
REM    * creates a Python virtual environment in .venv
REM    * installs dependencies from requirements.txt
REM    * generates SECRET_KEY and TUNNEL_SECRET into .env if missing
REM    * downloads cloudflared.exe
REM    * seeds the database (admin + sample cards) if the DB is missing
REM
REM  Every run:
REM    * starts the app (bound to 127.0.0.1 -- NOT reachable from the LAN)
REM    * starts the local header-injecting proxy (adds the tunnel secret)
REM    * starts the Cloudflare quick tunnel hidden in the background
REM    * prints the public https://...trycloudflare.com URL for remote admin
REM
REM  After first setup the SCAN screen works fully OFFLINE forever. The tunnel
REM  only matters when you want to reach Admin / Reports remotely.
REM
REM  Keep ALL text in this file ASCII. The app text is Georgian (in Python/HTML).
REM ===========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo === LUNCH meal-access : startup ===
echo.

REM ---------------------------------------------------------------------------
REM  1. Find a Python launcher
REM ---------------------------------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python was not found on PATH.
  echo         Install Python 3.11+ from https://www.python.org/downloads/
  echo         and CHECK "Add Python to PATH" during install, then re-run this file.
  pause
  exit /b 1
)
echo Using Python launcher: %PY%

REM ---------------------------------------------------------------------------
REM  2. Create / reuse the virtual environment
REM ---------------------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment in .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create the virtual environment.
    pause
    exit /b 1
  )
)
set "VENV_PY=.venv\Scripts\python.exe"

REM ---------------------------------------------------------------------------
REM  3. Install / update dependencies
REM ---------------------------------------------------------------------------
echo Installing dependencies (first run needs internet) ...
"%VENV_PY%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

REM ---------------------------------------------------------------------------
REM  4. Ensure .env exists and has SECRET_KEY + TUNNEL_SECRET
REM ---------------------------------------------------------------------------
if not exist ".env" (
  echo Creating .env from .env.example ...
  copy /y ".env.example" ".env" >nul
  echo.
  echo [ACTION REQUIRED] Open .env and set a STRONG ADMIN_PASSWORD, then re-run.
  echo                   SECRET_KEY and TUNNEL_SECRET will be auto-filled now.
)

REM Auto-fill SECRET_KEY and TUNNEL_SECRET if blank. This helper also prints
REM nothing on success; it edits .env in place.
"%VENV_PY%" scripts\ensure_secrets.py
if errorlevel 1 (
  echo [ERROR] Could not prepare secrets in .env
  pause
  exit /b 1
)

REM ---------------------------------------------------------------------------
REM  5. Validate config (refuses weak password / missing SECRET_KEY) + seed DB
REM ---------------------------------------------------------------------------
"%VENV_PY%" scripts\startup_prepare.py
if errorlevel 1 (
  echo.
  echo [ERROR] Startup checks failed (see message above).
  echo         Most likely: set a strong ADMIN_PASSWORD in .env, then re-run.
  pause
  exit /b 1
)

REM ---------------------------------------------------------------------------
REM  6. Download cloudflared.exe once
REM ---------------------------------------------------------------------------
if not exist "cloudflared.exe" (
  echo Downloading cloudflared.exe ...
  "%VENV_PY%" -c "import urllib.request; urllib.request.urlretrieve('https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe','cloudflared.exe')"
  if errorlevel 1 (
    echo [WARN] Could not download cloudflared.exe. The app + scan screen will
    echo        still run locally; remote admin via tunnel will be unavailable
    echo        until cloudflared.exe is present.
  )
)

REM ---------------------------------------------------------------------------
REM  7. Read PORT / PROXY_PORT from .env (defaults 8000 / 8001)
REM ---------------------------------------------------------------------------
set "PORT=8000"
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  if /i "%%a"=="PORT" set "PORT=%%b"
)
set /a PROXY_PORT=%PORT%+1
set "PROXY_PORT=%PROXY_PORT%"

REM ---------------------------------------------------------------------------
REM  8. Start the app (hidden) and the header-injecting proxy (hidden)
REM ---------------------------------------------------------------------------
echo.
if exist "lunch-pids.txt" del /q "lunch-pids.txt"

echo Starting the app on http://127.0.0.1:%PORT% ...
"%VENV_PY%" scripts\start_hidden.py --label app --log app.log --pid-file lunch-pids.txt -- "%VENV_PY%" run.py
if errorlevel 1 (
  echo [ERROR] Could not start the app. Check app.log.
  pause
  exit /b 1
)

echo Starting the tunnel proxy on http://127.0.0.1:%PROXY_PORT% ...
set "PROXY_PORT=%PROXY_PORT%"
"%VENV_PY%" scripts\start_hidden.py --label proxy --env PROXY_PORT=%PROXY_PORT% --log proxy.log --pid-file lunch-pids.txt -- "%VENV_PY%" tunnel_proxy.py
if errorlevel 1 (
  echo [ERROR] Could not start the tunnel proxy. Check proxy.log.
  pause
  exit /b 1
)

REM Give the app a moment to bind.
"%VENV_PY%" -c "import time;time.sleep(3)"

REM ---------------------------------------------------------------------------
REM  9. Start the Cloudflare quick tunnel hidden, pointed at the PROXY port.
REM     The public URL is captured into tunnel-url.txt and printed.
REM ---------------------------------------------------------------------------
if exist "cloudflared.exe" (
  echo Starting Cloudflare tunnel (remote admin) ...
  if exist "tunnel-url.txt" del /q "tunnel-url.txt"
  if exist "tunnel.log" del /q "tunnel.log"
  "%VENV_PY%" scripts\start_hidden.py --label tunnel --log tunnel.log --pid-file lunch-pids.txt -- ".\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:%PROXY_PORT%
  REM Poll the log for the public URL.
  "%VENV_PY%" scripts\print_tunnel_url.py
) else (
  echo [INFO] Skipping tunnel (cloudflared.exe missing).
)

echo.
echo ===========================================================================
echo  KIOSK (local, offline):   http://127.0.0.1:%PORT%/
echo  Open that in full-screen on the kiosk PC (press F11 in the browser).
echo.
echo  REMOTE ADMIN URL is shown above (the https://...trycloudflare.com link),
echo  and also saved in tunnel-url.txt . Open /admin or /reports on it.
echo  Admin/Reports are BLOCKED on the local machine by design.
echo  To stop the background processes, double-click stop.bat.
echo ===========================================================================
echo.
echo This window can stay open, or you can close it after copying the URLs.
pause
endlocal
