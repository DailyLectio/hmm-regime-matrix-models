# HMM Audit Data Pull

Generated: 2026-05-02 20:58:35 -04:00
Workspace: C:\Users\Valued Customer\NT8_Regimes

## What Is Included

- Regime matrices: V3D latest/history, Backtest Full, and SHADOW files for NQ and ES.
- HMM and macro outputs: current V3D, V3C model feed, Active legacy outputs, and archived snapshots.
- Trade outcomes: unified V1A/V1B/V3C/V3D trade logs, V3D enriched trade log, daily/weekly performance summaries, and data-quality reports.
- Gate evidence: V3D Stage A/B/C logs, regime reports, HUD override log, and matrix permission/reason-code columns.
- Raw inputs: NQ/ES 1-minute exports, older archive exports, value-area exports, and raw-data manifests/audits.
- Footprint evidence: Active\Footprint_Export.csv plus older source/docs that reference DEIA/EEMDF/SIB/DEB/PAR/ABS/TF/DT handling.
- OG baseline evidence: Strategy Analyzer exports, archived performance-bot CSVs, OG candidate list, and OG source snapshots.
- Source/docs: V3D/V3C/V1A/V1B code and handoff/architecture docs.

## Fast Read On Coverage

- Unified trade log has regime-at-entry fields: entry_regime, entry_macro, entry_hmm, entry_phase, entry_confidence, entry_reason_code.
- V3D enriched trade log has entry and exit regime fields and is the strongest trade-outcome file for cross-tabs.
- RegimeMatrix files have bot permission flags, size percentages, ReasonCode, BlockedReason, and BotPermissionSummary where available.
- Raw exports cover NQ and ES from 2023-06-01 through 2026-05-01 in the current Exports folder.
- Active\Footprint_Export.csv is present but currently has only the header row, so it does not provide populated footprint history.
- The OG folder structure exists but contains no files; OG evidence is pulled from Strategy Analyzer exports, archived performance CSVs, and Stage1 OG backups.

## Known Caveats

- V3D history matrices appear to contain repeated final live rows; de-duplicate by session_key/TimestampET before longitudinal statistics.
- Current raw 1-minute exports also repeat the final 2026-05-01 16:59 row at the tail; de-duplicate before feature re-derivation.
- Stage C logs show processing cycles and regime distributions, but I did not find a separate per-event gate-open/gate-close audit trail beyond matrix permission columns, reason fields, reports, and override log.
- The unified all-model weekly report flags 24 UNMAPPED_ACCOUNT rows and 1 row with UNMAPPED_ACCOUNT;MISSING_EXITREASON.

See MANIFEST.csv for the full file list, row counts, first/header line, source path, copied path, and notes.
