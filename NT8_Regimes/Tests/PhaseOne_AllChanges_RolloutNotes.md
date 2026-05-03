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

## Deployment Order

Recommended sequence:

1. **Deploy `HMMWatchdog_V3D.py` first** (RC#3). Run `--once --full-history --symbol BOTH` to re-fit the HMM with standardized features and verify the new distribution. Check `LabelAmbiguousFit` column — if 0, the fit is clean. If 1, consider widening `LOOKBACK_TRADING_DAYS`.

2. **Deploy `RegimeSupervisor_V3D.py` next** (RC#1). Run `--batch --symbol BOTH` against the newly re-fitted HMM output. Check `AsymHysteresisReason` distribution — should show a mix of `HYST_PASSED_*` and `HYST_BLOCK_*`.

3. **Deploy `RegimeMatrixSupervisor.py` last** (RC#1 + RC#2). On first live cycle, the V3C history CSV will be schema-migrated (`.schema_backup_*` file created). Verify the overnight tolerance works correctly by checking the `StaleReason` column at first checkpoint after market open.

---

## What These Changes Do NOT Do

- **Do not fix the V1A/V1B C# bot gate logic.** That migration to Python-centralized gates is a separate synthesis recommendation.
- **Do not enable Footprint-dependent paths.** `Footprint_Export.csv` is still header-only; Mode B and kill-switch paths remain blocked.
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
| All files syntax parse | 3 | 3/3 CLEAN |
