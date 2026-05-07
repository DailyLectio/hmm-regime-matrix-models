# Stage 1 Trade Logging / EOD and EOW Export Runbook

Updated: 2026-05-02

## Compile Clarification

The Python and batch-file changes do not need NinjaTrader compilation.

The NT8 strategy changes do need one successful NinjaScript compile before the new Stage 1 raw trade-close logging runs inside NinjaTrader. Closing NT8 without saving the workspace does not undo these source-file edits because they are saved directly in:

`C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies`

Next NT8 step:

1. Open NinjaTrader 8.
2. Open NinjaScript Editor.
3. Press Compile.
4. If compile succeeds, no workspace save is required just for these source-file edits.
5. If compile errors appear, capture the file/line rows from the NinjaScript Editor error grid.

Last Codex compile attempt note: Codex invoked the NinjaScript Editor compile button, but `NinjaTrader.Custom.dll` did not show a fresh timestamp afterward, so treat the compile as not confirmed.

## Strategy Files Already Updated

These active NT8 strategy files received Stage 1 raw trade-close logging and initial-stop capture:

| Family | File |
| :-- | :-- |
| V3D | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\ExpansionV3D.cs` |
| V3D | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\MomentumV3D.cs` |
| V3D | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\FaderV3D.cs` |
| V3D | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\SniperV3D.cs` |
| V3D | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\ADXDIV3D.cs` |
| V1A | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\KalmanPulseFader.cs` |
| V1B | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\KalmanPulse_Fader_V1B.cs` |
| OG | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\Pine.cs` |
| OG | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\Momo.cs` |
| OG | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\ADXX.cs` |
| OG | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\ADXDI.cs` |
| OG | `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\MomentumSlopeOG.cs` |

V3C strategy files were not modified.

Original backups:

`C:\Users\Valued Customer\NT8_Regimes\Archive\Stage1TradeLogBackup_20260502-133141`

## Stage 1 Raw Log Outputs

After each updated strategy closes a trade, it writes a per-bot CSV under one of these folders:

| Family | Folder |
| :-- | :-- |
| V1A | `C:\Users\Valued Customer\NT8_Regimes\V1A\TradeLog` |
| V1B | `C:\Users\Valued Customer\NT8_Regimes\V1B\TradeLog` |
| V3D | `C:\Users\Valued Customer\NT8_Regimes\V3D\TradeLog` |
| OG | `C:\Users\Valued Customer\NT8_Regimes\OG\TradeLog` |

Raw Stage 1 fields include:

`trade_date, entry_time, exit_time, model_version, account, strategy_name, bot_name, ab_mode, symbol, instrument, direction, contracts, entry_price, exit_price, gross_pnl, net_pnl, ticks, win_loss, exit_reason, initial_stop_price, initial_stop_distance, export_timestamp`

`initial_stop_distance` is total initial position risk in dollars:

`abs(entry_price - initial_stop_price) * point_value * contracts`

## Export Scripts Updated

| Purpose | File |
| :-- | :-- |
| Unified CSV export and enrichment | `C:\Users\Valued Customer\NT8_Regimes\Scripts\eod_export.py` |
| Daily / EOW markdown reports | `C:\Users\Valued Customer\NT8_Regimes\Scripts\trade_performance_report.py` |

Exporter coverage:

- Reads current combined logs and strategy-owned `*_TradeLog.csv` files.
- Discovers logs from `V1A`, `V1B`, `V3C`, and `OG`.
- For `V3D`, prefers `V3D\TradeLog\V3D_INTERNAL_TradeLog.csv`, then clean `SimV3D_*_TradeLog.csv` per-account files. The old `V3D_TradeLog.csv` is skipped as legacy/contaminated unless it has been intentionally archived and regenerated.
- Adds `initial_stop_price`, `initial_stop_distance`, and `r_multiple`.
- Writes model-specific history files and master unified files.
- Deduplicates repeated trade rows by trade signature and keeps the row with the richest Stage 1 fields.
- Preserves raw model labels when the account registry is weak or unknown, and preserves raw `OG` labels from OG strategy files.

## Daily Export Steps

One-click path:

`C:\Users\Valued Customer\NT8_Regimes\Master_Keys\ALL_MODELS_EXPORT.bat`

This runs:

1. `Scripts\eod_export.py --date today`
2. `Scripts\trade_performance_report.py --mode daily --date today`

Daily output paths:

| Output | Path |
| :-- | :-- |
| Master daily CSV | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_YYYYMMDD.csv` |
| Data quality report | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\DataQuality_Report_YYYYMMDD.txt` |
| Daily markdown review | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\Daily_Trade_Performance_YYYYMMDD.md` |
| V1A model file | `C:\Users\Valued Customer\NT8_Regimes\V1A\History\V1A_TradeLog_YYYYMMDD.csv` |
| V1B model file | `C:\Users\Valued Customer\NT8_Regimes\V1B\History\V1B_TradeLog_YYYYMMDD.csv` |
| V3C model file | `C:\Users\Valued Customer\NT8_Regimes\V3C\History\V3C_TradeLog_YYYYMMDD.csv` |
| V3D model file | `C:\Users\Valued Customer\NT8_Regimes\V3D\History\V3D_TradeLog_YYYYMMDD.csv` |
| OG model file | `C:\Users\Valued Customer\NT8_Regimes\OG\History\OG_TradeLog_YYYYMMDD.csv` |

## End-of-Week Export Steps

One-click path:

`C:\Users\Valued Customer\NT8_Regimes\Master_Keys\ALL_MODELS_EOW_EXPORT.bat`

This runs:

1. `Scripts\eod_export.py --date all`
2. `Scripts\trade_performance_report.py --mode weekly --week-ending auto`

Weekly output paths:

| Output | Path |
| :-- | :-- |
| Master all-history CSV | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_ALL.csv` |
| Weekly markdown review | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\EOW_Trade_Performance_YYYYMMDD.md` |
| All-history data quality report | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\DataQuality_Report_ALL.txt` |
| Model all-history files | `C:\Users\Valued Customer\NT8_Regimes\<MODEL>\History\<MODEL>_TradeLog_ALL.csv` |

`--week-ending auto` uses the latest Friday as the week-ending date.

## Performance Review Inputs

Use these files as the main inputs for daily and weekly review:

1. Daily master: `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_YYYYMMDD.csv`
2. Daily markdown: `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\Daily_Trade_Performance_YYYYMMDD.md`
3. Weekly master: `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_ALL.csv`
4. Weekly markdown: `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\EOW_Trade_Performance_YYYYMMDD.md`
5. Model-specific history: `C:\Users\Valued Customer\NT8_Regimes\<MODEL>\History`

## OG Candidates To Confirm Before Additional Strategy Updates

Already updated as OG:

- `Pine.cs`
- `Momo.cs`
- `ADXX.cs`
- `ADXDI.cs`
- `MomentumSlopeOG.cs`

New OG candidates from the image and your note, not yet updated:

- `AdxDiCrossBracketOG.cs`
- `@@AdxDiCrossOG.cs`
- `AdxDiCrossStrategyPineTrail.cs`
- `MomentumHA_Scalp_1m.cs`
- `MomentumExpansion_5m.cs`
- `MomentumRange_RangeBar.cs`
- `V3ExpansionRider.cs`
- `V3ValueFader.cs`
- `V3CompressionSniper.cs`

Possible candidates visible in the image, but needing confirmation before OG treatment:

- `CompositeEdgeMomentum.cs`
- `CompositeEdge_Momentum_V1B.cs`
- `VolStateFader.cs`
- `VolStateFaderV1B.cs`

Likely excluded unless you say otherwise:

- V3C files, because V3C already has a working Stage 1 write.
- V3D B/C variant files, unless you want those variants to receive the same Stage 1 logging patch.
