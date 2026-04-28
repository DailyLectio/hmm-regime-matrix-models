# Fader_V3D — Strategy Summary & Operator Reference
**Document path:** `C:\Users\Valued Customer\NT8_Regimes\V3D\Docs\Fader_V3D_Summary.md`
**Version:** 1.0  |  Applies to: `Fader_V3D.cs` (Version A) and `Fader_V3D_B.cs` (Version B)

---

## Executive Summary

Fader_V3D is the mean-reversion bot of the V3D model. It exists to capture edge-to-VWAP
rotations on confirmed two-sided auction days — sessions where price is oscillating within
a defined range, both buyers and sellers are active, and the structural edges (IB boundaries,
Prior Day Value Area) are acting as reliable rejection points.

The core mechanic is structural edge proximity combined with reversal bar confirmation.
Where a trend bot looks for price breaking out and holding, the Fader looks for price
reaching a structural boundary and reversing. The entry requires three things to agree
simultaneously: price must be near a known structural edge, price must have been trending
into that edge on the prior bar (a red bar for a long fade, a green bar for a short fade),
and price must reverse on the current bar (a green bar closing above its open for long,
red for short). This three-layer confirmation prevents chasing reversal entries in the
middle of the range where there is no structural justification.

The Bollinger band is a secondary confirmation only. It is used as a fallback when the
supervisor has not yet populated the IB and PD Value Area fields. When structural levels
are available — which is the designed operating state — Bollinger is informational only.

The two-leg structure separates quick profit capture from patience. Leg1 targets 50% of
the distance from entry to VWAP — a high-probability near-target that converts the trade
to a free position as soon as it fills. Leg2 targets full VWAP, giving the trade room to
complete the rotation all the way to the session's fair value center.

**Version A** uses a fixed VWAP target at entry time. The Leg2 target does not change
after the trade is opened.
**Version B** tracks VWAP dynamically. When the supervisor updates `SessionVWAP`, the
Leg2 profit target is recalculated and resubmitted if VWAP has moved by more than the
configured threshold.

---

## Where This Strategy Lives

### Chart Type — 1-Minute Candles (Required)

This strategy is designed for standard 1-minute candles. UniRenko is not appropriate
because the reversal bar logic (`wasRed && greenBar`) relies on time-based bar construction
— UniRenko bars complete on price movement, not time, which can produce misleading bar
color signals for a mean-reversion entry pattern.

### Instruments

| Instrument | TickValueDollars | Notes |
|---|---|---|
| NQ  | 5.00  | Primary. NQ's wide ATR creates larger edge-to-VWAP distance — better targets. |
| MNQ | 0.50  | Use when dollar risk calculation produces very small max contracts. |
| ES  | 12.50 | Secondary. ES tends to have tighter rotation ranges — adjust MinTargetTicks. |
| MES | 1.25  | Micro fallback for ES when ATR stop exceeds dollar risk ceiling. |

### Apex Account Assignment

| Account | Instrument | Version |
|---|---|---|
| Acc-NQ-3 | NQ / MNQ | Fader_V3D (A or B per test plan) |
| Acc-ES-3 | ES / MES | Fader_V3D (A or B per test plan) |

---

## Pre-Flight Checklist — Required Before Enabling

The Python pipeline, LiveDataExporter, and RegimeMatrixHUD_V3D requirements are identical
to all V3D bots. See `Expansion_V3D_Summary.md` Section "Pre-Flight Checklist" for the
full shared tree. The Fader-specific additions are below.

```
FADER-SPECIFIC REQUIREMENTS (in addition to shared pre-flight)
│
├── F1. Confirm IB and PD Value Area fields are populated in Latest.csv
│       Open NQ_RegimeMatrix_Latest.csv in a text editor
│       Check that IBHigh, IBLow, PDVAH, PDVAL columns contain non-zero values
│       If all are zero: structural edge detection will fall back to Bollinger only
│       (functional but not optimal — investigate supervisor configuration)
│
├── F2. Confirm TwoSidedFlag column exists in Latest.csv
│       The Fader requires this field — if missing, every entry will be blocked
│
├── F3. Confirm AllowFadeLong and AllowFadeShort columns exist
│       These are separate from AllowLong / AllowShort
│       If absent, the bot will never get permission to trade
│
└── F4. Time filter check
        Default window: 10:35–15:55 (post-IB formation through late day)
        The first 65 minutes (09:30–10:35) are excluded because IB is still forming —
        there are no defined IB edges to fade during that window.
        Adjust StartTime if you want to allow earlier entries on known-rotation days.
```

---

## Parameter Reference

### Group 1 — Regime

| Parameter | Default | Required | Notes |
|---|---|---|---|
| DataFolderPath | `C:\...\V3D` | Must set | Path to V3D folder with Latest.csv files |

### Group 2 — Risk

| Parameter | Default | Notes |
|---|---|---|
| ATR Stop Multiplier | 1.25 | Stop placed 1.25 ATR outside the structural edge. Wider than expansion (1.5) because rotation trades have more structural backing — the edge itself is the stop reference. |
| ATR Period | 14 | Standard 14-period ATR. |
| Edge Proximity (ATR) | 0.5 | Price must be within 0.5 ATR of a structural edge. Tighten to 0.3 for cleaner entries, loosen to 0.75 if too many missed setups. |
| Min Target Ticks | 10 | Minimum ticks from entry to VWAP for a trade to qualify. NQ default 10 = 2.5 points. Increase to 15–20 if getting too many marginal setups. |
| Tick Value ($) | 5.00 | NQ=5.00, ES=12.50, MNQ=0.50, MES=1.25. Must match instrument. |

### Group 3 — Signal

| Parameter | Default | Notes |
|---|---|---|
| Bollinger Period | 20 | Used as secondary fallback only when structural levels unavailable. Standard 20. |
| Bollinger StdDev | 2.0 | Standard 2 SD Bollinger. Wider bands = fewer but more extreme entries. |
| Min VWAP Move to Update (Version B only) | 4 ticks | VWAP must move at least 4 ticks before the Leg2 target is recalculated. Prevents excessive target updates on VWAP micro-drifts. |

### Group 4 — Guards

| Parameter | Default | Notes |
|---|---|---|
| Max Consecutive Losses | 2 | Same pattern as all V3D bots. Resets at session start. |
| Daily P&L Goal ($) | 0 (off) | Stop new entries after daily profit target. |
| Daily Loss Limit ($) | 0 (off) | Stop new entries after daily loss ceiling. Recommended: set to 1.5× average losing trade. |

### Group 5 — Time

| Parameter | Default | Notes |
|---|---|---|
| Enable Time Filter | true | Should almost always be true. |
| Start Time | 103500 | 10:35 ET — after IB formation. Change to 093500 only if explicit pre-IB fade setups are in the test plan. |
| End Time | 155500 | 15:55 ET — stops before cash close. |

---

## Operating Conditions — When This Bot Should Fire

| Condition | Required | Notes |
|---|---|---|
| FinalRegime | ROTATION_LIQUID | Hard gate. No entries in EXPANSION, COMPRESSION, ILLIQUID, or TRANSITION. |
| TwoSidedFlag | 1 | Auction must have traded both sides. This prevents fading what is actually a directional day with retracements. |
| AllowFadeLong or AllowFadeShort | Must match direction | Python supervisor controls. Bot uses fade-specific permissions, not trend direction flags. |
| Near structural edge | Required (or Bollinger fallback) | Entry must have structural justification. Middle-of-range entries are filtered out. |
| Reversal bar pattern | Required | Prior bar into edge (red for long, green for short) + current bar reversing. |
| distToVwap >= MinTargetTicks | Required | No trade if VWAP is too close to make a sensible risk/reward. |
| Within time window | Required | No fades before IB is formed. |
| faderSizePct > 0 | Required | Zero means supervisor has not approved fade sizing. |

---

## Typical Day Behavior

**On a true rotation day** (IB forming, two-sided activity, VWAP as magnet):
The Fader fires when price tests IB high or IB low and shows a reversal bar. Typically
1–3 setups per session. Leg1 hits quickly as price pulls back toward VWAP. Leg2 may
require patience — VWAP rotations can take 30–60 minutes to complete.

**On a trend day** (misclassified or early before trend asserts):
The regime will not be ROTATION_LIQUID once the trend is confirmed. If a trade was
entered during a ROTATION period and the regime shifts to TRANSITION, the TRANSITION exit
fires immediately. If it shifts to ROTATION_ILLIQUID (dead market), the ILLIQUID exit
fires. The bot is designed to get out when the structural basis for the fade no longer exists.

**On a day where structural levels are zero** (supervisor not yet providing them):
The bot falls back to Bollinger band edges. The Print line will show `BOLLINGER_FALLBACK`
as the trigger. This is a functional state but produces lower-quality entries than the
structural edge system. Investigate why IB and PD Value Area fields are zero in Latest.csv.

---

## A/B Test Protocol

| Item | Version A | Version B |
|---|---|---|
| File | Fader_V3D.cs | Fader_V3D_B.cs |
| Leg1 behavior | Identical | Identical |
| Leg2 target | Fixed at entry VWAP | Updates dynamically when VWAP moves ≥ threshold |
| Account | Acc-NQ-3 | Separate SIM account |

**What to measure** (focus on Leg2 outcomes specifically):

1. Leg1 win rate — should be identical between A and B
2. Leg2 win rate — this is where the versions will diverge
3. Average Leg2 outcome in ticks
4. Days where Leg2 was wrong direction: did B exit earlier than A?
5. Days where rotation completed cleanly: did B hold longer or shorter than A?

**Decision rule:**
If B's Leg2 average outcome > A's Leg2 average outcome by more than 0.5 ATR: promote B.
If results are within noise: keep A (simpler is better when outcomes are equivalent).

---

## Key Differences from Prior V3C Faders (V3ValueFader)

| Feature | V3ValueFader (prior) | Fader_V3D |
|---|---|---|
| Primary edge reference | Bollinger band only | Structural levels (IB, PD VAH/VAL) primary |
| Direction permission | AllowLong / AllowShort | AllowFadeLong / AllowFadeShort (separate) |
| Regime source | Stage A macro CSV (last line, positional) | V3D Latest.csv (header-driven) |
| SizePct | Not implemented | AllowPine_SizePct from supervisor |
| Runner management | None — fixed targets only | Free-trade pivot after Leg1 + ILLIQUID exit |
| ROTATION_ILLIQUID exit | None | Immediate runner exit |
| Daily guards | None | Optional DailyGoal / DailyLossLimit |
| Diagnostic Print | None | Full entry detail to NT8 Output window |

---

## Session Checklist (Operator Daily)

### Before session (5 minutes)
- [ ] Python pipeline running — check LastModified on Latest.csv files (< 35 min)
- [ ] HUD shows FRESH
- [ ] Open Latest.csv — confirm IBHigh, IBLow, PDVAH, PDVAL are non-zero
- [ ] Confirm TwoSidedFlag and AllowFadeLong/AllowFadeShort columns present

### During session
- Fader is a passive bot — it waits for structural edge tests.
- Do not expect entries at open. The IB must form first (before 10:35 start time).
- Check NT8 Output window periodically for `[Fader_V3D-A]` Print lines.
- If the HUD shows TREND_EXPANSION, this bot is correctly silent.

### After session (5 minutes)
- Export trade log — note Leg1 vs Leg2 outcomes separately for A/B tracking
- Check for any `BOLLINGER_FALLBACK` entries — if frequent, investigate structural level fields
- Flag any entry where `TwoSidedFlag` was 0 at entry (should never happen — indicates a bug)

---

*End of Fader_V3D_Summary.md — Version 1.0*
