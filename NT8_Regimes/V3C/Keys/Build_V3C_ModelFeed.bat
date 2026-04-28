@echo off
title Build V3C ModelFeed
color 0B

set "V3C_DIR=C:\Users\Valued Customer\NT8_Regimes\V3C"
set "SCRIPTS_DIR=%V3C_DIR%\Scripts"
set "SCRIPT=%SCRIPTS_DIR%\BuildV3CModelFeed.py"

echo.
echo ============================================================
echo   Build V3C Sidecar ModelFeed
echo ============================================================
echo.
echo This builds V3C-only Macro/HMM files under:
echo   %V3C_DIR%\ModelFeed
echo.
echo It does not write to NT8_Regimes\Active.
echo.

if not exist "%SCRIPT%" (
    echo ERROR: Could not find:
    echo   %SCRIPT%
    echo.
    pause
    exit /b 1
)

cd /d "%SCRIPTS_DIR%"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%SCRIPT%"
) else (
    python "%SCRIPT%"
)

echo.
echo Build finished.
pause
