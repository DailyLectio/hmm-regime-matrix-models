# Engineer Handoff — Regime Expansion Patch
**Date:** 2026-05-06  
**Prepared by:** Master Regime Project Analysis  
**Status:** Ready for engineer compile and deploy  
**Priority:** P1 — blocks expansion and momentum lanes on all clean breakout days

---

## Summary of Changes

Four files are patched and ready in the `deliverables/` folder:

| File | Change Type | Impact |
|---|---|---|
| `StageA_MacroRegimeBuilder_V3D_PATCHED.py` | Python — Stage A | Adds `same_side_vwap_minutes`, fixes `two_sided_trade_flag` sticky logic |
| `RegimeSupervisor_V3D_PATCHED.py` | Python — V3D Supervisor | Adds IB override lane, upgrades Transition exception path |
| `RegimeMatrixSupervisor_PATCHED.py` | Python — V3C Supervisor | Adds IB override lane, upgrades Transition + bracket initiative paths |
| `TradeLogExporter_V3D_PATCHED.cs` | C# — NT8 Indicator | Fixes HUD lookup key mismatch causing all `entry_regime=UNAVAILABLE` |

---

## Evidence That Drove These Changes

From the May 6 filtered session (298 rows, 09:30–15:00 ET):

- `TwoSidedFlag = 1` on **all 298 rows** — the flag never cleared despite NQ running 37% of IB width above IB high and holding >2.8 ATR above VWAP for the final hour.
- `AllowExpansion = 0` on **all 298 rows** — the Expansion bot was structurally dark for the entire session.
- `FinalRegime = TREND_EXPANSION` appeared **zero times**.
- `FinalRegime = TRANSITION` appeared **132 times** (44%), driven by `Macro=TREND + HMM=Balance` producing `ConflictScore=0.40` exactly at the threshold.
- `V3D_TradeLog.csv` had **3,745 rows** with `entry_regime=UNAVAILABLE` on every single row — zero regime context captured.
- The three dedicated bot logs (Expansion_A, Momentum_A, Sniper_A) were **header-only** — no trades.

---

## Patch 1 of 4 — StageA_MacroRegimeBuilder_V3D_PATCHED.py

**Deploy to:** `C:\Users\Valued Customer\NT8_Regimes\V3D\Scripts\StageA_MacroRegimeBuilder_V3D.py`  
**Also check:** `C:\Users\Valued Customer\NT8_Regimes\Scripts\Root_Scripts_MacroRegimeBuilder_V3D.py` — if this is the file actually launched by your batch/scheduled job, apply the same patch there. Both copies are included in the source pack; confirm which one the `.bat` file calls.

### What Changed

**New column: `same_side_vwap_minutes`**

Computed inside the `build_sessions()` checkpoint loop, immediately after the `two_sided_trade_flag` block. Counts consecutive 1-minute bars from the most recent bar backward where price stayed on the same side of session VWAP. Written to the output CSV as an integer.

This column was referenced by the V3C supervisor's `classify_v3c_candidate()` function (via `macro_row.get("same_side_vwap_minutes", 0.0)`) but was never actually computed or written by Stage A — it always read as 0. That silently disabled every IB override condition that depended on it.

**Two-sided flag decay (`two_sided_trade_flag`)**

The original logic set `two_sided_trade_flag = 1` for the entire session once price visited both sides of VWAP — even a single tick below VWAP during the first minute would lock the flag at 1 forever. This is the primary reason all 298 session rows showed `TwoSidedFlag=1`.

New logic: after computing `two_sided_raw`, a decay override clears the flag to 0 when all three conditions are true:
1. `ib_extension_pct >= thr["ib_strong"]` (NQ: 1.00, ES: 0.85)
2. `same_side_vwap_minutes >= 15`
3. `abs(close_vs_vwap_atr) >= 1.50`

These conditions together confirm that price has broken the IB range and sustained one-sided acceptance. A single random tick below VWAP early in the session no longer blocks expansion for the rest of the day.

**Backward compatibility note:** The output CSV gains one new column (`same_side_vwap_minutes`). The supervisor scripts read it with `.get(..., 0.0)` which returns 0 if absent, so old CSV files remain readable. The history CSV schema will need a version header note if you use `normalize_history_schema_if_needed()`.

---

## Patch 2 of 4 — RegimeSupervisor_V3D_PATCHED.py

**Deploy to:** `C:\Users\Valued Customer\NT8_Regimes\V3D\Scripts\RegimeSupervisor_V3D.py`  
**Also check:** `C:\Users\Valued Customer\NT8_Regimes\Scripts\RegimeSupervisor_V3D.py` if that is the launched copy.

### What Changed

**New path: `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`**

Inserted in `classify_final_regime()` **before** the PRIORITY 1 conflict check at line 592. This is intentional — the override needs to run before the `conflict_score >= 0.40` block, because today's failure was caused by that block firing on a single-source conflict while price had already confirmed expansion through price action.

Conditions (all required):
```python
ib_ext >= THRESHOLDS[symbol]["ib_strong"]    # NQ ≥ 1.00, ES ≥ 0.85
abs(close_vs_vwap_atr) >= 1.25
abs(net_move_since_open_atr) >= 2.0
returned_to_open_flag == 0
same_side_vwap_minutes >= 10
conflict_score < 0.60                        # allows single-source but blocks multi-source
direction != "NEUTRAL"
```

Output: `TREND_EXPANSION`, confidence = `min(85, 70 + ib_ext * 10)`, reason = `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`.

**Important design note:** The conflict ceiling is 0.60, not removed entirely. Genuine multi-source conflict (stale data + HMM flip storm + returned-to-open) still blocks. This override only fires when a single clean piece of evidence pushes conflict to exactly the 0.40 threshold. The `same_side_vwap_minutes >= 10` gate prevents single-bar spikes from triggering it.

**Upgraded exception path: `TRANSITION_IB_CONFIRMED_EXPANSION`**

In the `Macro=TREND, HMM=Transition` exception block, the original code capped at `TREND_COMPRESSION` regardless of IB extension. Now: if `ib_ext >= THRESHOLDS[symbol]["ib_strong"]`, the return is `TREND_EXPANSION` with reason `TRANSITION_IB_CONFIRMED_EXPANSION`. Otherwise it still returns `TREND_COMPRESSION` with `TRANSITION_MACRO_VELOCITY_IB_CONFIRMED` as before. This makes the escape hatch from Transition actually capable of waking the Expansion bot.

**New output column: `SameSideVwapMinutes`**

Added to the output dict in `process_symbol()` so the RegimeMatrix CSV carries the value for post-trade audit and EOD comparison.

---

## Patch 3 of 4 — RegimeMatrixSupervisor_PATCHED.py (V3C)

**Deploy to:** `C:\Users\Valued Customer\NT8_Regimes\V3C\Scripts\RegimeMatrixSupervisor.py`

### What Changed

**`same_side_vwap_minutes` now actually read from macro row**

The variable was already being read in `classify_v3c_candidate()` via `macro_row.get("same_side_vwap_minutes", 0.0)` — but Stage A was never writing it, so it always read 0. With Patch 1 in place, this now carries the real value.

**New path: `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`**

Inserted in `classify_v3c_candidate()` immediately after the conflict score is finalized and **before** the stale-data check. The stale check still runs after (stale data should always block). Conditions mirror V3D but use V3C's threshold dataclass:

```python
ib_ext >= th.strong_ib_ext                   # NQ: 1.10, ES: 1.25
abs(close_vs_vwap) >= 1.25
abs(net_move) >= 2.0
returned_open == 0
same_side_vwap_minutes >= 15                 # V3C uses 15 vs V3D's 10 (more conservative)
conflict < 55                                # V3C uses 55 threshold (vs V3D's 60)
direction in {"LONG", "SHORT"}
not stale_flag
```

Output: `TREND_EXPANSION`, reason = `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE`.

**`BRACKET_MACRO_WITH_INITIATIVE_EVIDENCE` can now promote to expansion**

Added a promotion block inside the existing bracket initiative path. When `developing_score >= 70` AND `ib_ext >= th.expansion_ib_ext` AND VWAP/net move confirm AND `same_side_vwap_minutes >= 10`, the candidate becomes `TREND_EXPANSION` with reason `BRACKET_IB_BREAK_EXPANSION_PROMOTED`. This directly addresses the V3C failure mode where bracket/rotation macro stayed sticky while price was clearly in expansion territory.

**`TRANSITION_IB_CONFIRMED_EXPANSION` promotion**

Same upgrade as V3D: when the Transition exception path fires AND `ib_ext >= th.strong_ib_ext`, return `TREND_EXPANSION` instead of `TREND_COMPRESSION`.

---

## Patch 4 of 4 — TradeLogExporter_V3D_PATCHED.cs

**Deploy to:** `C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\TradeLogExporter_V3D.cs`  
**Compile in:** NinjaTrader 8 → Tools → Edit NinjaScript → compile after saving. Verify no errors before reattaching to charts.

### Root Cause of UNAVAILABLE

`GetHud()` was doing a single dictionary lookup: `instances.Contains(leaderSymbol)` where `leaderSymbol` was computed by `GetLeaderSymbol()` as `"NQ"` or `"ES"`. If `RegimeMatrixHUD_V3D` registered itself under a different key format — such as `"NQ JUN26"` (the contract month format NT8 uses for `Instrument.FullName`) — the lookup silently returned null on every call, and every fill wrote `UNAVAILABLE`.

Because there is no HUD source file in the pack, we cannot confirm the exact key format the HUD uses. The fix tries multiple candidate keys in order:
1. `leaderSymbol` (auto-detected: `"NQ"` or `"ES"`)
2. `Instrument.FullName` (`"NQ JUN26"`)
3. `Instrument.MasterInstrument.Name.ToUpper()` (raw NT8 name)

If none of these match, the indicator now **Prints a diagnostic message** to the NT8 output log listing both what was tried and what IS registered in the dictionary. Check the NinjaTrader Output tab after the first fill to see the registered keys, then use the new `LeaderSymbolOverride` parameter to hardcode the correct key if auto-detection still misses.

### New Parameter: `LeaderSymbolOverride`

Appears in the indicator's parameter panel under "V3D Trade Log", Order 3. Leave blank for auto-detection. If the diagnostic Print shows the HUD is registered as `"NQ JUN26"`, enter `NQ JUN26` here. This survives session restarts and eliminates the key mismatch permanently.

### Deployment Steps for CS File

1. Open NT8 → New → NinjaScript Editor → open `TradeLogExporter_V3D.cs`
2. Replace entire file content with the patched version
3. Compile (F5 or Compile button) — verify 0 errors
4. Remove the existing `TradeLogExporter_V3D` indicator from all charts (it must be removed before reloading a new compiled version)
5. Re-add to each chart — set `BotName`, `ModelVersion`, and `LeaderSymbolOverride` if needed
6. On the first fill, check NinjaTrader Output tab for any `GetHud:` diagnostic messages

---

## Deployment Order

Apply in this exact order. Stage A must be deployed first because the supervisors depend on the new column it writes.

```
1. StageA_MacroRegimeBuilder_V3D_PATCHED.py  →  deploy, run once manually to verify output includes same_side_vwap_minutes
2. RegimeSupervisor_V3D_PATCHED.py           →  deploy
3. RegimeMatrixSupervisor_PATCHED.py         →  deploy
4. TradeLogExporter_V3D_PATCHED.cs           →  compile in NT8, redeploy to all charts
```

---

## Which Script Copy Is Launched?

The pack includes both `V3D\Scripts\StageA_MacroRegimeBuilder_V3D.py` and `Scripts\Root_Scripts_MacroRegimeBuilder_V3D.py`. These are different file paths. Before deploying, check your batch file or scheduler to confirm which path is actually executed. Apply the patch to that file. If both are identical and either could be launched, patch both.

The same applies to `RegimeSupervisor_V3D.py` — there is a root copy and a V3D-subfolder copy.

---

## Validation Checklist

### After deploying Stage A

- [ ] Run Stage A manually for a single recent date: `python StageA_MacroRegimeBuilder_V3D.py`
- [ ] Open the output CSV (`NQ_Macro_Regimes_V3D.csv`) and confirm `same_side_vwap_minutes` column exists with non-zero values after ~10:00 ET on a trending day
- [ ] Confirm `two_sided_trade_flag` still = 1 on early pre-breakout rows and transitions to 0 after confirmed IB breakout (check May 6 data if re-running history)
- [ ] Confirm no new NaN values in existing columns

### After deploying Supervisors

Run a backtest on May 6 data through both supervisors and check:

- [ ] `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE` appears in `ReasonCode` column around 11:05–11:35 ET when IBExtensionPct first crosses threshold with same_side_vwap_minutes >= 10/15
- [ ] `FinalRegime = TREND_EXPANSION` appears for at least some rows in that window
- [ ] `AllowExpansion = 1` on those rows
- [ ] `TwoSidedFlag` correctly clears when decay conditions are met
- [ ] No regressions on prior ROTATION_LIQUID or ROTATION_ILLIQUID days — spot-check 3–5 non-trending sessions and confirm expansion was NOT spuriously granted

### After deploying C# TradeLogExporter

- [ ] After first fill on any bot, check NinjaTrader Output tab — should NOT see `GetHud: No HUD instance found`
- [ ] Check `V3D_TradeLog.csv` — `entry_regime` field should now contain actual regime labels (e.g. `TREND_COMPRESSION`, `ROTATION_LIQUID`), not `UNAVAILABLE`
- [ ] Check dedicated bot logs (V3D_Expansion_A_TradeLog.csv, V3D_Momentum_A_TradeLog.csv) — should populate when the respective bot fills

---

## What Is NOT Changed (Intentional Deferrals)

Per the Phase One audit constraints and the engineer commentary:

| Item | Status | Reason |
|---|---|---|
| Conflict score threshold (0.40 V3D / 55 V3C) | Not changed | Requires longitudinal distribution + outcome cross-tab from Phase Two |
| 60-day HMM rolling window | Not changed | Phase Two auto-label drift audit required first |
| SizePct binary lock | Not changed | Awaiting trade-outcome expectancy validation |
| Footprint kill-switch paths | Not changed | Footprint_Export.csv still header-only; benched until populated |
| ES TrendUp quarantine | Not changed | Auto-label drift audit still pending |
| Asymmetric hysteresis parameters | Not changed | Current implementation passes all 21 test cases; no data to justify recalibration |

---

## Files Delivered

```
deliverables/
├── python_patches/
│   ├── StageA_MacroRegimeBuilder_V3D_PATCHED.py
│   ├── RegimeSupervisor_V3D_PATCHED.py
│   └── RegimeMatrixSupervisor_PATCHED.py
├── cs_patch/
│   └── TradeLogExporter_V3D_PATCHED.cs
└── docs/
    └── Engineer_Handoff_Regime_Expansion_Patch_20260506.md  ← this file
```

All patched files are complete, compilable/runnable files — not diff patches. Replace the corresponding source files in their deployment paths with these versions.

---

## Open Questions Requiring Engineer Confirmation

1. **Which script path does the batch/scheduler actually launch?** Both V3D\Scripts and root Scripts copies exist. Patching the wrong one will have no effect.

2. **What key does RegimeMatrixHUD_V3D use in InstancesV3D?** The HUD source is not in the pack. After deploying the C# fix, the first fill's diagnostic Print will reveal this. If the HUD registers under `"NQ JUN26"`, set `LeaderSymbolOverride = NQ JUN26` on the indicator.

3. **Does the V3C supervisor's `calculate_velocity()` buffer reset on restart?** The May 6 V3C latest snapshot showed `Velocity3CP = 0.0` despite an 80-minute trend. The pre-seeding fix was recommended (see prior audit session) but was not included in this patch set because the supervisor script file provided does not include the `process_instrument()` function body. If this is confirmed as an issue, add the velocity pre-seed in `process_instrument()` before the main processing loop.
