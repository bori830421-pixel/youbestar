@echo off
setlocal enabledelayedexpansion

set "PORT=8000"
set "HOST=127.0.0.1"
set "APP_DIR=%~dp0"
set "VENV_PY=%APP_DIR%.venv\Scripts\python.exe"
set "SERVER_URL=http://%HOST%:%PORT%"
set "HTML_FILE=%APP_DIR%index.html"

cd /d "%APP_DIR%"

echo [1/5] Checking port %PORT%...
for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"`) do (
    if not "%%P"=="" (
        echo Closing old process PID %%P on port %PORT%...
        taskkill /F /PID %%P >nul 2>nul
    )
)

echo [2/5] Preparing Python environment...
if not exist "%VENV_PY%" (
    echo Creating virtual environment .venv...
    python -m venv "%APP_DIR%.venv"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

"%VENV_PY%" -c "import fastapi, uvicorn, requests" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies from requirements.txt...
    "%VENV_PY%" -m pip install -r "%APP_DIR%requirements.txt"
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Model config is managed on the webpage and saved to youbestar.json.

echo [3/5] Starting FastAPI server on %SERVER_URL%...
start "AI Agent Server" cmd /k ""%VENV_PY%" -m uvicorn server:app --host %HOST% --port %PORT%"

echo [4/5] Waiting for server health check...
set "READY="
for /l %%I in (1,1,30) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri '%SERVER_URL%/health' -TimeoutSec 1; if ($r.status -eq 'ok') { exit 0 } } catch { exit 1 }" >nul 2>nul
    if not errorlevel 1 (
        set "READY=1"
        goto :OPEN_PAGE
    )
    timeout /t 1 /nobreak >nul
)

:OPEN_PAGE
if "%READY%"=="" (
    echo Server did not respond in time. Opening the page anyway.
) else (
    echo Server is ready.
)

echo [5/5] Opening browser page...
start "" "%HTML_FILE%"

endlocal
