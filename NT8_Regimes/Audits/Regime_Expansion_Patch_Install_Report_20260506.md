# Regime Expansion Patch Install Report

Date: 2026-05-06

## Installed Files

- `C:\Users\Valued Customer\NT8_Regimes\V3D\Scripts\MacroRegimeBuilder_V3D.py`
- `C:\Users\Valued Customer\NT8_Regimes\Scripts\MacroRegimeBuilder_V3D.py`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\Scripts\RegimeSupervisor_V3D.py`
- `C:\Users\Valued Customer\NT8_Regimes\Scripts\RegimeSupervisor_V3D.py`
- `C:\Users\Valued Customer\NT8_Regimes\V3C\Scripts\RegimeMatrixSupervisor.py`
- `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\TradeLogExporter_V3D.cs`
- `C:\Users\Valued Customer\NT8_Regimes\V3D\NinjaTrader\TradeLogExporter_V3D.cs`

## Backup Folder

`C:\Users\Valued Customer\NT8_Regimes\Audits\Backups_Regime_Expansion_Patch_20260506_123025`

## Important Adjustment Made During Install

The delivered `TradeLogExporter_V3D_PATCHED.cs` contained two NinjaScript generated-code regions. Both declared `cacheTradeLogExporter_V3D`, which would cause a duplicate-definition compile error in NT8. The stale parameterless generated block was removed. The remaining generated block includes the new `LeaderSymbolOverride` parameter.

## Validation

- Python syntax compile passed for all installed Python scripts.
- V3D Stage A `--help` loaded cleanly.
- V3D Stage C `--help` loaded cleanly.
- V3C supervisor passed Python syntax compile. It was not run in help mode because the script does not expose normal help-only behavior and timed out during a non-mutating help check.
- `TradeLogExporter_V3D.cs` brace balance passed.
- `TradeLogExporter_V3D.cs` indicator body compiled cleanly against local NT8 assemblies in a standalone smoke test.
- Full NT8 project compile was not possible from command line: this machine has only the .NET runtime, not the SDK required by the SDK-style `NinjaTrader.Custom.csproj`. Final compile still needs NinjaTrader F5/Compile.

## Restart / Compile Notes

- Restart Stage A and Stage C V3D processes so the patched Python files are loaded.
- Restart V3C supervisor if it is running.
- Compile in NinjaTrader 8 with F5.
- Re-add or refresh `TradeLogExporter_V3D` indicators after compile so the new `LeaderSymbolOverride` parameter is visible.
