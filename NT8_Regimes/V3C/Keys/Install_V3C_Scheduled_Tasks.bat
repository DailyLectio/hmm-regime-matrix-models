@echo off
setlocal EnableExtensions
title Install V3C Scheduled Tasks
color 0B

set "V3C_DIR=C:\Users\Valued Customer\NT8_Regimes\V3C"
set "KEYS_DIR=%V3C_DIR%\Keys"
set "START_BAT=%KEYS_DIR%\V3C_PreMarket_Master.bat"
set "EOD_BAT=%KEYS_DIR%\V3C_EndOfDay_Shutdown.bat"

echo.
echo ============================================================
echo   INSTALL V3C SCHEDULED TASKS
echo ============================================================
echo.
echo This creates:
echo   V3C PreMarket Master  - Monday-Friday 09:15 local time
echo   V3C EndOfDay Shutdown - Monday-Friday 16:05 local time
echo.

if not exist "%START_BAT%" (
    echo ERROR: Missing %START_BAT%
    pause
    exit /b 1
)

if not exist "%EOD_BAT%" (
    echo ERROR: Missing %EOD_BAT%
    pause
    exit /b 1
)

schtasks /Create /TN "V3C PreMarket Master" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:15 /TR "\"%START_BAT%\"" /F
if errorlevel 1 (
    echo ERROR: Could not create V3C PreMarket Master task.
    pause
    exit /b 1
)

schtasks /Create /TN "V3C EndOfDay Shutdown" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:05 /TR "\"%EOD_BAT%\"" /F
if errorlevel 1 (
    echo ERROR: Could not create V3C EndOfDay Shutdown task.
    pause
    exit /b 1
)

echo.
echo Installed tasks:
schtasks /Query /TN "V3C PreMarket Master"
schtasks /Query /TN "V3C EndOfDay Shutdown"
echo.
pause
exit /b 0
