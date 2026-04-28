@echo off
REM ============================================================
REM  Generate_Daily_Regime_Report.bat
REM  Run this each morning BEFORE market open to see
REM  yesterday's regime distribution and bot opportunities.
REM
REM  Output: Saved to C:\V3D\Reports\ with timestamp
REM ============================================================

ECHO.
ECHO ============================================================
ECHO  V3D Daily Regime Report Generator
ECHO  Analyzing yesterday's trading session...
ECHO ============================================================
ECHO.

REM --- Get yesterday's date (Windows PowerShell method) ---
FOR /F "tokens=*" %%i IN ('powershell -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') DO SET YESTERDAY=%%i

ECHO Yesterday's date: %YESTERDAY%
ECHO.

REM --- Run analysis for both instruments ---
python C:\V3D\Scripts\V3D_Regime_Analysis.py --date %YESTERDAY% --symbol BOTH

IF ERRORLEVEL 1 (
    ECHO.
    ECHO [ERROR] Report generation failed.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO ============================================================
ECHO  Report complete!
ECHO  File saved to: C:\V3D\Reports\
ECHO.
ECHO  You can also run specific analyses:
ECHO    - Last session:   python V3D_Regime_Analysis.py --last-session
ECHO    - Specific date:  python V3D_Regime_Analysis.py --date 2026-04-25
ECHO    - Full history:   python V3D_Regime_Analysis.py --full-history
ECHO ============================================================
PAUSE
