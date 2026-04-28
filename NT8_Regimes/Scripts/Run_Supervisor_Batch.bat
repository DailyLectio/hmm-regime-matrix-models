@echo off
REM ============================================================
REM  Run_Supervisor_Batch.bat
REM  ONE-TIME batch run: Processes full history and creates
REM  RegimeMatrix_Full.csv in the Backtest folder.
REM
REM  This produces the missing Stage C output needed for
REM  regime analysis and bot validation.
REM
REM  Run this ONCE after installing RegimeSupervisor_V3D.py
REM  Expected runtime: 2-5 minutes for ~750 days of data
REM ============================================================

ECHO.
ECHO ============================================================
ECHO  V3D RegimeSupervisor - BATCH MODE
ECHO  Processing full history...
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

REM --- Verify input files exist ---
IF NOT EXIST "C:\V3D\V3D\NQ_Macro_Regimes_V3D.csv" (
    ECHO [ERROR] NQ_Macro_Regimes_V3D.csv not found.
    ECHO         Run MacroRegimeBuilder_V3D.py --batch first.
    ECHO.
    PAUSE
    EXIT /B 1
)

IF NOT EXIST "C:\V3D\V3D\NQ_HMM_Regimes_V3D.csv" (
    ECHO [ERROR] NQ_HMM_Regimes_V3D.csv not found.
    ECHO         Run HMMWatchdog_V3D.py --once first.
    ECHO.
    PAUSE
    EXIT /B 1
)

ECHO Input files verified. Starting batch processing...
ECHO.

REM --- Run supervisor in batch mode for both instruments ---
python C:\V3D\Scripts\RegimeSupervisor_V3D.py --batch --symbol BOTH

IF ERRORLEVEL 1 (
    ECHO.
    ECHO [ERROR] Batch processing failed. See error above.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO ============================================================
ECHO  BATCH COMPLETE
ECHO.
ECHO  Output files created:
ECHO    C:\V3D\Backtest\NQ_RegimeMatrix_Full.csv
ECHO    C:\V3D\Backtest\ES_RegimeMatrix_Full.csv
ECHO.
ECHO  These files contain the complete regime classification
ECHO  history and are ready for analysis.
ECHO.
ECHO  Next step: Run regime analysis scripts or proceed to
ECHO  Run_Supervisor_Live.bat for real-time operation.
ECHO ============================================================
PAUSE
