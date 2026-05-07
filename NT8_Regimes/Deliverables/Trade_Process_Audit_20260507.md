# Trade Process Audit - 2026-05-07

## Operator Flow

Current daily use is now two clicks:

1. `C:\Users\Valued Customer\NT8_Regimes\Master_Keys\START_ALL_MODELS.bat`
2. `C:\Users\Valued Customer\NT8_Regimes\Master_Keys\EOD_ALL_MODELS.bat`

The prior multi-click files were archived to:

`C:\Users\Valued Customer\NT8_Regimes\Archive\Master_Keys_Simplified_20260507_161245`

## Start Flow

`START_ALL_MODELS.bat`:

- Generates previous-business-day V3C and V3D reports.
- Stops duplicate V3C and V3D live Python processes.
- Starts V3C ModelFeed Watchdog.
- Starts V3C Regime Matrix Supervisor.
- Starts V3D Stage A MacroRegime.
- Starts V3D Stage B HMMWatchdog.
- Starts V3D Stage C RegimeSupervisor.
- Checks the current V3C/V3D latest output files.

## EOD Flow

`EOD_ALL_MODELS.bat`:

- Stops V3C and V3D live Python processes.
- Generates and archives today's V3C report.
- Generates and archives today's V3D report.
- Runs V3C vs V3D comparison and V3D trade enrichment.
- Runs `Scripts\eod_export.py --date today`.
- Runs `Scripts\trade_performance_report.py --mode daily --date today`.
- On Fridays only, also runs the all-history export and weekly report.

## Trade Source Policy

V3D trade export is strategy-owned through `V3DStrategyTradeLogger.cs`.

V3D read priority for EOD/export scripts:

1. `V3D\TradeLog\V3D_INTERNAL_TradeLog.csv`
2. `V3D\TradeLog\SimV3D*_TradeLog.csv`

The legacy chart-exporter file `V3D\TradeLog\V3D_TradeLog.csv` is skipped by default and should be treated as contaminated unless archived and intentionally regenerated.

## Current Export Logic

- `Scripts\eod_export.py` discovers V1A, V1B, V3C, OG, and clean V3D logs.
- `V3D\Scripts\V3D_Regime_Comparison.py` uses the same clean V3D source policy.
- `Scripts\trade_performance_report.py` reads the unified outputs only, so it inherits the clean source policy from `eod_export.py`.
- `TradeLogExporter_V3D.cs` remains only as a guarded legacy chart-level exporter and blocks non-SimV3D accounts.
- `LiveDataExporter.cs` is not a trade exporter.

## Testing Status

- Python syntax check passed for:
  - `Scripts\eod_export.py`
  - `V3D\Scripts\V3D_Regime_Comparison.py`
- Clean V3D source discovery currently finds no `V3D_INTERNAL_TradeLog.csv` or `SimV3D*_TradeLog.csv` data rows yet, which matches the pending first V3D test trade.
- Existing `V3D_TradeLog.csv` is detected but skipped by policy.
