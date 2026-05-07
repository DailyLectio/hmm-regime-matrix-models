@echo off
setlocal EnableExtensions
title Start All Active Models
color 0A

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3C_DIR=%BASE_DIR%\V3C"
set "V3D_DIR=%BASE_DIR%\V3D"
set "V3C_SCRIPTS=%V3C_DIR%\Scripts"
set "V3D_SCRIPTS=%V3D_DIR%\Scripts"
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
echo   START ALL ACTIVE MODELS
echo ============================================================
echo.
echo This starts the current V3C and V3D live model feeds.
echo Leave the launched command windows open during market hours.
echo.

for %%F in (
    "%V3C_SCRIPTS%\V3C_Daily_Regime_Report.py"
    "%V3C_SCRIPTS%\V3C_Stop_Live_Processes.ps1"
    "%V3C_SCRIPTS%\V3C_ModelFeed_Watchdog.py"
    "%V3C_SCRIPTS%\RegimeMatrixSupervisor.py"
    "%V3D_SCRIPTS%\V3D_Daily_Regime_Report.py"
    "%V3D_SCRIPTS%\V3D_Stop_Live_Processes.ps1"
    "%V3D_SCRIPTS%\MacroRegimeBuilder_V3D.py"
    "%V3D_SCRIPTS%\HMMWatchdog_V3D.py"
    "%V3D_SCRIPTS%\RegimeSupervisor_V3D.py"
) do (
    if not exist "%%~F" (
        echo ERROR: Missing required file:
        echo   %%~F
        pause
        exit /b 1
    )
)

if not exist "%BASE_DIR%\Exports\NQ_1min_export.txt" (
    echo WARNING: NQ 1-minute export not found yet.
)
if not exist "%BASE_DIR%\Exports\ES_1min_export.txt" (
    echo WARNING: ES 1-minute export not found yet.
)

echo [1/8] Generating previous-business-day V3C report...
cd /d "%V3C_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%V3C_SCRIPTS%\V3C_Daily_Regime_Report.py" --date previous-business-day

echo.
echo [2/8] Generating previous-business-day V3D report...
cd /d "%V3D_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%V3D_SCRIPTS%\V3D_Daily_Regime_Report.py" --date previous-business-day

echo.
echo [3/8] Stopping duplicate V3C processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%V3C_SCRIPTS%\V3C_Stop_Live_Processes.ps1"

echo.
echo [4/8] Stopping duplicate V3D processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%V3D_SCRIPTS%\V3D_Stop_Live_Processes.ps1"

echo.
echo [5/8] Starting V3C live processes...
start "V3C ModelFeed Watchdog" cmd /k ""%PYTHON_EXE%" %PYTHON_ARGS% "%V3C_SCRIPTS%\V3C_ModelFeed_Watchdog.py""
timeout /t 3 /nobreak >nul
start "V3C Regime Matrix Supervisor" cmd /k ""%PYTHON_EXE%" %PYTHON_ARGS% "%V3C_SCRIPTS%\RegimeMatrixSupervisor.py""

echo.
echo [6/8] Starting V3D live processes...
start "V3D Stage A MacroRegime" cmd /k ""%PYTHON_EXE%" %PYTHON_ARGS% "%V3D_SCRIPTS%\MacroRegimeBuilder_V3D.py" --live --symbol BOTH --interval 30"
timeout /t 5 /nobreak >nul
start "V3D Stage B HMMWatchdog" cmd /k ""%PYTHON_EXE%" %PYTHON_ARGS% "%V3D_SCRIPTS%\HMMWatchdog_V3D.py" --live --symbol BOTH --interval 30"
timeout /t 5 /nobreak >nul
start "V3D Stage C RegimeSupervisor" cmd /k ""%PYTHON_EXE%" %PYTHON_ARGS% "%V3D_SCRIPTS%\RegimeSupervisor_V3D.py" --live --symbol BOTH --interval 30 --sim-test"

echo.
echo [7/8] Waiting 60 seconds for first model rows...
timeout /t 60 /nobreak >nul

echo.
echo [8/8] Checking latest output files...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$files=@('%V3C_DIR%\NQ_Regimes_V3C_Latest.csv','%V3C_DIR%\ES_Regimes_V3C_Latest.csv','%V3D_DIR%\NQ_RegimeMatrix_Latest.csv','%V3D_DIR%\ES_RegimeMatrix_Latest.csv','%V3D_DIR%\NQ_Macro_Regimes_V3D.csv','%V3D_DIR%\ES_Macro_Regimes_V3D.csv','%V3D_DIR%\NQ_HMM_Regimes_V3D.csv','%V3D_DIR%\ES_HMM_Regimes_V3D.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ('  OK   ' + $i.Name + '  ' + $i.LastWriteTime) } else { Write-Host ('  MISS ' + $f) } }"

echo.
echo ============================================================
echo   START COMPLETE
echo ============================================================
echo.
echo Open windows expected:
echo   V3C ModelFeed Watchdog
echo   V3C Regime Matrix Supervisor
echo   V3D Stage A MacroRegime
echo   V3D Stage B HMMWatchdog
echo   V3D Stage C RegimeSupervisor
echo.
pause
exit /b 0
