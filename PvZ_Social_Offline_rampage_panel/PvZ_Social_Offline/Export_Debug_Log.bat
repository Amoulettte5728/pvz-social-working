@echo off
title PvZ Debug Log Exporter
cls

set "LOGFILE=%APPDATA%\Macromedia\Flash Player\Logs\flashlog.txt"
set "SERVERLOG=server_log.txt"
set "OUTFILE=debug_export.txt"

echo =================================================================
echo   Exporting logs to %OUTFILE% ...
echo =================================================================
echo.
echo This bundles three things into one plain text file, so it can be
echo attached/uploaded directly instead of screenshotting terminals:
echo   1. The filtered [DEBUG-...] checkpoint lines from flashlog.txt
echo   2. The full flashlog.txt (the game's own client-side trace)
echo   3. server_log.txt (the server's console output - AMF calls,
echo      asset requests, 404s, the build check)
echo.

echo === PvZ debug export === > "%OUTFILE%"
echo Generated: %DATE% %TIME% >> "%OUTFILE%"
echo. >> "%OUTFILE%"
echo ---------------------------------------------------------------- >> "%OUTFILE%"
echo   Filtered flashlog.txt (DEBUG checkpoint lines only) >> "%OUTFILE%"
echo ---------------------------------------------------------------- >> "%OUTFILE%"
if exist "%LOGFILE%" (
    findstr /C:"[DEBUG-" "%LOGFILE%" >> "%OUTFILE%"
) else (
    echo (no flashlog.txt found at: %LOGFILE%) >> "%OUTFILE%"
    echo (run Enable_Debug_Log.bat once, then play, before this will exist) >> "%OUTFILE%"
)
echo. >> "%OUTFILE%"

echo ---------------------------------------------------------------- >> "%OUTFILE%"
echo   Full flashlog.txt (everything, including the game's own trace) >> "%OUTFILE%"
echo ---------------------------------------------------------------- >> "%OUTFILE%"
if exist "%LOGFILE%" (
    type "%LOGFILE%" >> "%OUTFILE%"
) else (
    echo (no flashlog.txt found) >> "%OUTFILE%"
)
echo. >> "%OUTFILE%"

echo ---------------------------------------------------------------- >> "%OUTFILE%"
echo   server_log.txt (the server's own console output) >> "%OUTFILE%"
echo ---------------------------------------------------------------- >> "%OUTFILE%"
if exist "%SERVERLOG%" (
    type "%SERVERLOG%" >> "%OUTFILE%"
) else (
    echo (no server_log.txt found - start the server via Start_Server.bat first) >> "%OUTFILE%"
)

echo [OK] Wrote %OUTFILE% in this folder.
echo.
echo That's a plain text file - upload/attach it directly, no need to
echo screenshot any console windows.
echo.
pause
