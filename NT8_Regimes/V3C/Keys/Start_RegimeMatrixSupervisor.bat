@echo off
title V3C Regime Matrix Supervisor
color 0A

REM ============================================================
REM V3C Regime Matrix Supervisor Launcher
REM Save as:
REM   C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\Start_RegimeMatrixSupervisor.bat
REM
REM This launches:
REM   C:\Users\Valued Customer\NT8_Regimes\V3C\Scripts\RegimeMatrixSupervisor.py
REM ============================================================

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3C_DIR=%BASE_DIR%\V3C"
set "SCRIPTS_DIR=%V3C_DIR%\Scripts"
set "SCRIPT=%SCRIPTS_DIR%\RegimeMatrixSupervisor.py"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"

echo.
echo ============================================================
echo   V3C Regime Matrix Supervisor
echo ============================================================
echo.
echo Base folder: %BASE_DIR%
echo Script:      %SCRIPT%
echo.

if not exist "%SCRIPT%" (
    echo ERROR: Could not find RegimeMatrixSupervisor.py
    echo Expected location:
    echo   %SCRIPT%
    echo.
    pause
    exit /b 1
)

cd /d "%SCRIPTS_DIR%"

REM Try Python launcher first. If unavailable, fall back to python.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    echo Starting with: py -3
    echo.
    py -3 "%SCRIPT%"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        echo Starting with: python
        echo.
        python "%SCRIPT%"
    ) else (
        if exist "%LOCAL_PYTHON%" (
            echo Starting with local Python
            echo.
            "%LOCAL_PYTHON%" "%SCRIPT%"
        ) else (
            echo ERROR: Python was not found on PATH.
            echo.
            pause
            exit /b 1
        )
    )
)

echo.
echo Supervisor stopped.
pause
