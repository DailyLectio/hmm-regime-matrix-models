# Backup Manifest

Last reviewed: 2026-04-28

## Included Sources

### `C:\Users\Valued Customer\NT8_Regimes`

The sync keeps the model development surface, including:

- Root model launch scripts and operator notes.
- `Docs`, `History`, `MacroRegime`, `Scripts`, `Stitcher` source code, `V3B`, `V3C`, and `V3D`.
- V3C/V3D Python scripts, docs, keys/launchers, small model artifacts, current `Latest` CSVs, and retained V3B backup material.

The sync excludes raw market data, large exports, large backtests, full-history regime CSVs, model-feed history CSVs, logs, trade logs, generated reports, cache folders, zip packages, shortcuts, and browser-export folders.

### `C:\Users\Valued Customer\Documents\NinjaTrader 8`

The sync copies only model-related files from:

- `bin\Custom\Indicators`
- `bin\Custom\Strategies`
- `templates\Strategy`

Matching terms are: `V3B`, `V3C`, `V3D`, `Regime`, `HMM`, `TradeLog`, `Matrix`, `LiveDataExporter`, and `ValueAreaExporter`.

## Safety Notes

- Large raw/export files around 50-54 MB were found under `Exports`, `MacroRegime\data\raw`, and `Stitcher`; those are excluded.
- Generated full-history CSVs in `Active`, `V3C\ModelFeed`, and `V3D\History` were also excluded to prevent noisy scheduled commits.
- NT8 strategy templates contain `ConnectionLossHandling` and account type metadata, but the scan did not identify literal password/API-token fields in the matched templates.
- Historical trade/performance CSVs use account-related column names and are treated as generated/account-adjacent output, so they are excluded.

## GitHub Remote

- `https://github.com/DailyLectio/hmm-regime-matrix-models.git`
