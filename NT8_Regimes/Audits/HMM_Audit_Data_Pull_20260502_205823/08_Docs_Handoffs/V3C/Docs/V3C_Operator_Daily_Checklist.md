# V3C Operator Daily Checklist

## Premarket

- Run `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_START.bat`.
- Confirm `V3C ModelFeed Watchdog` is open and printing `Lookback=100 days`.
- Confirm `V3C Regime Matrix Supervisor` is open.
- Confirm these files are updating:
  - `C:\Users\Valued Customer\NT8_Regimes\V3C\ES_Regimes_V3C_Latest.csv`
  - `C:\Users\Valued Customer\NT8_Regimes\V3C\NQ_Regimes_V3C_Latest.csv`
- On each ES/NQ chart family, load `Regime Matrix HUD V3C`.
- HUD settings:
  - `Data Folder Path = C:\Users\Valued Customer\NT8_Regimes\V3C`
  - `Use Leader Symbol Mapping = True`
  - `Debug Prints = False` after confirming fresh.

## RTH Arming Plan

- `09:25-09:35 ET`: observe only.
- First arm pass: one simple Momo V3C template per instrument.
- Avoid arming everything at once.
- Rotation-only lanes should wait for clear HUD support, such as `ROTATION_LIQUID` and `SNIPER: ON`.
- Treat `BLOCKED / WAIT` with `V3C FILE: FRESH` as a model/playbook block, not a data failure.

## End Of Day

- Run `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_EOD.bat`.
- Confirm the report appears in:
  - `C:\Users\Valued Customer\NT8_Regimes\V3C\Reports`
- Confirm archives appear in:
  - `C:\Users\Valued Customer\NT8_Regimes\V3C\History`
