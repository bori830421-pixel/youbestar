@echo off
setlocal enabledelayedexpansion

set "REMOTE_URL=https://github.com/bori830421-pixel/youbestar.git"
set "BRANCH=main"

cd /d "%~dp0"

echo [GitHub Upload] Repository: %REMOTE_URL%
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

git ls-files --error-unmatch youbestar.json >nul 2>nul
if not errorlevel 1 (
    echo WARNING: youbestar.json is already tracked by git.
    echo It may contain your API key.
    echo Run this command once, then run this bat again:
    echo git rm --cached youbestar.json
    pause
    exit /b 1
)

echo.
git status --short
echo.
set /p COMMIT_MSG=Commit message:
if "%COMMIT_MSG%"=="" set "COMMIT_MSG=Initial Youbestar Agent upload"

git add .
if errorlevel 1 (
    echo git add failed.
    pause
    exit /b 1
)

git diff --cached --quiet
if not errorlevel 1 (
    echo No staged changes to commit.
) else (
    git commit -m "%COMMIT_MSG%"
    if errorlevel 1 (
        echo Commit failed.
        pause
        exit /b 1
    )
)

echo Checking whether remote branch %BRANCH% already exists...
git ls-remote --exit-code --heads origin "%BRANCH%" >nul 2>nul
if errorlevel 1 (
    echo Remote branch does not exist yet. First upload mode enabled.
) else (
    echo Remote branch exists. Refreshing remote metadata before overwrite...
    git fetch origin "+%BRANCH%:refs/remotes/origin/%BRANCH%"
    if errorlevel 1 (
        echo Fetch failed.
        pause
        exit /b 1
    )
)

echo Uploading local %BRANCH% and overwriting GitHub safely...
git push -u --force-with-lease origin "%BRANCH%"
if errorlevel 1 (
    echo Push failed.
    echo The remote may have changed after the safety check.
    echo Run this bat again after confirming that local files should overwrite GitHub.
    echo If GitHub asks for login, sign in with Git Credential Manager or GitHub CLI, then run this bat again.
    pause
    exit /b 1
)

echo.
echo Upload complete.
pause
endlocal
