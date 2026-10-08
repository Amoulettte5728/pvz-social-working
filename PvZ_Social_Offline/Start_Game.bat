@echo off
rem PvZ Social Edition graphical launcher
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0launcher.py"
    exit /b
)

where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0launcher.py"
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0launcher.py"
    exit /b
)

echo Python is not installed or is not available on PATH.
echo Install Python 3, then run Start_Game.bat again.
pause
