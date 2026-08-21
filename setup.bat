@echo off
REM One-shot setup for Windows. Double-click this file, or run:  setup.bat
REM
REM Creates a private Python environment inside this folder, installs the tool
REM and its browser, and makes your config.yaml / profile.yaml from the
REM examples. Safe to re-run: it never overwrites files you've edited.

setlocal
cd /d "%~dp0"

echo.
echo 1/4  Checking Python
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON=python"
    ) else (
        echo.
        echo Python was not found.
        echo Install it from https://www.python.org/downloads/
        echo IMPORTANT: tick "Add Python to PATH" in the installer, then run this again.
        pause
        exit /b 1
    )
)

echo.
echo 2/4  Installing tt-autoapply ^(this takes a minute or two^)
if not exist .venv %PYTHON% -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -e .
if errorlevel 1 goto failed

echo.
echo 3/4  Installing the browser it drives
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 echo     Chromium install failed - try again with: .venv\Scripts\python.exe -m playwright install chromium

echo.
echo 4/4  Setting up your config
if exist config.yaml (
    echo      config.yaml already exists - left alone
) else (
    copy /y config.example.yaml config.yaml >nul
    echo      created config.yaml
)
if exist profile.yaml (
    echo      profile.yaml already exists - left alone
) else (
    copy /y profile.example.yaml profile.yaml >nul
    echo      created profile.yaml
)

echo.
echo Done. Two things next:
echo.
echo   1. Log in ^(a browser window opens - sign in as you normally would^):
echo.
echo        .venv\Scripts\tt-autoapply login
echo.
echo   2. Read the real page structure:
echo.
echo        .venv\Scripts\tt-autoapply discover
echo.
echo      That prints a block of text and saves a copy to
echo      state\discover\listing-report.json - send either one back to get
echo      your config.yaml filled in.
echo.
echo Every command starts with .venv\Scripts\tt-autoapply - there is nothing
echo to "activate" first.
echo.
pause
exit /b 0

:failed
echo.
echo Setup failed. Copy the error above and send it over.
pause
exit /b 1
