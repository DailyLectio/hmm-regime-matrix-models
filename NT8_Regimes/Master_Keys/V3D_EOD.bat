@echo off
setlocal EnableExtensions
title V3D End Of Day Shutdown + Comparison
color 0C

REM ============================================================
REM  V3D_EndOfDay_Shutdown.bat
REM  V3D EOD routine - now includes V3C vs V3D regime comparison
REM  and trade log enrichment.
REM
REM  Step 1  Stop live pipeline processes
REM  Step 2  Generate V3D daily regime report (JSON + TXT)
REM  Step 3  Run V3C vs V3D regime comparison + trade log enrichment
REM  Step 4  Verify archived files
REM  Step 5  Show output file timestamps
REM ============================================================

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3D_DIR=%BASE_DIR%\V3D"
set "SCRIPTS_DIR=%V3D_DIR%\Scripts"
set "HISTORY_DIR=%V3D_DIR%\History"

REM --- Python resolver ---
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
echo   V3D END OF DAY SHUTDOWN + COMPARISON
echo ============================================================
echo.

REM ============================================================
echo [1/5] Stopping V3D live pipeline processes...
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%\V3D_Stop_Live_Processes.ps1" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Stop script returned non-zero. Processes may already be stopped.
)
echo   Done.
echo.

REM ============================================================
echo [2/5] Generating V3D daily regime report...
REM ============================================================
cd /d "%V3D_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPTS_DIR%\V3D_Daily_Regime_Report.py" --date today --archive-latest

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] V3D_Daily_Regime_Report.py failed.
    echo         Check the output above for details.
    echo         Continuing with comparison step using existing JSON if available.
    echo.
) else (
    echo   Report written and archived.
)
echo.

REM ============================================================
echo [3/5] Running V3C vs V3D regime comparison + trade log...
REM ============================================================
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPTS_DIR%\V3D_Regime_Comparison.py" --date today

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] V3D_Regime_Comparison.py failed.
    echo         Review error above. Comparison CSV may be incomplete for today.
    echo.
) else (
    echo.
    echo   Comparison outputs:
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$files=@('%HISTORY_DIR%\V3C_V3D_Regime_Comparison.csv','%HISTORY_DIR%\V3C_V3D_Intraday_Comparison.csv','%HISTORY_DIR%\V3D_Trade_Log_Enriched.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; $rows=(Import-Csv $f).Count; Write-Host ('  OK  ' + $i.Name + '  rows=' + $rows + '  updated=' + $i.LastWriteTime) } else { Write-Host ('  MISS ' + $f) } }"
)
echo.

REM ============================================================
echo [4/5] Checking archived files...
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$dir='%HISTORY_DIR%\Archives'; if(Test-Path $dir){ Get-ChildItem $dir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name,LastWriteTime,Length | Format-Table -AutoSize } else { Write-Host '  No archive folder found.' }"
echo.

REM ============================================================
echo [5/5] Current V3D output file timestamps...
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$files=@( '%V3D_DIR%\NQ_RegimeMatrix_Latest.csv', '%V3D_DIR%\ES_RegimeMatrix_Latest.csv', '%HISTORY_DIR%\NQ_RegimeMatrix_History.csv', '%HISTORY_DIR%\ES_RegimeMatrix_History.csv', '%HISTORY_DIR%\V3C_V3D_Regime_Comparison.csv', '%HISTORY_DIR%\V3C_V3D_Intraday_Comparison.csv', '%HISTORY_DIR%\V3D_Trade_Log_Enriched.csv', '%V3D_DIR%\TradeLog\V3D_INTERNAL_TradeLog.csv' ); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ('  OK   ' + $i.Name + '  ' + $i.LastWriteTime) } else { Write-Host ('  MISS ' + $f) } }; $legacy='%V3D_DIR%\TradeLog\V3D_TradeLog.csv'; if(Test-Path $legacy){ $i=Get-Item $legacy; Write-Host ('  LEGACY/SKIP ' + $i.Name + '  ' + $i.LastWriteTime) }"

echo.
echo ============================================================
echo   V3D EOD COMPLETE
echo   Review files at: %HISTORY_DIR%
echo ============================================================
echo.
pause
exit /b 0
