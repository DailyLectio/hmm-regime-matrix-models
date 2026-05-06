# V3C Architecture Spec

Last updated: 2026-04-25

## Purpose

V3C is the side-by-side development version of the Dual-Regime futures supervision stack for ES and NQ. Its job is to improve regime detection and strategy gating while allowing V3B to continue running in parallel during SIM testing.

The core design principle is isolation:

- V3B and legacy live producers continue to own `C:\Users\Valued Customer\NT8_Regimes\Active`.
- V3C reads and writes its own sidecar files under `C:\Users\Valued Customer\NT8_Regimes\V3C`.
- V3C may fall back to `Active` only when sidecar feeds are missing, but it should not write to `Active`.

## Folder Taxonomy

### Root

`C:\Users\Valued Customer\NT8_Regimes`

Primary regime-system root.

### V3C

`C:\Users\Valued Customer\NT8_Regimes\V3C`

V3C Python supervisor, sidecar model feed, anchored HMM artifacts, launch scripts, backups, and V3C reference files.

Important files:

- `RegimeMatrixSupervisor.py`
- `BuildV3CModelFeed.py`
- `V3C_ModelFeed_Watchdog.py`
- `Build_V3C_ModelFeed.bat`
- `Start_V3C_ModelFeed_Watchdog.bat`
- `Start_RegimeMatrixSupervisor.bat`
- `V3C_Architecture_Spec.md`

### V3C ModelFeed

`C:\Users\Valued Customer\NT8_Regimes\V3C\ModelFeed`

V3C-only feed files consumed by the V3C supervisor:

- `ES_Macro_Regimes_V3C.csv`
- `NQ_Macro_Regimes_V3C.csv`
- `ES_Regimes_HMM_V3C.csv`
- `NQ_Regimes_HMM_V3C.csv`

These files are sidecar replacements for the legacy `Active` macro/HMM CSVs.

### V3C Models

`C:\Users\Valued Customer\NT8_Regimes\V3C\Models`

Anchored HMM model artifacts:

- `ES_Anchored_HMM_V3C.joblib`
- `NQ_Anchored_HMM_V3C.joblib`

These are trained from stitched long-history data and reused for inference. Live V3C should not refit the HMM on every export pulse.

### Raw Historical Data

`C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw`

Continuous stitched data files:

- `ES\ES_Continuous_20230601_20260424.Last.txt`
- `NQ\NQ_Continuous_20230601_20260424.Last.txt`

Practical coverage starts on `2023-06-01` for both ES and NQ.

Format:

```text
yyyyMMdd HHmmss;open;high;low;close;volume
```

### NinjaTrader Files

`C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom`

Installed V3C NinjaTrader files:

- `Indicators\RegimeMatrixHUDV3C.cs`
- `Strategies\MomoV3C.cs`
- `Strategies\ADXXV3C.cs`
- `Strategies\PineV3C.cs`
- `Strategies\ADXDIV3C.cs`

Reference copies also exist under:

`C:\Users\Valued Customer\NT8_Regimes\V3C\NT files`

## System Architecture

V3C has four layers.

### Layer 1: Long-History Data

ES and NQ raw quarterly exports were stitched into continuous files using non-overlapping front-contract windows. When the next quarterly contract begins, the prior contract is retired. This avoids duplicate timestamps and prevents hidden old/new contract switching during rollover overlap.

The stitched files are used for long-window Macro and anchored-HMM development.

### Layer 2: V3C ModelFeed Builder

`BuildV3CModelFeed.py` builds V3C-only feed files from stitched data.

It performs:

- Macro feed generation through existing Macro builders.
- V3C Macro feature enrichment.
- Anchored HMM training using long-history data.
- HMM feed export with probability diagnostics.
- `.joblib` model artifact export.

Run manually with:

`C:\Users\Valued Customer\NT8_Regimes\V3C\Build_V3C_ModelFeed.bat`

### Layer 3: V3C Live ModelFeed Watchdog

`V3C_ModelFeed_Watchdog.py` reads live NinjaTrader exports from:

- `C:\Users\Valued Customer\NT8_Regimes\Exports\ES_1min_export.txt`
- `C:\Users\Valued Customer\NT8_Regimes\Exports\NQ_1min_export.txt`

It writes only to:

`C:\Users\Valued Customer\NT8_Regimes\V3C\ModelFeed`

It uses fixed anchored HMM artifacts for inference and does not retrain on each live pulse.

Run with:

`C:\Users\Valued Customer\NT8_Regimes\V3C\Start_V3C_ModelFeed_Watchdog.bat`

### Layer 4: V3C Supervisor and NinjaTrader HUD

`RegimeMatrixSupervisor.py` reads V3C sidecar Macro/HMM feeds, calculates consensus regime state, and writes:

- `ES_Regimes_V3C.csv`
- `ES_Regimes_V3C_Latest.csv`
- `NQ_Regimes_V3C.csv`
- `NQ_Regimes_V3C_Latest.csv`

`RegimeMatrixHUDV3C.cs` reads the latest V3C CSVs and exposes static `InstancesV3C` for V3C strategies.

## V3C Design Goals

### Goal 1: Preserve V3B

V3C changes must not break or overwrite V3B. The `Active` folder remains the V3B/live shared folder.

### Goal 2: Reduce Macro Lag

The prior Macro label could stay `BRACKET_MACRO` during slow grind trend days because cumulative directional efficiency is lagging and path-dependent. V3C adds early initiative features so the supervisor can recognize developing initiative before the official macro label flips.

### Goal 3: Anchor the HMM

The prior HMM refit on current input data and assigned floating cluster labels. V3C trains the HMM on long-history stitched data and reuses fixed model artifacts for inference.

### Goal 4: Make Session Phase a Real Input

The same structural condition has different meaning at 10:35, 12:30, 14:45, and 15:35. V3C adds phase-aware penalties and permissions.

### Goal 5: Separate Bot Lanes From Regime Labels

Final regime and bot permissions are related but not identical. V3C emits explicit booleans for strategy lanes.

## Macro Feed Schema

V3C Macro files:

- `ES_Macro_Regimes_V3C.csv`
- `NQ_Macro_Regimes_V3C.csv`

Core inherited columns include:

- `trade_date`
- `symbol`
- `checkpoint_time`
- `minutes_from_open`
- `phase`
- `macro_logic_version`
- `pd_high`, `pd_low`, `pd_close`, `pd_range`
- `pd_vah`, `pd_val`, `pd_poc`
- `on_high`, `on_low`, `on_close`, `on_range`
- `on_vah`, `on_val`, `on_poc`, `on_volume`
- `rth_open`
- `last_price`
- `session_vwap`
- `close_vs_vwap_atr`
- `atr_5m`
- `net_move_since_open_atr`
- `directional_efficiency_since_open`
- `ib_width_so_far`
- `ib_extension_pct`
- `price_vs_ib_high_atr`
- `price_vs_ib_low_atr`
- `checkpoint_state`
- `official_bias_label`
- `official_regime_label`
- `volatility_state`
- `playbook_state`

V3C added Macro columns:

- `phase_bucket`
- `rolling_efficiency_10m`
- `rolling_efficiency_20m`
- `local_net_move_10m_atr`
- `local_net_move_20m_atr`
- `vwap_side`
- `vwap_hold_count`
- `same_side_vwap_minutes`
- `ib_escape_pressure`
- `value_acceptance_pressure`
- `developing_initiative_score`
- `initiative_direction`
- `late_extension_penalty`

## HMM Feed Schema

V3C HMM files:

- `ES_Regimes_HMM_V3C.csv`
- `NQ_Regimes_HMM_V3C.csv`

Columns:

- `TimestampET`
- `StateId`
- `RegimeLabel`
- `Tradeable`
- `AllowLong`
- `AllowShort`
- `SuggestedAdxMin`
- `SuggestedCiMax`
- `SuggestedSlopeGate`
- `SuggestedStopBucket`
- `ModelVersion`
- `StateProb`
- `StateMargin`
- `StateEntropy`
- `StateAge`
- `ret_1`
- `ret_3`
- `range_atr`
- `vol_z`
- `vwap_dist_atr`
- `phase_code`

V3C HMM labels remain:

- `TrendUp`
- `TrendDown`
- `Balance`
- `Transition`

But their state IDs are anchored by the long-history model artifact, not redefined on each live input.

## Supervisor Output Schema

V3C latest files:

- `ES_Regimes_V3C_Latest.csv`
- `NQ_Regimes_V3C_Latest.csv`

Important output columns:

- `SnapshotTimestamp`
- `MacroTimestamp`
- `MicroTimestamp`
- `Instrument`
- `MacroRegime`
- `MacroPlaybook`
- `HMM_Micro`
- `Phase`
- `CandidateRegime`
- `FinalRegime`
- `FinalDirection`
- `RegimeConfidence`
- `ConflictScore`
- `ReasonCode`
- `PersistenceStatus`
- `PendingCount`
- `Velocity3CP`
- `HMMFlipCount`
- `PhaseBucket`
- `DevelopingInitiativeScore`
- `InitiativeDirection`
- `RollingEfficiency10m`
- `RollingEfficiency20m`
- `LocalNetMove10mAtr`
- `SameSideVwapMinutes`
- `VwapHoldCount`
- `LateExtensionPenalty`
- `HMMStateProb`
- `HMMStateMargin`
- `HMMStateEntropy`
- `HMMStateAge`
- `IBExtensionPct`
- `CloseVsVwapAtr`
- `NetMoveAtr`
- `DirectionalEfficiency`
- `ReturnedToOpenFlag`
- `TwoSidedTradeFlag`
- `ValueBreakAcceptFlag`
- `LastPrice`
- `Atr5m`
- `StaleDataFlag`
- `StaleReason`

Bot permission columns:

- `AllowMomo`
- `AllowMomoLong`
- `AllowMomoShort`
- `AllowAdxx`
- `AllowPine`
- `AllowEsScalper`
- `AllowBracketSniper`
- `AllowExpansionBot`
- `AllowCompressionBot`
- `AllowFadeBot`
- `AllowLong`
- `AllowShort`

## Final Regime Definitions

V3C final regimes are:

- `TREND_EXPANSION`
- `TREND_COMPRESSION`
- `ROTATION_LIQUID`
- `ROTATION_ILLIQUID`
- `TRANSITION`

### TREND_EXPANSION

Strong directional auction with VWAP agreement, sufficient IB extension or velocity, low conflict, and enough confidence.

### TREND_COMPRESSION

Directional structure exists, but expansion is not clean enough for full trend-expansion classification. This is the primary Momo discovery lane from prior audits.

### ROTATION_LIQUID

Two-sided but tradable range. Suitable for fade/bracket concepts, not default Momo.

### ROTATION_ILLIQUID

Compressed, low-edge balance. Usually hard block.

### TRANSITION

Conflict, unresolved auction, stale data, HMM transition, return-to-open risk, or unclear alignment.

## Core Scoring Concepts

### Developing Initiative Score

Purpose: detect slow-grind initiative before cumulative macro labels flip.

Inputs:

- rolling efficiency over 10m and 20m
- local ATR-normalized move
- VWAP side persistence
- VWAP distance
- IB escape pressure
- value acceptance
- return-to-open penalty
- two-sided trade penalty
- lunch penalty

High score with aligned direction can produce:

`DEVELOPING_INITIATIVE_PHASE_AWARE`

### Conflict Score

Conflict is a hard safety mechanism. Sources include:

- stale macro/micro data
- HMM transition
- returned-to-open
- HMM trend not agreeing with VWAP/net move
- high HMM flip count
- two-sided trade during velocity
- failed value acceptance
- lunch trend penalty
- late-session extension penalty
- high HMM entropy
- low HMM state margin
- low HMM state probability

High conflict forces `TRANSITION`.

### Phase Awareness

Phase buckets:

- `PREMARKET`
- `OPEN`
- `EARLY_AM`
- `POST_IB_AM`
- `LUNCH`
- `PM`
- `POWER_HOUR`
- `CLOSE`

Early initiative is only favored in `EARLY_AM` and `POST_IB_AM`.

Lunch and late-day extension increase conflict and reduce bot permission.

## Bot Design Briefs

### Momo V3C

Primary role: directional continuation.

Current strict gate:

- `AllowMomo == True`
- long entries require `AllowMomoLong == True`
- short entries require `AllowMomoShort == True`

Momo is intended mainly for:

- `TREND_COMPRESSION`
- `TREND_EXPANSION`
- direction aligned with `FinalDirection`
- low conflict
- non-lunch phase

Prior audit finding:

The strongest Momo environment was:

`09:45-12:00 + TREND_COMPRESSION + SHORT`

### ADXX V3C

Primary role: ADX/DI breakout behavior.

Already uses HUD direction filtering more carefully than Momo did originally. It should continue to consume:

- `IsAdxAllowed`
- `AllowLong`
- `AllowShort`
- `FinalRegime`
- `FinalDirection`

### Pine V3C

Primary role: reversal/exhaustion or counter-alignment logic depending on its internal rules.

Consumes:

- `IsPineAllowed`
- `AllowLong`
- `AllowShort`
- Macro/HMM context

### ADXDI V3C

Should be audited separately against the new V3C sidecar feed. It should not be promoted until direction gating and time/regime DNA are verified.

## Risk and Permission Formulas

### Generic Direction Permissions

```text
AllowLong = FinalDirection in {LONG, BOTH}
AllowShort = FinalDirection in {SHORT, BOTH}
```

### Strict Momo Permissions

```text
momo_trend_lane = FinalRegime in {TREND_EXPANSION, TREND_COMPRESSION}
momo_quality_ok = RegimeConfidence >= 55 and ConflictScore <= 50
momo_phase_ok = Phase not in LUNCH or CASH_CLOSE

AllowMomoLong = AllowMomo and momo_trend_lane and momo_quality_ok and momo_phase_ok and FinalDirection in {LONG, BOTH}
AllowMomoShort = AllowMomo and momo_trend_lane and momo_quality_ok and momo_phase_ok and FinalDirection in {SHORT, BOTH}
AllowMomo = AllowMomoLong or AllowMomoShort
```

### Hard Blocks

Generally block trend bots when:

- `StaleDataFlag == True`
- `FinalRegime == ROTATION_ILLIQUID`
- `FinalRegime == TRANSITION`
- `ConflictScore >= 55`
- `ReasonCode == HMM_TRANSITION_OR_RETURN_TO_OPEN`
- `ReturnedToOpenFlag == 1`
- HMM state confidence is weak
- late extension penalty is high

## Launch Order for SIM

1. Ensure NinjaTrader is exporting live ES/NQ 1-minute files to:
   - `C:\Users\Valued Customer\NT8_Regimes\Exports\ES_1min_export.txt`
   - `C:\Users\Valued Customer\NT8_Regimes\Exports\NQ_1min_export.txt`

2. Start the V3C ModelFeed Watchdog:

   `C:\Users\Valued Customer\NT8_Regimes\V3C\Start_V3C_ModelFeed_Watchdog.bat`

3. Start the V3C Supervisor:

   `C:\Users\Valued Customer\NT8_Regimes\V3C\Start_RegimeMatrixSupervisor.bat`

4. In NinjaTrader, compile NinjaScript.

5. Add `RegimeMatrixHUD_V3C` to the relevant ES/NQ or MES/MNQ charts.

6. Run V3C strategies only on SIM until post-test audit is complete.

## Testing Protocol

### Historical Build Validation

Run:

`C:\Users\Valued Customer\NT8_Regimes\V3C\Build_V3C_ModelFeed.bat`

Expected outputs:

- Macro CSVs under `V3C\ModelFeed`
- HMM CSVs under `V3C\ModelFeed`
- anchored HMM artifacts under `V3C\Models`

### Runtime Smoke Test

Supervisor should produce:

- `ES_Regimes_V3C_Latest.csv`
- `NQ_Regimes_V3C_Latest.csv`

Each latest row should contain the new V3C diagnostic columns and bot permissions.

### Post-SIM Audit

After SIM testing:

1. Export trade data for Momo, Pine, ADXX, and ADXDI.
2. Merge trades to V3C latest/history by as-of timestamp.
3. Report:
   - Win Rate
   - Profit Factor
   - Net Profit
   - Trade Count
4. Cross-reference:
   - Time bucket
   - FinalRegime
   - FinalDirection
   - ReasonCode
   - ConflictScore
   - HMM diagnostics
   - Macro developing initiative fields

## Known Open Items

- HMM feature set should be revisited after first SIM run.
- Momo long lane remains suspect until re-audited with V3C strict gates.
- ES scalper lane is still optional and not the primary V3C trend lane.
- ADXDI needs a separate DNA audit before hard allow rules are finalized.
- HMM inference currently depends on fixed `.joblib` artifacts; retraining should be deliberate and versioned.

## Backup Policy

Before major V3C edits, copy affected files into:

`C:\Users\Valued Customer\NT8_Regimes\V3C\Backups`

Existing pre-upgrade backup:

`C:\Users\Valued Customer\NT8_Regimes\V3C\Backups\pre_v3c_upgrade_20260425_150141`

## Non-Negotiables

- Do not write V3C experimental outputs to `Active`.
- Do not rename the V3C HUD class or strategy classes without planning NinjaTrader compile impact.
- Do not refit the live HMM on every pulse.
- Do not allow Momo directionless entries.
- Do not promote any V3C lane to live before SIM audit confirms its regime/time DNA.

