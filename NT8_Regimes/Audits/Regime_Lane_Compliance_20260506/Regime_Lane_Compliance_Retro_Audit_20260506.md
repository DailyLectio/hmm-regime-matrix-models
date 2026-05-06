# Regime Lane Compliance Retro Audit - 2026-05-06

Scope: raw V3C Compression trade logs and raw V1A/V1B Kalman Fader logs from 2026-05-01 onward, joined to nearest prior NQ V3C regime snapshot. This is model-history evidence, not true historical HUD-read evidence.

## Raw Trade Join - Lane Summary
family | lane_bucket | trades | wins | losses | win_rate | net_pnl | avg_pnl | gross_pnl | ticks
Kalman Faders | OUT_OF_LANE | 131 | 33 | 98 | 25.2 | -12005.0 | -91.64 | -12005.0 | -2401.0
V3C Compression | IN_LANE | 208 | 163 | 45 | 78.4 | 32925.0 | 158.29 | 32925.0 | 6585.0
V3C Compression | OUT_OF_LANE | 212 | 188 | 24 | 88.7 | 46205.0 | 217.95 | 46205.0 | 9241.0


## Compression Lead-In Hypothesis
family | hypothesis_bucket | retro_regime | trades | wins | losses | win_rate | net_pnl | avg_pnl | gross_pnl | ticks
V3C Compression | IN_LANE | TREND_COMPRESSION | 208 | 163 | 45 | 78.4 | 32925.0 | 158.29 | 32925.0 | 6585.0
V3C Compression | OUT_LEADIN_TRANSITION_ROT_ILLIQUID | ROTATION_ILLIQUID | 41 | 38 | 3 | 92.7 | 10880.0 | 265.37 | 10880.0 | 2176.0
V3C Compression | OUT_LEADIN_TRANSITION_ROT_ILLIQUID | TRANSITION | 159 | 141 | 18 | 88.7 | 34215.0 | 215.19 | 34215.0 | 6843.0
V3C Compression | OUT_OF_LANE | ROTATION_LIQUID | 11 | 8 | 3 | 72.7 | 915.0 | 83.18 | 915.0 | 183.0
V3C Compression | OUT_OF_LANE | TREND_EXPANSION | 1 | 1 | 0 | 100.0 | 195.0 | 195.0 | 195.0 | 39.0


## By Day
family | trade_date | lane_bucket | trades | wins | losses | win_rate | net_pnl | avg_pnl | gross_pnl | ticks
Kalman Faders | 2026-05-01 | OUT_OF_LANE | 67 | 21 | 46 | 31.3 | -720.0 | -10.75 | -720.0 | -144.0
Kalman Faders | 2026-05-04 | OUT_OF_LANE | 32 | 6 | 26 | 18.8 | -7530.0 | -235.31 | -7530.0 | -1506.0
Kalman Faders | 2026-05-05 | OUT_OF_LANE | 11 | 0 | 11 | 0.0 | -2885.0 | -262.27 | -2885.0 | -577.0
Kalman Faders | 2026-05-06 | OUT_OF_LANE | 21 | 6 | 15 | 28.6 | -870.0 | -41.43 | -870.0 | -174.0
V3C Compression | 2026-05-01 | IN_LANE | 62 | 50 | 12 | 80.6 | 9205.0 | 148.47 | 9205.0 | 1841.0
V3C Compression | 2026-05-01 | OUT_OF_LANE | 40 | 39 | 1 | 97.5 | 10830.0 | 270.75 | 10830.0 | 2166.0
V3C Compression | 2026-05-04 | IN_LANE | 69 | 62 | 7 | 89.9 | 17380.0 | 251.88 | 17380.0 | 3476.0
V3C Compression | 2026-05-04 | OUT_OF_LANE | 124 | 108 | 16 | 87.1 | 23390.0 | 188.63 | 23390.0 | 4678.0
V3C Compression | 2026-05-05 | IN_LANE | 48 | 36 | 12 | 75.0 | 6175.0 | 128.65 | 6175.0 | 1235.0
V3C Compression | 2026-05-05 | OUT_OF_LANE | 28 | 26 | 2 | 92.9 | 8680.0 | 310.0 | 8680.0 | 1736.0
V3C Compression | 2026-05-06 | IN_LANE | 29 | 15 | 14 | 51.7 | 165.0 | 5.69 | 165.0 | 33.0
V3C Compression | 2026-05-06 | OUT_OF_LANE | 20 | 15 | 5 | 75.0 | 3305.0 | 165.25 | 3305.0 | 661.0


## By Regime
family | retro_regime | trades | wins | losses | win_rate | net_pnl | avg_pnl | gross_pnl | ticks
Kalman Faders | ROTATION_ILLIQUID | 24 | 9 | 15 | 37.5 | 2110.0 | 87.92 | 2110.0 | 422.0
Kalman Faders | TRANSITION | 35 | 7 | 28 | 20.0 | -6340.0 | -181.14 | -6340.0 | -1268.0
Kalman Faders | TREND_COMPRESSION | 72 | 17 | 55 | 23.6 | -7775.0 | -107.99 | -7775.0 | -1555.0
V3C Compression | ROTATION_ILLIQUID | 41 | 38 | 3 | 92.7 | 10880.0 | 265.37 | 10880.0 | 2176.0
V3C Compression | ROTATION_LIQUID | 11 | 8 | 3 | 72.7 | 915.0 | 83.18 | 915.0 | 183.0
V3C Compression | TRANSITION | 159 | 141 | 18 | 88.7 | 34215.0 | 215.19 | 34215.0 | 6843.0
V3C Compression | TREND_COMPRESSION | 208 | 163 | 45 | 78.4 | 32925.0 | 158.29 | 32925.0 | 6585.0
V3C Compression | TREND_EXPANSION | 1 | 1 | 0 | 100.0 | 195.0 | 195.0 | 195.0 | 39.0


## Join Lag Minutes
family | count | mean | std | min | 25% | 50% | 75% | max
Kalman Faders | 131.0 | 2.84 | 2.48 | 0.0 | 1.02 | 2.12 | 3.94 | 9.62
V3C Compression | 420.0 | 3.91 | 4.46 | 0.0 | 1.28 | 2.74 | 4.89 | 34.38


Artifacts: retro_trade_regime_join.csv, summary_by_lane.csv, summary_by_hypothesis_bucket.csv, summary_by_day_lane.csv, summary_by_regime.csv