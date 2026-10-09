@echo off
rem Opens the graphical launcher and starts its local server.
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0launcher.py" --server
    exit /b
)

where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0launcher.py" --server
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0launcher.py" --server
    exit /b
)

echo Python is not installed or is not available on PATH.
echo Install Python 3, then run Start_Server.bat again.
pause
