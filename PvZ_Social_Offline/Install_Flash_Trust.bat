@echo off
echo Installing Flash Player local trust configuration...
set TRUSTDIR=%APPDATA%\Macromedia\Flash Player\#Security\FlashPlayerTrust
if not exist "%TRUSTDIR%" mkdir "%TRUSTDIR%"
copy /Y "%~dp0FlashPlayerTrust\pvzsocial.cfg" "%TRUSTDIR%\pvzsocial.cfg"
echo.
echo Done. Installed to:
echo   %TRUSTDIR%\pvzsocial.cfg
echo.
echo This is a system-wide Flash Player setting (not specific to this
echo folder) - it tells Flash Player to fully trust anything served from
echo http://127.0.0.1:9090, the same way it would trust a local file.
echo.
pause
