@echo off
title V3C ModelFeed Watchdog
color 0B

set "V3C_DIR=C:\Users\Valued Customer\NT8_Regimes\V3C"
set "SCRIPTS_DIR=%V3C_DIR%\Scripts"
set "SCRIPT=%SCRIPTS_DIR%\V3C_ModelFeed_Watchdog.py"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"

echo.
echo ============================================================
echo   V3C ModelFeed Watchdog
echo ============================================================
echo.
echo Reads live NT exports and writes V3C-only ModelFeed files.
echo Does not write to NT8_Regimes\Active.
echo.

if not exist "%SCRIPT%" (
    echo ERROR: Could not find:
    echo   %SCRIPT%
    echo.
    pause
    exit /b 1
)

cd /d "%SCRIPTS_DIR%"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%SCRIPT%"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        python "%SCRIPT%"
    ) else (
        if exist "%LOCAL_PYTHON%" (
            "%LOCAL_PYTHON%" "%SCRIPT%"
        ) else (
            echo ERROR: Python was not found.
            pause
            exit /b 1
        )
    )
)

echo.
echo Watchdog stopped.
pause
