@echo off
REM ============================================================
REM  Run_V3D_Pipeline.bat
REM  Launches Stage A (MacroRegimeBuilder) and Stage B (HMMWatchdog)
REM
REM  REQUIRES: Run V3D_Setup_Junction.bat once first (as Administrator)
REM  That creates C:\V3D as a spaceless alias for the NT8_Regimes folder.
REM
REM  MODES:
REM    Double-click                  -> defaults to live mode
REM    Run_V3D_Pipeline.bat batch    -> full historical reprocess, then exit
REM    Run_V3D_Pipeline.bat live     -> continuous live loop
REM ============================================================

REM --- All paths use C:\V3D (no spaces — junction to NT8_Regimes folder) ---
SET SCRIPTS=C:\V3D\Scripts
SET STAGE_A=C:\V3D\Scripts\MacroRegimeBuilder_V3D.py
SET STAGE_B=C:\V3D\Scripts\HMMWatchdog_V3D.py
SET INTERVAL=30

REM --- Verify junction exists before doing anything ---
IF NOT EXIST "C:\V3D" (
    ECHO.
    ECHO [ERROR] C:\V3D junction not found.
    ECHO         Please run V3D_Setup_Junction.bat as Administrator first.
    ECHO         Right-click V3D_Setup_Junction.bat and choose Run as administrator.
    ECHO.
    PAUSE
    EXIT /B 1
)

REM --- Determine mode ---
SET MODE=%1
IF "%MODE%"=="" SET MODE=live

ECHO ============================================================
ECHO  V3D Pipeline Launcher  ^|  Mode: %MODE%
ECHO  Using path: C:\V3D  (alias for NT8_Regimes)
ECHO ============================================================

IF /I "%MODE%"=="batch" GOTO BATCH
IF /I "%MODE%"=="live"  GOTO LIVE

ECHO Unknown mode: %MODE%
ECHO Usage: Run_V3D_Pipeline.bat batch
ECHO        Run_V3D_Pipeline.bat live
PAUSE
EXIT /B 1


REM ============================================================
:BATCH
REM  Stage A then Stage B, sequentially in this window.
REM ============================================================
ECHO.
ECHO [BATCH] Step 1 of 2 - Stage A (MacroRegimeBuilder)...
ECHO         Processing full export history. May take 2-5 minutes.
ECHO.

python %STAGE_A% --batch --symbol BOTH

IF ERRORLEVEL 1 (
    ECHO.
    ECHO [ERROR] Stage A failed. Read the error above before continuing.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO [BATCH] Step 1 done. Starting Step 2 of 2 - Stage B (HMMWatchdog)...
ECHO.

python %STAGE_B% --once --symbol BOTH

IF ERRORLEVEL 1 (
    ECHO.
    ECHO [ERROR] Stage B failed. Read the error above.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO ============================================================
ECHO  BATCH COMPLETE.
ECHO  Four CSV files should now be in C:\V3D\V3D\
ECHO  (same folder as NT8_Regimes\V3D\)
ECHO  Next step: Run_V3D_Pipeline.bat live
ECHO ============================================================
PAUSE
EXIT /B 0


REM ============================================================
:LIVE
REM  Two separate windows, one per stage, running independently.
REM ============================================================
ECHO.
ECHO [LIVE] Opening Stage A window...

START "V3D-StageA-MacroRegime" cmd /k python %STAGE_A% --live --symbol BOTH --interval %INTERVAL%

TIMEOUT /T 5 /NOBREAK >NUL

ECHO [LIVE] Opening Stage B window...

START "V3D-StageB-HMMWatchdog" cmd /k python %STAGE_B% --live --symbol BOTH --interval %INTERVAL%

ECHO.
ECHO ============================================================
ECHO  LIVE MODE ACTIVE
ECHO  Two windows are now running - one for each stage.
ECHO  Leave them open during market hours.
ECHO  Close them when done trading for the day.
ECHO ============================================================
EXIT /B 0
