@echo off
setlocal EnableExtensions
title V3D End Of Day Shutdown
color 0C

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3D_DIR=%BASE_DIR%\V3D"
set "SCRIPTS_DIR=%V3D_DIR%\Scripts"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHON_EXE=python"
set "PYTHON_ARGS="

echo.
echo ============================================================
echo   V3D END OF DAY SHUTDOWN
echo ============================================================
echo.

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

echo [1/4] Stopping V3D live pipeline processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%\V3D_Stop_Live_Processes.ps1"

echo.
echo [2/4] Generating today's V3D regime report...
cd /d "%V3D_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPTS_DIR%\V3D_Daily_Regime_Report.py" --date today --archive-latest

echo.
echo [3/4] Checking archived files...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$dir='%V3D_DIR%\History\Archives'; if(Test-Path $dir){ Get-ChildItem $dir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name,LastWriteTime,Length | Format-Table -AutoSize } else { Write-Host 'No archive folder found.' }"

echo.
echo [4/4] Current V3D output timestamps...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@('%V3D_DIR%\NQ_RegimeMatrix_Latest.csv','%V3D_DIR%\ES_RegimeMatrix_Latest.csv','%V3D_DIR%\History\NQ_RegimeMatrix_History.csv','%V3D_DIR%\History\ES_RegimeMatrix_History.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ($i.FullName + '  ' + $i.LastWriteTime) } else { Write-Host ('MISS ' + $f) } }"

echo.
echo ============================================================
echo   V3D EOD COMPLETE
echo ============================================================
echo.
pause
exit /b 0
