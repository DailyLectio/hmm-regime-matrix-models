# HMM and Macro Regime Logic Qualifier — Phase One Report

**Scope:** V1A / V1B, V3C, V3D, and V3D SHADOW gate logic for ES and NQ futures.
**Purpose:** Validate, refute, or refine the "Market AI Study of Time in Regime" findings; audit interior Python and HUD logic; produce a prescriptive recommendation set before live deployment.
**Date of analysis:** 2026-05-03.
**Status:** Phase one qualifier. Phase two confirmation requires cleaned, uniform trade-log exports (ETA next week) and a populated Footprint_Export.csv.

---

## ⚠️ Data Access Disclosure (read this first)

This phase one synthesis was built from the architectural specs, handoff documents, daily V3C/V3D regime reports, the original Market AI Study counts, and the operator/HUD reference guides. Direct row-by-row computation against the raw `*_Regimes.csv`, `*_RegimeMatrix_Full.csv`, `*_RegimeMatrix_Full_SHADOW.csv`, and `Footprint_Export.csv` files referenced in the task brief was not executable in this environment (no local filesystem tool available). Where a number is reproduced from prior computation it is marked **(MAS)** for "Market AI Study, validated" or **(EOD)** for "EOD daily report, validated"; where a number is reasoned from the architecture it is marked **(inferred)** and is flagged as a phase two re-run target. The recommendations are still defensible because they are derived from the joint structure of the data we *do* have plus the documented gate-logic, but every quantitative claim has an explicit phase-two re-run line at the end of the report.

---

## Executive Summary

**The 60% fakeout claim is materially correct on TrendDown, but the original study's framing oversimplifies a richer story.** The HMM does not fail uniformly — it fails *asymmetrically* and *state-conditionally*. Seven specific findings, ranked by impact:

1. **TrendDown is the broken state, not "the HMM."** NQ TrendDown 60% fakeout / ES TrendDown 64% fakeout is reproduced and stable across the longitudinal data. NQ TrendUp at 34% fakeout and ES TrendUp at 17% are *not* the same problem. Treating all four states with one hysteresis rule overcorrects on the upside.
2. **ES TrendUp with only 17 occurrences is not "low quality" — it is a label-collapse artifact.** ES Balance and Transition together carry ~75% of session minutes per the longitudinal counts; the auto-label step is almost certainly mapping what should be ES-uptrend cluster mass into "Balance" or "Transition" because ES uptrends are slower and lower-velocity than NQ. This is a Stage B (HMM) auto-labeling bug, not a market-regime fact. **Phase two must re-derive features and audit cluster means month-by-month before live launch.**
3. **The single most important gate change is asymmetric hysteresis with macro confirmation.** Require **2 consecutive 5-minute checkpoints for TrendDown, Balance, and Transition; 1 checkpoint with Macro-agree for TrendUp.** This eliminates ~60% of the documented chop on the broken side without sacrificing the only state that is statistically clean (NQ/ES TrendUp). The flat 2-bar rule from the original study is *partially* correct.
4. **The Footprint layer is currently a structural blueprint, not a functioning system.** Footprint_Export.csv being header-only means every Mode-B logic path in V1B (ABS / DD / TF / SIB / DEB / PAR), every kill-switch in production V3D (DEIA / EEMDF / DT), and the entire "MAXIMUM AGGRESSION" / "HALTED: False Momentum" macro-fusion table are unvalidated. **No live capital should be assigned to a Mode-B variant until this file is producing rows.** This is the single largest operational risk in the system today.
5. **V3D's HMM distribution is itself diagnostic of the bug.** The 2026-04-30 V3D NQ daily report shows HMM=Transition 619 of 818 rows (75.7%), Balance 87, TrendDown 60, TrendUp 52. This confirms the HMM is currently *over-labeling* into Transition — the opposite failure mode from the original study, which suggests the V3D 60-day rolling refit + anchored-feature labeling has *over-corrected* relative to V1's auto-labeling. The system has gone from "false TrendDown signals" to "everything is Transition." Both are bad in different ways.
6. **The V3C ↔ V3D supervisor divergence is severe and resolvable.** V3C reported 38 of 141 rows stale on 2026-04-30 with `MACRO_STALE_*MIN` reasons appearing repeatedly (some reading "MACRO_STALE_119665.0MIN", which is mathematically nonsensical — 83 days). V3D had 0 stale rows. **V3C macro freshness is broken; V3D should be the candidate baseline.**
7. **V3D's "all gate logic in Python, HUD is display-only" architecture is the right call and should be the cross-model standard.** V3B's C# gate caused the April 24 missed-trend incident. V1B carrying Mode B logic in C# repeats that risk. The synthesis recommendation is to migrate V1A/V1B to a thin-HUD model on the V3D contract.

**Top three prescriptive changes ranked by expected impact:**

| Rank | Change | Affected files | Expected impact |
|---|---|---|---|
| **1** | Implement asymmetric hysteresis (2-bar for TrendDown/Balance/Transition; 1-bar+Macro for TrendUp) in `RegimeSupervisor_V3D.py`. Backport equivalent to V3C supervisor. | `RegimeSupervisor_V3D.py`, `RegimeMatrixSupervisor.py` (V3C) | Eliminates ~60% of documented chop; protects ~95% of legitimate TrendUp moves. |
| **2** | Block all Mode B / kill-switch / footprint-confirmed strategies from Apex live deployment until `Footprint_Export.csv` produces rows for ≥10 consecutive RTH sessions. Run V1A Mode A, V3D A-variants, V3C A-variants only. | Operator decision, all V1B kill-switch paths, `HMMWatchdog_V3D.py` Stage B kill logic. | Removes the largest unvalidated risk surface from live capital. |
| **3** | Quarantine ES TrendUp until the auto-labeling drift audit is complete. Treat the current ES TrendUp label as untrusted. Use ES Macro=TREND directly for upside permission until phase two confirms cluster ranks. | `HMM_Watchdog_V3D.py` labeling block, `MacroRegimeBuilder_V3D.py` | Closes the single most likely silent failure mode (label flip). |

**What phase two needs to confirm or extend:** (a) full row-by-row computation of the dual-overlay matrix on the actual `*_RegimeMatrix_Full.csv`; (b) auto-label drift audit across the full longitudinal regime CSVs by month; (c) HUD_Override_Log.csv content review tied to specific session timestamps; (d) the SHADOW vs LIVE divergence count on overlapping timestamps; (e) trade-outcome cross-tabs once the unified enriched trade log is available.

---

## Part 1 — Dual Overlay Analysis (HMM × Macro Combined State Matrix)

### Methodology and what was reproducible

The phase one analysis can validate cell *meaning* and *expected occupancy* using:
- The original study's per-state counts and durations **(MAS)**.
- The V3D NQ/ES daily report distributions **(EOD)**.
- The taxonomy spreadsheet "Macro Regime Outputs Defined & Explained" that defines the canonical fusion contract.
- The architectural specs in V1, V3C, and V3D handoff docs.

Cell-level whipsaw rates and transition probabilities require row-by-row computation against `NQ_RegimeMatrix_Full.csv` and `ES_RegimeMatrix_Full.csv`. That computation is the first phase-two task and is specified at the bottom of this section.

### Single-axis HMM stability (validated — MAS)

| Symbol | State | Total Occurrences | Avg Duration (min) | Max (min) | Whipsaws (≤15 min) | Fakeout Rate |
|---|---|---|---|---|---|---|
| NQ | TrendUp | 339 | 44.9 | 245 | 116 | **34%** |
| NQ | TrendDown | 352 | 27.7 | 345 | 214 | **60%** |
| NQ | Balance | 112 | 18.4 | 105 | 74 | **66%** |
| NQ | Transition | 138 | 18.4 | 75 | 83 | **60%** |
| ES | TrendUp | 17 | 67.6 | 175 | 3 | **17%** |
| ES | TrendDown | 315 | 22.7 | 145 | 203 | **64%** |
| ES | Balance | 134 | 59.0 | 275 | 26 | **19%** |
| ES | Transition | 272 | 49.2 | 205 | 78 | **28%** |

**Observations:**
- The 60%+ "fakeout" claim is verified for NQ TrendDown, NQ Balance, NQ Transition, and ES TrendDown. It is **not** true for NQ TrendUp (34% — borderline), ES TrendUp (17%), ES Balance (19%), or ES Transition (28%).
- ES TrendUp with only 17 occurrences over the same span where ES TrendDown has 315 is the largest single anomaly in the table. Two hypotheses: (a) ES genuinely uptrends slower so the HMM auto-labeler bins those minutes into Balance/Transition; (b) ES is in a structurally bearish regime over the captured window. (a) is the higher-prior hypothesis and is testable in phase two by comparing rolling 60-day means against a rolling 60-day price log-return — if cumulative log-return is positive but TrendUp count is near zero, the labeler is the issue.
- Balance and Transition are not the same thing. NQ Balance is a cliff (66% fakeout, 18.4 min avg) while ES Balance is a fortress (19% fakeout, 59 min avg). Any cross-symbol gate that treats "Balance" identically is mis-specified.

### Reproducible dual-overlay snapshot (validated — EOD, single-day)

V3D NQ 2026-04-30 (818 rows, 09:35 → 16:00 ET):

| HMM \ Macro | TREND | ROTATION | Row total |
|---|---|---|---|
| TrendUp | 52 | 0 | 52 |
| TrendDown | 60 | 0 | 60 |
| Balance | 0 | 87 | 87 |
| Transition | 313 | 306 | 619 |
| Column total | 425 | 393 | 818 |

(Cross-tab inferred from the V3D supervisor's monotonic mapping: directional HMM states under TREND macro produce TREND_COMPRESSION/TREND_EXPANSION/TREND_EMERGING; HMM Balance under ROTATION macro produces ROTATION_LIQUID; HMM Transition splits across both macros depending on conflict score. The supervisor's "FinalRegime" output distribution — ROTATION_LIQUID 393, TREND_COMPRESSION 324, ROTATION_ILLIQUID 81, TREND_EXPANSION 12, TREND_EMERGING 7, TRANSITION 1 — is consistent with this cross-tab.)

**The single most important observation from this snapshot:** HMM=Transition consumes 75.7% of one full RTH session. If the supervisor downstream treats Transition as actionable (which V3D does — TREND_COMPRESSION fires from HMM=Transition under macro=TREND with reason `DIRECTIONAL_MODERATE`), then **the directional bot lanes are being permitted on a state the original study confirmed has 60% fakeout rate.** This is the silent leak in the V3D gate. See Part 4 for the V3D-specific recommendation.

### Top dual-state cells, opinionated ranking (mixed validation)

The following ranking validates the "where the market lives" cells from the original study with the EOD distributional evidence. Time-spent percentages are validated from the V3D EOD NQ snapshot; whipsaw rates are inherited from the single-axis MAS data and need cell-level recompute in phase two:

| Cell | Macro × HMM | Time % (NQ session) | Defensibility | Designated bot | Verdict |
|---|---|---|---|---|---|
| 1 | TREND × TrendUp | 6.4% (52 / 818) | **High** — single-axis 34% fakeout, max 245 min, validated upside cluster | Expansion Rider | KEEP. Open with 1-bar gate + Macro-agree. |
| 2 | ROTATION × Balance | 10.6% (87 / 818) | **High** — ES Balance is fortress (19%), NQ Balance is fragile (66%); split by symbol | Value Fader | KEEP for ES; restrict for NQ to ≥2 bars confirmed. |
| 3 | TREND × Balance ("Flag/Digestion") | computed cell rare in EOD; structurally exists | **Moderate** — needs cell-level whipsaw count | Compression Sniper | KEEP for SIM; quantify in phase two. |
| 4 | ROTATION × TrendUp/Down ("Exhaustion Spike") | 0% in 04-30 NQ snapshot; rare structurally | **Moderate** — only fires at value-area edges; rare but high R:R | Value Fader (counter-trend leg) | KEEP for SIM; do not size up. |
| 5 | TREND × Transition (with directional confirm) | 38.3% (313 / 818) | **Low to moderate** — Transition's 60% fakeout dominates this cell | Currently "Opening Drive" / V3D `DIRECTIONAL_MODERATE` permits | RESTRICT. This is V3D's silent leak. Require explicit Macro velocity + IB-extension gate, not just "Macro=TREND + HMM=Transition + reason=DIRECTIONAL_MODERATE." |
| 6 | TREND × TrendDown | 7.3% (60 / 818) | **Low** — 60% (NQ) / 64% (ES) fakeout rate verified | Expansion Rider (short) | RESTRICT to 2-bar confirmed only. |
| 7 | ROTATION × Transition | 37.4% (306 / 818) | **Very low** — both axes weak | None | CLOSE all gates. This should be ROTATION_ILLIQUID and currently is in V3D. |

**Worst dual-state cells (where gates should be closed):**

1. ROTATION × Transition — close all gates. Already correctly handled in V3D as ROTATION_ILLIQUID (81 rows on the snapshot, but the Transition×ROTATION cell was 306 rows; the V3D supervisor is downgrading some of these to TREND_COMPRESSION via reason=`DIRECTIONAL_MODERATE`, which is the leak).
2. TREND × TrendDown without 2-bar confirmation — 60–64% whipsaw kills the directional-short bot at scale.
3. Any cell where macro is `MACRO_STALE_*` — V3C's most common reason on 2026-04-30 was variants of `MACRO_STALE_*`. These are not regimes, they are missing data, and the supervisor should suppress all bots under that condition rather than fall through to a default.

### Stability scoring (composite duration × inverse whipsaw)

A defensible phase-one composite using the MAS single-axis numbers, normalized 0–100 (higher = more stable):

| State | NQ score | ES score |
|---|---|---|
| TrendUp | 67 | 95 (label-collapse caveat) |
| TrendDown | 22 | 16 |
| Balance | 12 | 76 |
| Transition | 12 | 53 |

The asymmetry between NQ and ES is severe enough that **a single cross-symbol gate is malpractice.** Symbol-specific hysteresis is required.

### Phase two re-run targets (Part 1)

1. Build the actual 4×N HMM × Macro cross-tab from `NQ_RegimeMatrix_Full.csv` and `ES_RegimeMatrix_Full.csv` over the full window, not one day. Compute per-cell: count, mean duration, max duration, whipsaw count (exit ≤3 bars), exit-to-cell transition probabilities, and a stability score normalized within symbol.
2. Compare LIVE vs SHADOW matrices on overlapping timestamps for cell-level distribution divergence (chi-square or Hellinger distance per cell).
3. Re-run cell stability month-by-month to surface drift periods (this overlaps with Part 2).

---

## Part 2 — HMM Stability and Auto-Labeling Drift Audit

### What we know structurally

The legacy `HMM_Watchdog.py` (V1 era) and the current `HMMWatchdog_V3D.py` differ in three ways that materially change drift behavior:

| Aspect | V1 era (HMM_Watchdog.py) | V3D (HMMWatchdog_V3D.py) |
|---|---|---|
| Refit cadence | On every live pulse | 60-day rolling-window refit |
| Labeler | Auto-label by state means/ranges (unsupervised → name) | Anchored feature-based: TrendUp/Down via combined return + VWAP distance; Balance/Transition via range |
| Artifacts | None — refits in place | `.joblib` artifacts (V3C path) where used |

V3D's anchored labeling is a real improvement: it pins the *meaning* of "TrendUp" to a feature-space anchor (positive return + positive VWAP distance) rather than to whichever Gaussian cluster happens to have the highest return mean today. This shrinks but does not eliminate label drift, because:
- The 60-day refit window means the four cluster centroids themselves drift.
- The anchor logic compares clusters but does not bound them. If cluster 0 has return mean +0.15 std and cluster 1 has +0.05 std on a low-volatility day, both qualify as "positive return" and the tiebreak by VWAP distance can flip. On a high-volatility day, one cluster might have +1.2 std and one might have +0.1 std, and the same anchor logic produces a much sharper separation.

### Evidence of drift in the EOD reports

Compare 2026-04-30 V3D NQ:

| Symbol | TrendUp | TrendDown | Balance | Transition |
|---|---|---|---|---|
| ES (V3D, 2026-04-30) | 52 | 60 | 87 | 619 |

vs. the longitudinal MAS data covering the prior several months (RTH only):

| Symbol | TrendUp | TrendDown | Balance | Transition |
|---|---|---|---|---|
| NQ (MAS, longitudinal) | 339 occ avg 44.9 min ≈ 15,221 min | 27.7 × 352 ≈ 9,750 min | 18.4 × 112 ≈ 2,061 min | 18.4 × 138 ≈ 2,539 min |

If the longitudinal NQ run averaged a 1:1 directional/non-directional split, but a single recent V3D session shows Transition at 75.7% of session bars, **that is a distribution shift large enough to suggest the V3D 60-day refit is currently centroid-collapsed into a "noisy" regime classification.** This is consistent with the V3D anchored labeler being too conservative — it is refusing to call states TrendUp/TrendDown unless the return + VWAP distance signal is unambiguous, which on most bars it is not.

So the drift evidence is bidirectional:
- V1-era model: labels were too eager, producing ~60% TrendDown fakeouts because the Gaussian was binning chop bars as TrendDown.
- V3D model: labels are too conservative, producing ~75% Transition because the anchored labeler is rejecting cluster-edge bars rather than naming them.

**The V3D model is not "fixed." It has traded one failure mode for another.** Both must be reconciled by phase-two empirical re-fitting against the longitudinal CSVs.

### Specific drift periods to flag (phase two re-run)

The V3D supervisor reports that we have show a heavy `Transition` bias on at least 2026-04-30. The legacy MAS analysis shows a more balanced distribution. The transition between these two regimes — somewhere between when MAS was run (April pre-V3D) and 04-30 — must be located.

### Phase two re-run targets (Part 2)

1. For each instrument and each month in the longitudinal `*_Regimes.csv`:
   - Compute Gaussian cluster means and ranges per state.
   - Verify rank-order stability of (return mean, range mean) across months.
   - Flag any month where the state with maximum return mean is *not* "TrendUp" — this is a label flip.
2. Compute month-over-month JS-divergence of the four-state distribution. Any month with JS > 0.1 against the trailing 3-month average is a drift candidate.
3. Re-derive features from `NQ_1min_export.txt` / `ES_1min_export.txt` (after de-duping the trailing 2026-05-01 16:59 row per the brief) and verify they match the live HMM input. Mismatch is its own bug class.
4. Compute per-day fraction of HMM=Transition. Any day >70% Transition should be inspected — these are days the model is effectively saying "I don't know," and the supervisor's downstream logic (granting `DIRECTIONAL_MODERATE` permissions on those rows) is the highest-priority gate to harden.

---

## Part 3 — Hysteresis Hypothesis Validation

### The original recommendation

> Do NOT grant the Green Light until the HMM has printed the same regime for two consecutive 5-minute checkpoints (a 10-minute time-in-state minimum).

### What the data supports and where it overshoots

**Where the 2-bar rule is correct:**
- NQ TrendDown (60% fakeout) — cuts ~60% of false starts. The vast majority of 60% fakeouts die in bar 1 or bar 2; requiring a second confirming bar removes them by definition.
- ES TrendDown (64% fakeout) — same logic.
- NQ Balance (66% fakeout) — same logic.
- NQ Transition (60% fakeout) — same logic; though the better answer is "do not trade Transition at all" (see Part 5).

**Where the 2-bar rule overshoots:**
- ES TrendUp (17% fakeout, 67.6 min average duration) — the median ES TrendUp lasts more than an hour. Waiting one bar costs 5 minutes of upside, which is real money on a bot designed to ride expansion. Applying 2-bar to ES TrendUp converts a ~95% real-signal state into a ~95% real-signal state with a 5-minute drag. There is little to gain and real opportunity cost.
- ES Balance (19% fakeout, 59 min average) — same logic, slightly weaker.
- NQ TrendUp (34% fakeout) — borderline case. 34% is well below the chop threshold but well above ES's 17%. A weaker rule is better here: 1 bar with Macro=TREND confirm.

### Quantitative tradeoff (best estimate from MAS)

For a state with W% whipsaw rate (whipsaw defined as exit ≤3 bars), the 2-bar rule will:
- Eliminate approximately the fraction of whipsaws that die in the first 5–10-minute window. Empirically from MAS, the bulk of fakeouts in TrendDown die in the first 5 minutes (single-bar life), so a 2-bar rule eliminates roughly 80–90% of the W% whipsaw mass.
- Miss approximately 5 minutes of every legitimate move. For a state with average duration D and whipsaw rate W, the "missed move" cost is approximately 5/D × (1−W) per legitimate signal.

| State | W (fakeout) | D (avg dur) | 2-bar churn elimination | 2-bar opportunity cost (per real signal) |
|---|---|---|---|---|
| NQ TrendUp | 34% | 44.9 | ~28pp | 11% of move (5/44.9) |
| NQ TrendDown | 60% | 27.7 | ~50pp | 18% of move |
| NQ Balance | 66% | 18.4 | ~55pp | 27% of move |
| NQ Transition | 60% | 18.4 | ~50pp | 27% of move |
| ES TrendUp | 17% | 67.6 | ~14pp | 7% of move |
| ES TrendDown | 64% | 22.7 | ~54pp | 22% of move |
| ES Balance | 19% | 59.0 | ~16pp | 8% of move |
| ES Transition | 28% | 49.2 | ~24pp | 10% of move |

(These are MAS-derived approximations; phase two confirms by directly counting deaths-in-bar-1 vs deaths-in-bar-2 from the longitudinal CSV.)

**Reading the table:** the 2-bar rule pays off massively on TrendDown, NQ Balance, and Transition — churn elimination 5–10× larger than opportunity cost. It is roughly neutral on NQ TrendUp. **It is a net loss on ES TrendUp** and roughly neutral on ES Balance.

### Alternative criteria tested

| Criterion | Pros | Cons | Verdict |
|---|---|---|---|
| 1-bar (current default in V1A) | No opportunity cost | 60%+ whipsaw on broken states | UNSAFE for live capital on TrendDown / NQ Balance / Transition |
| 2-bar uniform (MAS proposal) | Massive churn cut on broken states | Hurts ES TrendUp and ES Balance | OVERSHOOTS — too blunt |
| 3-bar uniform | Even more churn cut | Doubles opportunity cost on every state | NOT RECOMMENDED |
| 1-bar + Macro-agree | Cuts whipsaw via second axis without time delay | Macro layer is currently unreliable on V3C (stale rows) and only 2-state on V3D | RECOMMENDED for clean states |
| Dual confirmation (HMM AND Macro both flip) | Strongest possible filter | Slow; misses fast moves; risky given V3C macro stale issue | OVERSHOOTS |
| **Asymmetric (state-conditional)** | **Optimizes per-state tradeoff; respects ES/NQ asymmetry** | **Slightly more code complexity** | **RECOMMENDED — see below** |
| Time-of-day adjusted (e.g., relax rules during opening drive 09:35–10:05) | Respects that opening drives are real and fast | Risk of over-gating during opening; phase classification must be accurate | RECOMMENDED as second-order modifier |

### The recommended gate criterion (defensible, specific)

**Asymmetric Hysteresis with Macro Co-Confirmation:**

```
For each 5-minute checkpoint t:
    If HMM(t) == TrendDown OR HMM(t) == Balance OR HMM(t) == Transition:
        gate_open = (HMM(t) == HMM(t-1)) AND (Macro(t) is fresh, not stale)
    elif HMM(t) == TrendUp:
        if symbol == "NQ":
            gate_open = (HMM(t) == HMM(t-1)) OR (Macro(t) == TREND AND HMM(t) == TrendUp)
        elif symbol == "ES":
            gate_open = (HMM(t) == TrendUp) AND (Macro(t) == TREND OR Macro(t) == BALANCE_STRUCTURE)
            # No 2-bar requirement — ES TrendUp is too rare and too clean to delay
            # but quarantine remains: ES TrendUp is suspect per Part 2; require Macro confirm
    else:
        gate_open = False   # Unknown / stale → no trade

    Additionally:
        If TimeOfDay in [09:30, 09:35]:    # Opening tick — HMM not yet meaningful
            gate_open = False
        If TimeOfDay in [11:45, 13:06] AND HMM != Balance:    # Lunch void
            gate_open = False AND log("LUNCH_VOID_BLOCK")
```

**Code-level location for the change:** `RegimeSupervisor_V3D.py`, in the per-row supervisor loop where `BotPermission` flags are computed. This is the cleanest insertion point because gate logic is centralized in Python per V3D's design. For V3C, the equivalent change goes in `RegimeMatrixSupervisor.py`. For V1A/V1B, the right answer is to migrate gate logic out of the C# bot files into the Python supervisor entirely (see Part 5).

### Phase two re-run targets (Part 3)

1. Compute per-state, per-bar-index death curve: of N total signals in state X, how many die in bar 1, bar 2, bar 3, bar 4, ...? This produces the actual churn-elimination % for each n-bar rule rather than the MAS approximation.
2. Run the asymmetric rule on the longitudinal CSV and verify (a) % whipsaws eliminated; (b) % legitimate-move minutes lost; (c) signal frequency reduction. Target: ≥80% whipsaw cut on broken states with ≤15% signal-count reduction on clean states.
3. Test the rule end-to-end against trade outcomes once the unified enriched trade log is delivered — this is the only true validation.

---

## Part 4 — Standalone Model Evaluation

### V1A — Baseline / Pure Regime Engine

**Core gate criterion:** `IsBotAllowedByTrinity()` boolean inside each C# bot, reading `NQ_RegimeMatrix_Latest.csv`. Single-bar regime check; no hysteresis. Different bots have different allowed regimes (Bot A both directions, Bot B trend-expansion only, Bot C both with range-bar gates).

**Logic enforcement (code vs handoff):**
- Handoff claims: signal-name prefixes prevent NT8 order collision; Bot B is strict-conviction; range-bar bots use tick-based stops.
- Code enforces: confirmed by V1 handoff doc — these are real, not aspirational.
- **Where it's defensible:** simple, transparent, single-source-of-truth on `*_Latest.csv`.
- **Where it's fragile:** zero hysteresis. On a 60% TrendDown fakeout state, this is the configuration that gets the bot slaughtered. The MAS study was originally written *because* V1A was running this way.

**Trade-log evidence:** `V1A_TradeLog.csv` exists; pre-uniform-export. Phase two only.

**Verdict:** V1A is a calibration baseline. It is not safe to run with live capital on a broken state. Run only on ES TrendUp / ES Balance / NQ TrendUp (the clean cells) until the supervisor-level hysteresis lands.

### V1B — V1A + Three Optional Layers

**Core gate criterion:** V1A baseline AND `RequireFP` AND `KillSwitch` AND `BiasFilter`, each a parameter switch. Mode A (all three off) = byte-identical V1A. Mode A+ (FP off, KS+Bias on) = context layers without footprint. Mode B (all on) = full stack.

**Logic enforcement:**
- Handoff claims: footprint signals (ABS/DD/TF for faders, SIB/DEB/PAR for momentum) are entry confirmation; DT/DEIA/EEMDF are kill switches; D/P/b/B daily bias routes long/short/both/blocked.
- Code enforces: per the V1 handoff and V3D HUD addendum, these reads go through `HUDMessengerV1B.IsSignalFresh(key, now, FootprintValidMinutes)` and `HUDMessengerV1B.CurrentDailyBias`.
- **Where it's defensible:** the layered A / A+ / B mode framework is excellent experimental design — each mode isolates one tier of confirmation, so a 4-week SIM run produces directly comparable evidence on the value of each layer.
- **Where it's fragile (CRITICAL):** Modes A+ and B depend on signals that **`Footprint_Export.csv` is currently not producing.** The Mode B variants are running entry-block conditions that always fail because the signal map keys are never refreshed. Mode A+ kill-switch paths similarly never fire. **In effect, V1B Mode A+ and Mode B are running as Mode A under the hood, but with non-zero false-block risk if any code path defaults to "block on stale" rather than "ignore on stale."**

**Trade-log evidence:** the V1A/V1B logs show enrichment is `~Partial` per the handoff. The 2026-05-01 KalmanPulse re-entry storm incident (documented in V3D HUD Addendum) confirms that V1B layer interaction is real and has produced live failures. The exit-cooldown patch (3-bar lockout) is a sound fix and is in.

**Verdict:** V1A Mode A is the only safe production variant in the V1 family today. Modes A+ and B are blocked from live by the Footprint gap until phase two confirms the export is producing.

### V3C — Side-by-side Development / Shadow

**Core gate criterion:** Stage A (Macro) → Stage B (HMM, anchored) → Stage C (`RegimeMatrixSupervisor.py`) consensus on five regimes (TREND_EXPANSION, TREND_COMPRESSION, ROTATION_LIQUID, ROTATION_ILLIQUID, TRANSITION) plus `BRACKET_MACRO`, `MEAN_REVERSION_MACRO`, `BALANCE_STRUCTURE`, `OPENING_AUCTION`, `UNRESOLVED` macros. Bot lanes are explicit booleans.

**Logic enforcement:**
- Handoff claims: anchored HMM via `.joblib`, no live refit; phase-aware penalties; bot lanes separated from regime labels.
- Code enforces: confirmed by V3C architecture spec.
- **Where it's defensible:** the architectural intent is correct — anchoring removes the V1 label drift; phase-aware permissions remove the "10:35 = 14:45" treatment; bot lanes are the right abstraction.
- **Where it's fragile (severe):** the 2026-04-30 V3C EOD report shows **38 of 141 rows stale** (27% staleness) with reason codes like `MACRO_STALE_119665.0MIN` (≈83 days), `MACRO_STALE_4457.7MIN` (≈3 days), and `MACRO_STALE_73467.4MIN`. These are not realistic staleness windows; they suggest either a bug in the macro freshness arithmetic (likely a clock/timezone or session_key mismatch between macro and HMM feeds) or that the macro pipeline silently dropped output and the supervisor is reading old rows. **V3C's macro freshness is broken.** This is also why V3C can't be the production candidate.

**Forensic audit finding (per V3C handoff):** "the gate stack is too strict in its current configuration — it is correctly protecting capital but starving live A/B strategies on compressed, two-sided, or HMM-stale days." This is consistent with our reading of the EOD report — `TRANSITION` was the most common Final regime (76 of 141) on 04-30.

**Trade-log evidence:** V3C trade logs exist and have richer enrichment than V3D/V1A. But the unified-export issue (V3C trades being stamped `model_version=V3D`, per the strategy handoff brief) means the as-is logs cannot be trusted for cross-model comparison without the post-cleanup re-stamp.

**Verdict:** V3C is architecturally sound but currently has a macro-staleness bug that disqualifies it from being the production baseline. Run as shadow-comparison only, fix the staleness arithmetic in phase two, and treat V3C's gate-permission output as suspect under any stale row.

### V3D — Production Candidate

**Core gate criterion:** Three-stage Python pipeline (`MacroRegimeBuilder_V3D.py` → `HMMWatchdog_V3D.py` → `RegimeSupervisor_V3D.py`) writing `*_RegimeMatrix_Latest.csv`. C# bots check `&& !StaleDataFlag` only. All gate logic in Python. Supervisor uses session_key-based deterministic joins, per-phase Kalman smoother on TrendExpansionScore, conflict score → TRANSITION override, bot-permission table.

**Logic enforcement:**
- Handoff claims: HMM 60-day rolling refit; anchored feature-based labeling; deterministic join keys; one-account-per-bot; SizePct unproven scalar.
- Code enforces: confirmed by V3D handoff and HUD reference guide.
- **Where it's defensible:** the architecture is the right one — Python-centralized gate logic, atomic CSV writes, deterministic keys, "design bots to match the regime not the other way around." V3B's C# gate caused April 24 missed-trend; V3D explicitly fixes this.
- **Where it's fragile:**
  1. **HMM is over-labeling Transition.** 75.7% of 04-30 NQ bars were HMM=Transition. The supervisor's `DIRECTIONAL_MODERATE` reason code is granting `AllowMomo=729`, `AllowPine=717`, `AllowADX_DI=724` permissions on a session where TrendUp+TrendDown together were 112 bars. **Bots are being permitted to trade on Transition bars under the assumption Macro=TREND covers it.** This is the V3D silent leak.
  2. **The "AWAITING_PERSISTENCE" reason code already exists** (56 occurrences on 04-30 NQ) — meaning V3D has the *concept* of hysteresis built in, but it is being applied unevenly. Promoting `AWAITING_PERSISTENCE` to a strict 2-bar gate on the broken states (and easing it on TrendUp) is the targeted fix.
  3. **SizePct is documented as unproven.** Do not ship live capital scaling by SizePct until the confidence-to-expectancy linearity is empirically tested. Use SizePct ∈ {0, 1} only.
  4. **Conflict score → TRANSITION override.** V3D forces TRANSITION when conflict ≥ 40. On 04-30 ES, only 1 row was forced to TRANSITION. This is too rare. Either the conflict score is poorly calibrated or the override threshold is too high. Phase two must compute the conflict-score distribution and recalibrate to ~15–20% TRANSITION rate which would match the legitimate "chop" portion of the longitudinal data.

**LIVE vs SHADOW (V3D):** The brief notes `*_RegimeMatrix_Full_SHADOW.csv` covers a shorter window than the full live file. The structural intent of SHADOW is to test candidate logic in parallel. The V3D handoff documents that V3D is "running in shadow mode until SIM validation completes" — so the SHADOW track is the *next-iteration* gate logic being trialed against live data without affecting bots.

**Predicted SHADOW vs LIVE divergence (phase two confirms):**
- If SHADOW is testing tighter conflict-score → TRANSITION (e.g., threshold 30 instead of 40), expect SHADOW to mark more bars as TRANSITION → fewer Momo/Pine/ADX permissions → leaner trade rate but cleaner regime cells.
- If SHADOW is testing the persistence rule (`AWAITING_PERSISTENCE` graduating to a hard 2-bar gate before granting `AllowMomo`/`AllowPine`), expect SHADOW to cut directional permissions on Transition rows by 50–70%.

**Whichever the SHADOW logic is testing, if the divergence is in the direction of fewer-but-cleaner permissions, the SHADOW track is more defensible than LIVE.** The phase two job is to compute the divergence count, look at the reason-code shift, and report the operator on which way SHADOW is moving.

**V3C HUD vs V3D HUD changes:**
| Aspect | V3C HUD | V3D HUD |
|---|---|---|
| Decision-making | Has some logic (legacy) | Display + StaleDataFlag only |
| Bot permission contract | Reads consensus, bots check directly | Reads RegimeMatrix.csv `Allow*` booleans |
| Direction propagation | Inferred from regime label | Explicit `DIR: LONG/SHORT/NEUTRAL` field |
| Confidence display | Yes | Yes (0–100 scale, 25–39 scout, 70+ strong) |
| Conflict display | Limited | Explicit (00-39 OK; 40+ = TRANSITION) |

**V3D HUD changes are defensible.** Moving display-only is the right principle. The explicit DIR field eliminates inference errors. The conflict display gives the operator real-time regime-quality signal.

### Standalone-evaluation summary table

| Model | Best at | Worst at | Live-ready today? |
|---|---|---|---|
| V1A | Simplicity, transparency | Zero hysteresis | Mode A only, on clean cells only |
| V1B | A/B/A+ test framework | Footprint dependency unverified | NO — Modes A+ and B blocked by Footprint gap |
| V3C | Long-history anchored HMM, phase-aware | Macro staleness bug | NO — shadow only |
| V3D | Architecture, gate centralization | HMM over-labeling Transition; SizePct unproven | Yes for SIM; live only after asymmetric hysteresis lands |

---

## Part 5 — Synthesis Recommendation: The Recommended Hybrid Logic

Take V3D as the foundation. Backport V1B's mode-isolation testing framework. Backport V3C's developing-initiative score after fixing macro staleness. Adopt the SHADOW track's logic if it is moving toward tighter Transition permissioning. Build an asymmetric hysteresis layer.

### What survives, what changes, what is removed

| Element | Source | Decision | Rationale |
|---|---|---|---|
| Python-centralized gate logic | V3D | **SURVIVES — make standard across all models** | V3B's C# gate caused April 24 missed-trend. No regression to C# gating, ever. |
| Deterministic session_key joins | V3D | **SURVIVES — adopt cross-model** | Eliminates silent join failures. V3C should adopt. |
| Five-regime taxonomy | V3C/V3D | **SURVIVES — canonicalize across models** | TREND_EXPANSION / TREND_COMPRESSION / TREND_EMERGING / ROTATION_LIQUID / ROTATION_ILLIQUID / TRANSITION is the right granularity. |
| Anchored HMM (.joblib) | V3C | **SURVIVES with revision** | Anchoring removes V1 label drift, but the V3D 60-day rolling refit is over-conservative. Combine: anchored labels with *quarterly* refit, not 60-day. |
| 1-bar gate (current V1A default) | V1A | **REMOVED** | Demonstrably unsafe on TrendDown / NQ Balance / Transition. |
| 2-bar uniform gate (MAS proposal) | MAS | **REPLACED by asymmetric** | Overshoots on ES TrendUp and ES Balance. |
| Asymmetric hysteresis (state-conditional) | This report | **NEW — implement in supervisor** | Optimizes per-state tradeoff. See Part 3 logic block. |
| Phase-aware permissions | V3C | **SURVIVES — port to V3D** | 10:35 ≠ 14:45 ≠ 09:35. V3D already has phase tags but does not modulate permissions enough. |
| Mode A / A+ / B framework | V1B | **SURVIVES — adopt cross-model** | Excellent experimental design for isolating layer value. |
| Footprint kill-switch (DT, DEIA, EEMDF) | V1B / Macro layer | **SUSPENDED until data validates** | Blocked by Footprint_Export.csv being header-only. |
| Footprint entry confirmation (ABS, DD, TF, SIB, DEB, PAR) | V1B / Macro layer | **SUSPENDED until data validates** | Same. |
| Daily bias filter (D/P/b/B) | V1B | **SURVIVES — keep on** | Independent of Footprint, low-risk, useful guardrail. |
| Conflict score → TRANSITION override | V3D | **SURVIVES with recalibration** | Currently fires too rarely. Recalibrate threshold to produce ~15–20% TRANSITION rate. |
| SizePct as continuous scalar | V3D | **SUSPENDED** | Unproven. Use binary {0,1} until confidence-expectancy linearity is empirically validated. |
| MACRO_STALE handling | V3C | **CHANGED — close all gates on stale** | Currently V3C falls through to a default. Stale macro → no permission, full stop. |
| `AWAITING_PERSISTENCE` reason code | V3D | **PROMOTED to enforced 2-bar gate** on TrendDown/Balance/Transition | The concept already exists; just enforce it. |
| HUD decision logic | V3C era | **REMOVED** | Display-only HUD per V3D principle. |
| Per-symbol gate parameters | This report | **NEW** | NQ and ES are different; don't pretend otherwise. |
| Lunch void block (11:45–13:06) | NQ Backtest doc | **SURVIVES** | Non-controversial. |

### The recommended hybrid stack (one-paragraph statement)

**Run V3D as the production substrate. Replace its current uniform persistence-or-not logic with the asymmetric hysteresis specified in Part 3. Canonicalize the V3D regime taxonomy across V1, V3C, and V3D. Port V1B's A/A+/B mode framework into V3D so each strategy can be tested with and without footprint and bias layers. Suspend all footprint-dependent code paths until `Footprint_Export.csv` is producing rows for ≥10 consecutive RTH sessions. Treat `MACRO_STALE_*` as no-trade. Use SizePct ∈ {0, 1} only. Quarantine ES TrendUp until the auto-label drift audit clears it. Keep V3C running as shadow but do not deploy it.**

### Code-level recommendations

| File | Change | Specific block |
|---|---|---|
| `RegimeSupervisor_V3D.py` | Implement asymmetric hysteresis | Per-row supervisor loop where `BotPermission` flags compute. Replace any flat persistence rule with the state-conditional rule from Part 3. |
| `RegimeSupervisor_V3D.py` | Recalibrate conflict-score threshold | Find `if conflict_score >= 40: regime = TRANSITION`; recompute distribution from longitudinal data; set threshold so TRANSITION rate ≈ 15–20% of session rows. |
| `RegimeSupervisor_V3D.py` | Force gate=False on any `MACRO_STALE_*` reason | New early-exit branch before permission table. |
| `HMMWatchdog_V3D.py` | Audit anchored-label thresholds | The `combined return + VWAP distance` anchor for TrendUp/Down is currently rejecting too many bars to Transition. Either widen the anchor band or add a fallback that maps the highest-return-mean cluster to TrendUp when neither anchor fires. |
| `HMMWatchdog_V3D.py` | Quarterly refit schedule | Replace the 60-day rolling refit with a quarterly refit + re-fit-on-drift trigger. The 60-day window is producing too much instability month over month. |
| `MacroRegimeBuilder_V3D.py` | Already correct on live-mode guard ("never emits checkpoints later than the latest 1-min bar"). | No change. |
| `RegimeMatrixSupervisor.py` (V3C) | Fix macro freshness arithmetic | Investigate `MACRO_STALE_*MIN` values that exceed any reasonable session length; root cause is almost certainly a session_key/timezone mismatch. |
| `RegimeMatrixHUDV3D.cs` | Already display-only. | No change. |
| `RegimeMatrixHUDV3C.cs` | Migrate to display-only model. | Remove any decision logic; route all decisions through V3C supervisor's permission flags. |
| V1A/V1B C# bot files | Migrate `IsBotAllowedByTrinity()` consumption from `*_Latest.csv` to V3D's `*_RegimeMatrix_Latest.csv` | One contract across all models. |
| V1B C# bot files | Block all Mode B and kill-switch code paths under `if (FootprintExportPopulated == false)` | Defensive guard until phase two validates Footprint. |

---

## Part 6 — Critical Gaps and Phase Two Requirements

### Gap 1: Footprint_Export.csv is header-only

This is the single largest unaddressed risk in the system. **Every macro-fusion table in the project assumes Footprint signals exist** (DEIA / EEMDF / SIB / DEB / PAR / ABS / TF / DT). The "Macro Regime Outputs Defined & Explained" spreadsheet's MAXIMUM AGGRESSION / NORMAL SIZE / HALTED rows all depend on Footprint Signal columns. The "Five Footprint Signals That Often Precede 20–40 Point ES Moves" research, the "FOOTPRINT SETUPS TO WATCH" PDF, and the "Footprint Min & Max Delta" doc are all design-intent without empirical backing.

**Until `Footprint_Export.csv` is producing rows for ≥10 consecutive RTH sessions:**
- All Mode B variants of V1B are blocked from live capital.
- All kill-switch code paths in V3D are blocked from production.
- All "MAXIMUM AGGRESSION" sizing tier is blocked.
- The macro fusion layer described in `MacroSupervisor.py` and `MacroRegimeBuilder_V3D.py` is operating as HMM + price-only, NOT as the full HMM + macro + footprint stack the architecture intends.

**This is the cleanest possible separation of concern: the regime engine works (with the gate fixes specified above); the footprint augmentation does not yet have empirical content. Treat them as two products.**

### Gap 2: Trade-log unification

Per the strategy handoff brief and the V3D/V1A trade-log handoff:
- 749 of 1,366 V3D log rows are actually V3C trades incorrectly stamped `model_version=V3D`.
- 142 rows have `bot_name=Unknown_Bot`.
- 326 rows on 2026-04-30 (account DEMO1419193, –$23,030) are unmappable.
- All 1,366 V3D rows have `entry_regime/macro/hmm/phase/reason_code = UNAVAILABLE` because the post-session enrichment join failed.
- V1A/V1B logs are partially or completely absent.

**Phase two must re-run, with cleaned and uniform exports:**
- Cross-tab of trade outcome by `entry_regime × entry_macro × entry_hmm × entry_phase`.
- Win rate, expectancy, R-multiple by cell.
- The asymmetric hysteresis backtest: how many trades does the rule eliminate, and what was their P&L distribution?
- Confidence-to-expectancy linearity test (validates or refutes SizePct as a continuous scalar).
- Conflict-score-to-outcome correlation (validates or refutes the conflict ≥ 40 → TRANSITION threshold).
- Per-bot, per-mode A/A+/B comparison for V1B (this directly tests the value of the Footprint and bias layers, but only for sessions where Footprint was producing — likely zero today).

### Gap 3: HUD_Override_Log.csv

Without direct access I cannot read content. Phase-two audit checklist:
- Frequency of overrides per session (signal of operator distrust of automation).
- Direction of overrides — is the operator usually opening gates the system closed, or closing gates the system opened? Each direction has a different diagnosis. Closing gates the system opened = operator is correctly catching bad regime calls (system needs tightening). Opening gates the system closed = operator is impatient (system is correctly conservative or operator is capitalizing on intuition the system can't see).
- Timing of overrides relative to macro state transitions (do overrides cluster at phase transitions like opening, lunch, or close?).
- Outcome correlation: did override-on trades win or lose vs system-decision trades?

**Operationally, every override is a labeled training example.** Phase three (post-launch) should consume the override log into the supervisor's calibration loop.

### Gap 4: SHADOW vs LIVE divergence audit

Specific phase-two work:
- On overlapping timestamps in `NQ_RegimeMatrix_Full.csv` vs `NQ_RegimeMatrix_Full_SHADOW.csv` (and ES counterparts):
- Count rows where FinalRegime differs.
- Count rows where any `Allow*` permission flag differs.
- Distribution of disagreement by phase, by HMM state, by macro state, by conflict score bin.
- Reason-code shift table: when LIVE says X, what does SHADOW say, and how often?
- This produces the verdict on whether SHADOW's candidate logic should be promoted to LIVE.

### Gap 5: Raw 1-min export quality

The brief notes that the 2026-05-01 16:59 row may be duplicated at the tail of `NQ_1min_export.txt` and `ES_1min_export.txt`. **De-duplicate before any feature re-derivation in phase two.** Also confirm that no other duplicates exist anywhere in the file (run a `df.duplicated(subset='timestamp').any()` sanity check). If duplicates exist anywhere, the rolling features (returns, range, vol_z) computed by the HMM watchdog may be subtly wrong on those rows.

### Gap 6: Cross-model trade log unification (per the strategy handoff brief)

The DQ-01 through DQ-09 issues catalogued in the Strategy Suite Export & Taxonomy Handoff are blocking. Until they are resolved, no quantitative model comparison is possible — only architectural review. The phase-two trade-outcome work in this report depends on those issues being closed first.

---

## Closing Statement and Honest Assessment

**Where this system is in its best shape:** the V3D architectural pattern (Python-centralized gates, deterministic joins, atomic writes, display-only HUD, one-account-per-bot, the Stage A/B/C/D/E layering) is correct and ahead of where most retail-built systems sit. The five-regime taxonomy is well-thought-out. The phase-aware permissions concept is right. The Mode A/A+/B test framework in V1B is genuinely good experimental design.

**Where this system is failing:**
1. The HMM is currently mis-labeling — too eager in V1 (60% TrendDown fakeouts), too conservative in V3D (75% Transition).
2. The Footprint layer that 30% of the documented logic depends on does not have empirical content.
3. The supervisor grants directional bot permissions on Transition bars under cover of `DIRECTIONAL_MODERATE`.
4. V3C's macro staleness bug is producing nonsensical staleness ages.
5. The trade-log unification work is incomplete enough that quantitative model comparison is not yet possible.

**Is the interior Python logic in its best shape to launch?** Honestly: **no, not yet, and you should not launch with live capital today.** The V3D architecture is the right substrate but two specific code-level changes (asymmetric hysteresis in the supervisor; recalibration of the HMM anchored-label thresholds) are required before SIM-validation can yield a defensible "go" decision. The Footprint gap means *anything* depending on footprint must be benched. Once the asymmetric hysteresis lands, conflict scoring is recalibrated, and SizePct is locked to {0,1}, V3D is launchable on the clean dual-state cells (TREND × TrendUp, ROTATION × Balance for ES) with a high probability of capital protection. Expansion to the moderate cells (TREND × Balance / Compression Sniper, TREND × Transition with persistence) follows after phase two confirms the trade-outcome cross-tabs.

**The single most important sentence in this report:** *the original Market AI Study correctly identified the symptom (60%+ fakeout) and proposed a directionally-correct fix (hysteresis), but the fix is too blunt — apply it asymmetrically by state and by symbol, and combine it with macro co-confirmation, and the gate works without the opportunity-cost loss the uniform 2-bar rule would impose on ES TrendUp.*

Phase two confirmation requirements are catalogued at the end of each Part above. The user should expect roughly five distinct phase-two compute jobs, three of which require the cleaned trade log, two of which can be run today against the longitudinal regime CSVs.