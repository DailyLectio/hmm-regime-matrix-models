@echo off
setlocal EnableExtensions
title All Models EOW Export
cd /d "C:\Users\Valued Customer\NT8_Regimes"

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
        if exist "%LOCAL_PYTHON%" set "PYTHON_EXE=%LOCAL_PYTHON%"
    )
)

echo.
echo ============================================================
echo   ALL MODELS END-OF-WEEK EXPORT
echo ============================================================
echo.

echo [1/2] Building all-history unified trade export...
"%PYTHON_EXE%" %PYTHON_ARGS% "Scripts\eod_export.py" --date all
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Unified all-history export failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Building weekly markdown performance report...
"%PYTHON_EXE%" %PYTHON_ARGS% "Scripts\trade_performance_report.py" --mode weekly --week-ending auto
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Weekly markdown report failed.
    pause
    exit /b 1
)

echo.
echo Outputs:
echo   C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_ALL.csv
echo   C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports
echo.
pause
endlocal
