@echo off
REM ============================================================
REM  Run_Supervisor_Live.bat
REM  Launches RegimeSupervisor in LIVE mode.
REM
REM  This runs continuously, reading Stage A and B outputs
REM  every 30 seconds and writing the latest regime state to
REM  RegimeMatrix_Latest.csv for the NT8 HUD to consume.
REM
REM  Leave this running during market hours.
REM  Close the window when done trading.
REM ============================================================

ECHO.
ECHO ============================================================
ECHO  V3D RegimeSupervisor - LIVE MODE
ECHO  Updates every 30 seconds
ECHO ============================================================
ECHO.

REM --- Verify junction exists ---
IF NOT EXIST "C:\V3D" (
    ECHO [ERROR] C:\V3D junction not found.
    ECHO         Please run V3D_Setup_Junction.bat as Administrator first.
    ECHO.
    PAUSE
    EXIT /B 1
)

REM --- Verify batch mode was run first ---
IF NOT EXIST "C:\V3D\Backtest\NQ_RegimeMatrix_Full.csv" (
    ECHO [WARNING] RegimeMatrix_Full.csv not found.
    ECHO           Run Run_Supervisor_Batch.bat first to process history.
    ECHO.
    ECHO Continue anyway? (Live mode will work but no historical baseline)
    PAUSE
)

ECHO Starting live supervisor...
ECHO Leave this window open during market hours.
ECHO Press Ctrl+C to stop.
ECHO.

REM --- Run in continuous loop ---
python C:\V3D\Scripts\RegimeSupervisor_V3D.py --live --symbol BOTH --interval 30

ECHO.
ECHO Supervisor stopped.
PAUSE
