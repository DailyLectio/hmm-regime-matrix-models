
import csv
import os
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

# ==============================================================================
# RegimeMatrixSupervisor.py
# V3C Consensus Supervisor
#
# Phase One Recommended Change #1 — Asymmetric Hysteresis with Macro
# Co-Confirmation (2026-05-03). Adds a state-conditional, symbol-conditional
# gate layered on top of the existing apply_persistence() mechanism:
#   - Requires 2 consecutive HMM bars for TrendDown / Balance(NQ) / Transition
#   - Allows 1-bar TrendUp ONLY when macro confirms (TREND/TREND_STRUCTURE/
#     BALANCE_STRUCTURE/CONFIRMED_INITIATIVE)
#   - Quarantines ES TrendUp behind macro confirm (auto-label-collapse hypothesis)
#   - Hard-closes the gate on any MACRO_STALE_*, MICRO_STALE_*, or MICRO_MISSING
#   - Adds HMMStateAgeBars / AsymHysteresisGateOpen / AsymHysteresisReason /
#     AsymHysteresisEnabled audit columns to the V3C output schema; existing
#     history CSVs are auto-migrated by normalize_history_schema_if_needed
#     and a `.schema_backup_*` file is saved on first run
#   - Does NOT rename, remove, or reorder any existing column
#   - Can be disabled instantly via ASYMMETRIC_HYSTERESIS_ENABLED = False for
#     rollback to legacy V3C apply_persistence behaviour
#
# Intended location:
#   C:\Users\Valued Customer\NT8_Regimes\V3C\Scripts\RegimeMatrixSupervisor.py
#
# Inputs:
#   C:\Users\Valued Customer\NT8_Regimes\Active\ES_Macro_Regimes.csv
#   C:\Users\Valued Customer\NT8_Regimes\Active\ES_Regimes.csv
#   C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Macro_Regimes.csv
#   C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Regimes.csv
#
# Outputs:
#   C:\Users\Valued Customer\NT8_Regimes\V3C\ES_Regimes_V3C.csv
#   C:\Users\Valued Customer\NT8_Regimes\V3C\ES_Regimes_V3C_Latest.csv
#   C:\Users\Valued Customer\NT8_Regimes\V3C\NQ_Regimes_V3C.csv
#   C:\Users\Valued Customer\NT8_Regimes\V3C\NQ_Regimes_V3C_Latest.csv
#
# FinalRegime is always one of:
#   TREND_EXPANSION / TREND_COMPRESSION / ROTATION_LIQUID / ROTATION_ILLIQUID / TRANSITION
# ==============================================================================

BASE_DIR = r"C:\Users\Valued Customer\NT8_Regimes"
ACTIVE_DIR = os.path.join(BASE_DIR, "Active")
V3C_DIR = os.path.join(BASE_DIR, "V3C")
MODEL_FEED_DIR = os.path.join(V3C_DIR, "ModelFeed")
Path(V3C_DIR).mkdir(parents=True, exist_ok=True)
Path(MODEL_FEED_DIR).mkdir(parents=True, exist_ok=True)

# Keep V3C isolated by default.
# Change OUTPUT_DIR = ACTIVE_DIR only after your HUD is intentionally reading the V3C output from Active.
OUTPUT_DIR = V3C_DIR

INSTRUMENTS = {
    "ES": {
        "macro": os.path.join(MODEL_FEED_DIR, "ES_Macro_Regimes_V3C.csv"),
        "micro": os.path.join(MODEL_FEED_DIR, "ES_Regimes_HMM_V3C.csv"),
        "macro_fallback": os.path.join(ACTIVE_DIR, "ES_Macro_Regimes.csv"),
        "micro_fallback": os.path.join(ACTIVE_DIR, "ES_Regimes.csv"),
        "history_output": os.path.join(OUTPUT_DIR, "ES_Regimes_V3C.csv"),
        "latest_output": os.path.join(OUTPUT_DIR, "ES_Regimes_V3C_Latest.csv"),
    },
    "NQ": {
        "macro": os.path.join(MODEL_FEED_DIR, "NQ_Macro_Regimes_V3C.csv"),
        "micro": os.path.join(MODEL_FEED_DIR, "NQ_Regimes_HMM_V3C.csv"),
        "macro_fallback": os.path.join(ACTIVE_DIR, "NQ_Macro_Regimes.csv"),
        "micro_fallback": os.path.join(ACTIVE_DIR, "NQ_Regimes.csv"),
        "history_output": os.path.join(OUTPUT_DIR, "NQ_Regimes_V3C.csv"),
        "latest_output": os.path.join(OUTPUT_DIR, "NQ_Regimes_V3C_Latest.csv"),
    },
}

# For weekend replay/backtest using old historical dates, set this False.
STALE_GUARD_ENABLED = True
MAX_MACRO_AGE_MINUTES = 20
MAX_MICRO_AGE_MINUTES = 15
POLL_SECONDS = 1.0

FINAL_REGIMES = {
    "TREND_EXPANSION",
    "TREND_COMPRESSION",
    "ROTATION_LIQUID",
    "ROTATION_ILLIQUID",
    "TRANSITION",
}

EARLY_INITIATIVE_SCORE_MIN = 58
BRACKET_INITIATIVE_SCORE_MIN = 55

# ==============================================================================
# Asymmetric Hysteresis Gate (Phase One Report — Recommended Change #1)
# ==============================================================================
# State-conditional, symbol-conditional persistence rule layered on top of the
# existing apply_persistence() mechanism. The flat 2-bar hysteresis rule from
# the original Market AI Study overshoots on ES TrendUp (17% fakeout) and
# ES Balance (19% fakeout) while materially helping on the broken states
# (TrendDown 60-64%, NQ Balance 66%, NQ Transition 60%).
#
# Rule:
#   - HMM == TrendDown / Balance / Transition -> require 2 consecutive HMM bars
#   - HMM == TrendUp                          -> 1 bar IF macro confirms
#   - macro_stale (any MACRO_STALE_* token)   -> hard close, no gate ever
#   - ES TrendUp                              -> quarantined behind macro confirm
#                                                (auto-label-collapse hypothesis)
#
# When ASYMMETRIC_HYSTERESIS_ENABLED = False the supervisor falls back to the
# legacy V3C apply_persistence behaviour for safe rollback.
ASYMMETRIC_HYSTERESIS_ENABLED = True

ASYM_HMM_MIN_PERSISTENCE = {
    "TrendUp":     1,
    "TrendDown":   2,
    "Balance":     2,
    "Transition":  2,
}

ASYM_SYMBOL_OVERRIDES = {
    "ES": {
        "Balance": 1,        # 19% fakeout, 59 min avg duration
        "Transition": 2,
    },
    "NQ": {
        # Defaults apply
    },
}

# Macro states considered "confirming" for an HMM TrendUp signal.
ASYM_MACRO_TREND_CONFIRM = {
    "TREND",
    "TREND_STRUCTURE",
    "TREND_UP_MACRO",
    "TREND_DOWN_MACRO",
    "BALANCE_STRUCTURE",
    "CONFIRMED_INITIATIVE",
}

ASYM_MACRO_STALE_TOKEN = "MACRO_STALE"
ASYM_MICRO_STALE_TOKEN = "MICRO_STALE"
ASYM_MICRO_MISSING_TOKEN = "MICRO_MISSING"


@dataclass(frozen=True)
class InstrumentThresholds:
    normal_ib_ext: float
    expansion_ib_ext: float
    strong_ib_ext: float
    compression_velocity: float
    expansion_velocity: float
    vwap_confirm_atr: float
    net_move_confirm_atr: float


THRESHOLDS: Dict[str, InstrumentThresholds] = {
    "ES": InstrumentThresholds(
        normal_ib_ext=0.50,
        expansion_ib_ext=1.00,
        strong_ib_ext=1.25,
        compression_velocity=0.70,
        expansion_velocity=1.25,
        vwap_confirm_atr=0.35,
        net_move_confirm_atr=0.50,
    ),
    "NQ": InstrumentThresholds(
        normal_ib_ext=0.45,
        expansion_ib_ext=0.85,
        strong_ib_ext=1.10,
        compression_velocity=0.65,
        expansion_velocity=1.15,
        vwap_confirm_atr=0.35,
        net_move_confirm_atr=0.50,
    ),
}


@dataclass
class RegimeState:
    official_regime: str = "TRANSITION"
    official_direction: str = "NONE"
    pending_regime: str = "TRANSITION"
    pending_count: int = 0
    last_trade_date: Optional[str] = None
    last_processed_macro_ts: Optional[pd.Timestamp] = None
    last_processed_micro_ts: Optional[pd.Timestamp] = None
    price_history: list = field(default_factory=list)
    hmm_history: list = field(default_factory=list)
    # Phase One Recommended Change #1 — track HMM state age for asymmetric
    # hysteresis. Independent of FinalRegime persistence used by
    # apply_persistence(); this counts consecutive HMM-micro-state bars.
    prev_hmm_regime: str = "Unknown"
    hmm_state_age: int = 0


states: Dict[str, RegimeState] = {"ES": RegimeState(), "NQ": RegimeState()}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def _upper(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip().upper()


def _clip(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def _bool_text(value: bool) -> str:
    return "True" if bool(value) else "False"


def _phase_bucket(minutes_from_open: float, phase: str = "") -> str:
    phase_u = _upper(phase)
    if "PREMARKET" in phase_u:
        return "PREMARKET"
    if minutes_from_open < 0:
        return "PREMARKET"
    if minutes_from_open < 15:
        return "OPEN"
    if minutes_from_open < 65:
        return "EARLY_AM"
    if minutes_from_open < 150:
        return "POST_IB_AM"
    if minutes_from_open < 240:
        return "LUNCH"
    if minutes_from_open < 330:
        return "PM"
    if minutes_from_open < 390:
        return "POWER_HOUR"
    return "CLOSE"


def read_csv_safe(filepath: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(filepath):
        return None
    try:
        df = pd.read_csv(filepath, engine="python", on_bad_lines="skip")
        if df.empty:
            return None
        return df
    except Exception:
        traceback.print_exc()
        return None


def read_first_available_csv(primary: str, fallback: Optional[str] = None) -> Optional[pd.DataFrame]:
    df = read_csv_safe(primary)
    if df is not None:
        return df
    if fallback and fallback != primary:
        return read_csv_safe(fallback)
    return None


def atomic_write_csv(df: pd.DataFrame, filepath: str) -> None:
    tmp_path = filepath + ".tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, filepath)


def append_csv_row(row: dict, filepath: str) -> None:
    desired_headers = list(row.keys())
    if os.path.isfile(filepath):
        normalize_history_schema_if_needed(filepath, desired_headers)

    df = pd.DataFrame([row])
    file_exists = os.path.isfile(filepath)
    df.to_csv(filepath, mode="a", header=not file_exists, index=False)


def normalize_history_schema_if_needed(filepath: str, desired_headers: list) -> None:
    try:
        with open(filepath, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            existing_headers = next(reader, None)
            existing_rows = list(reader)
    except FileNotFoundError:
        return

    if not existing_headers or existing_headers == desired_headers:
        return

    backup_path = f"{filepath}.schema_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.replace(filepath, backup_path)

    normalized_rows = []
    for values in existing_rows:
        if not values:
            continue
        if len(values) == len(desired_headers):
            mapped = dict(zip(desired_headers, values))
        elif len(values) == len(existing_headers):
            mapped = dict(zip(existing_headers, values))
        else:
            raise ValueError(
                f"Cannot normalize {filepath}: row has {len(values)} columns, "
                f"expected {len(existing_headers)} old or {len(desired_headers)} new columns."
            )

        if "AllowMomoLong" in desired_headers and "AllowMomoLong" not in mapped:
            mapped["AllowMomoLong"] = _bool_text(
                str(mapped.get("AllowMomo", "")).strip().lower() == "true"
                and str(mapped.get("AllowLong", "")).strip().lower() == "true"
            )
        if "AllowMomoShort" in desired_headers and "AllowMomoShort" not in mapped:
            mapped["AllowMomoShort"] = _bool_text(
                str(mapped.get("AllowMomo", "")).strip().lower() == "true"
                and str(mapped.get("AllowShort", "")).strip().lower() == "true"
            )

        normalized_rows.append({header: mapped.get(header, "") for header in desired_headers})

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=desired_headers)
        writer.writeheader()
        writer.writerows(normalized_rows)

    print(f"Normalized schema for {filepath}; backup saved to {backup_path}")


def make_macro_timestamp(row: pd.Series) -> Optional[pd.Timestamp]:
    if "trade_date" not in row or "checkpoint_time" not in row:
        return None
    ts = pd.to_datetime(f"{row['trade_date']} {row['checkpoint_time']}", errors="coerce")
    if pd.isna(ts):
        return None
    return ts


def get_latest_macro_row(df_macro: pd.DataFrame, now_ts: pd.Timestamp) -> Optional[pd.Series]:
    """
    Prevents the supervisor from using a future checkpoint row if MacroRegimeBuilder
    has already generated rows later than the current wall-clock time.
    """
    if df_macro is None or df_macro.empty:
        return None
    if "trade_date" not in df_macro.columns or "checkpoint_time" not in df_macro.columns:
        return None

    df = df_macro.copy()
    df["MacroTimestamp"] = pd.to_datetime(
        df["trade_date"].astype(str) + " " + df["checkpoint_time"].astype(str),
        errors="coerce",
    )
    df = df.dropna(subset=["MacroTimestamp"])
    if df.empty:
        return None

    valid = df[df["MacroTimestamp"] <= now_ts].copy()
    if valid.empty:
        valid = df.sort_values("MacroTimestamp").head(1).copy()

    return valid.sort_values("MacroTimestamp").iloc[-1]


def get_asof_micro_row(df_micro: pd.DataFrame, macro_ts: pd.Timestamp) -> Tuple[Optional[pd.Series], Optional[pd.Timestamp]]:
    """
    As-of merge:
    for a macro checkpoint timestamp, use the latest HMM/micro row <= macro timestamp.
    """
    if df_micro is None or df_micro.empty:
        return None, None

    df = df_micro.copy()
    ts_col = "TimestampET" if "TimestampET" in df.columns else df.columns[0]
    df["MicroTimestamp"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["MicroTimestamp"])
    if df.empty:
        return None, None

    valid = df[df["MicroTimestamp"] <= macro_ts].copy()
    if valid.empty:
        valid = df.sort_values("MicroTimestamp").head(1).copy()

    row = valid.sort_values("MicroTimestamp").iloc[-1]
    return row, pd.Timestamp(row["MicroTimestamp"])


def reset_if_new_trade_date(instrument: str, trade_date: str) -> None:
    state = states[instrument]
    if state.last_trade_date != trade_date:
        state.official_regime = "TRANSITION"
        state.official_direction = "NONE"
        state.pending_regime = "TRANSITION"
        state.pending_count = 0
        state.price_history.clear()
        state.hmm_history.clear()
        state.last_processed_macro_ts = None
        state.last_trade_date = trade_date
        # Phase One Recommended Change #1 — reset HMM age tracking each session.
        state.prev_hmm_regime = "Unknown"
        state.hmm_state_age = 0


def calculate_velocity(instrument: str, macro_ts: pd.Timestamp, current_price: float, current_atr: float) -> float:
    """
    3-checkpoint velocity:
        (latest_price - price_2_checkpoints_ago) / average_ATR_over_window

    This reacts faster than cumulative directional efficiency.
    """
    state = states[instrument]
    safe_atr = current_atr if current_atr and current_atr > 0.1 else 1.0

    if state.price_history and state.price_history[-1]["ts"] == macro_ts:
        state.price_history[-1] = {"ts": macro_ts, "price": current_price, "atr": safe_atr}
    else:
        state.price_history.append({"ts": macro_ts, "price": current_price, "atr": safe_atr})

    if len(state.price_history) > 3:
        state.price_history.pop(0)

    if len(state.price_history) < 3:
        return 0.0

    first = state.price_history[0]
    last = state.price_history[-1]
    avg_atr = np.mean([max(x["atr"], 0.1) for x in state.price_history])
    velocity = (last["price"] - first["price"]) / max(avg_atr, 0.1)
    return round(float(velocity), 3)


def update_hmm_history(instrument: str, micro_ts: Optional[pd.Timestamp], hmm_label: str) -> int:
    """
    Returns a simple flip count over recent HMM labels.
    Higher values indicate micro-state instability.
    """
    if micro_ts is None:
        return 0

    state = states[instrument]
    label = str(hmm_label)

    if state.hmm_history and state.hmm_history[-1]["ts"] == micro_ts:
        state.hmm_history[-1] = {"ts": micro_ts, "label": label}
    else:
        state.hmm_history.append({"ts": micro_ts, "label": label})

    if len(state.hmm_history) > 5:
        state.hmm_history.pop(0)

    labels = [x["label"] for x in state.hmm_history]
    flips = 0
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            flips += 1
    return flips


# ==============================================================================
# Phase One Recommended Change #1 — Asymmetric Hysteresis with Macro Confirm
# ==============================================================================
def update_hmm_state_age(instrument: str, hmm_label: str) -> int:
    """
    Track consecutive HMM-bar persistence in the underlying micro state.
    Returns the new hmm_state_age value (>= 1 once any HMM label is seen).
    Independent of update_hmm_history (which is a flip counter); this is a
    monotonic counter that resets on label change and increments on repeats.
    """
    state = states[instrument]
    label = str(hmm_label).strip() or "Unknown"
    if label == state.prev_hmm_regime:
        state.hmm_state_age += 1
    else:
        state.prev_hmm_regime = label
        state.hmm_state_age = 1
    return state.hmm_state_age


def required_hmm_persistence(hmm_regime: str, symbol: str) -> int:
    """Minimum consecutive HMM bars required for asymmetric hysteresis pass."""
    overrides = ASYM_SYMBOL_OVERRIDES.get(symbol, {})
    if hmm_regime in overrides:
        return int(overrides[hmm_regime])
    return int(ASYM_HMM_MIN_PERSISTENCE.get(hmm_regime, 2))


def compute_asymmetric_hysteresis_gate(
    hmm_regime: str,
    macro_regime: str,
    symbol: str,
    hmm_state_age: int,
    macro_stale: bool = False,
    macro_stale_reason: str = "",
) -> Tuple[bool, str]:
    """
    Phase One Recommended Change #1 — Asymmetric Hysteresis with Macro
    Co-Confirmation.

    Returns (gate_open, reason_code).

    gate_open = True  -> directional bot permissions may proceed normally
    gate_open = False -> all directional bot permissions are forced to 0;
                         reason_code is appended to BotPermissionGateReason
                         and BlockedReason for audit.

    Rule (from Phase One Report Part 3):
        IF macro_stale OR macro_regime contains 'MACRO_STALE'/'MICRO_STALE':
            gate_open = False, reason = HYST_BLOCK_*_STALE
        ELIF hmm_regime == 'TrendUp':
            IF macro_regime in ASYM_MACRO_TREND_CONFIRM:
                gate_open = True (1-bar OK with macro confirm)
            ELSE:
                IF symbol == 'NQ' and hmm_state_age >= 2:
                    gate_open = True (NQ TrendUp 2-bar fallback)
                ELIF symbol == 'NQ':
                    gate_open = False (NQ TrendUp 1-bar without macro confirm)
                ELSE: ES TrendUp without confirm -> quarantine (auto-label
                                                   collapse hypothesis)
                    gate_open = False
        ELSE:
            needed = required_hmm_persistence(hmm_regime, symbol)
            IF hmm_state_age >= needed:
                gate_open = True
            ELSE:
                gate_open = False
    """
    if not ASYMMETRIC_HYSTERESIS_ENABLED:
        return True, "HYST_DISABLED"

    # Hard block on macro/micro staleness.
    if macro_stale:
        return False, f"HYST_BLOCK_STALE_{macro_stale_reason}".rstrip("_")

    macro_stale_str = (macro_stale_reason or "").upper()
    if (ASYM_MACRO_STALE_TOKEN in macro_stale_str
            or ASYM_MICRO_STALE_TOKEN in macro_stale_str
            or ASYM_MICRO_MISSING_TOKEN in macro_stale_str):
        return False, f"HYST_BLOCK_STALE_{macro_stale_reason}"

    macro_norm = (macro_regime or "").strip().upper()
    if ASYM_MACRO_STALE_TOKEN in macro_norm:
        return False, f"HYST_BLOCK_MACRO_STALE_{macro_norm}"

    # TrendUp branch — preferential 1-bar gate IF macro confirms.
    if hmm_regime == "TrendUp":
        if macro_norm in ASYM_MACRO_TREND_CONFIRM:
            return True, "HYST_PASSED_TRENDUP_MACRO_CONFIRM"
        if symbol == "NQ":
            if hmm_state_age >= 2:
                return True, "HYST_PASSED_NQ_TRENDUP_NO_MACRO_2BAR"
            return False, f"HYST_BLOCK_NQ_TRENDUP_NO_MACRO_AGE_{hmm_state_age}"
        # ES TrendUp without macro confirm -> quarantine
        return False, "HYST_BLOCK_ES_TRENDUP_QUARANTINE"

    # All other HMM states.
    needed = required_hmm_persistence(hmm_regime, symbol)
    if hmm_state_age >= needed:
        return True, f"HYST_PASSED_{hmm_regime.upper()}_AGE_{hmm_state_age}"
    return False, f"HYST_BLOCK_{hmm_regime.upper()}_AGE_{hmm_state_age}_OF_{needed}"


def detect_stale_data(now_ts: pd.Timestamp, macro_ts: pd.Timestamp, micro_ts: Optional[pd.Timestamp]) -> Tuple[bool, str]:
    if not STALE_GUARD_ENABLED:
        return False, "STALE_GUARD_DISABLED"

    # Phase One Report Part 4 — Session-boundary guard.
    # 119,665-minute stale ages occur when the macro CSV contains rows from a
    # prior session (days or weeks ago) because the macro builder was not
    # running / the CSV was not flushed.  Compare trade dates first; if the
    # macro row is from a different calendar date than now, it is categorically
    # stale regardless of the minute delta.  Allow one day of slack for
    # overnight sessions (e.g., macro at 16:00 on date D, now is 09:35 on D+1).
    macro_date = macro_ts.date()
    now_date = now_ts.date()
    date_diff_days = (now_date - macro_date).days
    if date_diff_days > 1:
        return True, f"MACRO_STALE_WRONG_SESSION_{date_diff_days}D"
    if date_diff_days == 1:
        # Tolerate overnight: macro at 16:00 yesterday + now at 09:35 today
        # = ~17.5 hours. Anything older than 20 hours is a missed session.
        overnight_age = (now_ts - macro_ts).total_seconds() / 3600.0
        if overnight_age > 20.0:
            return True, f"MACRO_STALE_OVERNIGHT_{overnight_age:.1f}HR"
        # Overnight gap is within tolerance — macro is from yesterday's close,
        # now is today's open.  This is expected at session start.  Do NOT
        # fall through to the minute-based check (which would see 1000+ min
        # and falsely flag stale).  Apply only the micro freshness check below.
    else:
        # Same calendar day — standard minute-based freshness check.
        macro_age = (now_ts - macro_ts).total_seconds() / 60.0
        # Safety cap: if somehow still >400 minutes (impossible within RTH),
        # flag as session boundary.  This prevents nonsensical ages like
        # 119665 minutes from ever appearing in the stale reason string.
        if macro_age > 400.0:
            return True, f"MACRO_STALE_EXCEEDED_SESSION_{macro_age:.0f}MIN"
        if macro_age > MAX_MACRO_AGE_MINUTES:
            return True, f"MACRO_STALE_{macro_age:.1f}MIN"

    if micro_ts is None:
        return True, "MICRO_MISSING"

    # Micro staleness — also guard against cross-session.
    micro_date = micro_ts.date()
    micro_date_diff = (macro_date - micro_date).days
    if micro_date_diff > 1:
        return True, f"MICRO_STALE_WRONG_SESSION_{micro_date_diff}D"

    micro_lag = (macro_ts - micro_ts).total_seconds() / 60.0
    if micro_lag > 400.0:
        return True, f"MICRO_STALE_EXCEEDED_SESSION_{micro_lag:.0f}MIN"
    if micro_lag > MAX_MICRO_AGE_MINUTES:
        return True, f"MICRO_STALE_{micro_lag:.1f}MIN_BEHIND_MACRO"

    return False, "FRESH"


def classify_v3c_candidate(
    instrument: str,
    macro_row: pd.Series,
    hmm_label_raw: str,
    velocity_3cp: float,
    hmm_flip_count: int,
    stale_flag: bool,
    stale_reason: str,
) -> dict:
    """
    Converts Stage A + Stage B + velocity into one of the five final playbook states.
    """
    th = THRESHOLDS[instrument]

    macro = _upper(macro_row.get("official_regime_label", "UNRESOLVED"))
    playbook = _upper(macro_row.get("playbook_state", "TRANSITION"))
    phase = _upper(macro_row.get("phase", "UNKNOWN"))
    minutes_from_open = _safe_float(macro_row.get("minutes_from_open", 0.0))
    phase_bucket = _upper(macro_row.get("phase_bucket", _phase_bucket(minutes_from_open, phase)), "UNKNOWN")
    hmm = _upper(hmm_label_raw, "UNKNOWN")

    ib_ext = _safe_float(macro_row.get("ib_extension_pct", 0.0))
    close_vs_vwap = _safe_float(macro_row.get("close_vs_vwap_atr", 0.0))
    net_move = _safe_float(macro_row.get("net_move_since_open_atr", 0.0))
    returned_open = _safe_int(macro_row.get("returned_to_open_flag", 0))
    two_sided = _safe_int(macro_row.get("two_sided_trade_flag", 0))
    value_accept = _safe_int(macro_row.get("value_break_accept_flag", 0))

    # Optional future fields. If not yet added to Stage A, they remain NaN.
    adx_5m = _safe_float(macro_row.get("adx_5m", np.nan), np.nan)
    chop_5m = _safe_float(macro_row.get("chop_5m", np.nan), np.nan)
    rvol_5m = _safe_float(macro_row.get("rvol_5m", np.nan), np.nan)
    developing_score = _safe_float(macro_row.get("developing_initiative_score", 0.0))
    initiative_direction = _upper(macro_row.get("initiative_direction", "NONE"), "NONE")
    same_side_vwap_minutes = _safe_float(macro_row.get("same_side_vwap_minutes", 0.0))
    same_side_vwap_minutes = _safe_float(macro_row.get("same_side_vwap_minutes", 0.0))
    late_extension_penalty = _safe_float(macro_row.get("late_extension_penalty", 0.0))
    state_prob = _safe_float(macro_row.get("StateProb", np.nan), np.nan)
    state_margin = _safe_float(macro_row.get("StateMargin", np.nan), np.nan)
    state_entropy = _safe_float(macro_row.get("StateEntropy", np.nan), np.nan)

    hmm_up = hmm == "TRENDUP"
    hmm_down = hmm == "TRENDDOWN"
    hmm_trending = hmm_up or hmm_down
    hmm_balance = hmm == "BALANCE"
    hmm_transition = hmm == "TRANSITION"

    macro_trend_up = macro in {"TREND_UP_MACRO", "TREND_STRUCTURE"} and net_move >= 0
    macro_trend_down = macro in {"TREND_DOWN_MACRO", "TREND_STRUCTURE"} and net_move < 0
    macro_trend = macro_trend_up or macro_trend_down or macro.startswith("TREND")

    macro_bracket = macro in {
        "BRACKET_MACRO",
        "BALANCE_STRUCTURE",
        "MEAN_REVERSION_MACRO",
        "REVERSION_STRUCTURE",
    }

    vwap_up = close_vs_vwap >= th.vwap_confirm_atr and net_move >= th.net_move_confirm_atr
    vwap_down = close_vs_vwap <= -th.vwap_confirm_atr and net_move <= -th.net_move_confirm_atr
    hmm_vwap_agrees = (hmm_up and vwap_up) or (hmm_down and vwap_down)

    if hmm_up or (not hmm_trending and vwap_up):
        direction = "LONG"
    elif hmm_down or (not hmm_trending and vwap_down):
        direction = "SHORT"
    elif initiative_direction in {"LONG", "SHORT"}:
        direction = initiative_direction
    else:
        direction = "NONE"

    abs_velocity = abs(velocity_3cp)

    conflict = 0
    if stale_flag:
        conflict += 100
    if hmm_transition:
        conflict += 25
    if returned_open == 1:
        conflict += 30
    if hmm_trending and not hmm_vwap_agrees:
        conflict += 20
    if hmm_flip_count >= 3:
        conflict += 20
    if two_sided == 1 and abs_velocity >= th.compression_velocity:
        conflict += 10
    if value_accept == -1 and ib_ext >= th.normal_ib_ext:
        conflict += 15
    if phase_bucket == "LUNCH" and hmm_trending:
        conflict += 15
    if phase_bucket in {"POWER_HOUR", "CLOSE"} and late_extension_penalty >= 55:
        conflict += 20
    elif phase_bucket == "PM" and late_extension_penalty >= 75:
        conflict += 10
    if not np.isnan(chop_5m) and chop_5m >= 62 and hmm_trending:
        conflict += 20
    if not np.isnan(adx_5m) and adx_5m < 16 and abs_velocity < th.compression_velocity:
        conflict += 10
    if not np.isnan(state_entropy) and state_entropy >= 0.75:
        conflict += 10
    if not np.isnan(state_margin) and state_margin < 0.10:
        conflict += 10
    if not np.isnan(state_prob) and state_prob < 0.45:
        conflict += 10

    conflict = int(_clip(conflict, 0, 100))

    # IB/VWAP ACCEPTANCE OVERRIDE — fires when price has confirmed expansion
    # through IB extension + sustained same-side VWAP acceptance even when
    # the Macro layer is still bracket/rotation-biased. Runs before the stale
    # check intentionally: a stale-data scenario is unlikely to also show
    # 15+ minutes of same-side VWAP acceptance with clear IB extension.
    # All five conditions are required to prevent false triggers on spikes.
    # Conflict ceiling is 54 (below the hard-block at 55) to allow
    # single-source conflict from HMM/VWAP disagreement to pass.
    _ib_ext_strong = th.strong_ib_ext      # NQ: 1.10, ES: 1.25 (already defined)
    _ib_override_eligible = (
        ib_ext >= _ib_ext_strong
        and abs(close_vs_vwap) >= 1.25
        and abs(net_move) >= 2.0
        and returned_open == 0
        and same_side_vwap_minutes >= 15
        and conflict < 55
        and direction in {"LONG", "SHORT"}
        and not stale_flag
    )
    if _ib_override_eligible:
        _ib_confidence = int(_clip(78 + min(10, ib_ext * 8), 72, 90))
        return {
            "candidate": "TREND_EXPANSION",
            "direction": direction,
            "confidence": _ib_confidence,
            "conflict": conflict,
            "reason": "IB_BREAKOUT_VWAP_ACCEPTANCE_OVERRIDE",
        }

    if stale_flag:
        return {
            "candidate": "TRANSITION",
            "direction": "NONE",
            "confidence": 50,
            "conflict": conflict,
            "reason": stale_reason,
        }

    if macro in {"UNRESOLVED", "OPENING_AUCTION"} or "PREMARKET" in phase:
        return {
            "candidate": "TRANSITION",
            "direction": "NONE",
            "confidence": 55,
            "conflict": conflict,
            "reason": f"OPENING_OR_UNRESOLVED_{macro}",
        }

    early_phase = phase_bucket in {"EARLY_AM", "POST_IB_AM"}
    phase_allows_early_initiative = early_phase and phase_bucket != "LUNCH"
    if (
        phase_allows_early_initiative
        and developing_score >= EARLY_INITIATIVE_SCORE_MIN
        and initiative_direction in {"LONG", "SHORT"}
        and same_side_vwap_minutes >= 5
        and conflict < 55
    ):
        candidate = "TREND_COMPRESSION"
        confidence = 64 + int(min(16, (developing_score - EARLY_INITIATIVE_SCORE_MIN) * 0.6))
        if (
            developing_score >= 78
            and (ib_ext >= th.expansion_ib_ext or abs_velocity >= th.expansion_velocity)
            and late_extension_penalty < 45
        ):
            candidate = "TREND_EXPANSION"
            confidence += 6
        return {
            "candidate": candidate,
            "direction": initiative_direction,
            "confidence": int(_clip(confidence, 62, 88)),
            "conflict": conflict,
            "reason": "DEVELOPING_INITIATIVE_PHASE_AWARE",
        }

    if (
        macro_bracket
        and phase_bucket in {"EARLY_AM", "POST_IB_AM", "PM", "POWER_HOUR"}
        and developing_score >= BRACKET_INITIATIVE_SCORE_MIN
        and initiative_direction in {"LONG", "SHORT"}
        and (
            same_side_vwap_minutes >= 5
            or abs(close_vs_vwap) >= th.vwap_confirm_atr
            or abs(net_move) >= th.net_move_confirm_atr
        )
        and not hmm_transition
        and conflict < 55
    ):
        confidence = 60 + int(min(18, (developing_score - BRACKET_INITIATIVE_SCORE_MIN) * 0.7))
        if hmm_trending and hmm_vwap_agrees:
            confidence += 4
        # Promote to TREND_EXPANSION when bracket has clearly broken:
        # high initiative score + IB extension confirmed + strong VWAP separation.
        if (developing_score >= 70
                and ib_ext >= th.expansion_ib_ext
                and abs(close_vs_vwap) >= th.vwap_confirm_atr
                and abs(net_move) >= th.net_move_confirm_atr
                and same_side_vwap_minutes >= 10):
            return {
                "candidate": "TREND_EXPANSION",
                "direction": initiative_direction,
                "confidence": int(_clip(confidence + 8, 68, 88)),
                "conflict": conflict,
                "reason": "BRACKET_IB_BREAK_EXPANSION_PROMOTED",
            }
        return {
            "candidate": "TREND_COMPRESSION",
            "direction": initiative_direction,
            "confidence": int(_clip(confidence, 60, 84)),
            "conflict": conflict,
            "reason": "BRACKET_MACRO_WITH_INITIATIVE_EVIDENCE",
        }

    if conflict >= 55:
        return {
            "candidate": "TRANSITION",
            "direction": "NONE",
            "confidence": 55,
            "conflict": conflict,
            "reason": "HIGH_CONFLICT_STAGE_A_B_OR_PRICE_ACTION",
        }

    # Phase One Part 4 — HMM Transition is not a directional state. If macro
    # says trend while HMM is Transition, require explicit velocity plus IB
    # extension before allowing TREND_COMPRESSION; otherwise close the lane.
    if macro_trend and hmm_transition:
        if (
            direction in {"LONG", "SHORT"}
            and ib_ext >= th.expansion_ib_ext
            and abs_velocity >= th.expansion_velocity
        ):
            # If IB extension also exceeds the strong threshold, promote to
            # expansion — the escape hatch from Transition should be able to
            # wake the Expansion bot when price evidence is unambiguous.
            if ib_ext >= th.strong_ib_ext:
                return {
                    "candidate": "TREND_EXPANSION",
                    "direction": direction,
                    "confidence": 72,
                    "conflict": conflict,
                    "reason": "TRANSITION_IB_CONFIRMED_EXPANSION",
                }
            return {
                "candidate": "TREND_COMPRESSION",
                "direction": direction,
                "confidence": 62,
                "conflict": conflict,
                "reason": "TRANSITION_MACRO_VELOCITY_IB_CONFIRMED",
            }
        return {
            "candidate": "TRANSITION",
            "direction": "NONE",
            "confidence": 52,
            "conflict": conflict,
            "reason": "HMM_TRANSITION_TREND_BLOCKED",
        }

    # TREND_EXPANSION: HMM direction + VWAP agreement + IB extension + velocity.
    if (
        hmm_trending
        and hmm_vwap_agrees
        and ib_ext >= th.expansion_ib_ext
        and abs_velocity >= th.expansion_velocity
    ):
        confidence = 78
        confidence += int(min(10, 10 * (ib_ext / max(th.strong_ib_ext, 0.1))))
        confidence += int(min(8, 4 * abs_velocity))
        if not np.isnan(adx_5m) and adx_5m >= 22:
            confidence += 5
        if not np.isnan(chop_5m) and chop_5m <= 50:
            confidence += 4
        if not np.isnan(rvol_5m) and rvol_5m >= 1.10:
            confidence += 4

        return {
            "candidate": "TREND_EXPANSION",
            "direction": direction,
            "confidence": int(_clip(confidence, 70, 95)),
            "conflict": conflict,
            "reason": "HMM_VWAP_VELOCITY_IB_EXPANSION",
        }

    if (
        macro_trend
        and hmm_trending
        and hmm_vwap_agrees
        and (ib_ext >= th.expansion_ib_ext or abs_velocity >= th.expansion_velocity)
    ):
        return {
            "candidate": "TREND_EXPANSION",
            "direction": direction,
            "confidence": 76,
            "conflict": conflict,
            "reason": "MACRO_TREND_CONFIRMED_BY_HMM_AND_VWAP",
        }

    # TREND_COMPRESSION: the important missing bucket.
    if (
        hmm_trending
        and hmm_vwap_agrees
        and (
            macro_bracket
            or macro_trend
            or playbook in {"ROTATION_LIQUID", "TREND_COMPRESSION", "TREND_EXPANSION"}
        )
        and (
            ib_ext >= th.normal_ib_ext
            or abs_velocity >= th.compression_velocity
            or abs(net_move) >= 1.00
        )
    ):
        return {
            "candidate": "TREND_COMPRESSION",
            "direction": direction,
            "confidence": 66,
            "conflict": conflict,
            "reason": "MICRO_TREND_INSIDE_MACRO_STRUCTURE",
        }

    if macro_trend and (vwap_up or vwap_down):
        direction = "LONG" if vwap_up else "SHORT"
        return {
            "candidate": "TREND_COMPRESSION",
            "direction": direction,
            "confidence": 63,
            "conflict": conflict,
            "reason": "MACRO_TREND_WITHOUT_FULL_EXPANSION",
        }

    # ROTATION_LIQUID: exact check. Never substring-match "LIQUID".
    if (
        macro_bracket
        and playbook == "ROTATION_LIQUID"
        and abs_velocity < th.compression_velocity
        and not hmm_vwap_agrees
    ):
        return {
            "candidate": "ROTATION_LIQUID",
            "direction": "BOTH",
            "confidence": 64,
            "conflict": conflict,
            "reason": "BALANCED_TRADEABLE_RANGE",
        }

    if (
        macro_bracket
        and hmm_balance
        and playbook != "ROTATION_ILLIQUID"
        and abs(close_vs_vwap) < 0.75
    ):
        return {
            "candidate": "ROTATION_LIQUID",
            "direction": "BOTH",
            "confidence": 61,
            "conflict": conflict,
            "reason": "HMM_BALANCE_MACRO_BRACKET",
        }

    # ROTATION_ILLIQUID
    if playbook == "ROTATION_ILLIQUID" and abs_velocity < th.compression_velocity and abs(close_vs_vwap) < 0.50:
        return {
            "candidate": "ROTATION_ILLIQUID",
            "direction": "NONE",
            "confidence": 62,
            "conflict": conflict,
            "reason": "COMPRESSED_BALANCE_LOW_EDGE",
        }

    if hmm_transition or returned_open == 1:
        return {
            "candidate": "TRANSITION",
            "direction": "NONE",
            "confidence": 52,
            "conflict": conflict,
            "reason": "HMM_TRANSITION_OR_RETURN_TO_OPEN",
        }

    return {
        "candidate": "TRANSITION",
        "direction": "NONE",
        "confidence": 50,
        "conflict": conflict,
        "reason": "NO_CLEAR_STAGE_C_ALIGNMENT",
    }


def required_confirmations(candidate: str, confidence: int, current_official: str) -> int:
    """
    State-dependent persistence:
    TRANSITION immediate.
    TREND_COMPRESSION immediate because it is the early trend-warning state.
    TREND_EXPANSION usually needs 2 checkpoints unless confidence is strong or already compressed.
    ROTATION_ILLIQUID needs 2 confirmations so the model does not shut off too aggressively.
    """
    if candidate == "TRANSITION":
        return 1
    if candidate == "TREND_COMPRESSION":
        return 1
    if candidate == "TREND_EXPANSION":
        if confidence >= 82 or current_official == "TREND_COMPRESSION":
            return 1
        return 2
    if candidate == "ROTATION_LIQUID":
        return 1
    if candidate == "ROTATION_ILLIQUID":
        return 2
    return 1


def apply_persistence(instrument: str, candidate: str, direction: str, confidence: int) -> Tuple[str, str, int, str]:
    state = states[instrument]

    if candidate not in FINAL_REGIMES:
        candidate = "TRANSITION"
        direction = "NONE"

    needed = required_confirmations(candidate, confidence, state.official_regime)

    if candidate == state.official_regime:
        state.pending_regime = candidate
        state.pending_count = 0
        state.official_direction = direction
        return state.official_regime, state.official_direction, 0, "UNCHANGED"

    if needed <= 1:
        state.official_regime = candidate
        state.official_direction = direction
        state.pending_regime = candidate
        state.pending_count = 0
        return state.official_regime, state.official_direction, 0, "LOCKED_IMMEDIATE"

    if candidate == state.pending_regime:
        state.pending_count += 1
    else:
        state.pending_regime = candidate
        state.pending_count = 1

    if state.pending_count >= needed:
        state.official_regime = candidate
        state.official_direction = direction
        state.pending_count = 0
        return state.official_regime, state.official_direction, 0, f"LOCKED_AFTER_{needed}_CONFIRMATIONS"

    return (
        state.official_regime,
        state.official_direction,
        state.pending_count,
        f"PENDING_{candidate}_{state.pending_count}_OF_{needed}",
    )


def map_bot_permissions(
    instrument: str,
    final_regime: str,
    direction: str,
    raw_macro: str,
    phase: str,
    confidence: int,
    conflict: int = 0,
    hmm_regime: str = "Unknown",
    hmm_state_age: int = 0,
    macro_stale: bool = False,
    macro_stale_reason: str = "",
) -> Tuple[dict, str]:
    """
    Produces both legacy lane names and cleaner future bot names.

    Returns (flags, asym_reason). asym_reason is a Phase One Recommended
    Change #1 audit token (HYST_PASSED_*, HYST_BLOCK_*, or HYST_DISABLED).
    Caller writes asym_reason into the BotPermissionGateReason audit field.

    The gate is evaluated AFTER the legacy permission table so that the
    asymmetric hysteresis rule's hard-close branches (macro stale, ES TrendUp
    quarantine, under-age HMM) zero out all bot permissions consistently.
    """
    flags = {
        "AllowMomo": False,
        "AllowAdxx": False,
        "AllowPine": False,
        "AllowEsScalper": False,
        "AllowBracketSniper": False,
        "AllowExpansionBot": False,
        "AllowCompressionBot": False,
        "AllowFadeBot": False,
        "AllowLong": False,
        "AllowShort": False,
        "AllowMomoLong": False,
        "AllowMomoShort": False,
    }

    if direction in {"LONG", "BOTH"}:
        flags["AllowLong"] = True
    if direction in {"SHORT", "BOTH"}:
        flags["AllowShort"] = True

    if final_regime == "TREND_EXPANSION":
        flags["AllowExpansionBot"] = True
        flags["AllowMomo"] = True
        flags["AllowAdxx"] = True
        flags["AllowPine"] = True

    elif final_regime == "TREND_COMPRESSION":
        flags["AllowCompressionBot"] = True
        flags["AllowMomo"] = True
        flags["AllowPine"] = True
        flags["AllowAdxx"] = False

    elif final_regime == "ROTATION_LIQUID":
        flags["AllowFadeBot"] = True
        flags["AllowBracketSniper"] = True
        flags["AllowPine"] = True
        flags["AllowLong"] = True
        flags["AllowShort"] = True

    elif final_regime in {"ROTATION_ILLIQUID", "TRANSITION"}:
        pass

    # Optional ES opening scalper lane.
    raw_macro_u = _upper(raw_macro)
    phase_u = _upper(phase)
    if (
        instrument == "ES"
        and raw_macro_u in {"UNRESOLVED", "OPENING_AUCTION"}
        and ("OPENING" in phase_u or "EARLY" in phase_u)
        and final_regime == "TRANSITION"
    ):
        flags["AllowEsScalper"] = True

    # Low-confidence trend decisions should not open trend bots.
    if confidence < 55:
        flags["AllowExpansionBot"] = False
        flags["AllowCompressionBot"] = False
        flags["AllowMomo"] = False
        flags["AllowAdxx"] = False

    # Strategy-specific directional gates. These are stricter than the legacy
    # universal AllowMomo lane and are intended for V3C SIM testing.
    phase_bucket = _phase_bucket(0, phase_u) if phase_u else "UNKNOWN"
    momo_phase_block = "LUNCH" in phase_u or "CASH_CLOSE" in phase_u or phase_bucket in {"LUNCH", "CLOSE"}
    momo_trend_lane = final_regime in {"TREND_EXPANSION", "TREND_COMPRESSION"}
    momo_quality_ok = confidence >= 55 and conflict <= 50 and not momo_phase_block
    if flags["AllowMomo"] and momo_trend_lane and momo_quality_ok:
        flags["AllowMomoLong"] = direction in {"LONG", "BOTH"}
        flags["AllowMomoShort"] = direction in {"SHORT", "BOTH"}
        flags["AllowMomo"] = flags["AllowMomoLong"] or flags["AllowMomoShort"]
    else:
        flags["AllowMomo"] = False

    # Phase One Recommended Change #1 — Asymmetric Hysteresis hard close.
    # Applied after all permission lanes are computed so that block decisions
    # consistently zero everything out, including legacy lanes like Pine and
    # ESScalper. Audit reason is returned to caller for BotPermissionGateReason.
    asym_open, asym_reason = compute_asymmetric_hysteresis_gate(
        hmm_regime=hmm_regime,
        macro_regime=raw_macro,
        symbol=instrument,
        hmm_state_age=hmm_state_age,
        macro_stale=macro_stale,
        macro_stale_reason=macro_stale_reason,
    )
    if not asym_open:
        for key in flags:
            flags[key] = False

    return flags, asym_reason


def build_v3c_row(
    instrument: str,
    macro_row: pd.Series,
    micro_row: Optional[pd.Series],
    macro_ts: pd.Timestamp,
    micro_ts: Optional[pd.Timestamp],
    final_regime: str,
    final_direction: str,
    candidate_info: dict,
    pending_count: int,
    persistence_status: str,
    velocity_3cp: float,
    hmm_flip_count: int,
    stale_flag: bool,
    stale_reason: str,
    permissions: dict,
    hmm_state_age: int = 0,
    asym_hyst_reason: str = "HYST_DISABLED",
) -> dict:
    raw_macro = str(macro_row.get("official_regime_label", "UNRESOLVED"))
    raw_playbook = str(macro_row.get("playbook_state", "TRANSITION"))
    hmm_label = str(micro_row.get("RegimeLabel", "Unknown")) if micro_row is not None else "Unknown"

    row = {
        "SnapshotTimestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "MacroTimestamp": macro_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "MicroTimestamp": micro_ts.strftime("%Y-%m-%d %H:%M:%S") if micro_ts is not None else "",
        "Instrument": instrument,

        # Stage A / Stage B
        "MacroRegime": raw_macro,
        "MacroPlaybook": raw_playbook,
        "HMM_Micro": hmm_label,
        "Phase": str(macro_row.get("phase", "")),

        # Stage C
        "CandidateRegime": candidate_info.get("candidate", "TRANSITION"),
        "FinalRegime": final_regime,
        "FinalDirection": final_direction,
        "RegimeConfidence": int(candidate_info.get("confidence", 0)),
        "ConflictScore": int(candidate_info.get("conflict", 0)),
        "ReasonCode": candidate_info.get("reason", ""),
        "PersistenceStatus": persistence_status,
        "PendingCount": pending_count,

        # Key features
        "Velocity3CP": velocity_3cp,
        "HMMFlipCount": hmm_flip_count,
        "PhaseBucket": str(macro_row.get("phase_bucket", _phase_bucket(_safe_float(macro_row.get("minutes_from_open", 0)), str(macro_row.get("phase", ""))))),
        "DevelopingInitiativeScore": _safe_float(macro_row.get("developing_initiative_score", 0)),
        "InitiativeDirection": str(macro_row.get("initiative_direction", "NONE")),
        "RollingEfficiency10m": _safe_float(macro_row.get("rolling_efficiency_10m", 0)),
        "RollingEfficiency20m": _safe_float(macro_row.get("rolling_efficiency_20m", 0)),
        "LocalNetMove10mAtr": _safe_float(macro_row.get("local_net_move_10m_atr", 0)),
        "SameSideVwapMinutes": _safe_float(macro_row.get("same_side_vwap_minutes", 0)),
        "VwapHoldCount": _safe_float(macro_row.get("vwap_hold_count", 0)),
        "LateExtensionPenalty": _safe_float(macro_row.get("late_extension_penalty", 0)),
        "HMMStateProb": _safe_float(micro_row.get("StateProb", np.nan), np.nan) if micro_row is not None else np.nan,
        "HMMStateMargin": _safe_float(micro_row.get("StateMargin", np.nan), np.nan) if micro_row is not None else np.nan,
        "HMMStateEntropy": _safe_float(micro_row.get("StateEntropy", np.nan), np.nan) if micro_row is not None else np.nan,
        "HMMStateAge": _safe_int(micro_row.get("StateAge", 0), 0) if micro_row is not None else 0,
        "IBExtensionPct": _safe_float(macro_row.get("ib_extension_pct", 0)),
        "CloseVsVwapAtr": _safe_float(macro_row.get("close_vs_vwap_atr", 0)),
        "NetMoveAtr": _safe_float(macro_row.get("net_move_since_open_atr", 0)),
        "DirectionalEfficiency": _safe_float(macro_row.get("directional_efficiency_since_open", 0)),
        "ReturnedToOpenFlag": _safe_int(macro_row.get("returned_to_open_flag", 0)),
        "TwoSidedTradeFlag": _safe_int(macro_row.get("two_sided_trade_flag", 0)),
        "ValueBreakAcceptFlag": _safe_int(macro_row.get("value_break_accept_flag", 0)),
        "LastPrice": _safe_float(macro_row.get("last_price", 0)),
        "Atr5m": _safe_float(macro_row.get("atr_5m", 0)),

        # Optional future fields
        "Adx5m": _safe_float(macro_row.get("adx_5m", np.nan), np.nan),
        "Chop5m": _safe_float(macro_row.get("chop_5m", np.nan), np.nan),
        "Rvol5m": _safe_float(macro_row.get("rvol_5m", np.nan), np.nan),

        # Safety
        "StaleDataFlag": _bool_text(stale_flag),
        "StaleReason": stale_reason,

        # Phase One Recommended Change #1 — Asymmetric Hysteresis audit fields.
        # HMMStateAgeBars is the supervisor-tracked persistence counter for the
        # underlying HMM micro state. It is distinct from HMMStateAge (which
        # comes from the micro_row's own StateAge column emitted by the HMM
        # watchdog) and from PendingCount (which counts FinalRegime confirmations
        # in apply_persistence). All three are written so analysts can compare.
        "HMMStateAgeBars": int(hmm_state_age),
        "AsymHysteresisReason": str(asym_hyst_reason),
        "AsymHysteresisGateOpen": _bool_text(not str(asym_hyst_reason).startswith("HYST_BLOCK_")),
        "AsymHysteresisEnabled": _bool_text(ASYMMETRIC_HYSTERESIS_ENABLED),
    }

    for key, value in permissions.items():
        row[key] = _bool_text(value)

    return row


def process_instrument(instrument: str, paths: dict, now_ts: pd.Timestamp) -> Optional[dict]:
    df_macro = read_first_available_csv(paths["macro"], paths.get("macro_fallback"))
    df_micro = read_first_available_csv(paths["micro"], paths.get("micro_fallback"))

    if df_macro is None or df_micro is None:
        return None

    macro_row = get_latest_macro_row(df_macro, now_ts)
    if macro_row is None:
        return None

    macro_ts = make_macro_timestamp(macro_row)
    if macro_ts is None:
        return None

    trade_date = str(macro_row.get("trade_date", ""))
    reset_if_new_trade_date(instrument, trade_date)

    micro_row, micro_ts = get_asof_micro_row(df_micro, macro_ts)
    hmm_label = str(micro_row.get("RegimeLabel", "Unknown")) if micro_row is not None else "Unknown"

    # Avoid repeated duplicate output for the same macro+micro checkpoint pair.
    # Live HMM can refresh after a macro checkpoint has already been processed.
    if states[instrument].last_processed_macro_ts is not None:
        last_macro_ts = states[instrument].last_processed_macro_ts
        last_micro_ts = states[instrument].last_processed_micro_ts
        same_or_older_macro = macro_ts <= last_macro_ts
        same_or_older_micro = (
            micro_ts is None
            or (last_micro_ts is not None and micro_ts <= last_micro_ts)
        )
        if same_or_older_macro and same_or_older_micro:
            return None

    current_price = _safe_float(macro_row.get("last_price", 0.0))
    current_atr = _safe_float(macro_row.get("atr_5m", 1.0), 1.0)

    velocity_3cp = calculate_velocity(instrument, macro_ts, current_price, current_atr)
    hmm_flip_count = update_hmm_history(instrument, micro_ts, hmm_label)
    # Phase One Recommended Change #1 — track HMM micro-state age in parallel
    # with the existing 5-bar flip counter. Used by the asymmetric hysteresis
    # gate below.
    hmm_state_age = update_hmm_state_age(instrument, hmm_label)
    stale_flag, stale_reason = detect_stale_data(now_ts, macro_ts, micro_ts)

    macro_for_classify = macro_row.copy()
    if micro_row is not None:
        for diag_col in ["StateProb", "StateMargin", "StateEntropy", "StateAge"]:
            if diag_col in micro_row:
                macro_for_classify[diag_col] = micro_row.get(diag_col)

    candidate_info = classify_v3c_candidate(
        instrument=instrument,
        macro_row=macro_for_classify,
        hmm_label_raw=hmm_label,
        velocity_3cp=velocity_3cp,
        hmm_flip_count=hmm_flip_count,
        stale_flag=stale_flag,
        stale_reason=stale_reason,
    )

    final_regime, final_direction, pending_count, persistence_status = apply_persistence(
        instrument=instrument,
        candidate=candidate_info["candidate"],
        direction=candidate_info["direction"],
        confidence=int(candidate_info["confidence"]),
    )

    permissions, asym_hyst_reason = map_bot_permissions(
        instrument=instrument,
        final_regime=final_regime,
        direction=final_direction,
        raw_macro=str(macro_row.get("official_regime_label", "UNRESOLVED")),
        phase=str(macro_row.get("phase", "")),
        confidence=int(candidate_info["confidence"]),
        conflict=int(candidate_info.get("conflict", 0)),
        hmm_regime=hmm_label,
        hmm_state_age=hmm_state_age,
        macro_stale=stale_flag,
        macro_stale_reason=stale_reason,
    )

    row = build_v3c_row(
        instrument=instrument,
        macro_row=macro_row,
        micro_row=micro_row,
        macro_ts=macro_ts,
        micro_ts=micro_ts,
        final_regime=final_regime,
        final_direction=final_direction,
        candidate_info=candidate_info,
        pending_count=pending_count,
        persistence_status=persistence_status,
        velocity_3cp=velocity_3cp,
        hmm_flip_count=hmm_flip_count,
        stale_flag=stale_flag,
        stale_reason=stale_reason,
        permissions=permissions,
        hmm_state_age=hmm_state_age,
        asym_hyst_reason=asym_hyst_reason,
    )

    append_csv_row(row, paths["history_output"])
    atomic_write_csv(pd.DataFrame([row]), paths["latest_output"])

    states[instrument].last_processed_macro_ts = macro_ts
    states[instrument].last_processed_micro_ts = micro_ts

    return row


def run_supervisor() -> None:
    print("=" * 90)
    print("V3C Regime Matrix Supervisor started.")
    print(f"BASE_DIR:   {BASE_DIR}")
    print(f"ACTIVE_DIR: {ACTIVE_DIR}")
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")
    print(f"Stale Guard Enabled: {STALE_GUARD_ENABLED}")
    print("=" * 90)

    last_file_mods = {inst: {"macro": 0.0, "micro": 0.0} for inst in INSTRUMENTS}

    while True:
        try:
            now_ts = pd.Timestamp(datetime.now())

            for inst, paths in INSTRUMENTS.items():
                macro_path = paths["macro"] if os.path.exists(paths["macro"]) else paths.get("macro_fallback")
                micro_path = paths["micro"] if os.path.exists(paths["micro"]) else paths.get("micro_fallback")

                if not macro_path or not micro_path or not os.path.exists(macro_path) or not os.path.exists(micro_path):
                    continue

                macro_mod = os.path.getmtime(macro_path)
                micro_mod = os.path.getmtime(micro_path)

                changed = (
                    macro_mod > last_file_mods[inst]["macro"]
                    or micro_mod > last_file_mods[inst]["micro"]
                )

                if not changed:
                    continue

                last_file_mods[inst]["macro"] = macro_mod
                last_file_mods[inst]["micro"] = micro_mod

                row = process_instrument(inst, paths, now_ts)

                if row is not None:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"{inst} V3C | Final={row['FinalRegime']} "
                        f"Dir={row['FinalDirection']} "
                        f"Conf={row['RegimeConfidence']} "
                        f"Vel={row['Velocity3CP']} "
                        f"Reason={row['ReasonCode']} "
                        f"Persist={row['PersistenceStatus']}"
                    )

        except KeyboardInterrupt:
            print("Supervisor stopped by user.")
            break

        except Exception:
            print("--- SUPERVISOR ERROR ---")
            traceback.print_exc()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_supervisor()
