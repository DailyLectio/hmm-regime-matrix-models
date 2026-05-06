# Daily Regime Model Automation Audit Guidebook

Created: 2026-05-06

Purpose: give the daily automation a tactical review matrix for deciding whether the regime pipeline is healthy enough to keep moving V3C, V3D, and the active companion regime models toward live trading.

This audit is separate from the existing EOD trade-performance review. It should run after the EOD export/report process is expected to be complete so it can read the daily performance report, trade logs, regime histories, and latest model outputs.

## Primary Question

How do we prove the regime changes are working without waiting for trades?

The audit answers that by checking:

1. Whether the model outputs are structurally valid.
2. Whether regime decisions changed when the market gave the right evidence.
3. Whether trade permission gates matched the regime state.
4. Whether filled trades inherited usable regime labels.
5. Whether failure modes are accumulating evidence before they become live-trading risk.

## Daily Audit Stages

### Stage 0 - Inputs and Freshness

Run before any interpretation.

Check these files when present:

| Area | File |
| :-- | :-- |
| EOD performance report | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\Daily_Trade_Performance_YYYYMMDD.md` |
| Daily unified trade log | `C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_YYYYMMDD.csv` |
| V3D NQ latest | `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_RegimeMatrix_Latest.csv` |
| V3D ES latest | `C:\Users\Valued Customer\NT8_Regimes\V3D\ES_RegimeMatrix_Latest.csv` |
| V3D NQ history | `C:\Users\Valued Customer\NT8_Regimes\V3D\History\NQ_RegimeMatrix_History.csv` |
| V3D ES history | `C:\Users\Valued Customer\NT8_Regimes\V3D\History\ES_RegimeMatrix_History.csv` |
| V3D macro feed | `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_Macro_Regimes_V3D.csv` |
| V3D HMM feed | `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_HMM_Regimes_V3D.csv` |
| V3C latest | `C:\Users\Valued Customer\NT8_Regimes\V3C\NQ_Regimes_V3C_Latest.csv` |
| V3C macro feed | `C:\Users\Valued Customer\NT8_Regimes\V3C\ModelFeed\NQ_Macro_Regimes_V3C.csv` |
| V3C HMM feed | `C:\Users\Valued Customer\NT8_Regimes\V3C\ModelFeed\NQ_Regimes_HMM_V3C.csv` |
| V3D raw trade log | `C:\Users\Valued Customer\NT8_Regimes\V3D\TradeLog\V3D_TradeLog.csv` |
| V3C raw trade logs | `C:\Users\Valued Customer\NT8_Regimes\V3C\TradeLog\*.csv` |

Freshness checks:

- Latest and history files should have timestamps from the reviewed session.
- History rows should exist for the RTH checkpoints.
- EOD report should exist; if missing, mark the audit `WAITING_FOR_EOD_REVIEW`.
- Key columns should exist and not be all blank: `ReasonCode`, `FinalRegime`, `FinalDirection`, `AllowExpansion`, `TwoSidedFlag` or `TwoSidedTradeFlag`, `SameSideVwapMinutes`, `IBExtensionPct`, `ConflictScore`.

### Stage 1 - Offline Validation

Goal: prove patches behave on known data before relying on live fills.

Gold standard case: May 6.

Checks:

- Rebuild May 6 Stage A with the patched macro builder.
- Confirm `same_side_vwap_minutes` exists and is not all zeros.
- Around the 11:05 to 11:35 window, `same_side_vwap_minutes` should be meaningfully positive, normally around 30 to 80 minutes if the day held same-side VWAP.
- `two_sided_trade_flag` should be 1 early and should clear no later than the checkpoint where the IB breakout and VWAP acceptance conditions are met.
- The 12 checkpoint rows should not show NaN drift, corrupted velocity, or missing macro fields.
- Run the supervisor on May 6 macro plus HMM outputs.
- Confirm `ReasonCode = IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE` appears around the breakout-acceptance window.
- Confirm `FinalRegime = TREND_EXPANSION` on those rows.
- Confirm `AllowExpansion = 1` when the override fires. If the regime says expansion but the bot permission stays closed, inspect downstream permission mapping.

Regression case: April 30 or May 1 choppy/rotation session.

Checks:

- Run the same patched stack on the choppy date.
- Confirm `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE` does not appear.
- Confirm `TREND_EXPANSION` is not promoted spuriously.
- Confirm behavior is materially similar to the unpatched supervisor.

Broader sample:

- Pick 5 known trend-expansion sessions and 5 known chop/rotation sessions.
- Expansion sessions should show a reasonable number of `TREND_EXPANSION` rows.
- Chop sessions should not be over-promoted.

### Stage 2 - Intraday Monitoring

Goal: catch broken deployment, stale feeds, and permission mismatches while the session is still recoverable.

Primary file:

`C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_RegimeMatrix_Latest.csv`

Watch fields:

| Field | Healthy Sign | Failure Signal |
| :-- | :-- | :-- |
| `ReasonCode` | Clear explanation for current state; override appears on valid IB breakout acceptance days | Persistent `HIGH_CONFLICT`, `TWO_SIDED_CONFIRMED`, or `HYST_BLOCK_*` on a clearly directional day |
| `TwoSidedFlag` | Clears after a confirmed IB breakout and same-side VWAP acceptance | Stays 1 deep into a one-sided breakout session |
| `SameSideVwapMinutes` | Counts up during VWAP acceptance | Missing, blank, or stuck at 0 |
| `AllowExpansion` | Becomes 1 when expansion override fires | Remains 0 while `FinalRegime = TREND_EXPANSION` |
| `IBExtensionPct` | Matches chart logic using 09:30 to 10:30 IB | Disagrees materially with chart IB range |
| `ConflictScore` | Below override ceiling on clean trend days | Elevated enough to explain blocked permission |
| `StaleDataFlag` | 0 or false during active feed | 1 or true while the session is active |

Secondary NT8 and trade-log checks:

- On first V3D fill, the NT8 Output window should show either no unresolved `TradeLogExporter [NQ]:` diagnostic or a useful key-list diagnostic.
- Within 30 seconds of a V3D fill, the newest `V3D_TradeLog.csv` row should have `entry_regime` populated with an actual label, not `UNAVAILABLE`.
- If `UNAVAILABLE` persists, treat trade-regime attribution as unreliable until the C# key mapping is fixed and recompiled.

### Stage 3 - Post-Close Evidence Accumulation

Goal: build proof over a 2-week sample.

After the existing EOD performance report is complete, collect:

- Count of rows with `ReasonCode = IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`.
- Count of rows with `FinalRegime = TREND_EXPANSION`.
- Count of rows with `AllowExpansion = 1`.
- Count of V3D Expansion bot fills during expansion-approved windows.
- Net P&L, win rate, and average R for trades entered during expansion windows.
- Count of rows with `entry_regime = UNAVAILABLE`.
- Count of stale, missing, or malformed output files.
- V3C/V3D disagreement windows, especially where V3D promotes expansion earlier than V3C.

Evidence targets for first 10 sessions:

- If valid IB breakout-hold sessions occur, at least 50% to 80% should produce `TREND_EXPANSION` at least once.
- Override firing on 3 to 4 genuinely trending days out of 10 can be healthy.
- Override firing on 7 to 8 out of 10 sessions, including choppy sessions, means thresholds are probably too loose.
- Override firing near 0% on valid breakout-hold sessions means deployment or gating is probably broken.

Single metric:

`sessions_with_30min_IB_break_hold / sessions_with_FinalRegime_TREND_EXPANSION`

Before the patch, this was effectively 0%. Post-patch target is 50% to 80%, not 100%.

## Failure Mode Matrix

| Failure Mode | Diagnostic Symptom | Audit Action | Severity |
| :-- | :-- | :-- | :-- |
| Wrong Stage A file patched | `same_side_vwap_minutes` missing or all zero; `TwoSidedFlag` sticky all day | Compare called batch path against `V3D\Scripts\MacroRegimeBuilder_V3D.py` and root `Scripts\MacroRegimeBuilder_V3D.py` | Critical |
| History not rebuilt after patch | New column exists only on new rows; historical rows read blank/zero | Require `--full-history` rebuild or explicit macro CSV rebuild before backtest conclusions | High |
| False breakout over-promotion | Override fires on choppy days or fast traps | Tighten `SameSideVwapMinutes`, `IBExtensionPct`, `CloseVsVwapAtr`, or conflict ceiling | Critical |
| Two-sided decay clears too early | `TwoSidedFlag` clears in first 2 to 3 checkpoints | Raise same-side VWAP requirement to 20 or 25 minutes for volatile opens | High |
| Trade-log regime unavailable | `entry_regime = UNAVAILABLE` after first fill | Read NT8 diagnostic key list and set `LeaderSymbolOverride` to actual registered key | Critical |
| V3C/V3D disagreement | V3D grants expansion earlier than V3C | Mark expected if V3D threshold is looser; confirm which model controls each bot | Medium |
| V3C velocity cold start | `Velocity3CP = 0.0` after supervisor restart | Avoid intraday restarts; wait 3 checkpoint cycles before trusting V3C velocity | Medium |
| Stale feed | Latest files stop updating while market is active | Restart affected stage only after confirming source export is active | High |
| Permission mismatch | `FinalRegime = TREND_EXPANSION` but `AllowExpansion = 0` | Inspect bot permission mapping and hysteresis gate fields | Critical |
| IB mismatch | `IBExtensionPct` does not match chart expectation | Confirm Stage A uses 09:30 to 10:30 IB and chart uses the same definition | High |

## Daily Output Format

Each automation run should produce a concise report with:

1. `Status`: PASS, WATCH, FAIL, or WAITING_FOR_EOD_REVIEW.
2. `Session Date`.
3. `Files Reviewed`.
4. `Freshness and Schema`.
5. `Regime Behavior`.
6. `Override Evidence`.
7. `Trade Attribution`.
8. `V3C/V3D Divergences`.
9. `Failure Modes Triggered`.
10. `Recommended Next Actions`.

Suggested report path:

`C:\Users\Valued Customer\NT8_Regimes\Audits\Daily_Regime_Model_Audit_YYYYMMDD.md`

## Go / No-Go Interpretation

PASS:

- Files fresh.
- Required columns present.
- No unexplained stale feeds.
- Trade regime labels populated when fills exist.
- Override behavior matches market structure.

WATCH:

- No trades occurred, but regime outputs are healthy.
- V3C and V3D differ for explainable threshold reasons.
- Minor missing files that do not block today`s core conclusion.

FAIL:

- Required columns missing.
- `SameSideVwapMinutes` stuck at 0 on active breakout day.
- `FinalRegime = TREND_EXPANSION` with `AllowExpansion = 0`.
- `entry_regime = UNAVAILABLE` after live fills.
- Override fires on a clear chop/rotation day.
- Latest files stale during active session or missing after EOD.

WAITING_FOR_EOD_REVIEW:

- Existing EOD trade-performance report is not present yet.
- Automation should still review live/regime files, but it cannot finalize the trade-outcome section.

