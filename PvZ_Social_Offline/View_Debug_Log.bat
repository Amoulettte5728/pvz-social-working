@echo off
title PvZ Debug Log Viewer
cls

set "LOGFILE=%APPDATA%\Macromedia\Flash Player\Logs\flashlog.txt"

if not exist "%LOGFILE%" (
    echo =================================================================
    echo   No log file found yet.
    echo =================================================================
    echo.
    echo Expected it at:
    echo   %LOGFILE%
    echo.
    echo Before this will exist, you need to:
    echo   1. Run Enable_Debug_Log.bat once ^(if you haven't already^)
    echo   2. Fully close Flash Player if it's open
    echo   3. Play the game at least once through Start_Game.bat
    echo.
    pause
    exit
)

echo =================================================================
echo   Loading-bar trace  ^(filtered from flashlog.txt^)
echo =================================================================
echo.
echo This shows only the [DEBUG-...] lines - the checkpoints added to
echo track the loading sequence. Read them top to bottom: the last
echo [DEBUG-FLOW] line before the trace stops is where it's stuck.
echo A [DEBUG-LOADBAR-BLOCKED] or [DEBUG-IO-ERROR] line names the exact
echo file that failed to load.
echo.
echo -----------------------------------------------------------------
findstr /C:"[DEBUG-" "%LOGFILE%"
echo -----------------------------------------------------------------
echo.
echo (Nothing above? The game hasn't reached any traced checkpoint yet,
echo  or flashlog.txt is from an older run - try clearing it and
echo  playing again.)
echo.
echo Press any key to open the FULL raw log instead (includes the
echo game's own original debug output, much noisier)...
pause >nul
notepad "%LOGFILE%"
