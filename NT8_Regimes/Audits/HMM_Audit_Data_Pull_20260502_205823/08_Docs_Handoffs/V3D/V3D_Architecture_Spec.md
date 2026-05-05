# V3D Institutional Regime Matrix — Architecture Specification
**Document path:** `C:\Users\Valued Customer\NT8_Regimes\V3D\V3D_Architecture_Spec.md`
**Version:** 1.1 — V3D live stabilization update, 2026-04-28
**Status:** Reference document for all V3D build phases
**Instruments:** ES, NQ (with MES/MNQ micro equivalents)

---

## How to use this document

Paste the relevant section(s) at the start of each new build chat as context. Each section is self-contained so you only need to include what is relevant to the current phase. The full document is the authoritative record of all V3D design decisions.

---

## 2026-04-28 Live Stabilization Addendum

This addendum supersedes conflicting details in the original sections below.

### Stage A live guard

`MacroRegimeBuilder_V3D.py` must not emit live checkpoint rows whose checkpoint time is later than the latest actual 1-minute bar timestamp for that `trade_date`. Batch mode can still rebuild full historical sessions, but live mode must skip future checkpoints so late-morning data cannot populate afternoon rows with stale last price.

### Stage C regime and SIM mode

`RegimeSupervisor_V3D.py` supports SIM validation mode via `--sim-test`.

SIM mode changes:
- `TREND_COMPRESSION` Kalman threshold: 60 -> 50.
- `TREND_EMERGING` Kalman threshold: 40 -> 30.
- `ADX_DI` and `Sniper` are enabled in both `TREND_COMPRESSION` and `TREND_EMERGING`.
- Whenever a bot permission flag is ON, its `SizePct` floor is 25.

The `TREND_EMERGING` state is a scout tier between `ROTATION_ILLIQUID` and `TREND_COMPRESSION`. It requires Macro/HMM directional agreement and grants directional scout permissions before full trend confirmation.

### CSV schema contract

Stage C writes both size-column schemas permanently:
- Canonical short names: `ExpansionSizePct`, `MomoSizePct`, `PineSizePct`, `ADX_DISizePct`, `SniperSizePct`.
- Legacy HUD/bot aliases: `AllowExpansion_SizePct`, `AllowMomo_SizePct`, `AllowPine_SizePct`, `AllowADX_DI_SizePct`, `AllowSniper_SizePct`.

HUD and bots must accept both schemas. This prevents the failure mode where permission is ON but size is parsed as zero.

Stage C also publishes bot geometry aliases consumed by NinjaTrader strategies:
`SessionVWAP`, `IBHigh`, `IBLow`, `IBExtensionPct`, `IBWidthATR`, `PDVAH`, `PDVAL`, `TwoSidedFlag`, `SuggestedAdxMin`, `SuggestedCiMax`, `SuggestedSlopeGate`, `SuggestedStopBucket`.

### Diagnostic columns

Every `RegimeMatrix_Latest.csv` row includes:
- `BlockedReason`
- `BotPermissionSummary`
- `AnyDirectionalBotAllowed`
- `AnySizePctPositive`
- `SimTestingMode`

`BotPermissionSummary` uses pipe separators, not commas, so simple C# CSV splitting remains safe.

### Restart order

After any V3D schema or parser change, restart in this order:
1. Stage A
2. Stage B
3. Stage C
4. Reload HUD
5. Reload/re-enable bots

---

## Section 1: Project overview and design philosophy

### What V3D is

V3D is a three-stage quantitative regime classification system for ES and NQ futures, with purpose-built execution bots, risk-calibrated position sizing, and a single-account-per-bot deployment model for Apex funded accounts.

The system uses Auction Market Theory (AMT) as its structural foundation, a Hidden Markov Model (HMM) for 5-minute micro-state detection, and a Python consensus supervisor that merges both layers into a single authoritative `RegimeMatrix_Latest.csv` per instrument. NinjaTrader 8 strategy bots read from these files exclusively. All gate logic lives in Python. The HUD is a display and safety device, not a decision-maker.

### Core design principle

**Design bots to match the regime. Do not fit bots to the regime.**

Each bot is written to a specific regime design brief. The regime classification is not a mask applied to a general-purpose signal. The signal architecture of each bot is chosen specifically because it matches the structural character of its target regime state.

### Versions running concurrently

- V3B: retired. No longer used.
- V3C: continues running for comparison during V3D shadow testing.
- V3D: new build. Runs in shadow mode until SIM validation is complete. Uses separate file paths from V3C so there is no cross-contamination.

---

## Section 2: Folder taxonomy

All paths are absolute. Python scripts read from and write to these paths. NT8 strategies and HUD read from the V3D subfolder only.

```
C:\Users\Valued Customer\NT8_Regimes\
│
├── Exports\                          ← Raw NT8 1-minute bar exports (LiveDataExporter output)
│   ├── NQ_1min_export.txt            ← Appended by NT8 LiveDataExporter, realtime only
│   └── ES_1min_export.txt
│
├── Active\                           ← Stage A and Stage B outputs (V3C era, kept running)
│   ├── NQ_Macro_Regimes.csv
│   ├── ES_Macro_Regimes.csv
│   ├── NQ_Regimes.csv                ← HMM output
│   └── ES_Regimes.csv
│
├── V3D\                              ← All V3D outputs. NT8 bots read ONLY from here.
│   ├── V3D_Architecture_Spec.md     ← THIS FILE
│   ├── NQ_Macro_Regimes_V3D.csv     ← Stage A V3D output
│   ├── ES_Macro_Regimes_V3D.csv
│   ├── NQ_HMM_Regimes_V3D.csv       ← Stage B V3D output
│   ├── ES_HMM_Regimes_V3D.csv
│   ├── NQ_RegimeMatrix_Latest.csv   ← Stage C supervisor output (single row, atomic write)
│   ├── ES_RegimeMatrix_Latest.csv
│   └── History\                     ← Appended full-history matrix rows for analysis
│       ├── NQ_RegimeMatrix_History.csv
│       └── ES_RegimeMatrix_History.csv
│
├── Backtest\                         ← Batch historical run outputs for validation
│   ├── NQ_RegimeMatrix_Full.csv     ← Full history batch run (not Latest — all rows)
│   └── ES_RegimeMatrix_Full.csv
│
├── Overrides\                        ← HUD manual override log
│   └── HUD_Override_Log.csv         ← Timestamped record of all manual overrides
│
└── V3C\                              ← V3C files kept separate during transition
    ├── NQ_Regimes_V3C_Latest.csv
    └── ES_Regimes_V3C_Latest.csv
```

### Export file format

LiveDataExporter and the historical stitcher both write in this exact semicolon-delimited format:

```
YYYYMMDD HHmmss;Open;High;Low;Close;Volume
20260424 093100;17842.50;17848.25;17839.75;17845.00;1247
```

No header row. No quotes. Semicolon delimiter. Timestamp in ET.

---

## Section 3: Data foundation — historical stitching

### The problem

`LiveDataExporter.cs` only appends during `State.Realtime`. NT8 historical data exists in NT8's internal database but not in the export `.txt` files. Before running the V3D Python pipeline against historical data, a one-time stitching operation is required.

### Stitching target

Produce two clean, continuous, sorted, deduplicated files:
- `C:\Users\Valued Customer\NT8_Regimes\Exports\NQ_1min_export.txt`
- `C:\Users\Valued Customer\NT8_Regimes\Exports\ES_1min_export.txt`

Covering: March 2023 through present (RTH bars only, 09:30–16:00 ET).

### Stitching specification

The stitcher script (Chat V3D-1) must:
1. Accept one or more input files per instrument (any format: NT8 exports, CSV, Excel)
2. Parse timestamps to `datetime`, standardize to ET
3. Filter to RTH bars only: `09:30:00 <= time <= 16:00:00`, weekdays only
4. Remove duplicate timestamps (keep last)
5. Sort ascending by timestamp
6. Validate: flag gaps larger than 2 minutes during RTH (possible data dropout)
7. Write output in the standard semicolon-delimited format above
8. Print a summary: date range, total rows, gap count, symbols processed

### Data depth target

Minimum 2 full years (504 trading days). Target: March 2023 – present (~820 trading days as of mid-2026). This gives the HMM sufficient samples in all four states, including the rarest (Balance at ~7% = ~58 days minimum).

---

## Section 4: Stage A — MacroRegimeBuilder V3D

### Input

`NQ_1min_export.txt` / `ES_1min_export.txt` (semicolon-delimited, no header)

### Resampling

Resample to 5-minute RTH checkpoints. Checkpoint times (ET):
`09:35, 09:45, 09:55, 10:05, 10:15, 10:25, 10:35, 10:45, 10:55, 11:05, 11:35, 12:05, 12:35, 13:05, 13:35, 14:05, 14:35, 15:05, 15:35, 16:00`

### Key V3D changes from V3C MacroRegimeBuilder

1. **Dual-window directional efficiency.** Compute both cumulative (full session) and recent 3-bar window. Use `de_effective = max(de_cumulative, de_recent * 0.85)`. This catches slow-grind trends that V3B/C missed.

2. **Stored derived columns.** Pre-compute and store in the CSV (not computed at runtime by the supervisor):
   - `velocity_3cp_atr`: 3-checkpoint price change / ATR
   - `de_recent_3bar`: recent directional efficiency (3-bar window)
   - `ib_width_atr`: `ib_width_so_far / atr_5m`
   - `atr_pctile_20d`: ATR percentile rank over 20 trading days
   - `prior_day_type`: categorical — `TREND_UP`, `TREND_DOWN`, `ROTATION`, `INSIDE`, `NEWS`
   - `on_type`: overnight session type — `GAP_AND_GO`, `FADE_BACK`, `INSIDE_OVERNIGHT`
   - `rvol_vs_20d`: relative volume vs. 20-day rolling median

3. **Universal session key.** Every row gets a `session_key` field: `"{symbol}_{YYYYMMDD}_{HH:MM}"` e.g. `"NQ_20260424_10:35"`. This is the deterministic join key across all three files. No more fuzzy as-of merge.

4. **Phase field.** Map checkpoint time to session phase label:

| Checkpoint | Phase |
|---|---|
| 09:35 | OPENING_AUCTION |
| 09:45 | EARLY_TEST |
| 09:55–10:05 | FIRST_ACCEPTANCE |
| 10:15–10:25 | PRE_IB_MATURATION |
| 10:35–10:45 | POST_IB_MACRO |
| 10:55–11:35 | MID_MORNING_DISCOVERY |
| 12:05–12:35 | LUNCH_AUCTION |
| 13:05–13:35 | POST_LUNCH_ROTATION |
| 14:05–14:35 | AFTERNOON_TREND_TEST |
| 15:05–15:35 | LATE_DAY_CONVICTION |
| 16:00 | CASH_CLOSE |

### Per-symbol threshold configuration

| Parameter | ES | NQ |
|---|---|---|
| IB strong threshold | 1.00 | 0.85 |
| IB expanding threshold | 0.75 | 0.45 |
| VWAP confirm threshold | 0.50 | 0.40 |
| Net move confirm threshold | 0.75 | 0.60 |
| Velocity strong threshold | 1.00 | 0.85 |

### Output

`NQ_Macro_Regimes_V3D.csv` / `ES_Macro_Regimes_V3D.csv`

Key columns (minimum — full schema TBD in Chat V3D-2):
`session_key, trade_date, checkpoint_time, phase, symbol, last_price, rth_open, session_vwap, close_vs_vwap_atr, net_move_since_open_atr, directional_efficiency_since_open, de_recent_3bar, ib_extension_pct, ib_width_so_far, ib_width_atr, atr_5m, velocity_3cp_atr, atr_pctile_20d, two_sided_trade_flag, returned_to_open_flag, value_break_accept_flag, open_in_pd_value_flag, open_in_on_value_flag, close_in_pd_value_flag, close_in_on_value_flag, inside_value_score, prior_day_type, on_type, rvol_vs_20d, official_regime_label, official_bias_label, checkpoint_state, volatility_state, playbook_state`

---

## Section 5: Stage B — HMM Watchdog V3D

### Input

`NQ_1min_export.txt` / `ES_1min_export.txt`

### Rolling window (solves bloat and drift)

The HMM reads only the most recent `LOOKBACK_TRADING_DAYS = 60` trading days from the export file. The export file itself is never trimmed — it grows indefinitely as the archive. The HMM only consumes a rolling window.

```python
LOOKBACK_TRADING_DAYS = 60

unique_dates = df['Timestamp'].dt.date.unique()
if len(unique_dates) > LOOKBACK_TRADING_DAYS:
    cutoff_date = sorted(unique_dates)[-LOOKBACK_TRADING_DAYS]
    df = df[df['Timestamp'].dt.date >= cutoff_date]
```

This keeps HMM fit time constant regardless of archive length. The 60-day window ensures the Balance cluster has sufficient samples (~336 bars at 7% base rate) while keeping the model behaviorally current.

### Minimum refit interval

Refit only when the export file has grown by at least one full 5-minute checkpoint's worth of new bars since the last fit. Prevents constant refitting on every tick/minute append.

```python
MIN_NEW_BARS_TO_REFIT = 5  # ~5 new 1-min bars = one new checkpoint

bars_since_last_fit = current_row_count - last_fit_row_count
if bars_since_last_fit < MIN_NEW_BARS_TO_REFIT:
    return  # skip this cycle
```

### Feature matrix (V3D — anchored HMM)

Four features instead of the V3C three. The additional features anchor clusters to auction geometry:

| Feature | Source | Purpose |
|---|---|---|
| `Returns` | `Close.pct_change()` on 5-min bars | Directional return signal |
| `Range` | `(High - Low) / Close` on 5-min bars | Volatility proxy |
| `Vol_Z` | Volume Z-score vs. 20-bar rolling | Participation signal |
| `vwap_dist_atr` | `(Close - VWAP) / ATR_5m` | Spatial auction context |

The VWAP for `vwap_dist_atr` is computed as session VWAP from the 5-minute bars directly in the watchdog. ATR_5m uses a 14-period ATR on the 5-minute series.

### Label stability fix

Labels are assigned by combined criterion, not return-sort alone:
- `TrendUp`: highest mean return AND positive mean `vwap_dist_atr`
- `TrendDown`: lowest mean return AND negative mean `vwap_dist_atr`
- `Balance`: of remaining states, lowest mean range
- `Transition`: of remaining states, highest mean range

This prevents cluster identity drift when return distributions shift temporarily.

### Output columns

```
session_key, TimestampET, Symbol, StateId, RegimeLabel,
StateProb_TrendUp, StateProb_TrendDown, StateProb_Balance, StateProb_Transition,
HMM_FlipRate_5bar, HMM_PersistBars,
SuggestedAdxMin, SuggestedCiMax, SuggestedSlopeGate, SuggestedStopBucket,
ModelVersion, Tradeable, AllowLong, AllowShort
```

### Output files

`NQ_HMM_Regimes_V3D.csv` / `ES_HMM_Regimes_V3D.csv`

---

## Section 6: Stage C — RegimeSupervisor V3D

### Script

`RegimeSupervisor_V3D.py` (separate from V3C supervisor which continues running)

### Input files

- Stage A: `NQ_Macro_Regimes_V3D.csv`
- Stage B: `NQ_HMM_Regimes_V3D.csv`
- Joined on: `session_key` (deterministic — no fuzzy as-of merge)

### Five regime states

| State | Meaning | Bot assignment |
|---|---|---|
| `TREND_EXPANSION` | Confirmed IB breakout, VWAP separation, directional velocity | Expansion_V3D |
| `TREND_COMPRESSION` | Directional but momentum slowing, or micro-trend in bracket | Momentum_V3D, Sniper_V3D |
| `ROTATION_LIQUID` | Tradable chop, wide range, two-sided | Fader_V3D, ADX_DI_V3D |
| `ROTATION_ILLIQUID` | Dead chop, narrow range, stay out | All bots off |
| `TRANSITION` | Contradiction detected — danger override | All bots off |

### Classification priority chain

```python
if conflict_score >= conflict_threshold:  return "TRANSITION"
elif trend_expansion_conditions:          return "TREND_EXPANSION"
elif trend_compression_conditions:        return "TREND_COMPRESSION"
elif rotation_liquid_conditions:          return "ROTATION_LIQUID"
else:                                     return "ROTATION_ILLIQUID"
```

TRANSITION always fires first. It is a danger override, not a residual state.

### Kalman filter smoother

One `KalmanScoreFilter` instance per symbol, instantiated at session start. Applied to `TrendExpansionScore` before classification. Process noise `Q = 0.05`, observation noise `R = 0.15` (starting defaults — calibrate from Stage 4 analysis).

```python
class KalmanScoreFilter:
    def __init__(self, Q=0.05, R=0.15):
        self.Q = Q; self.R = R; self.x = 0.5; self.P = 1.0

    def update(self, z):
        P_pred = self.P + self.Q
        K = P_pred / (P_pred + self.R)
        self.x = self.x + K * (z - self.x)
        self.P = (1 - K) * P_pred
        return self.x
```

### Phase confidence multipliers

Applied to scoring thresholds — not to scores directly. Higher multiplier = easier to trigger that regime in that phase.

| Phase | Trend expansion multiplier | Rotation multiplier |
|---|---|---|
| OPENING_AUCTION | 0.70 | 1.10 |
| EARLY_TEST | 0.80 | 1.05 |
| FIRST_ACCEPTANCE | 0.90 | 1.00 |
| PRE_IB_MATURATION | 0.85 | 1.05 |
| POST_IB_MACRO | 1.10 | 0.95 |
| MID_MORNING_DISCOVERY | 1.00 | 1.00 |
| LUNCH_AUCTION | 0.75 | 1.15 |
| POST_LUNCH_ROTATION | 0.90 | 1.00 |
| AFTERNOON_TREND_TEST | 1.05 | 0.95 |
| LATE_DAY_CONVICTION | 0.80 | 0.90 |
| CASH_CLOSE | 0.60 | 0.70 |

### Bot permission mapping

| FinalRegime | AllowADXX | AllowPine | AllowMomo | AllowADX_DI | AllowExpansion | AllowSniper |
|---|---|---|---|---|---|---|
| TREND_EXPANSION | 1 | 0 | 1 | 0 | 1 | 0 |
| TREND_COMPRESSION | 0 | 1* | 1 | 0 | 0 | 1 |
| ROTATION_LIQUID | 0 | 1 | 1 | 1 | 0 | 0 |
| ROTATION_ILLIQUID | 0 | 0 | 0 | 0 | 0 | 0 |
| TRANSITION | 0 | 0 | 0 | 0 | 0 | 0 |

*Pine in TREND_COMPRESSION only at conflict < 0.35 (exhaustion fades at edges)

### SizePct output (confidence to position size scalar)

`SizePct` is a 0–100 integer output per bot. Bots read this and scale contracts.

```python
def compute_size_pct(regime_confidence: int, conflict_score: float) -> int:
    if conflict_score >= 0.40:
        return max(25, int(regime_confidence * 0.6))
    return int(min(100, max(25, (regime_confidence - 50) / 45 * 100)))
```

- Confidence 50 → SizePct ~0 (minimum 25)
- Confidence 75 → SizePct ~56
- Confidence 90 → SizePct ~89
- Confidence 95 → SizePct ~100

Note: SizePct values are relative — calibrate the effective scaling against Stage 4 expectancy analysis before going live. The relationship between confidence and expectancy must be validated empirically, not assumed to be linear.

### State persistence gate

`TREND_EXPANSION` is downgraded to `TREND_COMPRESSION` if `StateAgeBars < 2`. One-bar pokes do not get full expansion bot permissions.

### Output schema — `RegimeMatrix_Latest.csv`

Single-row file. Atomic write (`.tmp` → rename). The HUD reads only this file.

```
session_key, TimestampET, Symbol,
MacroRegime, MacroPlaybook, MacroCheckpointState,
HMMRegime, HMMDirection,
Velocity3P_ATR, VelocityConfirmed,
TrendExpansionScore, KalmanSmoothedScore, ConflictScore,
Phase, PhaseMultiplier,
FinalRegime, FinalDirection, RegimeConfidence,
AllowADXX, AllowADXX_SizePct,
AllowPine, AllowPine_SizePct,
AllowMomo, AllowMomo_SizePct,
AllowADX_DI, AllowADX_DI_SizePct,
AllowExpansion, AllowExpansion_SizePct,
AllowSniper, AllowSniper_SizePct,
AllowLong, AllowShort,
AllowFadeLong, AllowFadeShort,
ReasonCode, StateAgeBars, StaleDataFlag
```

### Run modes

```bash
# Single shot (both instruments)
python RegimeSupervisor_V3D.py --input-dir "C:\...\V3D" --output-dir "C:\...\V3D"

# Continuous loop every 30 seconds
python RegimeSupervisor_V3D.py --loop --interval 30

# Shadow mode (writes _SHADOW suffix — HUD ignores)
python RegimeSupervisor_V3D.py --shadow --loop --interval 30

# Single instrument
python RegimeSupervisor_V3D.py --symbol NQ
```

---

## Section 7: NT8 HUD V3D

### Class name

`RegimeMatrixHUD_V3D` — entirely separate from V3B (`RegimeMatrixHUD`) and V3C (`RegimeMatrixHUD_V3C`). Separate instances dictionary: `InstancesV3D["ES"]`, `InstancesV3D["NQ"]`.

### Core design rules

1. **Reads one file, one row.** `ES_RegimeMatrix_Latest.csv` or `NQ_RegimeMatrix_Latest.csv`. No dictionaries. No as-of merge. No multi-file orchestration.
2. **Header-driven parsing.** No positional column indices anywhere.
3. **Modification timestamp guard.** Minimum re-read interval: 15 seconds. Never reloads unless file has changed AND 15 seconds have elapsed.
4. **No gate logic in C#.** The only C# gate is `&& !StaleDataFlag`. All other decisions come from Python.
5. **Micro/mini symbol mapping.** MES reads ES file. MNQ reads NQ file.

```csharp
private string GetLeaderSymbol(string sym)
{
    if (sym == "MES") return "ES";
    if (sym == "MNQ") return "NQ";
    if (sym == "MGC") return "GC";
    if (sym == "MCL") return "CL";
    return sym;
}
```

### Public properties (read by bots)

```csharp
public string FinalRegime { get; private set; }
public string FinalDirection { get; private set; }
public int RegimeConfidence { get; private set; }
public double ConflictScore { get; private set; }
public string Phase { get; private set; }
public double Velocity3P { get; private set; }
public int StateAgeBars { get; private set; }
public bool StaleDataFlag { get; private set; }
public string ReasonCode { get; private set; }

// Bot permission booleans
public bool IsExpansionAllowed { get; private set; }
public bool IsMomoAllowed { get; private set; }
public bool IsPineAllowed { get; private set; }
public bool IsADX_DIAllowed { get; private set; }
public bool IsSniperAllowed { get; private set; }

// Directional permissions
public bool AllowLong { get; private set; }
public bool AllowShort { get; private set; }
public bool AllowFadeLong { get; private set; }
public bool AllowFadeShort { get; private set; }

// Sizing scalars (0–100)
public int ExpansionSizePct { get; private set; }
public int MomoSizePct { get; private set; }
public int PineSizePct { get; private set; }
public int ADX_DISizePct { get; private set; }
public int SniperSizePct { get; private set; }
```

### Safety layer (the only C# gate logic)

```csharp
private void ApplySafetyGuards()
{
    if (StaleDataFlag || ParseFailed || FileMissing)
    {
        ForceAllOff("SAFETY_GUARD: " + guardReason);
        return;
    }
}

private void ForceAllOff(string reason)
{
    IsExpansionAllowed = IsMomoAllowed = IsPineAllowed =
    IsADX_DIAllowed = IsSniperAllowed = false;
    AllowLong = AllowShort = AllowFadeLong = AllowFadeShort = false;
    ExpansionSizePct = MomoSizePct = PineSizePct =
    ADX_DISizePct = SniperSizePct = 0;
}
```

### Stale data threshold

`MaxStateAgeMinutes = 20`. Any `Latest.csv` older than 20 minutes triggers `StaleDataFlag = true` and `ForceAllOff()`.

### Manual override system

- Auto/Manual toggle button preserved from V3C
- Per-bot override buttons: EXPANSION, MOMO, PINE, ADX_DI, SNIPER
- Kill-all button: forces all permissions to false, logs event, requires deliberate re-enable
- Override auto-expiry: `MaxOverrideBars = 30` — manual overrides expire after 30 bars
- All overrides logged to `C:\...\V3D\Overrides\HUD_Override_Log.csv` with timestamp, bot, override state, and reason

### HUD display panel (top of chart)

```
[NQ → NQ]  V3D REGIME MATRIX  |  AUTO  |  FRESH
REGIME: TREND_EXPANSION        DIR: LONG  |  CONF: 82  |  CONFLICT: 08
MACRO: TREND_UP  |  HMM: TrendUp  |  VEL: 1.24  |  AGE: 4 bars
MOMO:ON(85%)  EXP:ON(82%)  PINE:OFF  ADX_DI:OFF  LONG:ON  SHORT:OFF
WHY: AUCTION_BREAKOUT_CONFIRMED  |  PHASE: POST_IB_MACRO
[AUTO/MAN]  [MOMO OVRD]  [EXP OVRD]  [PINE OVRD]  [KILL ALL]
```

---

## Section 8: Risk sizing formula

### Apex 50k EOD trailing drawdown parameters

- Trailing drawdown limit: $2,500
- Safety buffer: 60% utilization → maximum dollar risk per trade = $2,500 × 0.60 = **$1,500**

### Per-trade maximum contract calculation

```python
def max_contracts(atr_value, atr_multiplier, tick_size, tick_value):
    dollar_risk_per_contract = atr_value * atr_multiplier / tick_size * tick_value
    return max(1, int(1500 / dollar_risk_per_contract))
```

Instrument reference values (approximate):
- NQ tick size: 0.25, tick value: $5.00
- MNQ tick size: 0.25, tick value: $0.50
- ES tick size: 0.25, tick value: $12.50
- MES tick size: 0.25, tick value: $1.25

### SizePct scaling (applied after max_contracts)

```csharp
// In every V3D bot's SubmitWithStops method:
int maxContracts = CalculateMaxContracts(atr[0], AtrMultiplier);
int sizePct = GetSizePct();  // reads hudInstance.{Bot}SizePct
int actualContracts = Math.Max(1, (int)Math.Floor(maxContracts * sizePct / 100.0));
```

### Standard deviation risk adjustment

The 1.5 SD risk formulation from the V3C Apex spreadsheet is preserved. For bots with stops tighter than 1.0 ATR, use the mini contract (NQ, ES). For bots with stops wider than 1.5 ATR, scale down to micros (MNQ, MES) to stay within the $1,500 dollar risk ceiling.

| ATR stop multiplier | Instrument choice |
|---|---|
| < 1.0 ATR | Mini (NQ or ES) |
| 1.0 – 1.5 ATR | Mini or micro depending on calculated dollar risk |
| > 1.5 ATR | Micro (MNQ or MES) |

---

## Section 9: Deployment model — one account per bot

### Core rule

One Apex 50k EOD account per bot per instrument. No pod analysis required. Each bot manages its own direction, its own risk, and its own trailing drawdown independently.

### Account assignment (V3D initial deployment)

| Account | Instrument | Bot | Regime assignment |
|---|---|---|---|
| Acc-NQ-1 | NQ | Expansion_V3D | TREND_EXPANSION |
| Acc-NQ-2 | NQ | Momentum_V3D | TREND_COMPRESSION (primary) |
| Acc-NQ-3 | NQ | Fader_V3D | ROTATION_LIQUID |
| Acc-NQ-4 | NQ | Sniper_V3D | TREND_COMPRESSION (secondary) |
| Acc-NQ-5 | NQ | ADX_DI_V3D | ROTATION_LIQUID (bracket sniper) |
| Acc-ES-1 | ES | Expansion_V3D | TREND_EXPANSION |
| Acc-ES-2 | ES | Momentum_V3D | TREND_COMPRESSION (primary) |
| Acc-ES-3 | ES | Fader_V3D | ROTATION_LIQUID |
| Acc-ES-4 | ES | Sniper_V3D | TREND_COMPRESSION (secondary) |
| Acc-ES-5 | ES | ADX_DI_V3D | ROTATION_LIQUID (bracket sniper) |

### Counter-direction compliance

Since each account runs one bot, counter-directional positions across accounts are permitted by Apex policy — they are independent accounts. No pod coordination is required. A bot going long on Acc-NQ-1 while another bot goes short on Acc-NQ-3 is two independent accounts, not a hedge violation.

### Direction enforcement (code level)

Pod direction is enforced at the **code level**, not as a runtime parameter:

```csharp
// Expansion_V3D: hard-coded trend-follower
// Never enters short regardless of parameter settings
private bool CanEnterLong()  => hudInstance.AllowLong && !hudInstance.StaleDataFlag;
private bool CanEnterShort() => false;  // Expansion_V3D is long-biased by design brief

// Fader_V3D: uses AllowFadeLong / AllowFadeShort from HUD
// These are separate from AllowLong/AllowShort (Pine's counter-directional logic)
private bool CanFadeLong()  => hudInstance.AllowFadeLong && !hudInstance.StaleDataFlag;
private bool CanFadeShort() => hudInstance.AllowFadeShort && !hudInstance.StaleDataFlag;
```

---

## Section 10: Bot design briefs

### Bot 1: Expansion_V3D

**Target regime:** `TREND_EXPANSION` only. No entries in any other state.

**Signal architecture:** UniRenko brick physics. `WaitBricks` hysteresis gate (require N consecutive expansion bricks before entry). Multi-leg structure: Leg1 at 1:1 ATR target, Leg2 trailing runner with wobble-eject.

**Inherits from:** `V3ExpansionRider.cs` signal mechanics + `MomentumSlopeHybridScalp.cs` stop architecture (`HybridBarNThenTick` trail mode for Leg2).

**V3D changes:**
- Reads `ES_RegimeMatrix_Latest.csv` / `NQ_RegimeMatrix_Latest.csv` (header-driven, not Stage A CSV)
- Phase gate: no entries during `OPENING_AUCTION`, `EARLY_TEST`, or `CASH_CLOSE`
- Minimum `RegimeConfidence >= 75` at entry
- `VelocityConfirmed == 1` required in trade direction before entry
- Regime transition exit: if `FinalRegime` changes to `TRANSITION` while in position → exit immediately
- `SizePct` scaling applied to position size
- Consecutive loser lock: `MaxConsecutiveLosses = 2`, resets on session start and regime change
- Chart type: UniRenko (primary). Dual-series execution to 1-minute standard candles.

**Stop architecture:** `HybridBarNThenTick` on Leg2. N-bar trailing for first 3 bars after Leg1 target hit, then tick trailing. Wobble-eject: 1 opposite UniRenko brick kills runner.

**Direction:** Long-only by code design when `FinalDirection == LONG`. Short entries symmetrically when `FinalDirection == SHORT`.

---

### Bot 2: Momentum_V3D

**Target regimes:** `TREND_COMPRESSION` (primary), `TREND_EXPANSION` (secondary, reduced size).

**Signal architecture:** Wilder DI cross + CI/ADX dual-confirmation gate + slope-based exit. The all-weather anchor bot. Uses `ADXGu5v2.ConditionSeries` if the indicator is compiled and available; falls back to manual Wilder DI calculation otherwise.

**Inherits from:** `MomentumSlopeOG.cs` signal mechanics + `MomentumRegimeBetaV2.cs` regime lookup pattern (binary search for historical, `FileSystemWatcher` for live).

**V3D changes:**
- `AllowLong` / `AllowShort` read from `hudInstance` at submission (not static parameters)
- Regime file read replaced with V3D Latest.csv header-driven pattern
- CI threshold becomes regime-adaptive: `TREND_COMPRESSION` allows CI ≤ 58, `TREND_EXPANSION` requires CI ≤ 50
- Velocity secondary gate: if `Velocity3P_ATR >= instrument_threshold`, ADX floor reduced by 2 points
- `SizePct` scaling: `Leg2` contracts = confidence-scaled addition when `RegimeConfidence >= 80`
- Gu5 circuit breaker: `StopXLongSeries` / `StopXShortSeries` as universal position exit layer
- Consecutive loser lock: `MaxConsecutiveLosses = 2`
- Chart type: 1-minute candles (primary). `Calculate = OnPriceChange`.

**Exit architecture:** Slope exit (CI rise + ADX drop over N bars). Hysteresis mode preferred. Gu5 circuit breaker fires independently as override.

---

### Bot 3: Fader_V3D

**Target regime:** `ROTATION_LIQUID` only. Bidirectional (fades both edges).

**Signal architecture:** Structural edge proximity + Bollinger band confirmation + reversal signal. Entry requires price within 0.5 ATR of a structural level (IB edge, PD VAH, PD VAL, or session VWAP), Bollinger edge confirmation, and a reversal brick or DI cross.

**Inherits from:** `V3ValueFader.cs` Bollinger mechanics + `AdxDiCrossBracketOG.cs` two-leg bracket structure.

**V3D changes:**
- Primary edge reference from macro CSV: `ib_high`, `ib_low`, `pd_vah`, `pd_val` (not Bollinger alone)
- Bollinger band is secondary confirmation, not primary entry trigger
- Two-leg bracket: Leg1 at 50% distance to VWAP (high-probability near target), Leg2 to full opposite structural edge
- `MinTargetTicks` filter preserved: ignore if mean/VWAP is too close
- Uses `AllowFadeLong` / `AllowFadeShort` from HUD (not `AllowLong` / `AllowShort`)
- `two_sided_trade_flag == 1` required from macro CSV at entry checkpoint
- `SizePct` scaling applied
- Chart type: 1-minute candles.

**Direction note:** Fader_V3D is bidirectional. `AllowFadeLong` and `AllowFadeShort` are independent permissions. Both can be true simultaneously in `ROTATION_LIQUID`.

---

### Bot 4: Sniper_V3D

**Target regime:** `TREND_COMPRESSION` — specifically the dip-buy / rip-sell structure within confirmed directional micro-trend inside macro bracket (the "HMM TrendUp inside BRACKET_MACRO" composite state).

**Signal architecture:** EMA dip/rip entries. Fast EMA (9) is the trigger; slow EMA (21) is the trend anchor. Long entry: price dipped below fast EMA, touched slow EMA, closed back above fast EMA. Short entry: symmetric.

**Inherits from:** `V3CompressionSniper.cs` signal mechanics.

**V3D changes:**
- Direction read from `hudInstance.FinalDirection` (`LONG` / `SHORT`) — replaces `currentMacro.Contains("TREND_UP")` string matching
- IB extension gate at entry: only enter when `ib_extension_pct` is between 0.35 and 0.80 (above IB but not at exhaustion)
- Phase-adaptive EMA lookback: tighter entry zone during `LATE_DAY_CONVICTION` (within 1 ATR of fast EMA only)
- Regime file read: V3D Latest.csv header-driven pattern
- `SizePct` scaling applied
- Consecutive loser lock: `MaxConsecutiveLosses = 2`
- Chart type: 1-minute candles or 3-minute candles (configurable).

---

### Bot 5: ADX_DI_V3D

**Target regime:** `ROTATION_LIQUID` (bracket sniper lane). Secondary use: `TREND_COMPRESSION` edges.

**Signal architecture:** Wilder-smoothed ADX (Gu5 Pine variant) with precise DI gap gating. Bracket sniper: hunts the edges of Balance and Mean Reversion regimes.

**Inherits from:** `ADXDIV3C.cs` Wilder-smoothed signal mechanics.

**V3D changes:**
- `ib_width_atr` gate: only fire when IB width in ATR ≥ `rotation_liquid_ib_width_atr` threshold (default 2.0)
- `two_sided_trade_flag == 1` required from macro CSV
- ADX minimum reads `SuggestedAdxMin` from HMM output field in Latest.csv (dynamic floor)
- V3D Latest.csv header-driven read pattern
- `SizePct` scaling applied
- Chart type: 3-minute or 5-minute candles (wider timeframe for bracket edge precision).

---

## Section 11: Universal bot code patterns (apply to all V3D bots)

### Regime CSV read pattern (replace all prior patterns)

```csharp
// In OnStateChange / DataLoaded:
string symbol = GetLeaderSymbol(Instrument.MasterInstrument.Name);
string matrixFile = Path.Combine(DataFolderPath,
    $"{symbol}_RegimeMatrix_Latest.csv");

// In OnBarUpdate (timestamp-guarded):
private DateTime lastFileCheck = DateTime.MinValue;
private const int MinCheckSeconds = 15;

private void RefreshRegimeState()
{
    if ((DateTime.Now - lastFileCheck).TotalSeconds < MinCheckSeconds) return;
    try {
        DateTime writeTime = File.GetLastWriteTime(matrixFile);
        if (writeTime <= lastFileWriteUtc) return;
        // Read last row, parse by header name
        ReadLatestRow(matrixFile);
        lastFileWriteUtc = writeTime;
        lastFileCheck = DateTime.Now;
    } catch { }
}
```

### Direction gate at submission

```csharp
private void SubmitLongWithStops(int qty)
{
    var hud = RegimeMatrixHUD_V3D.InstancesV3D.ContainsKey(leaderSymbol)
        ? RegimeMatrixHUD_V3D.InstancesV3D[leaderSymbol] : null;

    bool dirOk = hud != null && hud.AllowLong && !hud.StaleDataFlag;
    if (!dirOk) return;

    int scaledQty = ScaleByConfidence(qty, hud.MomoSizePct);  // bot-specific SizePct
    if (scaledQty < 1) return;

    double risk = Math.Max(AtrStopMult * atr[0], MinStopTicks * TickSize);
    SetStopLoss(LEntry, CalculationMode.Price, RT(Close[0] - risk), false);
    SetProfitTarget(LEntry, CalculationMode.Price, RT(Close[0] + risk * RiskReward));
    EnterLong(scaledQty, LEntry);
}

private int ScaleByConfidence(int maxQty, int sizePct)
{
    return Math.Max(1, (int)Math.Floor(maxQty * sizePct / 100.0));
}
```

### Consecutive loser circuit breaker

```csharp
private int consecutiveLosers = 0;

protected override void OnExecutionUpdate(Execution exec, ...)
{
    if (exec.Order?.OrderState == OrderState.Filled
        && SystemPerformance.AllTrades.Count > 0)
    {
        var last = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
        if (last.ProfitCurrency < 0) consecutiveLosers++;
        else consecutiveLosers = 0;
    }
}

// In OnBarUpdate entry logic:
if (consecutiveLosers >= MaxConsecutiveLosses) return;
```

### Gu5 circuit breaker (universal exit layer — requires ADXGu5v2 indicator)

```csharp
// If ADXGu5v2 is available:
if (Position.MarketPosition == MarketPosition.Long)
    if (gu5_Fast.StopXLongSeries[0] > 0 || FinalRegime == "TRANSITION")
        { ExitLong("CircuitBreaker"); return; }

if (Position.MarketPosition == MarketPosition.Short)
    if (gu5_Fast.StopXShortSeries[0] > 0 || FinalRegime == "TRANSITION")
        { ExitShort("CircuitBreaker"); return; }
```

---

## Section 12: Operator role and session responsibilities

V3D is not a fully automated fire-and-forget system. The operator has three defined responsibilities:

### Before each session (5 minutes)

1. Confirm Python pipeline ran successfully. Check `LastModified` timestamp on `NQ_RegimeMatrix_Latest.csv` and `ES_RegimeMatrix_Latest.csv`. Both should be within the last 35 minutes (one checkpoint cycle).
2. Confirm HUD shows `FRESH` status on both NQ and ES charts. If `STALE` is displayed, restart the Python supervisor before enabling bots.
3. Confirm all five bots per instrument show their expected account assignment in NT8.

### During session (continuous awareness)

The HUD is the primary display. The operator does not second-guess the regime classification under normal conditions. Operator intervention is required only for:
- News events not reflected in price data (scheduled FOMC, CPI surprise)
- Technical failures: Python stopped writing (HUD shows STALE), NT8 chart freeze
- Anomalous market conditions: circuit breaker halt, flash crash, extreme gap
- Use the kill-all button for any of the above. Log the reason.

### After each session (5 minutes)

Review the trade log against the regime matrix. One row per trade: timestamp, regime at entry, confidence, conflict score, outcome. Look for systematic mismatches — bot firing in a regime it should not be in indicates either a pipeline bug or a regime misclassification. Flag anomalies for investigation in the weekend review.

---

## Section 13: Development phase sequence and chat taxonomy

Each phase runs in a separate Claude chat. Paste the relevant section(s) of this document as context at the start of each chat.

| Chat | Phase | Input | Output | Spec sections |
|---|---|---|---|---|
| V3D-1 | Data stitching | Raw NT8 export files | Clean `NQ_1min_export.txt`, `ES_1min_export.txt` | Sections 2, 3 |
| V3D-2 | Python pipeline | Stitched export files | `MacroRegimeBuilder_V3D.py`, `HMM_Watchdog_V3D.py`, `RegimeSupervisor_V3D.py` | Sections 4, 5, 6 |
| V3D-3 | NT8 HUD | Spec | `RegimeMatrixHUD_V3D.cs` | Sections 7, 11 |
| V3D-4a | Bot: Expansion_V3D | Spec + existing V3ExpansionRider.cs | `Expansion_V3D.cs` | Sections 8, 9, 10 (Bot 1), 11 |
| V3D-4b | Bot: Momentum_V3D | Spec + existing MomentumSlopeOG.cs | `Momentum_V3D.cs` | Sections 8, 9, 10 (Bot 2), 11 |
| V3D-4c | Bot: Fader_V3D | Spec + existing V3ValueFader.cs | `Fader_V3D.cs` | Sections 8, 9, 10 (Bot 3), 11 |
| V3D-4d | Bot: Sniper_V3D | Spec + existing V3CompressionSniper.cs | `Sniper_V3D.cs` | Sections 8, 9, 10 (Bot 4), 11 |
| V3D-4e | Bot: ADX_DI_V3D | Spec + existing ADXDIV3C.cs | `ADX_DI_V3D.cs` | Sections 8, 9, 10 (Bot 5), 11 |
| V3D-5 | Validation framework | Python pipeline output | Regime characterization scripts, trade log analysis tools | Sections 3–6 |
| V3D-6 | SIM deployment | All above | Deployment checklist, SIM validation protocol | Sections 9, 12 |

### How to start each chat

```
I am building the V3D Institutional Regime Matrix for ES/NQ futures trading.
Here is the relevant specification for this phase:

[PASTE SECTIONS FROM V3D_Architecture_Spec.md]

My goal for this chat: [one sentence description of the deliverable]
```

---

## Section 14: Known caveats and monitoring items

| Caveat | Description | Mitigation |
|---|---|---|
| 5-minute checkpoint latency | Regime state updates every 5 minutes. Bot signals provide sub-checkpoint granularity. | Gu5 circuit breaker exits on bar-by-bar signal deterioration faster than checkpoint updates. |
| HMM cluster drift | 60-day rolling window reduces drift but does not eliminate it. Clusters can relabel during unusual market cycles. | Weekly monitoring: check HMM label distribution. Flag if TrendUp/TrendDown share drops below 70% combined (suggests cluster collapse). |
| Confidence score relativity | `RegimeConfidence` is ordinal, not calibrated probability. High confidence in a low-information session may not equal high confidence in a high-information session. | Stage 4 validation: verify confidence → expectancy monotonicity from historical matrix before using as size scalar. |
| Data stitching discontinuity | Stitched historical data may have different tick aggregation than live data. Gaps at holidays and half-days produce anomalous regime labels at boundaries. | Flag rows within 2 bars of detected gaps with `DataQualityFlag = BOUNDARY`. Exclude from HMM training if flagged. |
| Apex trailing drawdown management | The $1,500 per-trade risk ceiling assumes the drawdown is fully available at trade entry. After a losing trade, effective remaining drawdown is lower. | Consider adding a session drawdown tracker that recalculates the risk ceiling after each trade. Not required for V3D-1 but flagged for V3D+. |
| ADXGu5v2 dependency | `MomentumEngine_V5_Trinity_Final` and related bots depend on `ADXGu5v2` as a compiled NT8 indicator. If unavailable, bots fall back to manual Wilder DI calculation. | Confirm `ADXGu5v2` is compiled and available in NT8 before starting V3D-4b. If not available, the manual Wilder DI implementation from `MomentumSlopeOG.cs` is the fallback. |

---

## Section 15: Key design decisions log

These are the architectural decisions made during the V3D design conversation. Each is final unless explicitly revisited.

| Decision | Choice | Rationale |
|---|---|---|
| Gate logic location | Python only | C# gate logic in V3B caused the April 24 missed trend problem. All decisions in Python. |
| HUD role | Display + safety only | Prevents the HUD from being the brain. Python is the brain. |
| Regime join key | `session_key` deterministic string | Eliminates fuzzy as-of merge silent failures. |
| Directional permission for Pine | `AllowFadeLong` / `AllowFadeShort` separate from `AllowLong` / `AllowShort` | Pine is counter-directional by design. Needs its own permission set. |
| Bot development approach | Design to regime, not fit to regime | Fitting bots to regime overfits to a specific regime classification version. Design briefs produce bots that are architecturally correct for their target state. |
| HMM window | 60 trading days rolling | Solves bloat, improves recency, maintains Balance cluster stability. |
| Deployment model | One account per bot | Simpler than pod architecture for V3D scale. Full Apex policy compliance. |
| SIM testing | Live Apex SIM accounts | Behavioral testing in real market conditions catches slippage, partial fills, and order rejection that replay cannot surface. |
| Live deployment order | Fader → Momentum → Expansion | Lowest-risk regime first. Rare events last. |
| V3B status | Retired | No ongoing role. No cross-contamination risk. |
| V3C status | Continues running | Shadow comparison during V3D validation. Separate file paths prevent interference. |
| `SizePct` assumption | Validate before scaling | Confidence → expectancy relationship must be empirically confirmed in Stage 4 before using as size scalar. Do not assume linearity. |

---

*End of V3D_Architecture_Spec.md — Version 1.1*
*Generated from V3D design conversation. Update this document as architectural decisions are revised during build phases.*
