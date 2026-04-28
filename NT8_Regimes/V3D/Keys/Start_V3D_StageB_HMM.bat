@echo off
setlocal EnableExtensions
title V3D Stage B HMMWatchdog
color 0B

set "BASE_DIR=C:\Users\Valued Customer\NT8_Regimes"
set "V3D_DIR=%BASE_DIR%\V3D"
set "SCRIPTS_DIR=%V3D_DIR%\Scripts"
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

echo V3D Stage B HMMWatchdog live feed
echo Writes: %V3D_DIR%\NQ_HMM_Regimes_V3D.csv and ES_HMM_Regimes_V3D.csv
echo.
cd /d "%V3D_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPTS_DIR%\HMMWatchdog_V3D.py" --live --symbol BOTH --interval 30
pause
