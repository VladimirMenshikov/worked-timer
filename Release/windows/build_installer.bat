@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\WorkTimer.exe" (
    echo [ERROR] dist\WorkTimer.exe not found. Run build_exe.bat first.
    pause
    exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo [ERROR] Inno Setup Compiler not found.
    echo Install Inno Setup 6 from https://jrsoftware.org/isdl.php and try again.
    pause
    exit /b 1
)

if not exist "output" mkdir output

"%ISCC%" installer.iss

echo.
echo === Done ===
echo Result: output\WorkTimerSetup-1.0.0.exe
pause
