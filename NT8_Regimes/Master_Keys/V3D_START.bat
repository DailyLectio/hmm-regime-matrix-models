@echo off
setlocal EnableExtensions
title V3D PreMarket Master
color 0A

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3D_DIR=%BASE_DIR%\V3D"
set "KEYS_DIR=%V3D_DIR%\Keys"
set "SCRIPTS_DIR=%V3D_DIR%\Scripts"
set "LOCAL_PYTHON=C:\Users\Valued Customer\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHON_EXE=python"
set "PYTHON_ARGS="

echo.
echo ============================================================
echo   V3D PREMARKET MASTER
echo ============================================================
echo.
echo Base folder: %BASE_DIR%
echo V3D folder:  %V3D_DIR%
echo.

if not exist "%V3D_DIR%" (
    echo ERROR: Missing V3D folder:
    echo   %V3D_DIR%
    pause
    exit /b 1
)

for %%F in (
    "%SCRIPTS_DIR%\MacroRegimeBuilder_V3D.py"
    "%SCRIPTS_DIR%\HMMWatchdog_V3D.py"
    "%SCRIPTS_DIR%\RegimeSupervisor_V3D.py"
    "%SCRIPTS_DIR%\V3D_Daily_Regime_Report.py"
) do (
    if not exist "%%~F" (
        echo ERROR: Missing required file:
        echo   %%~F
        pause
        exit /b 1
    )
)

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

if not exist "%BASE_DIR%\Exports\NQ_1min_export.txt" (
    echo WARNING: NQ export file not found yet:
    echo   %BASE_DIR%\Exports\NQ_1min_export.txt
)

if not exist "%BASE_DIR%\Exports\ES_1min_export.txt" (
    echo WARNING: ES export file not found yet:
    echo   %BASE_DIR%\Exports\ES_1min_export.txt
)

echo [1/6] Generating previous business day V3D regime report...
cd /d "%V3D_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPTS_DIR%\V3D_Daily_Regime_Report.py" --date previous-business-day

echo.
echo [2/6] Stopping any duplicate V3D live processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%\V3D_Stop_Live_Processes.ps1"

echo.
echo [3/6] Starting V3D Stage A MacroRegime...
start "V3D-StageA-MacroRegime" cmd /k ""%KEYS_DIR%\Start_V3D_StageA_Macro.bat""
timeout /t 5 /nobreak >nul

echo.
echo [4/6] Starting V3D Stage B HMMWatchdog...
start "V3D-StageB-HMMWatchdog" cmd /k ""%KEYS_DIR%\Start_V3D_StageB_HMM.bat""
timeout /t 5 /nobreak >nul

echo.
echo [5/6] Starting V3D Stage C RegimeSupervisor...
start "V3D-StageC-Supervisor" cmd /k ""%KEYS_DIR%\Start_V3D_StageC_Supervisor.bat""

echo.
echo [6/6] Waiting 60 seconds for first V3D rows...
timeout /t 60 /nobreak >nul

echo.
echo Verifying V3D latest files...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@('%V3D_DIR%\NQ_RegimeMatrix_Latest.csv','%V3D_DIR%\ES_RegimeMatrix_Latest.csv','%V3D_DIR%\NQ_Macro_Regimes_V3D.csv','%V3D_DIR%\ES_Macro_Regimes_V3D.csv','%V3D_DIR%\NQ_HMM_Regimes_V3D.csv','%V3D_DIR%\ES_HMM_Regimes_V3D.csv'); foreach($f in $files){ if(Test-Path $f){ $i=Get-Item $f; Write-Host ('OK  ' + $i.FullName + '  ' + $i.LastWriteTime) } else { Write-Host ('MISS ' + $f) } }"

echo.
echo ============================================================
echo   V3D PREMARKET STARTUP COMPLETE
echo ============================================================
echo.
echo Leave the three V3D command windows open during market hours:
echo   V3D-StageA-MacroRegime
echo   V3D-StageB-HMMWatchdog
echo   V3D-StageC-Supervisor
echo.
pause
exit /b 0
