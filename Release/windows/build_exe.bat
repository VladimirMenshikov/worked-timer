@echo off
setlocal
cd /d "%~dp0"

set "SRC_DIR=..\..\Win"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Creating build environment...
python -m venv build_venv
call build_venv\Scripts\pip.exe install --quiet --upgrade pip
call build_venv\Scripts\pip.exe install --quiet -r "%SRC_DIR%\requirements.txt" pyinstaller

echo [2/3] Building WorkTimer.exe...
call build_venv\Scripts\pyinstaller.exe --noconfirm --clean work-timer.spec

echo [3/3] Copying .env.example...
copy /y "%SRC_DIR%\.env.example" "dist\.env.example" >nul

echo.
echo === Done ===
echo Result: dist\WorkTimer.exe
echo.
echo Next: run build_installer.bat to produce a Setup.exe installer
echo (requires Inno Setup, see README.md).
pause
