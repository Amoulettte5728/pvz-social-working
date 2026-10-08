@echo off
rem Lets phones and other devices on your home Wi-Fi reach the game server
rem (TCP port 9090). Only needed once. Asks for administrator permission.
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
netsh advfirewall firewall delete rule name="PvZ Social Offline (port 9090)" >nul 2>&1
netsh advfirewall firewall add rule name="PvZ Social Offline (port 9090)" dir=in action=allow protocol=TCP localport=9090 profile=private
if %errorlevel%==0 (
    echo.
    echo Done. Devices on a network Windows calls "Private" can now connect.
    echo If your Wi-Fi is set to "Public", change it in Settings - Network - Wi-Fi - your network.
) else (
    echo.
    echo Could not add the firewall rule.
)
echo.
pause
