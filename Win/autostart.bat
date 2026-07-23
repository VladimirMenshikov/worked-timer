@echo off
setlocal

set "APP_DIR=%~dp0"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WorkTimer.lnk"

powershell -NoProfile -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
    "$s.TargetPath = '%APP_DIR%.venv\Scripts\pythonw.exe';" ^
    "$s.Arguments = '\"%APP_DIR%timer.py\"';" ^
    "$s.WorkingDirectory = '%APP_DIR%';" ^
    "$s.IconLocation = '%APP_DIR%.venv\Scripts\pythonw.exe';" ^
    "$s.Save()"

echo Autostart configured: %SHORTCUT%
echo To disable, delete this file.
pause
