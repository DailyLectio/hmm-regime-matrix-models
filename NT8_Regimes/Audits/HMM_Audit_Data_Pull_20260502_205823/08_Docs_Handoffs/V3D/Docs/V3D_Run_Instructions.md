# V3D Manual Run Instructions

Manual mode is recommended for the first few V3D sessions.

## Morning Startup

Double-click:

`C:\Users\Valued Customer\NT8_Regimes\V3D\Keys\V3D_START.bat`

This runs `V3D_PreMarket_Master.bat`, which:

1. Checks the V3D folders and scripts.
2. Generates the previous business day report.
3. Stops duplicate V3D live processes.
4. Starts the three live windows:
   - Stage A MacroRegime
   - Stage B HMMWatchdog
   - Stage C RegimeSupervisor
5. Waits 60 seconds.
6. Confirms the current V3D output files.

Leave the three V3D command windows open during market hours.

## End Of Day

Double-click:

`C:\Users\Valued Customer\NT8_Regimes\V3D\Keys\V3D_EOD.bat`

This runs `V3D_EndOfDay_Shutdown.bat`, which:

1. Stops the V3D live pipeline.
2. Generates today's daily regime report.
3. Archives the latest, history, macro, and HMM files.
4. Prints the final output timestamps.

## Active V3D Output Files

These stay in the root V3D folder:

- `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_RegimeMatrix_Latest.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\ES_RegimeMatrix_Latest.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_Macro_Regimes_V3D.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\ES_Macro_Regimes_V3D.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_HMM_Regimes_V3D.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\ES_HMM_Regimes_V3D.csv`

## Reports

Reports are written to:

`C:\Users\Valued Customer\NT8_Regimes\V3D\Reports`

End-of-day archives are written to:

`C:\Users\Valued Customer\NT8_Regimes\V3D\History\Archives`

## Scheduling

The `Install_V3D_Scheduled_Tasks.bat` file is intentionally a placeholder for now. After a few clean manual sessions, use Task Scheduler for:

- 09:15 ET Monday-Friday: `V3D_START.bat`
- 16:05 ET Monday-Friday: `V3D_EOD.bat`
