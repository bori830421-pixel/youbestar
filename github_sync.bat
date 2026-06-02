@echo off
setlocal enabledelayedexpansion

set "REMOTE_URL=https://github.com/bori830421-pixel/youbestar.git"
set "BRANCH=main"

cd /d "%~dp0"

echo [GitHub Sync] Repository: %REMOTE_URL%
echo.

git --version >nul 2>nul
if errorlevel 1 (
    echo Git is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist ".git" (
    echo Initializing local git repository...
    git init -b "%BRANCH%" >nul 2>nul
    if errorlevel 1 (
        git init
        if errorlevel 1 (
            echo git init failed.
            pause
            exit /b 1
        )
        git symbolic-ref HEAD refs/heads/%BRANCH% >nul 2>nul
    )
)

set "CURRENT_BRANCH="
for /f "usebackq tokens=*" %%B in (`git branch --show-current`) do set "CURRENT_BRANCH=%%B"
if not "%CURRENT_BRANCH%"=="%BRANCH%" (
    if "%CURRENT_BRANCH%"=="" (
        git symbolic-ref HEAD refs/heads/%BRANCH% >nul 2>nul
    ) else (
        git branch -M "%BRANCH%"
    )
)

git remote get-url origin >nul 2>nul
if errorlevel 1 (
    echo Adding origin remote...
    git remote add origin "%REMOTE_URL%"
) else (
    echo Updating origin remote...
    git remote set-url origin "%REMOTE_URL%"
)

if errorlevel 1 (
    echo Failed to configure origin remote.
    pause
    exit /b 1
)

echo Checking remote branch %BRANCH%...
git ls-remote --exit-code --heads origin "%BRANCH%" >nul 2>nul
if errorlevel 1 (
    echo Remote branch %BRANCH% does not exist yet.
    echo This is normal for an empty GitHub repository.
    echo Run github_upload.bat first to create the first commit on GitHub.
    pause
    exit /b 0
)

echo Fetching latest code...
git fetch origin "%BRANCH%"
if errorlevel 1 (
    echo Fetch failed.
    pause
    exit /b 1
)

echo Pulling with rebase...
git pull --rebase origin "%BRANCH%"
if errorlevel 1 (
    echo Pull failed. Resolve conflicts, then run this bat again.
    pause
    exit /b 1
)

echo.
echo Sync complete.
pause
endlocal
