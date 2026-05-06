# Regime Model SIM Health Check

Date: 2026-05-06 13:13 ET

## Process Status

PASS: V3D Stage A Macro, Stage B HMM, and Stage C Supervisor are running from `V3D\Scripts`.
PASS: V3C ModelFeed watchdog and RegimeMatrixSupervisor are running.
NOTE: Each script shows a `py.exe` launcher and a `python.exe` child. That is normal, not a duplicate model instance.

## Fresh Output Status

PASS: `V3D\NQ_Macro_Regimes_V3D.csv` fresh at 13:13.
PASS: `V3D\NQ_RegimeMatrix_Latest.csv` fresh at 13:12:54 with `StaleDataFlag=0`.
PASS: `V3D\ES_RegimeMatrix_Latest.csv` fresh at 13:12:55 with `StaleDataFlag=0`.
PASS: V3C latest files are fresh to the 13:05 checkpoint and report `StaleDataFlag=False`.

## New Field Status

PASS: Stage A output contains `same_side_vwap_minutes`.
PASS: V3D latest contains `SameSideVwapMinutes`.
PASS: V3C latest contains `SameSideVwapMinutes`.

Latest V3D NQ:
- `FinalRegime=TRANSITION`
- `ReasonCode=HMM_TRANSITION_TREND_BLOCKED`
- `MacroRegime=TREND`
- `HMMRegime=Transition`
- `IBExtensionPct=0.1923`
- `TwoSidedFlag=1`
- `SameSideVwapMinutes=146`
- `StaleDataFlag=0`
- `AllowExpansion=0`
- `AllowMomo=0`

Latest V3C NQ:
- `FinalRegime=TREND_COMPRESSION`
- `FinalDirection=LONG`
- `ReasonCode=MICRO_TREND_INSIDE_MACRO_STRUCTURE`
- `SameSideVwapMinutes=150`
- `IBExtensionPct=0.3`
- `TwoSidedTradeFlag=1`
- `AllowExpansionBot=False`
- `AllowMomo=False`

## Expansion Override Status

INCOMPLETE / NOT TRIGGERED: No current V3D or V3C row fired `IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE` or `TRANSITION_IB_CONFIRMED_EXPANSION`.

Reason: the current session's live `IBExtensionPct` is below the configured strong-break thresholds.

Current V3D Stage A NQ day summary:
- Rows today: 14
- Max `ib_extension_pct`: 0.2822
- Latest `ib_extension_pct`: 0.1923
- Max `same_side_vwap_minutes`: 146
- `two_sided_trade_flag=0` rows: 0
- `two_sided_trade_flag=1` rows: 14

The decay and override plumbing is present, but live conditions have not qualified under current thresholds.

## TradeLogExporter Status

FAIL / NEEDS CHART CLEANUP: `V3D_TradeLog.csv` is still writing `entry_regime=UNAVAILABLE`.

Current file:
- Rows: 3816
- `entry_regime=UNAVAILABLE`: 3816
- populated entry regime rows: 0

Rows after 13:00:
- Total rows: 9
- V3D account rows: 0
- Non-V3D account rows: 9
- Base bot-name rows: 0
- `entry_regime=UNAVAILABLE`: 9

Observed bad exporter names after 13:00:
- `Unknown_Bot` on `SimMomo1`
- `NQ Expansion A` on `SimMomo1`

Action needed:
- Remove `TradeLogExporter_V3D` from non-V3D charts.
- Remove duplicate/default instances with `BotName=Unknown_Bot`.
- Do not use friendly names like `NQ Expansion A`.
- On V3D charts only, use base lane names: `Expansion_V3D`, `Momentum_V3D`, `Fader_V3D`, `Sniper_V3D`, `ADX_DI_V3D`.
- Verify actual V3D account fills after chart cleanup. No V3D account rows were present after 13:00 in the log checked here.

## Overall Pass/Fail

PASS: Python regime pipeline is up and fresh.
PASS: new same-side VWAP field is flowing into V3D and V3C.
PASS: stale flags are clean.
INCOMPLETE: expansion override has not fired because current `IBExtensionPct` is below threshold.
FAIL: trade log exporter setup is not clean yet; new rows are still non-V3D/incorrect bot-name rows and are still `UNAVAILABLE`.
