@echo off
setlocal EnableExtensions
title V3C End Of Day Shutdown
color 0C

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3C_DIR=%BASE_DIR%\V3C"
set "SCRIPTS_DIR=%V3C_DIR%\Scripts"
set "PYTHON_CMD=python"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"

echo.
echo ============================================================
echo   V3C END OF DAY SHUTDOWN
echo ============================================================
echo.

if not exist "%V3C_DIR%" (
    echo ERROR: Missing V3C folder:
    echo   %V3C_DIR%
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

echo [1/4] Stopping V3C Python pipeline processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%\V3C_Stop_Live_Processes.ps1"

echo.
echo [2/4] Generating today's V3C regime report...
cd /d "%V3C_DIR%"
%PYTHON_CMD% "%SCRIPTS_DIR%\V3C_Daily_Regime_Report.py" --date today --archive-latest

echo.
echo [3/4] Showing latest V3C file timestamps...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@('%V3C_DIR%\NQ_Regimes_V3C_Latest.csv','%V3C_DIR%\ES_Regimes_V3C_Latest.csv','%V3C_DIR%\ModelFeed\NQ_Macro_Regimes_V3C.csv','%V3C_DIR%\ModelFeed\NQ_Regimes_HMM_V3C.csv','%V3C_DIR%\ModelFeed\ES_Macro_Regimes_V3C.csv','%V3C_DIR%\ModelFeed\ES_Regimes_HMM_V3C.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ($i.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') + '  ' + $i.FullName) } }"

echo.
echo [4/4] V3C EOD complete.
echo Reports:
echo   %V3C_DIR%\Reports
echo Archives:
echo   %V3C_DIR%\History
echo.
pause
exit /b 0
