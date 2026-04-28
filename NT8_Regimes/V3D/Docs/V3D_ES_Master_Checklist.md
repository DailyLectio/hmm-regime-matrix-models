# V3D Institutional Regime Matrix — ES Master Setup & Test Checklist
**Document path:** `C:\Users\Valued Customer\NT8_Regimes\V3D\Docs\V3D_ES_Master_Checklist.md`
**Instrument:** ES / MES
**Version:** 1.0 | Status: SIM testing phase

---

## System Prerequisites — Complete Once Before First Session

These steps are shared with the NQ setup. If the NQ checklist has been completed, only
ES-specific items below need separate verification.

### P1. ES Export File
- [ ] `C:\Users\Valued Customer\NT8_Regimes\Exports\ES_1min_export.txt` exists
- [ ] LiveDataExporter applied to a separate ES 1-minute chart

### P2. Python Pipeline — ES Outputs Verified
After running `Run_V3D_Pipeline.bat batch`, confirm these files exist in the V3D folder:
- [ ] `ES_Macro_Regimes_V3D.csv`
- [ ] `ES_HMM_Regimes_V3D.csv`
- [ ] `ES_RegimeMatrix_Latest.csv`

### P3. ES NT8 Indicators and Strategies
Same compiled files as NQ — all strategy files support both instruments via the
`GetLeaderSymbol()` mapping. No separate compilation needed for ES.
- [ ] Confirm `ValueAreaExporter` applied to an ES daily chart (produces `ValueArea_ES.csv`)

### P4. Apex SIM Accounts — ES Assigned

| Account Label | Strategy | Bot File | A/B Assignment |
|---|---|---|---|
| Acc-ES-1A | Expansion_V3D | Expansion_V3D.cs | Version A (momentum-first) |
| Acc-ES-1B | Expansion_V3D_B | Expansion_V3D_B.cs | Version B (velocity-confirm) |
| Acc-ES-2A | Momentum_V3D | Momentum_V3D.cs | Version A (single-leg) |
| Acc-ES-2B | Momentum_V3D_B | Momentum_V3D_B.cs | Version B (confidence runner) |
| Acc-ES-3A | Fader_V3D | Fader_V3D.cs | Version A (fixed VWAP target) |
| Acc-ES-3B | Fader_V3D_B | Fader_V3D_B.cs | Version B (dynamic VWAP) |
| Acc-ES-4A | Sniper_V3D | Sniper_V3D.cs | Version A (3-bar coherent) |
| Acc-ES-4B | Sniper_V3D_B | Sniper_V3D_B.cs | Version B (2-bar strict) |
| Acc-ES-5A | ADX_DI_V3D | ADX_DI_V3D.cs | Version A (fixed target) |
| Acc-ES-5B | ADX_DI_V3D_B | ADX_DI_V3D_B.cs | Version B (no target) |
| Acc-ES-5C | ADX_DI_V3D_C | ADX_DI_V3D_C.cs | Version C (full Gu5 unified) |

---

## ES-Specific Parameter Differences

ES behaves differently from NQ in several structural ways. The strategies are the same
code but several parameter defaults should be adjusted for ES:

### Key ES thresholds (from spec Section 4)
| Parameter | NQ default | ES default | Reason |
|---|---|---|---|
| TickValueDollars | 5.00 | 12.50 | ES tick value is 2.5× NQ |
| IB strong threshold | 0.85 | 1.00 | ES requires wider IB for trend |
| IB expanding threshold | 0.45 | 0.75 | ES is structurally wider |
| VWAP confirm threshold | 0.40 | 0.50 | ES VWAP separation threshold |
| Net move confirm threshold | 0.60 | 0.75 | ES requires more displacement |
| Velocity strong threshold | 0.85 | 1.00 | ES velocity measure |

These thresholds live in the Python supervisor and MacroRegimeBuilder — they affect what
`FinalRegime` the strategy bots receive. The bot parameters below reflect adjustments
needed at the C# level.

---

## NT8 Workspace Setup — V3D ES Test Workspace

### Workspace Name
`V3D_ES_Test` — separate from V3D_NQ_Test, V3C, and V3B workspaces

### Chart Layout
Same 4-column grid layout as NQ. 11 ES charts + 1 reference chart.

---

## Chart Specifications — ES

### Chart 1 — ES LiveData + HUD Reference
**Template name:** `V3D_ES_LiveData`

| Setting | Value |
|---|---|
| Instrument | ES (continuous) |
| Timeframe | 1-minute |
| Session | RTH only (09:30–16:00 ET) |
| Indicators | LiveDataExporter (ES export path auto-detected) |
| Indicators | RegimeMatrixHUD_V3D (DataFolderPath = V3D folder) |
| Strategies | None |

**Note:** The ES HUD reads `ES_RegimeMatrix_Latest.csv`. MES charts auto-map to ES file.

---

### Charts 2–3 — Expansion_V3D A and B
**Template name:** `V3D_ES_Expansion_A` / `V3D_ES_Expansion_B`

| Setting | Version A | Version B |
|---|---|---|
| Instrument | ES (continuous) | ES (continuous) |
| Timeframe | UniRenko | UniRenko |
| Brick size | 4–8 pts (start with 4) | Same as A |
| Session | RTH only | RTH only |
| Calculate | OnBarClose | OnBarClose |
| Strategy | Expansion_V3D | Expansion_V3D_B |
| Account | Acc-ES-1A | Acc-ES-1B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | **12.50** | **12.50** |
| AtrMultiplier | 1.5 | 1.5 |
| WaitBricks | 3 | 3 |
| MinConfidence | 75 | 75 |
| MinVelocityAtr | — | **1.0** (ES threshold) |

**ES note:** Use 4-point UniRenko bricks as the starting point. ES expansion days move
~30–60 points — 4-point bricks produce 7–15 bricks per clean expansion move, appropriate
for the WaitBricks=3 gate.

---

### Charts 4–5 — Momentum_V3D A and B
**Template name:** `V3D_ES_Momentum_A` / `V3D_ES_Momentum_B`

| Setting | Version A | Version B |
|---|---|---|
| Instrument | ES (continuous) | ES (continuous) |
| Timeframe | 1-minute | 1-minute |
| Session | RTH only | RTH only |
| Calculate | OnPriceChange | OnPriceChange |
| Strategy | Momentum_V3D | Momentum_V3D_B |
| Account | Acc-ES-2A | Acc-ES-2B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | **12.50** | **12.50** |
| AtrStopMult | 0.75 | 0.75 |
| RiskReward | 1.5 | 1.5 |
| CiMaxCompression | 58 | 58 |
| CiMaxExpansion | 50 | 50 |
| AdxEntryThreshold | 18 | 18 |
| VelocityReliefThreshold | **1.0** | **1.0** |
| MinConfidence | 65 | 65 |
| SlopeExit | Hysteresis | Hysteresis |

**ES note:** ES velocity threshold is 1.0 (vs NQ's 0.85) per spec Section 4 thresholds.
ES is structurally more deliberate — velocity must be stronger to confirm momentum.

---

### Charts 6–7 — Fader_V3D A and B
**Template name:** `V3D_ES_Fader_A` / `V3D_ES_Fader_B`

| Setting | Version A | Version B |
|---|---|---|
| Instrument | ES (continuous) | ES (continuous) |
| Timeframe | 1-minute | 1-minute |
| Session | RTH only | RTH only |
| Calculate | OnBarClose | OnBarClose |
| Strategy | Fader_V3D | Fader_V3D_B |
| Account | Acc-ES-3A | Acc-ES-3B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | **12.50** | **12.50** |
| AtrStopMult | 1.25 | 1.25 |
| EdgeProximityAtr | 0.5 | 0.5 |
| MinTargetTicks | **15** | **15** |
| StartTime | 103500 | 103500 |
| EndTime | 155500 | 155500 |
| VwapUpdateThresholdTicks | — | 4 |

**ES note:** ES MinTargetTicks should be raised to 15 (NQ default is 10). ES point values
are different — a 10-tick minimum on ES is only 2.5 points (too tight for a meaningful
edge-to-VWAP rotation target). 15 ticks = 3.75 points, more appropriate for ES rotation.

---

### Charts 8–9 — Sniper_V3D A and B
**Template name:** `V3D_ES_Sniper_A` / `V3D_ES_Sniper_B`

| Setting | Version A | Version B |
|---|---|---|
| Instrument | ES (continuous) | ES (continuous) |
| Timeframe | **3-minute** | **3-minute** |
| Session | RTH only | RTH only |
| Calculate | OnBarClose | OnBarClose |
| Strategy | Sniper_V3D | Sniper_V3D_B |
| Account | Acc-ES-4A | Acc-ES-4B |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | **12.50** | **12.50** |
| TargetAtr | 0.75 | 0.75 |
| StopAtr | 1.0 | 1.0 |
| FastEmaPeriod | 9 | 9 |
| SlowEmaPeriod | 21 | 21 |
| IbExtensionMin | 0.35 | 0.35 |
| IbExtensionMax | 0.80 | 0.80 |
| MinConfidence | 60 | 60 |

**ES note:** Use 3-minute charts for ES Sniper (vs 1-minute for NQ). ES compression
pullbacks are structurally slower — the EMA dip/rip pattern on 1-minute ES produces
excessive noise. The 3-minute chart gives each bar more structural weight.

---

### Charts 10–11–12 — ADX_DI_V3D A, B, and C
**Template name:** `V3D_ES_ADXDI_A` / `V3D_ES_ADXDI_B` / `V3D_ES_ADXDI_C`

| Setting | Version A | Version B | Version C |
|---|---|---|---|
| Instrument | ES (continuous) | ES (continuous) | ES (continuous) |
| Timeframe | **5-minute** | **5-minute** | **5-minute** |
| Session | RTH only | RTH only | RTH only |
| Calculate | OnPriceChange | OnPriceChange | OnPriceChange |
| Strategy | ADX_DI_V3D | ADX_DI_V3D_B | ADX_DI_V3D_C |
| Account | Acc-ES-5A | Acc-ES-5B | Acc-ES-5C |
| DataFolderPath | `C:\...\V3D` | `C:\...\V3D` | `C:\...\V3D` |
| TickValueDollars | **12.50** | **12.50** | **12.50** |
| AtrMultiplier | 1.0 | 1.0 | 1.0 |
| RiskReward | 1.0 | — (no target) | — (no target) |
| IbWidthAtrMin | 2.0 | 2.0 | 2.0 |
| MinConfidence | 55 | 55 | 55 |
| LevelRange | — | — | 20 |
| LevelTrend | — | — | 35 |

**ES note:** Use 5-minute charts for ES ADX_DI (vs 3-minute for NQ). ES rotation is
structurally slower and the 5-minute DI cross aligns with one full supervisor checkpoint
cycle — the DI cross and the regime confirmation from the supervisor are temporally matched.

---

## Daily Session Checklist — ES

### Pre-Session (5 minutes before 09:30 ET)

**Step 1 — Python pipeline**
Same pipeline as NQ — both instruments processed by the same scripts simultaneously.
- [ ] Both console windows running (Stage A + Stage B)
- [ ] Confirm `ES_RegimeMatrix_Latest.csv` LastModified < 35 minutes ago

**Step 2 — ES-specific column verification**
Open `C:\Users\Valued Customer\NT8_Regimes\V3D\ES_RegimeMatrix_Latest.csv`:

| Column | Required for | ES-specific note |
|---|---|---|
| IBWidthATR | Fader, ADX_DI | ES IB minimum width is higher than NQ — if zero, rotation entries blocked |
| SuggestedAdxMin | Momentum, ADX_DI | ES ADX patterns differ from NQ |
| TwoSidedFlag | Fader, ADX_DI | ES is typically more two-sided than NQ on rotation days |
| FinalDirection | Sniper, Momentum | Should match ES macro direction — verify independently |
| IBExtensionPct | Sniper | ES IB extension is slower to develop |

**Step 3 — HUD verification**
- [ ] V3D_ES_LiveData chart HUD shows `FRESH`
- [ ] ES FinalRegime populated and reasonable given market conditions

**Step 4 — Strategy accounts**
- [ ] All 11 ES strategy charts visible in V3D_ES_Test workspace
- [ ] TickValueDollars = 12.50 on all ES charts (not 5.00)
- [ ] Correct Apex SIM account per chart

---

### During Session

**ES-specific observation notes:**

ES typically lags NQ regime transitions by 1–2 checkpoints. If NQ shows TREND_EXPANSION
and ES still shows TREND_COMPRESSION, this is normal — the Expansion_V3D on NQ may be
active while ES Expansion is still waiting. Do not manually override ES to match NQ.

ES rotation days (ROTATION_LIQUID) tend to produce cleaner IB ranges than NQ. Fader_V3D
on ES should have a higher structural edge hit rate than on NQ. Track this in the weekly log.

---

### Post-Session (5 minutes after 16:00 ET)

**Step 1 — Trade log export**
Same procedure as NQ. File naming: `ES_[BotName]_[Version]_[YYYYMMDD].csv`

**Step 2 — ES vs NQ comparison note**
Each week, note whether ES and NQ regimes agreed. Days where they disagreed:
- Same strategy firing on NQ but not ES (or vice versa) = regime divergence day
- These are the most valuable days for validating that the regime model is instrument-aware

**Step 3 — A/B tracking**
Update the same weekly spreadsheet as NQ, in the ES rows.

---

## Weekly A/B Test Review Protocol — ES

Same decision framework as NQ. ES-specific notes:

### Sniper ES: 3-minute chart A vs B
The 3-minute chart means fewer total entries than NQ's 1-minute. Expect 4–6 weeks of data
before any statistical significance. Do not draw conclusions from fewer than 30 trades per version.

### ADX_DI ES: 5-minute chart A vs B vs C
The 5-minute chart aligns with the supervisor checkpoint cycle. Version C's `hlRange`
chop gate will suppress more entries on ES than on NQ because ES 5-minute charts
naturally produce lower ADX values. If Version C entry count is extremely low (< 1 per
day on average), lower `LevelRange` from 20 to 15 and note the change.

### Momentum ES
ES CI and ADX profiles differ from NQ. If CI rarely reaches below 58 on ES compression
days, lower `CiMaxCompression` from 58 to 62 incrementally and track the effect on
signal frequency. Note: any parameter change restarts the A/B test clock for that version.

---

## File and Template Taxonomy Summary

### NT8 Workspaces
| Workspace | Purpose |
|---|---|
| `V3D_ES_Test` | ES SIM testing — all 11 ES A/B/C charts |
| `V3C_ES_Live` | V3C ES production (runs concurrently for comparison) |
| `V3B_ES_Archive` | V3B retired — do not enable |

### NT8 Chart Templates (ES)
| Template | Chart | Strategy | Version |
|---|---|---|---|
| `V3D_ES_LiveData` | 1-min ES | None (indicators only) | — |
| `V3D_ES_Expansion_A` | UniRenko ES (4pt) | Expansion_V3D | A |
| `V3D_ES_Expansion_B` | UniRenko ES (4pt) | Expansion_V3D_B | B |
| `V3D_ES_Momentum_A` | 1-min ES | Momentum_V3D | A |
| `V3D_ES_Momentum_B` | 1-min ES | Momentum_V3D_B | B |
| `V3D_ES_Fader_A` | 1-min ES | Fader_V3D | A |
| `V3D_ES_Fader_B` | 1-min ES | Fader_V3D_B | B |
| `V3D_ES_Sniper_A` | 3-min ES | Sniper_V3D | A |
| `V3D_ES_Sniper_B` | 3-min ES | Sniper_V3D_B | B |
| `V3D_ES_ADXDI_A` | 5-min ES | ADX_DI_V3D | A |
| `V3D_ES_ADXDI_B` | 5-min ES | ADX_DI_V3D_B | B |
| `V3D_ES_ADXDI_C` | 5-min ES | ADX_DI_V3D_C | C |

### Key Parameter Differences: ES vs NQ Summary
| Strategy | Parameter | NQ | ES | Reason |
|---|---|---|---|---|
| All | TickValueDollars | 5.00 | 12.50 | ES tick = $12.50 |
| Expansion | UniRenko brick size | 10–20 pts | 4–8 pts | ES moves fewer points per expansion |
| Expansion B | MinVelocityAtr | 0.5 | 1.0 | ES velocity threshold per spec |
| Momentum | VelocityReliefThreshold | 0.85 | 1.0 | ES velocity threshold per spec |
| Fader | MinTargetTicks | 10 | 15 | ES tick value difference |
| Sniper | Timeframe | 1-min | 3-min | ES compression is structurally slower |
| ADX_DI | Timeframe | 3-min | 5-min | ES rotation aligns with 5-min checkpoint |

### V3D Folder Contents (ES files)
| File | Stage | Updated |
|---|---|---|
| `ES_1min_export.txt` | Raw data | Continuously by LiveDataExporter |
| `ES_Macro_Regimes_V3D.csv` | Stage A | Every 30s by MacroRegimeBuilder |
| `ES_HMM_Regimes_V3D.csv` | Stage B | Every 5+ new bars by HMM Watchdog |
| `ES_RegimeMatrix_Latest.csv` | Stage C | Every 30s by Supervisor |
| `ES_RegimeMatrix_History.csv` | Archive | Appended by Supervisor |

---

*End of V3D_ES_Master_Checklist.md — Version 1.0*
*Update when: ES chart templates created, account labels assigned, ES-specific parameter calibrations are made, or A/B decisions are reached.*
