# Daily Regime Model Automation Audit — 2026-05-06

Status: **FAIL**

Session Date: **2026-05-06** (America/New_York)

Core Objective: determine whether the V3C, V3D, and active companion regime model pipelines are producing trustworthy outputs and whether the **May 6 regime-expansion / IB-breakout acceptance** changes are behaving correctly enough to continue toward live trading.

---

## Files Reviewed

### Unified EOD performance artifacts (present)
- `UNIFIED\Reports\Daily_Trade_Performance_20260506.md` (LastWriteTime: 2026-05-06 16:21)
- `UNIFIED\AllModels_TradeLog_20260506.csv` (148 rows; LastWriteTime: 2026-05-06 16:21)
- `UNIFIED\DataQuality_Report_20260506.txt` (LastWriteTime: 2026-05-06 16:21)

### V3D regime pipeline artifacts (present)
- `V3D\NQ_RegimeMatrix_Latest.csv` (1 row; 67 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\ES_RegimeMatrix_Latest.csv` (1 row; 67 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\History\NQ_RegimeMatrix_History.csv` (17,551 rows total; 759 rows for 2026-05-06; 67 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\History\ES_RegimeMatrix_History.csv` (17,532 rows total; 67 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\NQ_Macro_Regimes_V3D.csv` (15,125 rows total; 41 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\ES_Macro_Regimes_V3D.csv` (15,111 rows total; 41 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\NQ_HMM_Regimes_V3D.csv` (4,702 rows total; 21 cols; LastWriteTime: 2026-05-06 16:00)
- `V3D\ES_HMM_Regimes_V3D.csv` (4,703 rows total; 21 cols; LastWriteTime: 2026-05-06 16:00)
- `V3D\TradeLog\V3D_TradeLog.csv` (3,823 rows total; 624 rows for 2026-05-06; 32 cols; LastWriteTime: 2026-05-06 15:46)
- `V3D\History\V3D_Trade_Log_Enriched.csv` (3,796 rows total; 624 rows for 2026-05-06; 41 cols; LastWriteTime: 2026-05-06 16:18)
- `V3D\History\V3D_TradeLog_20260506.csv` (2 rows; 43 cols; LastWriteTime: 2026-05-06 16:21)
- `V3D\History\V3C_V3D_Intraday_Comparison.csv` (320 rows total; 40 rows for 2026-05-06; LastWriteTime: 2026-05-06 16:18)
- `V3D\History\V3C_V3D_Regime_Comparison.csv` (16 rows total; 2 rows for 2026-05-06; LastWriteTime: 2026-05-06 16:18)

### V3C regime pipeline artifacts (present)
- `V3C\NQ_Regimes_V3C_Latest.csv` (1 row; 61 cols; LastWriteTime: 2026-05-06 16:01)
- `V3C\ES_Regimes_V3C_Latest.csv` (1 row; 61 cols; LastWriteTime: 2026-05-06 16:15)
- `V3C\NQ_Regimes_V3C.csv` (100 rows for 2026-05-06; LastWriteTime: 2026-05-06 16:01)
- `V3C\ModelFeed\NQ_Macro_Regimes_V3C.csv` (47 rows for 2026-05-06; 61 cols; LastWriteTime: 2026-05-06 16:17)
- `V3C\ModelFeed\NQ_Regimes_HMM_V3C.csv` (86 rows for 2026-05-06; 21 cols; LastWriteTime: 2026-05-06 16:17)
- `V3C\TradeLog\SimV3C_NQ_*.csv` (multiple; 51 rows for 2026-05-06 across files)

---

## Freshness and Schema

Pass:
- All primary V3C/V3D latest/history/macro/HMM files exist and were written on **2026-05-06** during the session/EOD window.
- Required columns exist in V3D history (`ReasonCode`, `FinalRegime`, `FinalDirection`, `AllowExpansion`, `TwoSidedFlag`, `SameSideVwapMinutes`, `IBExtensionPct`, `ConflictScore`, `StaleDataFlag`, and bot permission fields).
- Unified EOD report and unified trade log exist for the session (so this is **not** `WAITING_FOR_EOD_REVIEW`).

Fail signals:
- V3D NQ history for 2026-05-06 shows **severe duplication / multi-variant rows per checkpoint**:
  - 759 rows for the session but only **20 distinct** `TimestampET` values (e.g., `2026-05-06 11:35:00` appears **58** times with **multiple variants**).
  - This undermines confidence in any simple row-count interpretation and suggests history-writing or append/rebuild hygiene issues.

---

## Regime Behavior (Key Fields)

### V3D (NQ) — end-of-day snapshot
- `TimestampET=2026-05-06 16:00:00`
- `FinalRegime=TREND_COMPRESSION`, `FinalDirection=LONG`
- `AllowExpansion=0`
- `TwoSidedFlag=1`
- `SameSideVwapMinutes=178`
- `ReasonCode=DIRECTIONAL_MODERATE`

### V3C (NQ) — end-of-day snapshot
- `MacroTimestamp=2026-05-06 16:00:00`
- `FinalRegime=TREND_EXPANSION`, `FinalDirection=SHORT`
- `AllowExpansionBot=True`
- `TwoSidedTradeFlag=1`
- `SameSideVwapMinutes=325.0`
- `ReasonCode=IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`

### Two-sided decay / clearing (critical watch)
- V3D: `TwoSidedFlag=1` for **759 / 759** session rows.
- V3C: `TwoSidedTradeFlag=1` for **99 / 100** session rows.
- Guidebook expectation: this should clear after valid breakout + VWAP acceptance conditions; it did **not** clear in either pipeline.

### V3C velocity cold start (medium)
- `Velocity3CP` equals `0` or `0.0` for **68 / 100** V3C session rows.
- This can indicate a cold-start/restart artifact or a feed/aggregation issue; it reduces trust in direction/persistence logic that depends on velocity.

---

## Override Evidence (May 6 acceptance change)

### V3D (NQ)
- `ReasonCode=IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`: **0** rows (2026-05-06).
- `FinalRegime=TREND_EXPANSION`: **28** rows, but all at **one timestamp** (`2026-05-06 14:35:00`) and **all** have `AllowExpansion=0`.

### V3C (NQ)
- `ReasonCode=IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`: **4** rows (all at `15:55` and `16:00`).
- Those override rows do set `FinalRegime=TREND_EXPANSION`, but expansion gating is inconsistent:
  - `AllowExpansionBot=True` occurs at `16:00` (and also appears in some `BRACKET_IB_BREAK_EXPANSION_PROMOTED` rows at `15:15` / `15:25`).
  - There are also duplicate/conflicting rows at the same timestamps (including conflicting `FinalDirection` at `15:55`).

### Required check: expansion regime with gate closed (critical)
- V3D: `FinalRegime=TREND_EXPANSION` AND `AllowExpansion!=1` rows: **28** (critical permission mismatch).
- V3C: `FinalRegime=TREND_EXPANSION` occurs **9** times; `AllowExpansionBot` is not reliably open across those rows (mixture of `True` and `False` at the same timestamps).

Interpretation:
- The **acceptance override behavior is not trustworthy yet** across the full pipeline:
  - V3D never shows the override, yet it produces `TREND_EXPANSION` without opening permissions.
  - V3C shows the override but appears late-day and duplicates/conflicts at the same checkpoint.

---

## Trade Attribution (Critical)

Trade regime attribution must be reliable if we are moving toward live trading.

### Raw / enriched trade logs
- `V3D\TradeLog\V3D_TradeLog.csv` (2026-05-06): **624 / 624** trades have `entry_regime=UNAVAILABLE`.
- `V3D\History\V3D_Trade_Log_Enriched.csv` (2026-05-06): **624 / 624** trades have `entry_regime=UNAVAILABLE`.
- V3C raw trade logs aggregated (2026-05-06): **51 / 51** trades have `entry_regime=UNAVAILABLE`.

### Unified trade log (works)
- `UNIFIED\AllModels_TradeLog_20260506.csv` (2026-05-06): **0 / 148** trades missing `entry_regime`.

Interpretation:
- Even though the unified pipeline recovers usable `entry_regime`, the **model-local trade attribution pipelines (V3D and V3C raw/enriched) are currently failing**. Per the guidebook this is a **critical failure mode** because live monitoring and model-level QA depend on those files being correct immediately after fills.

---

## Cross-Reference: EOD Trade Results (from unified report)

From `UNIFIED\Reports\Daily_Trade_Performance_20260506.md`:
- Trades: **148**
- Net P&L: **$3,213.40**
- Win rate: **45.3%**
- By model:
  - **V3C**: 114 trades, **$4,473.40**
  - **V3D**: 2 trades, **-$640.00**

Expansion-bot labeled trades (by `exported_bot_name` containing “Expansion”):
- `NQ Expansion A`: **4 trades**, net P&L **+$200**
- All 4 were entered with `entry_regime=TREND_COMPRESSION` (not `TREND_EXPANSION`).

Interpretation:
- Expansion-labeled trading did occur, but it did **not** align to expansion regime windows as labeled by `entry_regime`. This is not proof the acceptance changes are working correctly; it is evidence the naming / gating / attribution alignment needs investigation before live trading.

---

## V3C / V3D Divergences

From `V3D\History\V3C_V3D_Intraday_Comparison.csv` (2026-05-06, 40 checkpoints):
- `v3c_final_regime != v3d_final_regime`: **36 / 40**
- `v3c_direction != v3d_direction`: **31 / 40**
- `v3c_hmm_regime != v3d_hmm_regime`: **34 / 40**
- `v3d_allow_expansion` is **0** for **40 / 40** checkpoints.

Interpretation:
- Some divergence is expected due to threshold differences, but the magnitude here (near-total mismatch) is **suspicious** and consistent with broader pipeline instability (history duplication, two-sided sticky, gating mismatch).

---

## Failure Modes Triggered (Guidebook Matrix)

Critical:
- **Trade-log regime unavailable**: `entry_regime=UNAVAILABLE` in V3D/V3C raw + V3D enriched logs.
- **Permission mismatch**: V3D produces `FinalRegime=TREND_EXPANSION` while `AllowExpansion=0` (28 rows).

High:
- **Two-sided decay clears too early / too late** (here: effectively never clears): `TwoSidedFlag/TwoSidedTradeFlag` stays at 1 throughout the day.
- **History hygiene / stale rebuild risk**: V3D history duplicates many variants per checkpoint on 2026-05-06.

Medium:
- **V3C/V3D disagreement**: regime/direction/HMM mismatches across most checkpoints.
- **V3C velocity cold start**: `Velocity3CP` is 0 in 68% of session rows.

Not observed today:
- Stale feed (`StaleDataFlag=1`) in V3C/V3D latest/history slices was not observed (all 0/False in the slices checked).

---

## Evidence Counts (Quick)

### V3D (NQ history, 2026-05-06 slice)
- Session rows: **759** (20 distinct checkpoints)
- `ReasonCode=IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`: **0**
- `FinalRegime=TREND_EXPANSION`: **28** (all at `14:35`)
- `AllowExpansion=1`: **0**
- `TREND_EXPANSION` with `AllowExpansion!=1`: **28**
- `TwoSidedFlag=1`: **759 / 759**

### V3C (NQ regimes, 2026-05-06 slice)
- Session rows: **100**
- `ReasonCode=IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`: **4**
- `FinalRegime=TREND_EXPANSION`: **9**
- `TwoSidedTradeFlag=1`: **99 / 100**
- `Velocity3CP in {0,0.0}`: **68 / 100**

### Trade attribution
- V3D raw (2026-05-06): `entry_regime=UNAVAILABLE` **624 / 624**
- V3D enriched (2026-05-06): `entry_regime=UNAVAILABLE` **624 / 624**
- V3C raw aggregated (2026-05-06): `entry_regime=UNAVAILABLE` **51 / 51**
- Unified (2026-05-06): missing/blank/UNAVAILABLE `entry_regime` **0 / 148**

---

## Tactical Next Actions (Conservative / Live-Readiness)

1. **Block live-trading progression for expansion logic until fixed**: permission + two-sided clearing are not behaving consistently across V3C/V3D.
2. **Fix trade attribution in model-local logs (critical)**:
   - Resolve why V3D raw + enriched exports write `entry_regime=UNAVAILABLE` while unified can populate it.
   - This must be correct intraday (within seconds of a fill) for trustworthy live monitoring.
3. **Investigate V3D history duplication / variant rows**:
   - Confirm whether `V3D\History\NQ_RegimeMatrix_History.csv` is being appended multiple times per checkpoint and why multiple state variants are being persisted for the same `session_key`.
4. **Re-validate the May 6 acceptance override path**:
   - For May 6 specifically, confirm the intended override window and whether V3D is reading the patched Stage A/macro outputs.
   - Explain why V3C override appears near 15:55–16:00 instead of the earlier window described in the guidebook.
5. **Check two-sided decay / clearing rules**:
   - Identify why `TwoSidedFlag/TwoSidedTradeFlag` stays stuck at 1 even when same-side VWAP evidence exists.
6. **Validate V3C velocity initialization**:
   - Determine whether `Velocity3CP=0` is expected for early checkpoints or indicates cold-start/restart behavior that should be guarded before trusting direction gating.

