# HMM Regime Matrix Models

Separate backup repository for the Python/HMM Regime Matrix model system that works alongside the NinjaTrader 8 V3C/V3D indicators and strategies.

This repo is intentionally separate from `DailyLectio/nt8-custom-backup`. The NT8 backup protects the broader NinjaScript and template tree. This repo protects the model-side Python code, HMM artifacts, V3B/V3C/V3D regime documents, selected live model outputs, and the NT8 bridge files that directly support the model.

## Source Folders

- `C:\Users\Valued Customer\NT8_Regimes`
- `C:\Users\Valued Customer\Documents\NinjaTrader 8`

## Mirrored Layout

- `NT8_Regimes/` - curated mirror of the local model system.
- `NinjaTrader8/bin/Custom/Indicators/` - model-related NT8 indicators/exporters.
- `NinjaTrader8/bin/Custom/Strategies/` - model-related NT8 strategies.
- `NinjaTrader8/templates/Strategy/` - model-related NT8 strategy templates.
- `scripts/sync_backup.ps1` - refreshes the mirror from the live folders.
- `scripts/backup_and_push.ps1` - refreshes, commits changes, and pushes to GitHub.

## Backup Policy

Included by default:

- Python source files.
- PowerShell and batch launch scripts.
- Markdown/text architecture and run documents.
- V3B, V3C, and V3D model folders, excluding generated noise.
- Small serialized HMM model artifacts such as `.joblib`.
- Model-related NT8 `.cs` indicators/strategies.
- Model-related NT8 strategy template XML files.

Excluded by default:

- Virtual environments and Python caches.
- Raw market data exports and stitched continuous data dumps.
- Backtest output folders and Strategy Analyzer output.
- Runtime logs, trade logs, override logs, reports, zips, shortcuts, and browser-export folders.
- `.env`, key/certificate files, token/credential files, and other local secret-style files.

Run `scripts\backup_and_push.ps1` to manually trigger the same backup flow used by the scheduled task.
