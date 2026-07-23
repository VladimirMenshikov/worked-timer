@echo off
setlocal

echo === Work Timer - install ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.10+ from https://python.org
    echo Make sure "Add python.exe to PATH" is checked during installation.
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv .venv

echo [2/3] Installing Python dependencies...
call .venv\Scripts\pip.exe install --quiet --upgrade pip
call .venv\Scripts\pip.exe install --quiet -r requirements.txt

echo [3/3] Preparing .env...
if not exist .env (
    copy .env.example .env >nul
    echo Created .env - fill in SUPABASE_URL and SUPABASE_KEY before running.
) else (
    echo .env already exists, skipping.
)

echo.
echo === Done! ===
echo.
echo Edit .env, then run:
echo   run.bat
echo.
pause
