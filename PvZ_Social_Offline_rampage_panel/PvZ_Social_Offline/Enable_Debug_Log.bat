@echo off
title Enable Flash Debug Log
cls

echo =================================================================
echo   Enabling the Flash Player debug log...
echo =================================================================
echo.

(
echo ErrorReportingEnable=1
echo TraceOutputFileEnable=1
echo MaxWarnings=0
) > "%USERPROFILE%\mm.cfg"

echo [OK] Wrote: %USERPROFILE%\mm.cfg
echo.
echo From now on, every time you play, a file called flashlog.txt will
echo be created/updated at:
echo.
echo   %APPDATA%\Macromedia\Flash Player\Logs\flashlog.txt
echo.
echo That file contains the real trace output from the game, including
echo every line starting with [DEBUG-...] that shows exactly what the
echo loading bar is doing and where it gets stuck.
echo.
echo Close this window, then play the game as normal. Use
echo View_Debug_Log.bat afterwards to see the log.
echo.
pause
