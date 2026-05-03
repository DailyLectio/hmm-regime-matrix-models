# V3D Institutional Regime Matrix — NQ Master Setup & Test Checklist
**Document path:** `C:\Users\Valued Customer\NT8_Regimes\V3D\Docs\V3D_NQ_Master_Checklist.md`
**Instrument:** NQ / MNQ
**Version:** 1.0 | Status: SIM testing phase

---

## System Prerequisites — Complete Once Before First Session

These steps are one-time setup tasks. Confirm each is complete before proceeding to
daily session checklists.

### P1. Folder Structure
Confirm all folders exist at the correct paths:
- [ ] `C:\Users\Valued Customer\NT8_Regimes\Exports\` — NQ_1min_export.txt present
- [ ] `C:\Users\Valued Customer\NT8_Regimes\V3D\` — working directory for all V3D outputs
- [ ] `C:\Users\Valued Customer\NT8_Regimes\V3D\History\` — history log folder
- [ ] `C:\Users\Valued Customer\NT8_Regimes\V3D\Docs\` — this document and summaries
- [ ] `C:\Users\Valued Customer\NT8_Regimes\Overrides\` — HUD override log folder
- [ ] `C:\Users\Valued Customer\NT8_Regimes\Active\` — V3C era files (kept separate)
- [ ] `C:\Users\Valued Customer\NT8_Regimes\V3C\` — V3C latest files

### P2. Python Pipeline — Installed and Verified
- [ ] Python 3.10+ installed, packages: `pandas`, `numpy`, `hmmlearn`, `scikit-learn`
- [ ] `MacroRegimeBuilder_V3D.py` placed in `C:\V3D\Scripts\`
- [ ] `HMM_Watchdog_V3D.py` placed in `C:\V3D\Scripts\`
- [ ] `RegimeSupervisor_V3D.py` placed in `C:\V3D\Scripts\`
- [ ] Run_V3D_Pipeline.bat placed in `C:\V3D\`
- [ ] Junction `C:\V3D` → `C:\Users\Valued Customer\NT8_Regimes` created (run as Admin)
- [ ] Batch run completed: `Run_V3D_Pipeline.bat batch` — all four CSV files generated in V3D folder

### P3. NT8 Indicators — Compiled and Available
- [ ] `LiveDataExporter` compiled in NT8 (indicator, not strategy)
- [ ] `ValueAreaExporter` compiled in NT8 (indicator, daily chart)
- [ ] `RegimeMatrixHUD_V3D` compiled in NT8 (indicator)
- [ ] All five strategy files compiled: `Expansion_V3D`, `Momentum_V3D`, `Fader_V3D`, `Sniper_V3D`, `ADX_DI_V3D`
- [ ] All A/B variant files compiled: `Expansion_V3D_B`, `Momentum_V3D_B`, `Fader_V3D_B`, `Sniper_V3D_B`, `ADX_DI_V3D_B`, `ADX_DI_V3D_C`

### P4. Apex SIM Accounts — Assigned
One dedicated Apex 50k EOD SIM account per strategy per instrument:

| Account Label | Strategy | Bot File | A/B Assignment |
|---|---|---|---|
| Acc-NQ-1A | Expansion_V3D | Expansion_V3D.cs | Version A (momentum-first) |
| Acc-NQ-1B | Expansion_V3D_B | Expansion_V3D_B.cs | Version B (velocity-confirm) |
| Acc-NQ-2A | Momentum_V3D | Momentum_V3D.cs | Version A (single-leg) |
| Acc-NQ-2B | Momentum_V3D_B | Momentum_V3D_B.cs | Version B (confidence runner) |
| Acc-NQ-3A | Fader_V3D | Fader_V3D.cs | Version A (fixed VWAP target) |
| Acc-NQ-3B | Fader_V3D_B | Fader_V3D_B.cs | Version B (dynamic VWAP) |
| Acc-NQ-4A | Sniper_V3D | Sniper_V3D.cs | Version A (3-bar coherent) |
| Acc-NQ-4B | Sniper_V3D_B | Sniper_V3D_B.cs | Version B (2-bar strict) |
| Acc-NQ-5A | ADX_DI_V3D | ADX_DI_V3D.cs | Version A (fixed target) |
| Acc-NQ-5B | ADX_DI_V3D_B | ADX_DI_V3D_B.cs | Version B (no target) |
| Acc-NQ-5C | ADX_DI_V3D_C | ADX_DI_V3D_C.cs | Version C (full Gu5 unified) |

---

## NT8 Workspace Setup — V3D NQ Test Workspace

### Workspace Name
`V3D_NQ_Test` — separate from V3C and V3B workspaces

### Chart Layout
All charts are small tiles. The workspace displays all 11 NQ charts simultaneously.
Suggested layout: 4-column grid, 3 rows (12 slots — 11 charts + 1 HUD monitor).

---

## Chart Specifications — NQ

### Chart 1 — NQ LiveData + HUD Reference
**Template name:** `V3D_NQ_LiveData`
**Purpose:** Data feed + master HUD display. Always visible.

| Setting | Value |
|---|---|
| Instrument | NQ (continuous) |
| Timeframe | 1-minute |
| Session | RTH only (09:30–16:00 ET) |
| Calculate | OnBarClose |
| Indicators | LiveDataExporter (data feed — must be active) |
| Indicators | RegimeMatrixHUD_V3D (display, DataFolderPath = V3D folder) |
| Strategies | None |

**Confirm before session:**
- LiveDataExporter is appending to `NQ_1min_export.txt`
- HUD panel shows `FRESH` status
- HUD shows FinalRegime and FinalDirection populated (not UNKNOWN)

---

### Charts 2–3 — Expansion_V3D A and B
**Template name:** `V3D_NQ_Expansion_A` / `V3D_NQ_Expansion_B`
**Regime target:** TREND_EXPANSION only
**Signal:** UniRenko brick physics + WaitBricks hysteresis

| Setting | Version A | Version B |
|---|---|---|
| Instrument | NQ (continuous) | NQ (continuous) |
| Timeframe | UniRenko | UniRenko |
| Brick size | 10–20 pts (test 10 first) | Same as A |
| Session | RTH only | RTH only |
| Calculate | OnBarClose | OnBarClose |
| Strategy | Expansion_V3D | Expansion_V3D_B |
| Account | Acc-NQ-1A | Acc-NQ-1B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | 5.00 | 5.00 |
| AtrMultiplier | 1.5 | 1.5 |
| WaitBricks | 3 | 3 |
| MinConfidence | 75 | 75 |
| MinVelocityAtr | — | 0.5 |
| TickTrailAtr | 1.25 | 1.25 |
| TickTrailAtrDegraded | 0.75 | 0.75 |

**A/B difference:** Version B adds Gate 10 — `abs(Velocity3P_ATR) >= MinVelocityAtr` before entry.

**What to watch in Output window:** `[Expansion_V3D-A]` and `[Expansion_V3D-B]` entry prints.

---

### Charts 4–5 — Momentum_V3D A and B
**Template name:** `V3D_NQ_Momentum_A` / `V3D_NQ_Momentum_B`
**Regime target:** TREND_COMPRESSION (primary), TREND_EXPANSION (secondary)
**Signal:** DI cross + CI threshold + ADX floor + slope exit

| Setting | Version A | Version B |
|---|---|---|
| Instrument | NQ (continuous) | NQ (continuous) |
| Timeframe | 1-minute | 1-minute |
| Session | RTH only | RTH only |
| Calculate | OnPriceChange | OnPriceChange |
| Strategy | Momentum_V3D | Momentum_V3D_B |
| Account | Acc-NQ-2A | Acc-NQ-2B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | 5.00 | 5.00 |
| AtrStopMult | 0.75 | 0.75 |
| RiskReward | 1.5 | 1.5 (Leg2) |
| CiMaxCompression | 58 | 58 |
| CiMaxExpansion | 50 | 50 |
| AdxEntryThreshold | 18 | 18 |
| MinConfidence | 65 | 65 |
| SlopeExit | Hysteresis | Hysteresis |
| Leg1TargetMult | — | 0.75 |
| ConfidenceScaleThreshold | — | 80 |

**A/B difference:** Version B adds a second leg (Leg2 runner) when RegimeConfidence >= 80.

**What to watch:** `[Momentum_V3D-A]` prints — check CI, ADX, Conflict values. Version B prints `Leg2: YES` or `NO`.

---

### Charts 6–7 — Fader_V3D A and B
**Template name:** `V3D_NQ_Fader_A` / `V3D_NQ_Fader_B`
**Regime target:** ROTATION_LIQUID only — bidirectional
**Signal:** Structural edge proximity + Bollinger fallback + reversal bar

| Setting | Version A | Version B |
|---|---|---|
| Instrument | NQ (continuous) | NQ (continuous) |
| Timeframe | 1-minute | 1-minute |
| Session | RTH only | RTH only |
| Calculate | OnBarClose | OnBarClose |
| Strategy | Fader_V3D | Fader_V3D_B |
| Account | Acc-NQ-3A | Acc-NQ-3B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | 5.00 | 5.00 |
| AtrStopMult | 1.25 | 1.25 |
| EdgeProximityAtr | 0.5 | 0.5 |
| MinTargetTicks | 10 | 10 |
| StartTime | 103500 | 103500 |
| EndTime | 155500 | 155500 |
| VwapUpdateThresholdTicks | — | 4 |

**A/B difference:** Version B tracks VWAP dynamically — Leg2 target updates when VWAP moves >= threshold ticks.

**What to watch:** `[Fader_V3D-A]` prints — note `EDGE:` vs `BOLLINGER_FALLBACK` trigger. If BOLLINGER_FALLBACK appears frequently, structural level fields in Latest.csv need investigation.

---

### Charts 8–9 — Sniper_V3D A and B
**Template name:** `V3D_NQ_Sniper_A` / `V3D_NQ_Sniper_B`
**Regime target:** TREND_COMPRESSION — dip-buy / rip-sell
**Signal:** EMA(9) / EMA(21) dip/rip pattern

| Setting | Version A | Version B |
|---|---|---|
| Instrument | NQ (continuous) | NQ (continuous) |
| Timeframe | 1-minute | 1-minute |
| Session | RTH only | RTH only |
| Calculate | OnBarClose | OnBarClose |
| Strategy | Sniper_V3D | Sniper_V3D_B |
| Account | Acc-NQ-4A | Acc-NQ-4B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | 5.00 | 5.00 |
| TargetAtr | 0.75 | 0.75 |
| StopAtr | 1.0 | 1.0 |
| FastEmaPeriod | 9 | 9 |
| SlowEmaPeriod | 21 | 21 |
| IbExtensionMin | 0.35 | 0.35 |
| IbExtensionMax | 0.80 | 0.80 |
| MinConfidence | 60 | 60 |

**A/B difference:** Version A allows 3-bar coherent dip (bar[2] dip OK if bar[1] still compressed). Version B requires strict adjacent 2-bar: both dip and compression on bar[1], recovery bar[0].

**What to watch:** Version A prints `DIP_BAR1` or `DIP_BAR2` — tally these separately each week to determine which pattern drives better outcomes.

---

### Charts 10–11–12 — ADX_DI_V3D A, B, and C
**Template name:** `V3D_NQ_ADXDI_A` / `V3D_NQ_ADXDI_B` / `V3D_NQ_ADXDI_C`
**Regime target:** ROTATION_LIQUID (primary), TREND_COMPRESSION edges (secondary)
**Signal:** Wilder DI cross + dynamic ADX floor

| Setting | Version A | Version B | Version C |
|---|---|---|---|
| Instrument | NQ (continuous) | NQ (continuous) | NQ (continuous) |
| Timeframe | 3-minute | 3-minute | 3-minute |
| Session | RTH only | RTH only | RTH only |
| Calculate | OnPriceChange | OnPriceChange | OnPriceChange |
| Strategy | ADX_DI_V3D | ADX_DI_V3D_B | ADX_DI_V3D_C |
| Account | Acc-NQ-5A | Acc-NQ-5B | Acc-NQ-5C |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | 5.00 | 5.00 | 5.00 |
| AtrMultiplier | 1.0 | 1.0 | 1.0 |
| RiskReward | 1.0 | — (no target) | — (no target) |
| AdxFloorFallback | 20 | 20 | — |
| MinDiGap | 5.0 | 5.0 | — |
| LevelRange | — | — | 20 (chop gate) |
| LevelTrend | — | — | 35 (strong entry) |
| AllowWeakEntry | — | — | true |
| MinConfidence | 55 | 55 | 55 |

**A/B/C differences:**
- Version A: hybrid (manual DI + built-in ADX floor), fixed 1:1 ATR target
- Version B: hybrid (manual DI + built-in ADX floor), no fixed target — pure StopX + trail
- Version C: fully unified Gu5 — manual DI + manual sig computed from same DI series, condition state machine (±1.0 strong, ±0.5 weak, 0 exit), no fixed target, `hlRange` chop gate

**What to watch in Output window:**
- A: `[ADX_DI_V3D-A]` — check ADX level, Floor, DiGap at each entry
- B: `[ADX_DI_V3D-B]` — note trade durations vs A's target hits
- C: `[ADX_DI_V3D-C]` — note `Strength: STRONG` vs `Strength: WEAK` entries; `Sig:` value shows unified ADX

---

## Daily Session Checklist — NQ

### Pre-Session (5 minutes before 09:30 ET)

**Step 1 — Python pipeline**
- [ ] Run `Run_V3D_Pipeline.bat live` if not already running (two console windows open)
- [ ] Confirm `NQ_RegimeMatrix_Latest.csv` LastModified < 35 minutes ago
- [ ] Open Latest.csv — FinalRegime is not UNKNOWN, StaleDataFlag is 0

**Step 2 — Critical columns verification**
Open `C:\Users\Valued Customer\NT8_Regimes\V3D\NQ_RegimeMatrix_Latest.csv` in a text editor.
Confirm these columns contain non-zero values:

| Column | Required for | Action if zero |
|---|---|---|
| IBWidthATR | Fader, ADX_DI | Supervisor not projecting IB fields — investigate |
| SuggestedAdxMin | Momentum, ADX_DI | Falls back to static threshold — acceptable |
| Velocity3P_ATR | Expansion B, Momentum | Velocity gate disabled — acceptable |
| TwoSidedFlag | Fader, ADX_DI | May block rotation entries — check market structure |
| FinalDirection | Sniper, Momentum | Must be LONG or SHORT, not NEUTRAL, on compression days |
| IBExtensionPct | Sniper | Must be 0.35–0.80 for Sniper to fire after 10:35 |

**Step 3 — HUD verification**
- [ ] Chart 1 (LiveData) HUD panel shows `FRESH`
- [ ] FinalRegime populated
- [ ] FinalDirection populated

**Step 4 — Strategy accounts**
- [ ] All 11 NQ strategy charts visible in V3D_NQ_Test workspace
- [ ] Correct Apex SIM account assigned per chart (verify account label matches table above)
- [ ] All strategies show `Enabled` in NT8

---

### During Session

**HUD is your primary display.** Watch Chart 1.

Intervene with the kill-all button only for:
- Scheduled FOMC/CPI/news not reflected in price data
- HUD shows `STALE` mid-session (Python stopped writing)
- NT8 chart freeze or order error
- Circuit breaker halt or flash crash

Do not second-guess regime classification under normal conditions.

---

### Post-Session (5 minutes after 16:00 ET)

**Step 1 — Trade log export**
Export each strategy's trade log from NT8 Control Center → Account Performance.
File-naming convention: `NQ_[BotName]_[Version]_[YYYYMMDD].csv`
Examples: `NQ_Expansion_A_20260501.csv`, `NQ_ADXDI_C_20260501.csv`

**Step 2 — NT8 Output window review**
For each strategy, scroll the Output window and note:
- Entry count
- Any unexpected regime values (FinalRegime ≠ expected)
- Any `BOLLINGER_FALLBACK` entries in Fader (structural levels not populating)
- ADX / DiGap values at ADX_DI entries — flag if DiGap < 7 at entry

**Step 3 — A/B tracking log**
Update the weekly A/B tracking spreadsheet:

| Entry | Version A count | Version B count | Version C count |
|---|---|---|---|
| Expansion today | | | — |
| Momentum today | | | — |
| Fader today | | | — |
| Sniper DIP_BAR1 | — | | — |
| Sniper DIP_BAR2 | — | | — |
| ADX_DI today | | | |

---

## Weekly A/B Test Review Protocol

Perform each Friday after the session. Minimum 4 weeks of data before drawing conclusions.

### Expansion A vs B
**Question:** Does the velocity confirmation gate (Version B) improve win rate without reducing trade count too severely?
- Compare weekly: entry count, win rate, average R per trade
- B should have fewer entries. Acceptable if win rate compensates.
- **Promote B if:** win rate B > win rate A AND B entry count >= 60% of A
- **Keep A if:** win rate difference < 5% or B entry count < 50% of A

### Momentum A vs B
**Question:** Does the Leg2 confidence runner add expectancy proportional to its size cost?
- Track `Leg2: YES` vs `Leg2: NO` entries in Version B separately
- **Promote B if:** high-confidence Leg2 trades have materially better overall R than single-leg A trades
- **Keep A if:** no material difference or Leg2 win rate materially below Leg1 win rate

### Fader A vs B
**Question:** Does dynamic VWAP tracking improve Leg2 outcomes?
- Compare Leg2 average outcome only (Leg1 should be identical)
- **Promote B if:** B Leg2 average outcome > A by more than 0.5 ATR
- **Keep A if:** within noise

### Sniper A vs B
**Question:** Does strict 2-bar adjacent dip produce better quality entries?
- From Version A Output log, tally DIP_BAR1 vs DIP_BAR2 entries and their outcomes
- **Promote B if:** DIP_BAR2 win rate in A is materially lower than DIP_BAR1 win rate
- **Keep A if:** DIP_BAR1 and DIP_BAR2 outcomes are similar — lookback is adding real setups

### ADX_DI A vs B vs C
**Question 1 (A vs B):** Does removing the fixed target allow winners to run further, improving expectancy?
- Compare average winner in R-multiples. B should show longer winning trades.
- **Promote B over A if:** B average winner > 1.5× A average winner

**Question 2 (C vs A):** Does the full Gu5 unified signal (chop gate, sigUp, condition state machine) produce better quality entries than the raw DI cross?
- Compare win rate C vs A. C should have fewer entries but higher win rate.
- **Promote C if:** C win rate > A win rate by more than 5% over 50+ trades

**Question 3 (C vs B):** Best overall — unified signal + no fixed target vs hybrid + no target?
- Compare C vs B expectancy per trade
- If C > B: full Gu5 architecture is the production candidate

---

## File and Template Taxonomy Summary

### NT8 Workspaces
| Workspace | Purpose |
|---|---|
| `V3D_NQ_Test` | NQ SIM testing — all 11 NQ A/B/C charts |
| `V3C_NQ_Live` | V3C NQ production (runs concurrently for comparison) |
| `V3B_NQ_Archive` | V3B retired — do not enable |

### NT8 Chart Templates (NQ)
| Template | Chart | Strategy | Version |
|---|---|---|---|
| `V3D_NQ_LiveData` | 1-min NQ | None (indicators only) | — |
| `V3D_NQ_Expansion_A` | UniRenko NQ | Expansion_V3D | A |
| `V3D_NQ_Expansion_B` | UniRenko NQ | Expansion_V3D_B | B |
| `V3D_NQ_Momentum_A` | 1-min NQ | Momentum_V3D | A |
| `V3D_NQ_Momentum_B` | 1-min NQ | Momentum_V3D_B | B |
| `V3D_NQ_Fader_A` | 1-min NQ | Fader_V3D | A |
| `V3D_NQ_Fader_B` | 1-min NQ | Fader_V3D_B | B |
| `V3D_NQ_Sniper_A` | 1-min NQ | Sniper_V3D | A |
| `V3D_NQ_Sniper_B` | 1-min NQ | Sniper_V3D_B | B |
| `V3D_NQ_ADXDI_A` | 3-min NQ | ADX_DI_V3D | A |
| `V3D_NQ_ADXDI_B` | 3-min NQ | ADX_DI_V3D_B | B |
| `V3D_NQ_ADXDI_C` | 3-min NQ | ADX_DI_V3D_C | C |

### Strategy Files (NQ)
| File | Regime | Chart | Key distinction |
|---|---|---|---|
| `Expansion_V3D.cs` | TREND_EXPANSION | UniRenko | Momentum-first entry |
| `Expansion_V3D_B.cs` | TREND_EXPANSION | UniRenko | Velocity-confirmation entry |
| `Momentum_V3D.cs` | TREND_COMPRESSION | 1-min | Single-leg, slope exit |
| `Momentum_V3D_B.cs` | TREND_COMPRESSION | 1-min | Two-leg confidence runner |
| `Fader_V3D.cs` | ROTATION_LIQUID | 1-min | Fixed VWAP target |
| `Fader_V3D_B.cs` | ROTATION_LIQUID | 1-min | Dynamic VWAP target |
| `Sniper_V3D.cs` | TREND_COMPRESSION | 1-min | 3-bar coherent dip |
| `Sniper_V3D_B.cs` | TREND_COMPRESSION | 1-min | 2-bar strict adjacent dip |
| `ADX_DI_V3D.cs` | ROTATION_LIQUID | 3-min | Hybrid DI, fixed target |
| `ADX_DI_V3D_B.cs` | ROTATION_LIQUID | 3-min | Hybrid DI, no target |
| `ADX_DI_V3D_C.cs` | ROTATION_LIQUID | 3-min | Full Gu5 unified, no target |

### V3D Folder Contents (NQ files)
| File | Stage | Updated |
|---|---|---|
| `NQ_1min_export.txt` | Raw data | Continuously by LiveDataExporter |
| `NQ_Macro_Regimes_V3D.csv` | Stage A | Every 30s by MacroRegimeBuilder |
| `NQ_HMM_Regimes_V3D.csv` | Stage B | Every 5+ new bars by HMM Watchdog |
| `NQ_RegimeMatrix_Latest.csv` | Stage C | Every 30s by Supervisor |
| `NQ_RegimeMatrix_History.csv` | Archive | Appended by Supervisor |

### Python Scripts
| Script | Function | Run mode for live |
|---|---|---|
| `MacroRegimeBuilder_V3D.py` | Stage A macro regime | `--live --interval 30` |
| `HMM_Watchdog_V3D.py` | Stage B HMM | `--live --interval 30` |
| `RegimeSupervisor_V3D.py` | Stage C consensus | `--loop --interval 30` |
| `Run_V3D_Pipeline.bat` | Launcher for all three | `live` (double-click default) |

---

*End of V3D_NQ_Master_Checklist.md — Version 1.0*
*Update this document when: chart templates are created, account labels are assigned, or A/B decisions are made.*
