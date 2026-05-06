# Engineer Response Commentary - Expansion/Momentum Darkness

## Main Response

The audit confirms the user's concern. On May 6, the price action had breakout/expansion characteristics, but both V3D and V3C were structurally biased toward non-expansion outputs.

The most important finding is that V3D's `TRANSITION_MACRO_VELOCITY_IB_CONFIRMED` branch returns `TREND_COMPRESSION`, not `TREND_EXPANSION`. In other words, the escape hatch from Transition is not an expansion escape hatch. It is a compression downgrade. That alone can explain why Expansion accounts stay dark on breakout days.

V3C shows a sibling issue: bracket/macro initiative evidence is captured, but usually capped as `TREND_COMPRESSION`. At the latest NQ snapshot, HMM was TrendUp and price was far above VWAP/IB, yet Macro remained `ROTATION_ILLIQUID`, so Expansion stayed false while Compression/Momo were allowed.

## Suggested Next Patch

Patch one thing first: add a narrow, auditable `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE` that returns `TREND_EXPANSION` only under high-confidence conditions.

Minimum recommended gates:

- IBExtensionPct above expansion threshold
- abs(CloseVsVwapAtr) >= 1.25
- abs(NetMoveAtr) >= 2.0
- ReturnedToOpenFlag == 0
- SameSideVwapMinutes >= 10
- HMM TrendUp/TrendDown OR HMM Transition with strong price evidence
- ConflictScore below hard-danger level, or conflict caused only by stale TwoSidedFlag

Also patch the trade logger before the next test run. The V3D log has 3,745 rows with `entry_regime=UNAVAILABLE`, which means the performance dataset cannot currently answer which regime any trade belonged to.

## Operational Comment

Do not simply lower all thresholds. The current model is guarding against false breakouts. The correct fix is a specific override for confirmed IB/VWAP acceptance days, plus decay for stale two-sided flags. That preserves safety while opening the expansion/momentum lanes when the market has obviously left balance.
