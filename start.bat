@echo off
setlocal enabledelayedexpansion

set "PORT=8000"
set "HOST=127.0.0.1"
set "LOCAL_HOST=127.0.0.1"
set "APP_DIR=%~dp0"
set "VENV_PY=%APP_DIR%.venv\Scripts\python.exe"
set "LOCAL_URL=http://%LOCAL_HOST%:%PORT%"

cd /d "%APP_DIR%"

echo [1/6] Loading service sharing config...
for /f "usebackq tokens=1,2 delims=|" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$base = $env:YOUBESTAR_LOCAL_HOME; if (-not $base) { $base = $env:YOUBESTAR_LOCAL_DIR }; if (-not $base) { $base = 'D:\YoubestarLocal' }; $path = Join-Path $base 'config\service.json'; $enabled = $false; $port = %PORT%; if (Test-Path -LiteralPath $path) { try { $config = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json; if ($null -ne $config.lan_share_enabled) { $enabled = [bool]$config.lan_share_enabled }; if ($null -ne $config.port) { $port = [int]$config.port } } catch {} }; $hostName = if ($enabled) { '0.0.0.0' } else { '127.0.0.1' }; Write-Output ($hostName + '|' + $port)"`) do (
    set "HOST=%%A"
    set "PORT=%%B"
)
set "LOCAL_URL=http://%LOCAL_HOST%:%PORT%"

echo [2/6] Checking port %PORT%...
set "PORT_IN_USE="
set "PORT_PIDS="
set "PORT_PIDS_PS="
for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"`) do (
    if not "%%P"=="" (
        set "PORT_IN_USE=1"
        set "PORT_PIDS=!PORT_PIDS! %%P"
        if "!PORT_PIDS_PS!"=="" (
            set "PORT_PIDS_PS=%%P"
        ) else (
            set "PORT_PIDS_PS=!PORT_PIDS_PS!,%%P"
        )
        echo Port %PORT% is already used by PID %%P.
    )
)
if "%PORT_IN_USE%"=="1" (
    echo.
    echo Port %PORT% is already in use.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$pids = @(%PORT_PIDS_PS%); Get-CimInstance Win32_Process | Where-Object { $pids -contains $_.ProcessId } | Select-Object ProcessId,Name,CommandLine | Format-List"
    echo.
    choice /C YN /N /M "Stop the old process above and continue? [Y/N]: "
    if errorlevel 2 (
        echo Startup cancelled. Close the old process or edit PORT in this file, then run start.bat again.
        pause
        exit /b 1
    )
    echo Stopping old process...
    for %%P in (%PORT_PIDS%) do (
        taskkill /F /PID %%P >nul 2>nul
        if errorlevel 1 (
            echo Failed to stop PID %%P. Please close it manually.
            pause
            exit /b 1
        ) else (
            echo Stopped PID %%P.
        )
    )
    timeout /t 1 /nobreak >nul
    for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"`) do (
        if not "%%P"=="" (
            echo Port %PORT% is still used by PID %%P.
            echo Please close it manually or edit PORT in this file, then run start.bat again.
            pause
            exit /b 1
        )
    )
)

echo [3/6] Preparing Python environment...
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

echo [4/6] Preparing LAN access info...
set "LAN_IP="
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ip = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4Address } | Sort-Object InterfaceIndex | ForEach-Object { $_.IPv4Address.IPAddress } | Select-Object -First 1; if (-not $ip) { $ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceOperationalStatus -eq 'Up' } | Sort-Object InterfaceIndex | Select-Object -First 1 -ExpandProperty IPAddress }; if (-not $ip) { $ip = '127.0.0.1' }; $ip"`) do (
    set "LAN_IP=%%A"
)
if "%LAN_IP%"=="" set "LAN_IP=127.0.0.1"
set "LAN_URL=http://%LAN_IP%:%PORT%"

if "%HOST%"=="0.0.0.0" (
    echo LAN sharing is ON. Ensuring Windows Firewall allows inbound TCP %PORT%...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$name = 'YouBestar LAN %PORT%'; if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName $name -Direction Inbound -Protocol TCP -LocalPort %PORT% -Action Allow | Out-Null }" >nul 2>nul
    if errorlevel 1 (
        echo Firewall rule was not created automatically. Run PowerShell as Administrator:
        echo New-NetFirewallRule -DisplayName "YouBestar LAN %PORT%" -Direction Inbound -Protocol TCP -LocalPort %PORT% -Action Allow
    ) else (
        echo Firewall rule is ready: YouBestar LAN %PORT%
    )
) else (
    echo LAN sharing is OFF. Service will listen on %HOST%.
)

echo [5/6] Starting FastAPI server from "%APP_DIR%"...
set "YOUBESTAR_SERVICE_HOST=%HOST%"
set "YOUBESTAR_SERVICE_PORT=%PORT%"
start "AI Agent Server" cmd /k ""%VENV_PY%" -m uvicorn server:app --host %HOST% --port %PORT%"

echo [6/6] Waiting for server health check...
set "READY="
for /l %%I in (1,1,30) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri '%LOCAL_URL%/health' -TimeoutSec 1; if ($r.status -eq 'ok') { exit 0 } } catch { exit 1 }" >nul 2>nul
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

echo.
echo Local access:
echo   %LOCAL_URL%
echo LAN access:
if "%HOST%"=="0.0.0.0" (
    echo   %LAN_URL%
) else (
    echo   OFF. Open Management Config to enable LAN sharing.
)
echo.
if "%HOST%"=="0.0.0.0" (
    echo Other Windows computers on the same LAN should open:
    echo   %LAN_URL%
)
echo.
echo Opening browser page from the FastAPI service...
start "" "%LOCAL_URL%"

echo.
echo This helper window is kept open so you can copy the LAN URL.
echo The server log is in the "AI Agent Server" window.
pause

endlocal
