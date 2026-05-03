# V3C Regime Matrix Launch Instructions

Use these batch files for the V3C HUD:

1. `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_START.bat`

Or, for the individual windows:

1. `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\Start_V3C_ModelFeed_Watchdog.bat`
2. `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\Start_RegimeMatrixSupervisor.bat`

The V3C HUD should read from:

`C:\Users\Valued Customer\NT8_Regimes\V3C`

Expected active V3C files:

- `C:\Users\Valued Customer\NT8_Regimes\V3C\NQ_Regimes_V3C_Latest.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3C\ES_Regimes_V3C_Latest.csv`

The root-level launchers below are the older lane and macro engines. They still update files under `C:\Users\Valued Customer\NT8_Regimes\Active`, but those `Active` files are not the final V3C HUD files:

- `C:\Users\Valued Customer\NT8_Regimes\Start_Macro_Regimes.bat`
- `C:\Users\Valued Customer\NT8_Regimes\Start_Trading_Engines_HMM.bat`

NinjaTrader HUD settings:

- Indicator: `Regime Matrix HUD V3C`
- Data Folder Path: `C:\Users\Valued Customer\NT8_Regimes\V3C`
- Use Leader Symbol Mapping: `True`
- Debug Prints: `True` only while confirming file reads, then set back to `False`
