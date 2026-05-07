# Model Indicator Taxonomy - 2026-05-07

Source inputs:
- `C:\Users\Valued Customer\Downloads\May 7 2026 strategy list.csv`
- Active NinjaTrader folders:
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators`
  - `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies`

## V3D Strategy Export Architecture

V3D trade export is now strategy-owned. Each V3D strategy has editable settings:
- `AccountNameFilter`: baked SimV3D account allow-list for that strategy class.
- `ConfiguredStrategyName`: baked exported strategy identity.
- `TradeLogFolder`: default `C:\Users\Valued Customer\NT8_Regimes\V3D\TradeLog`.

The helper `V3DStrategyTradeLogger.cs` writes:
- Per-account clean logs: `V3D\TradeLog\SimV3D_*_TradeLog.csv`
- Clean internal aggregate: `V3D\TradeLog\V3D_INTERNAL_TradeLog.csv`

The legacy chart indicator `Trade Log Exporter (V3D)` is not required for V3D strategy fills. If it remains on any chart, it now defaults to a SimV3D-only account allow-list and blocks V3C accounts.

## V3D Strategy Account Map

| Strategy tab | Baked V3D account(s) | Internal bot name | AB mode |
|---|---|---|---|
| Expansion_V3D / Expansion_V3D ES | SimV3D-NQ-1A; SimV3D-ES-1A | V3D_Expansion_A | A |
| Expansion_V3D_B / Expansion_V3D_B ES | SimV3D-NQ-1B; SimV3D-ES-2B | V3D_Expansion_B | B |
| Momentum_V3D / Momentum_V3D ES | SimV3D-NQ-2A; SimV3D-ES-2A | V3D_Momentum_A | A |
| Momentum_V3D_B | SimV3D-NQ-2B | V3D_Momentum_B | B |
| Fader_V3D A | SimV3D-NQ-3A; SimV3D-ES-3A | V3D_Fader_A | A |
| Fader_V3D_B | SimV3D-NQ-3B | V3D_Fader_B | B |
| Sniper_V3D | SimV3D-NQ-4A; SimV3D-ES-4A | V3D_Sniper_A | A |
| Sniper_V3D_B | SimV3D-NQ-4B | V3D_Sniper_B | B |
| ADX_DI_V3D / ADX_DI_V3D ES | SimV3D-NQ-5A; SimV3D-NQ-5B; SimV3D-ES-5A | V3D_ADX_DI_A | A |
| ADX_DI_V3D_C | SimV3D-NQ-5C | V3D_ADX_DI_C | C |

## Indicator Ownership

| Indicator/helper | Model ownership | Purpose | Use on V3C charts? |
|---|---|---|---|
| `V3DStrategyTradeLogger.cs` | V3D only | Internal strategy-owned V3D trade logging helper. Not a chart indicator. | No |
| `RegimeMatrixHUDV3D.cs` | V3D only | V3D HUD and safety interlock reading V3D latest/macro/HMM files. | No |
| `TradeLogExporter_V3D.cs` | V3D legacy only | Legacy chart-level V3D trade exporter to `V3D_TradeLog.csv`; now SimV3D account-filtered. Prefer internal strategy export. | No |
| `@@TradeLogExporterV3D.cs` | V3D legacy placeholder only | No production export logic. | No |
| `ValueAreaExporter.cs` | V3D data feed | Writes prior-day Value Area data for Python Stage A. | No unless explicitly shared by an approved runbook |
| `ValueAreaBackfillReporter.cs` | V3D data maintenance | Backfills Value Area rows from loaded chart history. | No |
| `RegimeMatrixHUDV3C.cs` | V3C only | V3C HUD and safety state for V3C strategies. | Yes, V3C only |
| `V3CTradeLogger.cs` | V3C only | Internal V3C trade logging helper. Not a chart indicator. | Yes, helper only |
| `TradeLogExporterV1AB.cs` | V1A/V1B only | Chart-level trade logger for V1A/V1B tabs. Requires exact `AccountNameFilter` and `ModelVersion`. | No |
| `LiveDataExporter.cs` | Shared V1A/V1B/V3C/V3D data feed | Writes `Exports\NQ_1min_export.txt` and `Exports\ES_1min_export.txt`. This is not a trade exporter and cannot write V3D trade rows. | Yes, when the shared 1-minute feed is required |
| `@@LiveRegimeExporter.cs` | Legacy/shared research only | Writes `Live_*_Data.txt` under the NT8 user folder for older HMM tests. Not production V3C/V3D trade export. | Avoid unless deliberately testing legacy HMM feed |

## V3C Specific Warning

The May 7 strategy list shows:

`NQ.ADX.DI.5m.V3C - 5A` has `AccountNameFilter = NQ.ADX.DI.5m.V3C - 5A`.

That is the strategy/tab name, not the account. It must be changed in NT8 strategy settings to:

`SimV3C-NQ-5A`

Until that is changed in the active NT8 workspace, that tab may fail to log correctly through the V3C internal logger.

## Handoff Items

1. Compile NinjaScript when workspaces are ready. Marked done by operator on 2026-05-07.
2. In NT8, remove any chart indicator named `Trade Log Exporter (V3D)`, `TradeLogExporter_V3D`, or `TradeLogExporterV3D` from V3C and Trade Screen charts.
3. Fix the V3C 5A strategy setting: `AccountNameFilter = SimV3C-NQ-5A`. Marked done by operator on 2026-05-07.
4. After first V3D fills post-compile, verify clean rows appear in:
   - `V3D\TradeLog\SimV3D_*_TradeLog.csv`
   - `V3D\TradeLog\V3D_INTERNAL_TradeLog.csv`
5. EOD/export scripts updated on 2026-05-07 to prefer `V3D_INTERNAL_TradeLog.csv`, then clean `SimV3D_*_TradeLog.csv`; `V3D_TradeLog.csv` is skipped as legacy/contaminated.
6. Investigate the DEMO1419193 duplicate path in the Trade Screen workspace. The code pass cannot remove live workspace indicator instances.
