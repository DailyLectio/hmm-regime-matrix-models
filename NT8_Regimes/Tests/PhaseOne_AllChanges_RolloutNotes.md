# Phase One — All Recommended Python Changes: Rollout Notes

**Date: 2026-05-03**
**Covers: Recommended Change #1 (Asymmetric Hysteresis), #2 (V3C Macro Freshness Fix), #3 (V3D HMM Feature Standardization + Label Guard)**

---

## Files Delivered (All Drop-In Replacements)

| File | Replaces | Bytes | Changes included |
|---|---|---|---|
| `RegimeSupervisor_V3D.py` | `C:\...\V3D\Scripts\RegimeSupervisor_V3D.py` | 56,015 | RC#1: Asymmetric hysteresis |
| `RegimeMatrixSupervisor.py` | `C:\...\V3C\Scripts\RegimeMatrixSupervisor.py` | 52,630 | RC#1: Asymmetric hysteresis + RC#2: Macro freshness fix |
| `HMMWatchdog_V3D.py` | `C:\...\V3D\Scripts\HMMWatchdog_V3D.py` | 27,992 | RC#3: Feature standardization + label confidence guard |

**All filenames are unchanged.** Batch files, scheduled tasks, and shortcuts work without modification.

**Cross-version consistency:** V3C and V3D asymmetric hysteresis gates produce **identical open/close decisions across 960 swept input combinations** (0 mismatches).

---

## Recommended Change #1 — Asymmetric Hysteresis (V3D + V3C)

### The Rule

| HMM State | Symbol | Requirement | Rationale |
|---|---|---|---|
| TrendUp | NQ | 1-bar IF macro confirms; else 2-bar | 34% fakeout — borderline; macro confirm covers it |
| TrendUp | ES | 1-bar IF macro confirms; else QUARANTINE | Only 17 occurrences — auto-label-collapse hypothesis |
| TrendDown | Both | 2 consecutive HMM bars | 60-64% fakeout rate |
| Balance | NQ | 2 consecutive HMM bars | 66% fakeout rate |
| Balance | ES | 1-bar OK | 19% fakeout, 59-min avg — fortress state |
| Transition | Both | 2 consecutive HMM bars | 60% fakeout rate |
| MACRO_STALE_* | Both | Hard close — all bots zeroed | Missing data = no trade |

### Macro-confirming states

`TREND`, `TREND_STRUCTURE`, `TREND_UP_MACRO`, `TREND_DOWN_MACRO`, `BALANCE_STRUCTURE`, `CONFIRMED_INITIATIVE`

### New output columns (appended, no existing columns changed)

| Column | Type | Description |
|---|---|---|
| `HMMStateAgeBars` | int | Consecutive HMM bars in current micro-state |
| `AsymHysteresisGateOpen` | bool | True = gate permits; False = gate blocks |
| `AsymHysteresisReason` | string | `HYST_PASSED_*` or `HYST_BLOCK_*` audit token |
| `AsymHysteresisEnabled` | bool | Mirrors the kill-switch constant |

### Kill switch (instant rollback)

```python
ASYMMETRIC_HYSTERESIS_ENABLED = False   # in either file
```

### Test evidence

- V3D: 21/21 gate tests, 5/5 integration tests, end-to-end process_symbol pass
- V3C: 21/21 gate tests, 5/5 integration tests, build_v3c_row schema verified
- Cross-version: 960/960 identical decisions

---

## Recommended Change #2 — V3C Macro Freshness Fix (V3C only)

### Root cause

`detect_stale_data()` computed `(now_ts - macro_ts).total_seconds() / 60.0` without checking whether the timestamps were from the same trading session. When the macro CSV contained a row from 83 days ago (the latest valid row after a macro pipeline outage), the arithmetic produced `MACRO_STALE_119665.0MIN` — a technically correct but operationally nonsensical value that confused operators and broke log analysis.

### The fix

Three-layer session-boundary guard added to `detect_stale_data()`:

1. **Cross-session guard**: if `macro_date` is >1 calendar day before `now_date`, return `MACRO_STALE_WRONG_SESSION_{N}D` immediately. No minute computation needed.
2. **Overnight tolerance**: if `date_diff == 1` (yesterday's close → today's open), check the hour gap. Under 20 hours = normal overnight, pass through to micro-freshness check. Over 20 hours = `MACRO_STALE_OVERNIGHT_{N}HR`.
3. **Same-day cap**: if same calendar day but somehow >400 minutes apart (impossible during RTH), return `MACRO_STALE_EXCEEDED_SESSION_{N}MIN` as a safety net.

Same guards applied to micro staleness.

### What changes operationally

- `MACRO_STALE_119665.0MIN` → `MACRO_STALE_WRONG_SESSION_83D` (clear, actionable)
- `MACRO_STALE_4457.7MIN` → `MACRO_STALE_WRONG_SESSION_3D`
- Normal overnight at session start (macro at 16:00 yesterday, now at 09:35) → `FRESH` (was previously flagged as stale because 1055 min > 20 min threshold)
- No false-positives on session open: the overnight path explicitly avoids the minute-based check

### Test evidence

- 8/8 stale-detection test cases pass
- Overnight tolerance verified: 17.5hr gap = FRESH; 22hr gap = MACRO_STALE_OVERNIGHT
- 83-day gap produces WRONG_SESSION, not minute count
- Guard-disabled path unchanged

---

## Recommended Change #3 — V3D HMM Feature Standardization + Label Guard (V3D HMM only)

### Root cause

The V3D `HMMWatchdog_V3D.py` dropped the feature standardization step that was present in the legacy `HMM_Watchdog.py`. Without z-scoring, features on vastly different scales — Range (~0.001–0.01), Returns (~-0.005 to +0.005), Vol_Z (~-2 to +3), vwap_dist_atr (~-2 to +2) — distort the GaussianHMM covariance estimate. The Gaussian clusters become dominated by high-variance features (Vol_Z, vwap_dist_atr), and the four states lose semantic distinction. This produces the 75.7% Transition over-labeling observed on 2026-04-30.

### The fix

1. **`standardize_features(X)`**: z-scores the feature matrix before fitting. Returns `(X_scaled, means, stds)` so the scaler can be passed to predict and label-assignment.

2. **`fit_hmm(X)`**: now returns `(model, score, scaler_means, scaler_stds)` — a 4-tuple instead of 2-tuple. The model trains on standardized features.

3. **`assign_labels()`**: un-scales cluster means to natural units before applying the `vwap_dist_atr > 0 / < 0` sign checks for TrendUp/TrendDown assignment. This ensures the directional semantics are correct regardless of scaling.

4. **Label confidence guard**: computes the TrendUp/TrendDown vwap_dist_atr separation in natural units. If below `LABEL_VWAP_MIN_SEPARATION` (default 0.10), logs a `LABEL CONFIDENCE WARNING` and sets `LabelAmbiguousFit=1` in the output CSV. This gives the supervisor a programmatic signal that the current HMM fit may be drifting.

5. **`build_output()`**: accepts scaler params and standardizes features before `model.predict()` / `model.predict_proba()` to ensure consistency between training and inference.

### New output columns (appended to HMM CSV)

| Column | Type | Description |
|---|---|---|
| `LabelAmbiguousFit` | int (0/1) | 1 = TrendUp/TrendDown vwap separation below threshold |
| `LabelVwapSeparation` | float | Absolute vwap_dist_atr separation between TrendUp and TrendDown cluster means |

### What changes operationally

- The 75.7% Transition rate should drop significantly because Range and Returns now contribute proportionally to cluster assignment, producing cleaner TrendUp/TrendDown clusters with distinct return-sign + vwap-direction anchors.
- The exact new distribution depends on the current 60-day rolling window content — run `--once --full-history` on the first deployment to see the re-fitted distribution.
- The `LabelAmbiguousFit` column gives the supervisor a canary signal: if it flips to 1, the model is drifting and the 60-day window may need to be widened or a manual re-fit triggered.

### State file compatibility

The state JSON (`HMMWatchdog_V3D_state.json`) now includes `{symbol}_label_diagnostics` alongside the existing `{symbol}_label_map`. Old state files without this key will work — the diagnostics are only written, never read for gating.

### Test evidence

- `standardize_features`: zero-mean, unit-variance verified
- `fit_hmm`: returns 4-tuple with valid scaler
- `assign_labels` with scaler: produces correct 4-label set, diagnostics populated
- Well-separated data: `ambiguous_fit=False`
- Collapsed data: `ambiguous_fit=True`, warning logged
- All 5 HMM tests pass

---

## Recommended Change #4 - Footprint Export Production + ES Label Drift Rollout

### Root cause

`Active\Footprint_Export.csv` was header-only because the installed NinjaTrader `OrderFlowSetupScanner` cleared the CSV on every chart load and only exported the old six-column NQ/MNQ schema. It also exported at most one setup per bar, omitted DD from CSV production, and detected DT after the HUD broadcast pass, so current-bar DT could be missed by strategy gates.

Separately, the corrected V3D HMM watchdog existed in `V3D\Scripts`, but the root launcher path `Scripts\HMMWatchdog_V3D.py` was still the stale pre-standardization copy. The active V3D HMM CSVs were still old schema, with no `LabelAmbiguousFit` or `LabelVwapSeparation` diagnostics.

### The fix

1. Updated the installed NinjaTrader source:
   `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\OrderFlowSetupScanner.cs`

2. Mirrored the same production source into the project tree:
   `C:\Users\Valued Customer\NT8_Regimes\V1B\NinjaTrader\OrderFlowSetupScanner.cs`

3. Preserved the first six footprint columns and appended production context fields:
   `Symbol`, `Direction`, `Category`, `ClosePrice`, `HighPrice`, `LowPrice`, `ActiveBias`, `SourceChart`

4. Replaced destructive CSV initialization with schema-safe initialization:
   missing/empty files get a header; mismatched schema files are backed up as `.schema_backup_YYYYMMDD_HHMMSS.csv`.

5. Expanded export coverage to `NQ`, `MNQ`, `ES`, and `MES`, mapping minis to leader symbols (`MNQ -> NQ`, `MES -> ES`).

6. Export now writes every unique signal/direction pair per bar instead of one prioritized signal. This lets V1B Mode B and kill-switch validation observe ABS, DD, TF, SIB, DEB, PAR, DEIA, EEMDF, and DT events.

7. DT detection now runs before CSV export and before HUD broadcast, so `Scanner_DT` is current-bar fresh for V1B gates.

8. Synced corrected V3D scripts into the root launcher path:
   `Scripts\HMMWatchdog_V3D.py`
   `Scripts\RegimeSupervisor_V3D.py`

9. Fixed full-history HMM rebuild gating so `--full-history` always rebuilds even when the latest 5-minute bar timestamp is unchanged.

10. Fixed HMM diagnostics serialization so `LabelAmbiguousFit` writes cleanly to `HMMWatchdog_V3D_state.json`.

### Production files refreshed

- `Active\Footprint_Export.csv` header updated to the production schema.
- `V3D\NQ_HMM_Regimes_V3D.csv` regenerated: 59,448 rows.
- `V3D\ES_HMM_Regimes_V3D.csv` regenerated: 59,381 rows.
- `Backtest\NQ_RegimeMatrix_Full.csv` regenerated: 15,056 rows.
- `Backtest\ES_RegimeMatrix_Full.csv` regenerated: 15,037 rows.
- `V3C\ES_Regimes_V3C.csv` and `V3C\NQ_Regimes_V3C.csv` schema-normalized with Phase One hysteresis audit columns. Backups were saved beside each file.
- `V3C\ES_Regimes_V3C_Latest.csv` and `V3C\NQ_Regimes_V3C_Latest.csv` refreshed once.

### Test evidence

- HMM full-history rebuild completed successfully for both NQ and ES.
- V3D supervisor batch completed successfully for both NQ and ES.
- V3D HMM outputs now include `LabelAmbiguousFit` and `LabelVwapSeparation`.
- V3D RegimeMatrix outputs now include `HMMStateAgeBars`, `AsymHysteresisGateOpen`, `AsymHysteresisReason`, and `AsymHysteresisEnabled`.
- V3C output schema was normalized and latest rows were written with `HYST_BLOCK_STALE_MACRO_STALE_WRONG_SESSION_2D`, as expected for a Sunday run against Friday data.

---

## Recommended Change #5 - Parts 4-6 Audit Completion

### Part 4 - V3D Transition leak closed

The audit's silent leak was confirmed: V3D could promote `Macro=TREND + HMM=Transition` into actionable `TREND_COMPRESSION` through `DIRECTIONAL_MODERATE`. That is unsafe because the original study showed Transition has roughly 60% fakeout risk.

Implemented in:

- `V3D\Scripts\RegimeSupervisor_V3D.py`
- `Scripts\RegimeSupervisor_V3D.py`
- `V3C\Scripts\RegimeMatrixSupervisor.py`

New rule:

- `HMM=Transition` is non-directional by default.
- If `Macro=TREND` and `HMM=Transition`, directional compression is blocked with `HMM_TRANSITION_TREND_BLOCKED`.
- The only exception is explicit price proof: macro direction plus velocity plus IB-extension confirmation. Those rare rows use `TRANSITION_MACRO_VELOCITY_IB_CONFIRMED`.
- V3D `EXTREME_THRUST` now also requires IB extension, so it cannot bypass the Part 4 rule with velocity alone.

Post-patch V3D full-history verification:

| Symbol | HMM=Transition rows still promoted to directional regimes | Reason |
|---|---:|---|
| NQ | 5 | `TRANSITION_MACRO_VELOCITY_IB_CONFIRMED` |
| ES | 0 | none |

V3D full-history outputs were rebuilt after the patch:

- `Backtest\NQ_RegimeMatrix_Full.csv`: 15,056 rows.
- `Backtest\ES_RegimeMatrix_Full.csv`: 15,037 rows.

### Part 5 - Synthesis recommendation status

Completed or already in place:

- V3D remains the production substrate.
- Python-centralized V3D gate logic is preserved.
- V3C/V3D five-regime taxonomy is active.
- Asymmetric hysteresis V3C/V3D is active.
- ES TrendUp quarantine is active.
- V3C macro freshness wrong-session guard is active.
- Footprint exporter is production-capable and ES/NQ-aware.
- Trade-log unification now writes separated V1A, V1B, V3C, V3D, and all-model history files.
- Raw 1-minute exports are de-duplicated.
- Transition permissioning is now restricted by the Part 4 rule.

Still intentionally deferred until post-test evidence:

- Continuous `SizePct` expectancy validation. Current sizing columns remain present; live interpretation should still be treated as binary permission/no-permission until outcome validation.
- Conflict-score threshold recalibration. The audit wanted phase-two distribution/outcome analysis before changing the threshold.
- Footprint expectancy validation. The exporter is repaired, but `Footprint_Export.csv` must still produce populated rows for at least 10 consecutive RTH sessions before Mode B / kill-switch capital is trusted.
- V1A/V1B migration to fully Python-centralized gates. The audit identifies this as a larger architecture migration, not a same-pass patch.

### Part 6 gap closure

#### Gap 1 - Footprint export

Status: production header and producer repaired; live row validation pending.

- `Active\Footprint_Export.csv` has the production schema:
  `TimestampET, Signal, Volume, Delta, DeltaPct, VwapDistanceTicks, Symbol, Direction, Category, ClosePrice, HighPrice, LowPrice, ActiveBias, SourceChart`
- Current row count is still 0 because no live RTH chart has produced rows since the repair.
- Next-week test requirement: confirm rows for NQ/ES RTH sessions and keep the >=10 consecutive RTH session validation rule.

#### Gap 2 - Trade-log unification

Status: refreshed and materially repaired.

The root `accounts_registry.json` was missing from the location expected by `Scripts\eod_export.py`; it has been placed at the root and the all-history export was rerun.

Updated files:

- `UNIFIED\AllModels_TradeLog_ALL.csv`: 119 rows.
- `V1A\History\V1A_TradeLog_ALL.csv`: 4 rows.
- `V1B\History\V1B_TradeLog_ALL.csv`: 1 row.
- `V3C\History\V3C_TradeLog_ALL.csv`: 63 rows.
- `V3D\History\V3D_TradeLog_ALL.csv`: 51 rows.
- `UNIFIED\DataQuality_Report_ALL.txt`

Current model-version split:

| Model | Rows |
|---|---:|
| V3C | 63 |
| V3D | 51 |
| V1A | 4 |
| V1B | 1 |

Current data-quality flags:

| Flag | Rows |
|---|---:|
| OK | 94 |
| UNMAPPED_ACCOUNT | 24 |
| UNMAPPED_ACCOUNT;MISSING_EXITREASON | 1 |

The old raw `V3D\TradeLog\V3D_TradeLog.csv` remains an untrusted raw source with 1,483 unavailable-context rows and 160 `Unknown_Bot` rows. The cleaned model-history and `UNIFIED` outputs are the files to use for next-week model testing.

#### Gap 3 - HUD override log

Status: present and readable.

File:

- `Overrides\HUD_Override_Log.csv`

Current contents:

- 2 override rows.
- 2026-04-28 11:08:35 NQ manual mode off.
- 2026-04-28 11:18:40 NQ auto mode restored.

No repair needed. Keep this file in the weekly audit packet because every override is a useful labeled supervision event.

#### Gap 4 - SHADOW vs LIVE divergence

Status: audit is now quantified.

Overlap and divergence after Part 4 live rebuild:

| Symbol | Overlap rows | FinalRegime differs | Permission differs |
|---|---:|---:|---:|
| NQ | 1,184 | 300 | 622 |
| ES | 1,194 | 95 | 233 |

The divergence is large enough that SHADOW should remain a comparison track, not be silently promoted. Next-week testing should include a reason-code shift table before adopting SHADOW logic.

#### Gap 5 - raw 1-minute export quality

Status: repaired.

Backups created:

- `Exports\NQ_1min_export.pre_dedupe_20260503_124202.txt`
- `Exports\ES_1min_export.pre_dedupe_20260503_124202.txt`

De-duplication result:

| Symbol | Before rows | After rows | Duplicates removed | Duplicate timestamps now |
|---|---:|---:|---:|---:|
| NQ | 1,030,297 | 1,024,627 | 5,670 | 0 |
| ES | 1,028,273 | 1,023,028 | 5,245 | 0 |

After de-duplication, V3D HMM full-history and V3D supervisor batch were rerun successfully.

---

## Deployment Order

Recommended sequence:

1. **Deploy `HMMWatchdog_V3D.py` first** (RC#3). Run `--once --full-history --symbol BOTH` to re-fit the HMM with standardized features and verify the new distribution. Check `LabelAmbiguousFit` column — if 0, the fit is clean. If 1, consider widening `LOOKBACK_TRADING_DAYS`.

2. **Deploy `RegimeSupervisor_V3D.py` next** (RC#1). Run `--batch --symbol BOTH` against the newly re-fitted HMM output. Check `AsymHysteresisReason` distribution — should show a mix of `HYST_PASSED_*` and `HYST_BLOCK_*`.

3. **Deploy `RegimeMatrixSupervisor.py` last** (RC#1 + RC#2). On first live cycle, the V3C history CSV will be schema-migrated (`.schema_backup_*` file created). Verify the overnight tolerance works correctly by checking the `StaleReason` column at first checkpoint after market open.

---

## What These Changes Do NOT Do

- **Do not fix the V1A/V1B C# bot gate logic.** That migration to Python-centralized gates is a separate synthesis recommendation.
- **Do not assume footprint expectancy is validated yet.** `Footprint_Export.csv` is now production-capable, but Mode B / kill-switch capital should still wait for the audit's >=10 consecutive RTH sessions of populated rows.
- **Do not change the 60-day rolling window size.** Phase Two's auto-label drift audit will determine whether quarterly refit is better.
- **Do not change SizePct to binary.** That is a separate recommendation awaiting trade-outcome validation.
- **Do not change the conflict-score threshold (0.40).** That recalibration requires the full longitudinal CSV computation specified in Phase Two.

---

## Complete Test Summary

| Test suite | Cases | Result |
|---|---|---|
| V3D asymmetric hysteresis gate | 21 | 21/21 PASS |
| V3D compute_bot_permissions integration | 5 | 5/5 PASS |
| V3D process_symbol end-to-end | 2 bars | PASS |
| V3C asymmetric hysteresis gate | 21 | 21/21 PASS |
| V3C map_bot_permissions integration | 5 | 5/5 PASS |
| V3C build_v3c_row schema | 4 audit cols | PASS |
| V3C ↔ V3D cross-version consistency | 960 | 0 mismatches |
| V3C detect_stale_data (freshness fix) | 8 | 8/8 PASS |
| V3D HMM standardize_features | 1 | PASS |
| V3D HMM fit_hmm 4-tuple return | 1 | PASS |
| V3D HMM assign_labels with scaler | 1 | PASS |
| V3D HMM ambiguous_fit=False (clean data) | 1 | PASS |
| V3D HMM ambiguous_fit=True (collapsed data) | 1 | PASS |
| V3D Part 4 Transition directional leak check | NQ/ES | PASS |
| Raw 1-minute duplicate timestamp check | NQ/ES | PASS |
| Unified trade-log model split check | V1A/V1B/V3C/V3D | PASS |
| All files syntax parse | 3 | 3/3 CLEAN |
