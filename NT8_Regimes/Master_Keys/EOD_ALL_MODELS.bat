@echo off
setlocal EnableExtensions
title EOD All Active Models
color 0C

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3C_DIR=%BASE_DIR%\V3C"
set "V3D_DIR=%BASE_DIR%\V3D"
set "V3C_SCRIPTS=%V3C_DIR%\Scripts"
set "V3D_SCRIPTS=%V3D_DIR%\Scripts"
set "ROOT_SCRIPTS=%BASE_DIR%\Scripts"
set "UNIFIED_DIR=%BASE_DIR%\UNIFIED"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHON_EXE=python"
set "PYTHON_ARGS="

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
) else (
    where python >nul 2>nul
    if not %ERRORLEVEL%==0 (
        if exist "%LOCAL_PYTHON%" (
            set "PYTHON_EXE=%LOCAL_PYTHON%"
        ) else (
            echo ERROR: Python was not found.
            pause
            exit /b 1
        )
    )
)

echo.
echo ============================================================
echo   EOD ALL ACTIVE MODELS
echo ============================================================
echo.
echo This replaces the old three-click sequence:
echo   V3C_EOD, V3D_EOD, ALL_MODELS_EXPORT.
echo.

for %%F in (
    "%V3C_SCRIPTS%\V3C_Stop_Live_Processes.ps1"
    "%V3C_SCRIPTS%\V3C_Daily_Regime_Report.py"
    "%V3D_SCRIPTS%\V3D_Stop_Live_Processes.ps1"
    "%V3D_SCRIPTS%\V3D_Daily_Regime_Report.py"
    "%V3D_SCRIPTS%\V3D_Regime_Comparison.py"
    "%ROOT_SCRIPTS%\eod_export.py"
    "%ROOT_SCRIPTS%\trade_performance_report.py"
) do (
    if not exist "%%~F" (
        echo ERROR: Missing required file:
        echo   %%~F
        pause
        exit /b 1
    )
)

echo [1/8] Stopping V3C live processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%V3C_SCRIPTS%\V3C_Stop_Live_Processes.ps1"

echo.
echo [2/8] Stopping V3D live processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%V3D_SCRIPTS%\V3D_Stop_Live_Processes.ps1" 2>nul

echo.
echo [3/8] Generating today's V3C regime report...
cd /d "%V3C_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%V3C_SCRIPTS%\V3C_Daily_Regime_Report.py" --date today --archive-latest
if %ERRORLEVEL% NEQ 0 echo WARNING: V3C report returned non-zero.

echo.
echo [4/8] Generating today's V3D regime report...
cd /d "%V3D_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%V3D_SCRIPTS%\V3D_Daily_Regime_Report.py" --date today --archive-latest
if %ERRORLEVEL% NEQ 0 echo WARNING: V3D report returned non-zero.

echo.
echo [5/8] Running V3C vs V3D comparison and V3D trade enrichment...
"%PYTHON_EXE%" %PYTHON_ARGS% "%V3D_SCRIPTS%\V3D_Regime_Comparison.py" --date today
if %ERRORLEVEL% NEQ 0 echo WARNING: V3D comparison returned non-zero. Continuing to unified export.

echo.
echo [6/8] Building unified daily trade export...
cd /d "%BASE_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%ROOT_SCRIPTS%\eod_export.py" --date today
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Unified EOD export failed.
    pause
    exit /b 1
)

echo.
echo [7/8] Building daily markdown performance report...
"%PYTHON_EXE%" %PYTHON_ARGS% "%ROOT_SCRIPTS%\trade_performance_report.py" --mode daily --date today
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Daily markdown report failed.
    pause
    exit /b 1
)

echo.
echo [8/9] Checking whether weekly export is due...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if ((Get-Date).DayOfWeek -eq 'Friday') { exit 0 } else { exit 1 }"
if %ERRORLEVEL% EQU 0 (
    echo Friday detected. Building all-history export and weekly report...
    "%PYTHON_EXE%" %PYTHON_ARGS% "%ROOT_SCRIPTS%\eod_export.py" --date all
    if %ERRORLEVEL% NEQ 0 (
        echo WARNING: Weekly all-history export returned non-zero.
    ) else (
        "%PYTHON_EXE%" %PYTHON_ARGS% "%ROOT_SCRIPTS%\trade_performance_report.py" --mode weekly --week-ending auto
        if %ERRORLEVEL% NEQ 0 echo WARNING: Weekly markdown report returned non-zero.
    )
) else (
    echo Not Friday. Weekly export skipped.
)

echo.
echo [9/9] Checking current EOD outputs...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$today=Get-Date -Format yyyyMMdd; $files=@('%V3C_DIR%\Reports\V3C_Regime_Report_'+$today+'.json','%V3D_DIR%\Reports\V3D_Regime_Report_'+$today+'.json','%V3D_DIR%\History\V3C_V3D_Regime_Comparison.csv','%V3D_DIR%\History\V3D_Trade_Log_Enriched.csv','%UNIFIED_DIR%\AllModels_TradeLog_'+$today+'.csv','%UNIFIED_DIR%\Reports\Daily_Trade_Performance_'+$today+'.md','%V3D_DIR%\TradeLog\V3D_INTERNAL_TradeLog.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ('  OK   ' + $i.Name + '  ' + $i.LastWriteTime) } else { Write-Host ('  MISS ' + $f) } }; $legacy='%V3D_DIR%\TradeLog\V3D_TradeLog.csv'; if(Test-Path $legacy){ $i=Get-Item $legacy; Write-Host ('  LEGACY/SKIP ' + $i.Name + '  ' + $i.LastWriteTime) }"

echo.
echo ============================================================
echo   EOD COMPLETE
echo ============================================================
echo.
echo Primary outputs:
echo   %UNIFIED_DIR%
echo   %UNIFIED_DIR%\Reports
echo.
pause
exit /b 0
