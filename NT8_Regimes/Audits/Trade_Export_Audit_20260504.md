# Trade Export Audit - 2026-05-04

## Completed Repairs

- Refreshed `C:\Users\Valued Customer\NT8_Regimes\accounts_registry.json` from the current master CSV:
  - `C:\Users\Valued Customer\Downloads\Master Accounts Registry 05-04-2026 - Sheet1 (1).csv`
- Patched `C:\Users\Valued Customer\NT8_Regimes\Scripts\eod_export.py` so the live batch launcher now uses:
  - clear missing-registry error text
  - contamination guard based on the account registry
  - EXCLUDE account filtering
  - trade-log discovery diagnostics
  - account-name normalization for V1 account aliases with stray hyphen spacing
- Deployed `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\V3CTradeLogger.cs`.
- Verified the four live V3C strategy files in `Custom\Strategies` already match the delivered audit copies by hash:
  - `ADXDIV3C.cs`
  - `MomoV3C.cs`
  - `V3_Expansion_Rider_V3C.cs`
  - `V3_Value_Fader_V3C.cs`
- Patched `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\V3_Compression_Sniper_V3C.cs` with the missing Stage 1 logger integration.

## Registry Refresh - 2026-05-04

- Normalized the export registry from the latest master accounts CSV and wrote updated copies to:
  - `C:\Users\Valued Customer\NT8_Regimes\accounts_registry.json`
  - `C:\Users\Valued Customer\NT8_Regimes\Audits\accounts_registry.json`
- Copied the source CSV into the audit package:
  - `C:\Users\Valued Customer\NT8_Regimes\Audits\Master Accounts Registry 05-04-2026 - Sheet1 (1).csv`
- Current merged export-registry count: 41 accounts.
  - 37 active accounts from the master CSV
  - 4 legacy carryforwards retained for export compatibility: `Sim101`, `SimPine2`, `SimADX1`, `DEMO1419193`
- Added the three V3D ES accounts present in the master CSV:
  - `SimV3D-ES-1A`
  - `SimV3D-ES-3A`
  - `SimV3D-ES-4A`
- Applied the corrected Top Middle V3C compression tab names:
  - `SimV3C-NQ-2A` -> `Compression Fast A`
  - `SimV3C-NQ-2B` -> `Compression Clean B`
  - `SimV3C-NQ-2C` -> `Compression Sniper C`
- Applied the corrected 2C template name:
  - `NQ V3C Compression Sniper C 20-40-60`
- Cross-check note: the master CSV still contains the `Trinitiy` typo in the 5B template string. The audit package preserved that raw template text for consistency with the source sheet rather than silently renaming a live NT8 template.
- Cross-check note: `Sim1` is treated as the current active unknown/standalone lane from the master sheet, while legacy `Sim101` was retained as a historical alias for export continuity.

## EOD Run Result

- `python Scripts\eod_export.py --date today`: success
- `python Scripts\trade_performance_report.py --mode daily --date today`: success
- Output files verified:
  - `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_20260504.csv`
  - `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\DataQuality_Report_20260504.txt`
  - `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\Daily_Trade_Performance_20260504.md`

## Final Export Metrics

- Unified rows: 68
- Model breakdown:
  - V3C: 46
  - V1A: 17
  - V1B: 2
  - V3D: 2
  - OG: 1
- Data quality flags:
  - OK: 68
- R-multiple coverage:
  - Covered rows: 33 / 68
  - By model: V3C 21, V1A 9, V1B 1, V3D 1, OG 1

## Remaining Issues

- `C:\Users\Valued Customer\NT8_Regimes\V3C\TradeLog\V3C_TradeLog.csv` is still missing.
- V3C rows in today's unified export were recovered from the contaminated `V3D_TradeLog.csv` using the registry guard, not from a native V3C trade-log file.
- Native V3C compression logging is now patched into `V3_Compression_Sniper_V3C.cs`, but it still requires NT8 runtime verification after the next closed trade on:
  - `SimV3C-NQ-2A`
  - `SimV3C-NQ-2B`
  - `SimV3C-NQ-2C`
- V3D per-bot files remain incomplete:
  - `V3D_Expansion_A_TradeLog.csv`: header only
  - `V3D_Momentum_A_TradeLog.csv`: header only
  - `V3D_Sniper_A_TradeLog.csv`: header only
- NinjaTrader compile/runtime verification is still required. File deployment is complete from this machine, but compile success and first post-close row creation must be confirmed inside NT8.

## Submit For Review / Testing

- Runtime fixes:
  - `C:\Users\Valued Customer\NT8_Regimes\accounts_registry.json`
  - `C:\Users\Valued Customer\NT8_Regimes\Scripts\eod_export.py`
- Audit package refresh:
  - `C:\Users\Valued Customer\NT8_Regimes\Audits\accounts_registry.json`
  - `C:\Users\Valued Customer\NT8_Regimes\Audits\Master Accounts Registry 05-04-2026 - Sheet1 (1).csv`
  - `C:\Users\Valued Customer\NT8_Regimes\Audits\Trade_Export_Audit_20260504.md`
- NT8 deployment files:
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\V3CTradeLogger.cs`
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\ADXDIV3C.cs`
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\MomoV3C.cs`
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\V3_Expansion_Rider_V3C.cs`
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\V3_Value_Fader_V3C.cs`
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\V3_Compression_Sniper_V3C.cs`
- Generated artifacts:
  - `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_20260504.csv`
  - `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\DataQuality_Report_20260504.txt`
  - `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\Daily_Trade_Performance_20260504.md`

## NT8 Operator Follow-Up

- Compile `V3CTradeLogger.cs` first in NinjaScript Editor.
- Compile the five patched V3C strategies after that.
- Set `AccountNameFilter` on every V3C tab and any V3D tab still missing it.
- For the Top Middle compression tabs, use the corrected tab names from the refreshed registry:
  - `Compression Fast A`
  - `Compression Clean B`
  - `Compression Sniper C`
- After the next closed trade, confirm new per-account files appear under `C:\Users\Valued Customer\NT8_Regimes\V3C\TradeLog\`.
