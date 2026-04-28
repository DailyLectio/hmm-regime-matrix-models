# Operator Start / EOD Checklist - V3C and V3D

Use this while you are running both systems manually.

## Key Idea

You only need to double-click the short one-click command files.

For V3C:

- Morning: `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_START.bat`
- EOD: `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_EOD.bat`

For V3D:

- Morning: `C:\Users\Valued Customer\NT8_Regimes\V3D\Keys\V3D_START.bat`
- EOD: `C:\Users\Valued Customer\NT8_Regimes\V3D\Keys\V3D_EOD.bat`

The longer master files are called automatically by those one-click files:

- `V3C_START.bat` calls `V3C_PreMarket_Master.bat`
- `V3C_EOD.bat` calls `V3C_EndOfDay_Shutdown.bat`
- `V3D_START.bat` calls `V3D_PreMarket_Master.bat`
- `V3D_EOD.bat` calls `V3D_EndOfDay_Shutdown.bat`

## Morning Startup - 9:15 AM ET

- [ ] Confirm NinjaTrader is running and live export is active.
- [ ] Double-click `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_START.bat`.
- [ ] Wait for the V3C startup window to finish its 60-second check.
- [ ] Confirm the V3C windows are open:
  - [ ] V3C ModelFeed Watchdog
  - [ ] V3C Regime Matrix Supervisor
- [ ] Double-click `C:\Users\Valued Customer\NT8_Regimes\V3D\Keys\V3D_START.bat`.
- [ ] Wait for the V3D startup window to finish its 60-second check.
- [ ] Confirm the V3D windows are open:
  - [ ] V3D Stage A MacroRegime
  - [ ] V3D Stage B HMMWatchdog
  - [ ] V3D Stage C Supervisor
- [ ] Confirm V3C output files are updating:
  - [ ] `V3C\NQ_Regimes_V3C_Latest.csv`
  - [ ] `V3C\ES_Regimes_V3C_Latest.csv`
- [ ] Confirm V3D output files are updating:
  - [ ] `V3D\NQ_RegimeMatrix_Latest.csv`
  - [ ] `V3D\ES_RegimeMatrix_Latest.csv`
- [ ] Open or refresh the NinjaTrader charts.
- [ ] Confirm the V3C HUD is fresh.
- [ ] Confirm the V3D HUD is fresh if using it.
- [ ] Leave all live command windows open during market hours.

## During Market Hours

- [ ] Do not close the V3C watchdog or supervisor windows.
- [ ] Do not close the V3D Stage A, Stage B, or Stage C windows.
- [ ] If a HUD shows stale, first check whether the matching command windows are still open.
- [ ] If a HUD shows blocked/wait but fresh, treat it as a regime/permission state, not a data failure.

## End Of Day - 4:10 PM ET

- [ ] Confirm trading is finished and no strategy needs the live feed.
- [ ] Double-click `C:\Users\Valued Customer\NT8_Regimes\V3D\Keys\V3D_EOD.bat`.
- [ ] Wait for V3D shutdown/report/archive to complete.
- [ ] Confirm the V3D report was created in `V3D\Reports`.
- [ ] Double-click `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_EOD.bat`.
- [ ] Wait for V3C shutdown/report/archive to complete.
- [ ] Confirm the V3C report was created in `V3C\Reports`.
- [ ] Confirm the live command windows have closed or stopped.
- [ ] Review daily reports if needed.

## Does Order Matter?

Morning order is not strict, but use this order for consistency:

1. Start V3C.
2. Start V3D.
3. Refresh NinjaTrader charts.
4. Confirm HUD freshness.

End-of-day order is not strict either, but use this order for consistency:

1. Shut down V3D.
2. Shut down V3C.
3. Review reports.

Do not double-click the longer master files if you already used the short one-click files. The short files already call the longer files.
