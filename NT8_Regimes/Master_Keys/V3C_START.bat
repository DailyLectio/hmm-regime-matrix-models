@echo off
setlocal EnableExtensions
title V3C PreMarket Master
color 0A

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3C_DIR=%BASE_DIR%\V3C"
set "KEYS_DIR=%V3C_DIR%\Keys"
set "SCRIPTS_DIR=%V3C_DIR%\Scripts"
set "PYTHON_CMD=python"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"

echo.
echo ============================================================
echo   V3C PREMARKET MASTER
echo ============================================================
echo.
echo Base folder: %BASE_DIR%
echo V3C folder:  %V3C_DIR%
echo.

if not exist "%V3C_DIR%" (
    echo ERROR: Missing V3C folder:
    echo   %V3C_DIR%
    pause
    exit /b 1
)

if not exist "%SCRIPTS_DIR%\RegimeMatrixSupervisor.py" (
    echo ERROR: Missing RegimeMatrixSupervisor.py
    pause
    exit /b 1
)

if not exist "%SCRIPTS_DIR%\V3C_ModelFeed_Watchdog.py" (
    echo ERROR: Missing V3C_ModelFeed_Watchdog.py
    pause
    exit /b 1
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYTHON_CMD=python"
    ) else (
        if exist "%LOCAL_PYTHON%" (
            set "PYTHON_CMD=%LOCAL_PYTHON%"
        ) else (
            echo ERROR: Python was not found on PATH.
            echo Install Python or add Python to PATH.
            pause
            exit /b 1
        )
    )
)

if not exist "%BASE_DIR%\Exports\NQ_1min_export.txt" (
    echo WARNING: NQ export file not found yet:
    echo   %BASE_DIR%\Exports\NQ_1min_export.txt
)

if not exist "%BASE_DIR%\Exports\ES_1min_export.txt" (
    echo WARNING: ES export file not found yet:
    echo   %BASE_DIR%\Exports\ES_1min_export.txt
)

echo [1/5] Generating previous business day V3C regime report...
cd /d "%V3C_DIR%"
%PYTHON_CMD% "%SCRIPTS_DIR%\V3C_Daily_Regime_Report.py" --date previous-business-day

echo.
echo [2/5] Stopping any duplicate V3C live processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%\V3C_Stop_Live_Processes.ps1"

echo.
echo [3/5] Starting V3C ModelFeed Watchdog...
start "V3C ModelFeed Watchdog" cmd /k ""%KEYS_DIR%\Start_V3C_ModelFeed_Watchdog.bat""

echo.
echo [4/5] Starting V3C Regime Matrix Supervisor...
start "V3C Regime Matrix Supervisor" cmd /k ""%KEYS_DIR%\Start_RegimeMatrixSupervisor.bat""

echo.
echo [5/5] Waiting 60 seconds for first V3C rows...
timeout /t 60 /nobreak >nul

echo.
echo Verifying V3C latest files...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@('%V3C_DIR%\NQ_Regimes_V3C_Latest.csv','%V3C_DIR%\ES_Regimes_V3C_Latest.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ('OK  ' + $i.FullName + '  ' + $i.LastWriteTime) } else { Write-Host ('MISS ' + $f) } }"

echo.
echo ============================================================
echo   V3C PREMARKET STARTUP COMPLETE
echo ============================================================
echo.
echo NinjaTrader HUD settings:
echo   Data Folder Path = %V3C_DIR%
echo   Use Leader Symbol Mapping = True
echo   Debug Prints = False after confirming fresh
echo.
echo Operator reminder:
echo   09:25-09:35 observe only.
echo   First arm pass: one simple Momo V3C template per instrument.
echo.
pause
exit /b 0
