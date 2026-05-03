@echo off
REM ============================================================
REM  Run_HMM_FullHistory.bat
REM  ONE-TIME run: Generates HMM classifications for FULL HISTORY
REM  (not just 60-day rolling window)
REM
REM  This will take 5-10 minutes to complete.
REM  Run this ONCE before running RegimeSupervisor batch mode.
REM ============================================================

ECHO.
ECHO ============================================================
ECHO  HMM Watchdog - FULL HISTORY MODE
ECHO  Processing entire export file (all ~750 days)
ECHO  Expected runtime: 5-10 minutes
ECHO ============================================================
ECHO.

REM --- Verify junction exists ---
IF NOT EXIST "C:\V3D" (
    ECHO [ERROR] C:\V3D junction not found.
    ECHO         Run V3D_Setup_Junction.bat as Administrator first.
    ECHO.
    PAUSE
    EXIT /B 1
)

REM --- Verify export files exist ---
IF NOT EXIST "C:\V3D\Exports\NQ_1min_export.txt" (
    ECHO [ERROR] NQ_1min_export.txt not found in C:\V3D\Exports\
    ECHO         Make sure the export files exist before running this.
    ECHO.
    PAUSE
    EXIT /B 1
)

ECHO Starting HMM batch processing with FULL HISTORY flag...
ECHO This will OVERWRITE the existing HMM_Regimes_V3D.csv files.
ECHO.
PAUSE

REM --- Run HMM with --full-history flag ---
python C:\V3D\Scripts\HMMWatchdog_V3D.py --once --full-history --symbol BOTH

IF ERRORLEVEL 1 (
    ECHO.
    ECHO [ERROR] HMM processing failed. See error above.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO ============================================================
ECHO  FULL HISTORY HMM PROCESSING COMPLETE
ECHO.
ECHO  Output files created:
ECHO    C:\V3D\V3D\NQ_HMM_Regimes_V3D.csv
ECHO    C:\V3D\V3D\ES_HMM_Regimes_V3D.csv
ECHO.
ECHO  These files should now contain roughly 59,000 rows each
ECHO  (5-minute RTH HMM bars across the full export history)
ECHO.
ECHO  Next step: Run Run_Supervisor_Batch.bat to merge
ECHO  macro and HMM regimes into final classifications.
ECHO ============================================================
PAUSE
