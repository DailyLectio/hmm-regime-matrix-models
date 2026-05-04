# HUD Pipeline Status Upgrade - EOD Compile Notes

Prepared: 2026-05-04

## Status

Source updates are prepared and staged. NinjaTrader compile/refresh is intentionally deferred until EOD because the V3C and V3D HUDs are live.

## Files Updated

Installed NinjaTrader indicator files:

- `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\RegimeMatrixHUDV3D.cs`
- `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\RegimeMatrixHUDV3C.cs`
- `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\PipelineMonitorV1A.cs`

Mirrored regime source/archive files:

- `C:\Users\Valued Customer\NT8_Regimes\V3D\NinjaTrader\RegimeMatrixHUD_V3D.cs`
- `C:\Users\Valued Customer\NT8_Regimes\V3C\NT files\RegimeMatrixHUD_V3C.cs`
- `C:\Users\Valued Customer\NT8_Regimes\V1A\NinjaTrader\PipelineMonitor_V1A.cs`

Backups created before editing:

- `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\RegimeMatrixHUDV3D.pre_hud_upgrade_*.bak`
- `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\RegimeMatrixHUDV3C.pre_hud_upgrade_*.bak`

## V3D HUD Additions

- Adds display fields for:
  - `AsymHysteresisGateOpen`
  - `AsymHysteresisReason`
  - `AsymHysteresisEnabled`
  - `HMMStateAgeBars`
  - `LabelAmbiguousFit`
  - `LabelVwapSeparation`
- Adds a new HUD row:
  - `GATE: OPEN/BLOCKED/DISABLED`
  - `HMM AGE: N bars`
  - `HMM DRIFT: OK/WARN`
  - hysteresis reason text
- Reads V3D `LabelAmbiguousFit` from:
  - `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_HMM_Regimes_V3D.csv`
  - `C:\Users\Valued Customer\NT8_Regimes\V3D\ES_HMM_Regimes_V3D.csv`

## V3C HUD Additions

- Adds a compact pipeline row:
  - `PIPELINE: 1M OK/STALE | DATA FRESH/STALE`
- Adds a gate row:
  - `GATE: OPEN/BLOCKED/DISABLED/SCHEMA?`
  - `HMM AGE: N bars`
  - hysteresis reason text
- V3C `LabelAmbiguousFit` is intentionally omitted for now because the current V3C HMM CSV does not include that column.

## New V1A Monitor

Adds `PipelineMonitor_V1A`, a lightweight load-once indicator for V1A/V1B infrastructure health.

Checks:

- `Exports\NQ_1min_export.txt`
- `Exports\ValueArea_NQ.csv`
- `Active\Footprint_Export.csv`
- `HUDMessenger.CurrentDailyBias`
- latest file in `V1A\TradeLog`

Load location:

- Add once to the V1A 15 Range Volumetric chart or another stable V1A leader/support chart.
- Do not add to every V1A strategy tab.

## EOD Compile Steps

1. Confirm all strategies/HUDs are shut down or safe to refresh.
2. In NinjaTrader, open NinjaScript Editor.
3. Compile indicators.
4. If compile succeeds, refresh/re-add:
   - `RegimeMatrixHUD_V3D` on V3D NQ leader chart.
   - `RegimeMatrixHUD_V3C` on V3C NQ leader chart.
   - `PipelineMonitor_V1A` once on the V1A support/leader chart.
5. Confirm new HUD rows appear.
6. Confirm V3C/V3D strategy tabs still see their one leader HUD instance.

## Acceptance Checks

- V3D HUD shows gate/hysteresis row and HMM drift status.
- V3C HUD shows pipeline row and gate/hysteresis row.
- V1A monitor loads and shows live feed, value area, footprint, bias, and trade log status.
- No strategy chart has duplicate support exporters added.
- No NinjaTrader compile errors.
