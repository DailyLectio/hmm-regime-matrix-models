"""
RegimeSupervisor_V3D.py — Stage C of the V3D Institutional Regime Matrix
Merges Stage A (Macro) and Stage B (HMM) classifications into final regime states
with bot permissions, confidence scoring, and position sizing.

Run modes:
    --batch     Process full history, write RegimeMatrix_Full.csv
    --live      Continuous loop, atomic write to RegimeMatrix_Latest.csv
    --symbol    NQ | ES | BOTH (default: BOTH)
    --interval  Loop sleep seconds in live mode (default: 30)
    --shadow    Write with _SHADOW suffix (for testing)

Usage examples:
    python RegimeSupervisor_V3D.py --batch --symbol BOTH
    python RegimeSupervisor_V3D.py --live --interval 30
    python RegimeSupervisor_V3D.py --batch --symbol NQ --shadow
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = r"C:\V3D"   # Junction alias for C:\Users\Valued Customer\NT8_Regimes
INPUT_DIR  = os.path.join(BASE_DIR, "V3D")
OUTPUT_DIR = os.path.join(BASE_DIR, "V3D")
BACKTEST_DIR = os.path.join(BASE_DIR, "Backtest")
HISTORY_DIR  = os.path.join(OUTPUT_DIR, "History")

# Input files (Stage A and B outputs)
MACRO_FILES = {
    "NQ": os.path.join(INPUT_DIR, "NQ_Macro_Regimes_V3D.csv"),
    "ES": os.path.join(INPUT_DIR, "ES_Macro_Regimes_V3D.csv"),
}
HMM_FILES = {
    "NQ": os.path.join(INPUT_DIR, "NQ_HMM_Regimes_V3D.csv"),
    "ES": os.path.join(INPUT_DIR, "ES_HMM_Regimes_V3D.csv"),
}

# Output files
LATEST_FILES = {
    "NQ": os.path.join(OUTPUT_DIR, "NQ_RegimeMatrix_Latest.csv"),
    "ES": os.path.join(OUTPUT_DIR, "ES_RegimeMatrix_Latest.csv"),
}
FULL_FILES = {
    "NQ": os.path.join(BACKTEST_DIR, "NQ_RegimeMatrix_Full.csv"),
    "ES": os.path.join(BACKTEST_DIR, "ES_RegimeMatrix_Full.csv"),
}
HISTORY_FILES = {
    "NQ": os.path.join(HISTORY_DIR, "NQ_RegimeMatrix_History.csv"),
    "ES": os.path.join(HISTORY_DIR, "ES_RegimeMatrix_History.csv"),
}

# ---------------------------------------------------------------------------
# Regime Classification Thresholds
# ---------------------------------------------------------------------------
# Per-symbol thresholds (from Section 4)
THRESHOLDS = {
    "NQ": {
        "velocity_strong": 0.85,
        "ib_strong": 0.85,
        "vwap_confirm": 0.40,
    },
    "ES": {
        "velocity_strong": 1.00,
        "ib_strong": 1.00,
        "vwap_confirm": 0.50,
    },
}

# Phase confidence multipliers (Section 6)
PHASE_MULTIPLIERS = {
    "OPENING_AUCTION":        {"trend": 0.80, "rotation": 1.10},
    "EARLY_TEST":             {"trend": 0.88, "rotation": 1.05},
    "FIRST_ACCEPTANCE":       {"trend": 0.95, "rotation": 1.00},
    "PRE_IB_MATURATION":      {"trend": 0.85, "rotation": 1.05},
    "POST_IB_MACRO":          {"trend": 1.10, "rotation": 0.95},
    "MID_MORNING_DISCOVERY":  {"trend": 1.00, "rotation": 1.00},
    "LUNCH_AUCTION":          {"trend": 0.75, "rotation": 1.15},
    "POST_LUNCH_ROTATION":    {"trend": 0.90, "rotation": 1.00},
    "AFTERNOON_TREND_TEST":   {"trend": 1.05, "rotation": 0.95},
    "LATE_DAY_CONVICTION":    {"trend": 0.80, "rotation": 0.90},
    "CASH_CLOSE":             {"trend": 0.60, "rotation": 0.70},
}

# Default multiplier for unknown phases
DEFAULT_MULTIPLIERS = {"trend": 1.00, "rotation": 1.00}

# Macro-only early-session thrust thresholds. This override is intentionally
# narrow and only promotes to TREND_COMPRESSION, never TREND_EXPANSION.
EXTREME_THRUST_THRESH = {"NQ": 1.50, "ES": 1.00}

# Instrument-aware HMM weighting. NQ HMM trend blocks are late but meaningful;
# ES HMM TrendUp/TrendDown is a session-boundary artifact, while ES Balance is
# useful as rotation context.
HMM_TREND_WEIGHT = {"NQ": 0.40, "ES": 0.10}
HMM_ROTATION_WEIGHT = {"NQ": 0.30, "ES": 0.50}

# Conflict threshold for TRANSITION state
CONFLICT_THRESHOLD = 0.40

# Minimum confidence thresholds for regime classification
MIN_TREND_EXPANSION_CONFIDENCE = 70
MIN_TREND_COMPRESSION_CONFIDENCE = 60
MIN_TREND_EMERGING_CONFIDENCE = 40
MIN_ROTATION_LIQUID_CONFIDENCE = 55

# SIM testing loosens scout/compression entry so live paper validation can
# exercise the bots without changing the production thresholds above.
SIM_TREND_COMPRESSION_CONFIDENCE = 50
SIM_TREND_EMERGING_CONFIDENCE = 30

# State persistence gate
MIN_STATE_AGE_BARS = 2  # TREND_EXPANSION requires 2+ bars persistence
MIN_BOT_PERMISSION_AGE_BARS = 2  # New compression/emerging labels hold Momo/Sniper briefly
MIN_TRANSITION_EXIT_BOT_AGE_BARS = 3  # Transition exits need extra proof before Momo/Sniper resume
REGIME_FLIP_LOOKBACK_BARS = 10
MAX_REGIME_FLIPS_10BAR = 4

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("RegimeSupervisor_V3D")


# ===========================================================================
# KALMAN FILTER — smooths TrendExpansionScore
# ===========================================================================

def get_kalman_params(phase: str) -> dict:
    """Return phase-specific Kalman Q/R values."""
    if phase in ("OPENING_AUCTION", "EARLY_TEST"):
        return {"Q": 0.12, "R": 0.10}
    if phase == "FIRST_ACCEPTANCE":
        return {"Q": 0.08, "R": 0.12}
    return {"Q": 0.05, "R": 0.15}


class KalmanScoreFilter:
    """
    Single-state Kalman filter for smoothing regime confidence scores.
    Parameters are updated per phase before each observation.
    """
    def __init__(self, Q: float = 0.05, R: float = 0.15):
        # Q/R are set dynamically by phase before each observation.
        self.Q = Q  # Process noise
        self.R = R  # Observation noise
        self.x = 0.5  # Initial state (neutral)
        self.P = 1.0  # Initial uncertainty

    def set_params(self, params: Dict[str, float]) -> None:
        """Update Q/R without resetting the filter state."""
        self.Q = float(params.get("Q", self.Q))
        self.R = float(params.get("R", self.R))

    def update(self, z: float) -> float:
        """Update filter with new observation z, return smoothed estimate."""
        # Prediction
        P_pred = self.P + self.Q
        
        # Update
        K = P_pred / (P_pred + self.R)
        self.x = self.x + K * (z - self.x)
        self.P = (1 - K) * P_pred
        
        return self.x

    def reset(self):
        """Reset filter state (call at session boundaries)."""
        self.x = 0.5
        self.P = 1.0


# ===========================================================================
# DATA LOADING
# ===========================================================================

def load_macro_regimes(symbol: str) -> pd.DataFrame:
    """Load Stage A macro regime CSV."""
    path = MACRO_FILES[symbol]
    if not os.path.exists(path):
        raise FileNotFoundError(f"Macro regimes file not found: {path}")
    
    df = pd.read_csv(path)
    log.info(f"[{symbol}] Loaded macro regimes: {len(df)} rows")
    return df


def load_hmm_regimes(symbol: str) -> pd.DataFrame:
    """Load Stage B HMM regime CSV."""
    path = HMM_FILES[symbol]
    if not os.path.exists(path):
        raise FileNotFoundError(f"HMM regimes file not found: {path}")
    
    df = pd.read_csv(path)
    log.info(f"[{symbol}] Loaded HMM regimes: {len(df)} rows")
    return df


def merge_stages(macro_df: pd.DataFrame, hmm_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Merge Stage A checkpoints with the most recent non-stale Stage B HMM row.
    Returns unified DataFrame with all input columns plus derived metrics.
    """
    macro = macro_df.copy()
    hmm = hmm_df.copy()

    macro["_join_dt"] = pd.to_datetime(
        macro["trade_date"].astype(str) + " " + macro["checkpoint_time"].astype(str),
        errors="coerce",
    )
    hmm["_join_dt"] = pd.to_datetime(hmm["TimestampET"], errors="coerce")
    hmm["HMM_TimestampET"] = hmm["TimestampET"]

    macro_bad = macro["_join_dt"].isna().sum()
    hmm_bad = hmm["_join_dt"].isna().sum()
    if macro_bad:
        log.warning(f"[{symbol}] Dropping {macro_bad} macro rows with invalid checkpoint timestamps")
    if hmm_bad:
        log.warning(f"[{symbol}] Dropping {hmm_bad} HMM rows with invalid timestamps")

    macro = macro.dropna(subset=["_join_dt"]).sort_values("_join_dt")
    hmm = hmm.dropna(subset=["_join_dt"]).sort_values("_join_dt")

    hmm_lookup = hmm.drop(columns=["session_key", "TimestampET"], errors="ignore")
    merged = pd.merge_asof(
        macro,
        hmm_lookup,
        on="_join_dt",
        direction="backward",
        tolerance=pd.Timedelta("10min"),
    )

    unmatched = merged["RegimeLabel"].isna().sum() if "RegimeLabel" in merged.columns else len(merged)
    if unmatched:
        log.warning(f"[{symbol}] Dropping {unmatched} macro rows with no HMM reading within 10 minutes")
        merged = merged.dropna(subset=["RegimeLabel"])

    # Macro checkpoint drives the output timestamp; HMM_TimestampET records the
    # as-of lookup source for diagnostics.
    merged["TimestampET"] = merged["_join_dt"]
    merged["HMMJoinLagMinutes"] = (
        merged["TimestampET"] - pd.to_datetime(merged["HMM_TimestampET"], errors="coerce")
    ).dt.total_seconds() / 60.0
    merged.drop(columns=["_join_dt"], inplace=True, errors="ignore")

    log.info(
        f"[{symbol}] As-of merged {len(merged)} rows "
        f"(macro {len(macro_df)}, hmm {len(hmm_df)}, tolerance 10min)"
    )

    merged.sort_values("TimestampET", inplace=True)
    merged.reset_index(drop=True, inplace=True)
    
    return merged


# ===========================================================================
# SCORING FUNCTIONS
# ===========================================================================

def hmm_trend_scale(symbol: str) -> float:
    """Scale HMM trend contribution relative to the NQ baseline."""
    baseline = HMM_TREND_WEIGHT["NQ"]
    return HMM_TREND_WEIGHT.get(symbol, baseline) / baseline


def hmm_trend_is_reliable(symbol: str) -> bool:
    """Whether HMM trend labels can independently support trend classification."""
    return HMM_TREND_WEIGHT.get(symbol, HMM_TREND_WEIGHT["NQ"]) >= 0.25


def hmm_regime_direction(hmm_regime: str) -> str:
    if hmm_regime == "TrendUp":
        return "LONG"
    if hmm_regime == "TrendDown":
        return "SHORT"
    return "NEUTRAL"


def determine_direction(row: pd.Series, symbol: str) -> str:
    """Prefer macro direction; only use HMM direction for instruments where it is reliable."""
    macro_bias = row.get("official_bias_label", "")
    if macro_bias in ("LONG", "SHORT"):
        return macro_bias

    hmm_direction = hmm_regime_direction(row.get("RegimeLabel", ""))
    if hmm_trend_is_reliable(symbol) and hmm_direction != "NEUTRAL":
        return hmm_direction

    return "NEUTRAL"


def hmm_confirms_macro_direction(row: pd.Series, symbol: str) -> bool:
    """Return True only when a reliable HMM trend agrees with macro direction."""
    if not hmm_trend_is_reliable(symbol):
        return False

    macro_bias = row.get("official_bias_label", "")
    hmm_direction = hmm_regime_direction(row.get("RegimeLabel", ""))
    return macro_bias in ("LONG", "SHORT") and macro_bias == hmm_direction


def compute_trend_expansion_score(row: pd.Series, symbol: str) -> float:
    """
    Compute raw TrendExpansionScore from macro + HMM signals.
    Returns 0-100 score before Kalman smoothing.
    """
    thr = THRESHOLDS[symbol]
    score = 0.0
    
    # Component 1: IB breakout confirmed (30 points max)
    ib_ext = row.get("ib_extension_pct", 0.0)
    if ib_ext > 0.50:
        score += 30
    elif ib_ext > 0.25:
        score += 20
    elif ib_ext > 0.10:
        score += 10
    
    # Component 2: Velocity confirmation (25 points max)
    vel = abs(row.get("velocity_3cp_atr", 0.0))
    if vel >= thr["velocity_strong"]:
        score += 25
    elif vel >= thr["velocity_strong"] * 0.70:
        score += 15
    
    # Component 3: VWAP separation (20 points max)
    vwap_sep = abs(row.get("close_vs_vwap_atr", 0.0))
    if vwap_sep >= thr["vwap_confirm"]:
        score += 20
    elif vwap_sep >= thr["vwap_confirm"] * 0.60:
        score += 10
    
    # Component 4: HMM directional agreement (15 points max)
    hmm_regime = row.get("RegimeLabel", "")
    official_bias = row.get("official_bias_label", "")
    hmm_scale = hmm_trend_scale(symbol)
    
    if hmm_regime in ["TrendUp", "TrendDown"]:
        if (hmm_regime == "TrendUp" and official_bias == "LONG") or \
           (hmm_regime == "TrendDown" and official_bias == "SHORT"):
            score += 15 * hmm_scale
        else:
            score += 5 * hmm_scale  # Partial credit for HMM trend but wrong direction
    
    # Component 5: Directional efficiency (10 points max)
    de = row.get("de_effective", 0.0)
    if de >= 0.70:
        score += 10
    elif de >= 0.50:
        score += 5
    
    return min(100.0, score)


def compute_conflict_score(row: pd.Series, symbol: str) -> float:
    """
    Compute ConflictScore: degree of disagreement between macro and HMM.
    Returns 0.0 (perfect agreement) to 1.0 (maximum conflict).
    """
    conflict = 0.0
    
    # Conflict 1: Macro says TREND, HMM says Balance (strong conflict)
    macro_regime = row.get("official_regime_label", "")
    hmm_regime = row.get("RegimeLabel", "")
    trend_scale = min(1.0, hmm_trend_scale(symbol))
    
    if macro_regime == "TREND" and hmm_regime == "Balance":
        conflict += 0.40 * trend_scale
    elif macro_regime == "BALANCE" and hmm_regime in ["TrendUp", "TrendDown"]:
        conflict += 0.40 * trend_scale
    
    # Conflict 2: Directional disagreement (moderate conflict)
    macro_bias = row.get("official_bias_label", "")
    if macro_regime == "TREND" and hmm_regime in ["TrendUp", "TrendDown"]:
        if (macro_bias == "LONG" and hmm_regime == "TrendDown") or \
           (macro_bias == "SHORT" and hmm_regime == "TrendUp"):
            conflict += 0.30 * trend_scale
    
    # Conflict 3: Macro ROTATION but low two-sided evidence (minor conflict)
    if macro_regime == "ROTATION":
        two_sided = row.get("two_sided_trade_flag", 0)
        if two_sided == 0:
            conflict += 0.15
    
    # Conflict 4: High HMM flip rate (state instability)
    flip_rate = row.get("HMM_FlipRate_5bar", 0.0)
    if flip_rate > 0.60:
        conflict += 0.15 * trend_scale
    
    return min(1.0, conflict)


def apply_phase_multipliers(
    trend_score: float,
    rotation_score: float,
    phase: str
) -> Tuple[float, float]:
    """
    Apply phase-specific multipliers to regime thresholds.
    Returns adjusted (trend_threshold, rotation_threshold).
    """
    mult = PHASE_MULTIPLIERS.get(phase, DEFAULT_MULTIPLIERS)
    
    # Base thresholds
    trend_base = MIN_TREND_EXPANSION_CONFIDENCE
    rotation_base = MIN_ROTATION_LIQUID_CONFIDENCE
    
    # Apply multipliers (higher multiplier = easier to trigger)
    trend_threshold = trend_base / mult["trend"]
    rotation_threshold = rotation_base / mult["rotation"]
    
    return trend_threshold, rotation_threshold


def extreme_thrust_override(phase: str, macro_row: pd.Series, symbol: str):
    """
    Macro-only early-session override for extreme opening thrusts.
    Returns a conservative TREND_COMPRESSION classification or None.
    """
    if phase not in ("OPENING_AUCTION", "EARLY_TEST"):
        return None

    try:
        nm = float(macro_row.get("net_move_since_open_atr", 0.0))
    except Exception:
        nm = 0.0
    try:
        vel = float(macro_row.get("velocity_3cp_atr", 0.0))
    except Exception:
        vel = 0.0

    if pd.isna(nm):
        nm = 0.0
    if pd.isna(vel):
        vel = 0.0

    thresh = EXTREME_THRUST_THRESH.get(symbol, 1.50)
    if abs(nm) >= thresh and abs(vel) >= thresh * 0.60:
        direction = "LONG" if nm > 0 else "SHORT"
        return {
            "FinalRegime": "TREND_COMPRESSION",
            "FinalDirection": direction,
            "RegimeConfidence": 50,
            "OverrideSource": "EXTREME_THRUST",
        }

    return None


# ===========================================================================
# REGIME CLASSIFICATION
# ===========================================================================

def classify_final_regime(
    row: pd.Series,
    kalman_score: float,
    conflict_score: float,
    symbol: str,
    prev_regime: str = None,
    state_age: int = 0,
    sim_test: bool = False
) -> Tuple[str, str, int, str]:
    """
    Final regime classification with priority chain.
    
    Returns: (FinalRegime, FinalDirection, RegimeConfidence, ReasonCode)
    """
    # Get phase multipliers
    phase = row.get("phase", "UNKNOWN")
    trend_threshold, rotation_threshold = apply_phase_multipliers(
        kalman_score, 0.0, phase
    )
    
    # Extract key signals
    macro_regime = row.get("official_regime_label", "")
    macro_bias = row.get("official_bias_label", "")
    hmm_regime = row.get("RegimeLabel", "")
    playbook_state = row.get("playbook_state", "")
    ib_width_atr = row.get("ib_width_atr", 0.0)
    two_sided = row.get("two_sided_trade_flag", 0)
    vel = abs(row.get("velocity_3cp_atr", 0.0))
    compression_threshold = (
        SIM_TREND_COMPRESSION_CONFIDENCE if sim_test
        else MIN_TREND_COMPRESSION_CONFIDENCE
    )
    emerging_threshold = (
        SIM_TREND_EMERGING_CONFIDENCE if sim_test
        else MIN_TREND_EMERGING_CONFIDENCE
    )
    
    # Determine direction. ES ignores HMM-only direction because its trend
    # labels are session-boundary artifacts; NQ can still use HMM direction.
    direction = determine_direction(row, symbol)
    
    # PRIORITY 1: TRANSITION (danger override)
    if conflict_score >= CONFLICT_THRESHOLD:
        return "TRANSITION", "NEUTRAL", 0, "HIGH_CONFLICT"
    
    # PRIORITY 2: TREND_EXPANSION
    if kalman_score >= trend_threshold:
        if playbook_state == "TREND_STRONG":
            # Apply state persistence gate
            if prev_regime == "TREND_EXPANSION" or state_age >= MIN_STATE_AGE_BARS:
                confidence = int(kalman_score)
                return "TREND_EXPANSION", direction, confidence, "STRONG_BREAKOUT"
            else:
                # Downgrade to compression until persistence confirmed
                confidence = int(kalman_score * 0.85)
                return "TREND_COMPRESSION", direction, confidence, "AWAITING_PERSISTENCE"
        elif macro_regime == "TREND" and hmm_confirms_macro_direction(row, symbol):
            confidence = int(kalman_score * 0.90)
            return "TREND_EXPANSION", direction, confidence, "MACRO_HMM_AGREE"
    
    # PRIORITY 3: TREND_COMPRESSION
    if macro_regime == "TREND" or (
            hmm_trend_is_reliable(symbol)
            and hmm_regime in ["TrendUp", "TrendDown"]):
        if kalman_score >= compression_threshold:
            confidence = int(kalman_score * 0.80)
            return "TREND_COMPRESSION", direction, confidence, "DIRECTIONAL_MODERATE"
    
    # PRIORITY 4: TREND_EMERGING — scout tier (added 2026-04-28)
    # Fires when macro and HMM both agree on direction but Kalman has not yet
    # cleared the compression threshold. Grants ADX_DI and Sniper
    # at half-confidence sizing. Prevents the full blackout that previously
    # occurred during the Kalman catch-up window on rotation → trend transitions.
    # Threshold: kalman_score >= 40 production / 30 SIM
    # AND macro_regime == "TREND" AND hmm_regime in [TrendUp, TrendDown]
    # AND direction is not NEUTRAL (both layers agree directionally)
    if (macro_regime == "TREND"
            and direction != "NEUTRAL"
            and kalman_score >= emerging_threshold
            and (symbol == "ES" or hmm_confirms_macro_direction(row, symbol))):
        confidence = max(25, int(kalman_score * 0.70))  # Conservative scout floor
        reason = "ES_MACRO_EMERGING" if symbol == "ES" else "EMERGING_SIGNAL"
        return "TREND_EMERGING", direction, confidence, reason

    # PRIORITY 5: ROTATION_LIQUID
    if two_sided == 1 and ib_width_atr >= 1.5:
        if playbook_state in ["ROTATION_LIQUID", "ROTATION_CHOP"]:
            rotation_boost = 0
            reason = "TWO_SIDED_CONFIRMED"
            if macro_regime == "ROTATION" and hmm_regime == "Balance":
                rotation_boost = int(20 * HMM_ROTATION_WEIGHT.get(symbol, 0.30))
                reason = "HMM_BALANCE_ROTATION_CONFIRMED"
            confidence = max(55, min(90, int(70 - conflict_score * 30 + rotation_boost)))
            return "ROTATION_LIQUID", "NEUTRAL", confidence, reason

    # PRIORITY 6: ROTATION_ILLIQUID (default fallback)
    return "ROTATION_ILLIQUID", "NEUTRAL", 40, "LOW_CONVICTION"


# ===========================================================================
# BOT PERMISSIONS AND SIZING
# ===========================================================================

def compute_bot_permission_gate_reason(
    final_regime: str,
    state_age: int = 0,
    prev_regime: str = None,
    flip_count_10bar: int = 0
) -> str:
    """Return diagnostic tags for supervisor-level bot permission gates."""
    reasons = []
    if flip_count_10bar >= MAX_REGIME_FLIPS_10BAR:
        reasons.append("CHOPPY_REGIME_FLIPS")
    if (
        state_age < MIN_BOT_PERMISSION_AGE_BARS
        and final_regime in ("TREND_COMPRESSION", "TREND_EMERGING")
    ):
        reasons.append("REGIME_PERMISSION_COOLDOWN")
    if (
        prev_regime == "TRANSITION"
        and final_regime != "TRANSITION"
        and state_age < MIN_TRANSITION_EXIT_BOT_AGE_BARS
    ):
        reasons.append("TRANSITION_EXIT_COOLDOWN")
    return "|".join(reasons) if reasons else "NONE"


def compute_bot_permissions(
    final_regime: str,
    final_direction: str,
    hmm_regime: str,
    conflict_score: float,
    state_age: int = 0,
    prev_regime: str = None,
    flip_count_10bar: int = 0,
    sim_test: bool = False
) -> Dict[str, int]:
    """
    Map FinalRegime to bot permission flags.
    Returns dict with Allow{Bot} and {Bot}SizePct keys.

    V3D Fader uses the Pine permission/size lane. In TREND_EXPANSION that lane
    only opens when HMM confirms the expansion direction; the directional fade
    flags decide which counter-trend side can actually trade.

    state_age is the number of consecutive bars this final regime label has
    persisted. Brand-new trend labels hold Momo/Sniper back to reduce whipsaw
    entries during regime transitions.
    """
    hmm_confirms_expansion = (
        final_regime == "TREND_EXPANSION"
        and final_direction in ("LONG", "SHORT")
        and hmm_regime_direction(hmm_regime) == final_direction
    )
    gate_reason = compute_bot_permission_gate_reason(
        final_regime, state_age, prev_regime, flip_count_10bar
    )
    
    # Base permission table (Section 6)
    BOT_PERMISSIONS = {
        "TREND_EXPANSION": {
            "AllowExpansion": 1, "AllowMomo": 1, "AllowPine": int(hmm_confirms_expansion),
            "AllowADX_DI": 0, "AllowSniper": 0,
        },
        "TREND_COMPRESSION": {
            "AllowExpansion": 0, "AllowMomo": 1, "AllowPine": 1,
            "AllowADX_DI": 0, "AllowSniper": 1,
        },
        "TREND_EMERGING": {
            # Scout tier — directional scouts only, half-size implied via confidence scalar
            # ADX_DI and Sniper fire; Momo/Pine/Expansion held until Kalman confirms
            "AllowExpansion": 0, "AllowMomo": 0, "AllowPine": 0,
            "AllowADX_DI": 1, "AllowSniper": 1,
        },
        "ROTATION_LIQUID": {
            "AllowExpansion": 0, "AllowMomo": 1, "AllowPine": 1,
            "AllowADX_DI": 1, "AllowSniper": 0,
        },
        "ROTATION_ILLIQUID": {
            "AllowExpansion": 0, "AllowMomo": 0, "AllowPine": 0,
            "AllowADX_DI": 0, "AllowSniper": 0,
        },
        "TRANSITION": {
            "AllowExpansion": 0, "AllowMomo": 0, "AllowPine": 0,
            "AllowADX_DI": 0, "AllowSniper": 0,
        },
    }
    
    perms = BOT_PERMISSIONS.get(final_regime, BOT_PERMISSIONS["TRANSITION"]).copy()
    
    # SIM testing opens the directional scout lane in moderate trend states.
    if sim_test and final_regime in ["TREND_COMPRESSION", "TREND_EMERGING"]:
        perms["AllowADX_DI"] = 1
        perms["AllowSniper"] = 1
    
    # Special case: Pine only in TREND_COMPRESSION if conflict < 0.35
    if final_regime == "TREND_COMPRESSION" and conflict_score >= 0.35:
        perms["AllowPine"] = 0

    if "REGIME_PERMISSION_COOLDOWN" in gate_reason or "TRANSITION_EXIT_COOLDOWN" in gate_reason:
        perms["AllowMomo"] = 0
        perms["AllowSniper"] = 0
    
    if "CHOPPY_REGIME_FLIPS" in gate_reason:
        for key in perms:
            perms[key] = 0
    
    return perms


def compute_size_pct(regime_confidence: int, conflict_score: float) -> int:
    """
    Convert RegimeConfidence to SizePct (0-100).
    Formula from Section 6.
    """
    if conflict_score >= 0.40:
        return max(25, int(regime_confidence * 0.6))
    
    # Linear scaling: confidence 50 → 0%, confidence 95 → 100%
    size_pct = int(min(100, max(25, (regime_confidence - 50) / 45 * 100)))
    return size_pct


def compute_directional_permissions(
    final_regime: str,
    final_direction: str,
    macro_bias: str,
    hmm_regime: str
) -> Dict[str, int]:
    """
    Compute AllowLong, AllowShort, AllowFadeLong, AllowFadeShort.
    """
    perms = {
        "AllowLong": 0,
        "AllowShort": 0,
        "AllowFadeLong": 0,
        "AllowFadeShort": 0,
    }
    
    # Trend-following permissions (Expansion, Momentum, Sniper)
    if final_regime in ["TREND_EXPANSION", "TREND_COMPRESSION"]:
        if final_direction == "LONG":
            perms["AllowLong"] = 1
        elif final_direction == "SHORT":
            perms["AllowShort"] = 1

    # Scout tier directional permissions — ADX_DI/Sniper fire during Kalman catch-up
    if final_regime == "TREND_EMERGING":
        if final_direction == "LONG":
            perms["AllowLong"] = 1
        elif final_direction == "SHORT":
            perms["AllowShort"] = 1

    # Expansion-fade permissions: fade the confirmed expansion direction only.
    if final_regime == "TREND_EXPANSION" and hmm_regime_direction(hmm_regime) == final_direction:
        if final_direction == "LONG":
            perms["AllowFadeShort"] = 1
        elif final_direction == "SHORT":
            perms["AllowFadeLong"] = 1

    # Rotation fade permissions remain bidirectional.
    if final_regime == "ROTATION_LIQUID":
        # Bidirectional fading allowed
        perms["AllowFadeLong"] = 1
        perms["AllowFadeShort"] = 1
        # Also allow trend-following in rotation for Momentum
        perms["AllowLong"] = 1
        perms["AllowShort"] = 1
    
    return perms


BOT_SIZE_SCHEMA = [
    ("Expansion", "AllowExpansion", "ExpansionSizePct", "AllowExpansion_SizePct", "EXP"),
    ("Momo", "AllowMomo", "MomoSizePct", "AllowMomo_SizePct", "MOMO"),
    ("Pine", "AllowPine", "PineSizePct", "AllowPine_SizePct", "PINE"),
    ("ADX_DI", "AllowADX_DI", "ADX_DISizePct", "AllowADX_DI_SizePct", "ADX_DI"),
    ("Sniper", "AllowSniper", "SniperSizePct", "AllowSniper_SizePct", "SNP"),
]


def clean_number(value, default=0.0):
    """Return a finite float for CSV output, replacing missing/NaN values."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def build_size_outputs(bot_perms: Dict[str, int], base_size_pct: int) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Build both SizePct schemas:
      - canonical short names: MomoSizePct
      - legacy HUD/bot aliases: AllowMomo_SizePct
    """
    size_values = {}
    output = {}
    for _, allow_col, canonical_col, alias_col, _ in BOT_SIZE_SCHEMA:
        pct = max(25, int(base_size_pct)) if bot_perms.get(allow_col, 0) else 0
        size_values[canonical_col] = pct
        output[canonical_col] = pct
        output[alias_col] = pct
    return size_values, output


def build_bot_permission_summary(
    bot_perms: Dict[str, int],
    dir_perms: Dict[str, int],
    size_values: Dict[str, int]
) -> str:
    parts = []
    for _, allow_col, canonical_col, _, label in BOT_SIZE_SCHEMA:
        parts.append(f"{label}:{int(bot_perms.get(allow_col, 0))}/{int(size_values.get(canonical_col, 0))}")
    parts.extend([
        f"LONG:{int(dir_perms.get('AllowLong', 0))}",
        f"SHORT:{int(dir_perms.get('AllowShort', 0))}",
        f"FADE_L:{int(dir_perms.get('AllowFadeLong', 0))}",
        f"FADE_S:{int(dir_perms.get('AllowFadeShort', 0))}",
    ])
    return "|".join(parts)


def any_directional_bot_allowed(bot_perms: Dict[str, int], dir_perms: Dict[str, int]) -> int:
    trend_bot_on = any(bot_perms.get(col, 0) for col in [
        "AllowExpansion", "AllowMomo", "AllowADX_DI", "AllowSniper"
    ])
    trend_dir_on = bool(dir_perms.get("AllowLong", 0) or dir_perms.get("AllowShort", 0))
    fade_on = bool(bot_perms.get("AllowPine", 0) and (
        dir_perms.get("AllowFadeLong", 0) or dir_perms.get("AllowFadeShort", 0)
    ))
    return int((trend_bot_on and trend_dir_on) or fade_on)


def build_blocked_reason(
    final_regime: str,
    final_direction: str,
    reason_code: str,
    bot_perms: Dict[str, int],
    dir_perms: Dict[str, int],
    size_values: Dict[str, int]
) -> str:
    if final_regime == "TRANSITION":
        return f"TRANSITION_{reason_code}"
    if not any(bot_perms.get(allow_col, 0) for _, allow_col, _, _, _ in BOT_SIZE_SCHEMA):
        return "NO_BOT_PERMISSION"
    if any_directional_bot_allowed(bot_perms, dir_perms) == 0:
        if final_direction == "NEUTRAL":
            return "NEUTRAL_DIRECTION"
        return "NO_DIRECTIONAL_PERMISSION"
    if not any(int(v) > 0 for v in size_values.values()):
        return "NO_SIZE_PCT"
    return "NONE"


# ===========================================================================
# MAIN PROCESSING
# ===========================================================================

def process_symbol(
    symbol: str,
    mode: str = "batch",
    shadow: bool = False,
    sim_test: bool = False
) -> pd.DataFrame:
    """
    Main processing pipeline for one symbol.
    
    Args:
        symbol: "NQ" or "ES"
        mode: "batch" or "live"
        shadow: If True, write with _SHADOW suffix
    
    Returns:
        DataFrame with full RegimeMatrix output
    """
    log.info(f"[{symbol}] Starting {mode} processing...")
    
    # Load inputs
    macro_df = load_macro_regimes(symbol)
    hmm_df = load_hmm_regimes(symbol)
    
    # Merge stages
    merged = merge_stages(macro_df, hmm_df, symbol)
    
    if merged.empty:
        log.warning(f"[{symbol}] No merged data after as-of HMM lookup.")
        return pd.DataFrame()
    
    # Initialize Kalman filter (one per session)
    kalman_filter = KalmanScoreFilter()
    current_date = None
    
    # Track state age for persistence gate
    prev_regime = None
    prev_regime_before_current = None
    state_age = 0
    regime_flip_history = []
    
    # Output rows
    output_rows = []
    
    for idx, row in merged.iterrows():
        timestamp = row["TimestampET"]
        trade_date = pd.to_datetime(row["trade_date"]).date()
        
        # Reset Kalman filter at new session
        if trade_date != current_date:
            kalman_filter.reset()
            current_date = trade_date
            prev_regime = None
            prev_regime_before_current = None
            state_age = 0
            regime_flip_history = []
        
        # Compute scores
        phase = row.get("phase", "UNKNOWN")
        kalman_filter.set_params(get_kalman_params(phase))
        override = extreme_thrust_override(phase, row, symbol)
        raw_trend_score = compute_trend_expansion_score(row, symbol)
        kalman_score = kalman_filter.update(raw_trend_score)
        conflict_score = compute_conflict_score(row, symbol)
        
        # Classify final regime
        if override is not None:
            final_regime = override["FinalRegime"]
            final_direction = override["FinalDirection"]
            regime_confidence = override["RegimeConfidence"]
            reason_code = override["OverrideSource"]
            override_source = override["OverrideSource"]
        else:
            final_regime, final_direction, regime_confidence, reason_code = \
                classify_final_regime(
                    row, kalman_score, conflict_score, symbol,
                    prev_regime, state_age, sim_test
                )
            override_source = ""
        
        # Update state age and short-window flip count
        prior_regime = prev_regime
        is_regime_flip = prior_regime is not None and final_regime != prior_regime
        regime_flip_history.append(1 if is_regime_flip else 0)
        if len(regime_flip_history) > REGIME_FLIP_LOOKBACK_BARS:
            regime_flip_history.pop(0)
        flip_count_10bar = sum(regime_flip_history)

        if final_regime == prev_regime:
            state_age += 1
        else:
            state_age = 1
            prev_regime_before_current = prior_regime
            prev_regime = final_regime
        
        # Compute bot permissions
        bot_perms = compute_bot_permissions(
            final_regime, final_direction, row.get("RegimeLabel", ""),
            conflict_score, state_age,
            prev_regime_before_current, flip_count_10bar, sim_test
        )
        if override_source == "EXTREME_THRUST":
            bot_perms["AllowExpansion"] = 0
            bot_perms["AllowMomo"] = 1
            bot_perms["AllowPine"] = 0
            bot_perms["AllowADX_DI"] = 0
            bot_perms["AllowSniper"] = 1
        bot_gate_reason = compute_bot_permission_gate_reason(
            final_regime, state_age, prev_regime_before_current, flip_count_10bar
        )
        if "REGIME_PERMISSION_COOLDOWN" in bot_gate_reason or "TRANSITION_EXIT_COOLDOWN" in bot_gate_reason:
            bot_perms["AllowMomo"] = 0
            bot_perms["AllowSniper"] = 0
        if "CHOPPY_REGIME_FLIPS" in bot_gate_reason:
            for key in bot_perms:
                bot_perms[key] = 0
        dir_perms = compute_directional_permissions(
            final_regime, final_direction,
            row.get("official_bias_label", ""),
            row.get("RegimeLabel", "")
        )
        
        # Compute sizing
        size_pct = compute_size_pct(regime_confidence, conflict_score)
        size_values, size_outputs = build_size_outputs(bot_perms, size_pct)
        any_directional = any_directional_bot_allowed(bot_perms, dir_perms)
        any_size_positive = int(any(int(v) > 0 for v in size_values.values()))
        bot_summary = build_bot_permission_summary(bot_perms, dir_perms, size_values)
        blocked_reason = build_blocked_reason(
            final_regime, final_direction, reason_code,
            bot_perms, dir_perms, size_values
        )
        if bot_gate_reason != "NONE" and blocked_reason != "NONE":
            blocked_reason = f"{blocked_reason}|{bot_gate_reason}"
        
        # Build output row
        output_row = {
            # Core identifiers
            "session_key": row["session_key"],
            "TimestampET": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "Symbol": symbol,
            
            # Macro layer
            "MacroRegime": row.get("official_regime_label", ""),
            "MacroPlaybook": row.get("playbook_state", ""),
            "MacroCheckpointState": row.get("checkpoint_state", ""),
            
            # HMM layer
            "HMMRegime": row.get("RegimeLabel", ""),
            "HMMDirection": "LONG" if row.get("RegimeLabel") == "TrendUp" else
                           "SHORT" if row.get("RegimeLabel") == "TrendDown" else "NEUTRAL",
            "HMMAsOfTimestampET": row.get("HMM_TimestampET", ""),
            "HMMJoinLagMinutes": round(clean_number(row.get("HMMJoinLagMinutes", 0.0)), 2),
            "SuggestedAdxMin": int(clean_number(row.get("SuggestedAdxMin", 0), 0)),
            "SuggestedCiMax": int(clean_number(row.get("SuggestedCiMax", 0), 0)),
            "SuggestedSlopeGate": clean_number(row.get("SuggestedSlopeGate", 0.0), 0.0),
            "SuggestedStopBucket": row.get("SuggestedStopBucket", ""),
            
            # Macro geometry aliases consumed by NT8 bots
            "SessionVWAP": round(clean_number(row.get("session_vwap", 0.0)), 4),
            "IBHigh": round(clean_number(row.get("ib_high_so_far", 0.0)), 4),
            "IBLow": round(clean_number(row.get("ib_low_so_far", 0.0)), 4),
            "IBExtensionPct": round(clean_number(row.get("ib_extension_pct", 0.0)), 4),
            "IBWidthATR": round(clean_number(row.get("ib_width_atr", 0.0)), 4),
            "PDVAH": round(clean_number(row.get("pd_vah", 0.0)), 4),
            "PDVAL": round(clean_number(row.get("pd_val", 0.0)), 4),
            "TwoSidedFlag": int(clean_number(row.get("two_sided_trade_flag", 0), 0)),
            
            # Velocity signals
            "Velocity3P_ATR": round(row.get("velocity_3cp_atr", 0.0), 4),
            "VelocityConfirmed": 1 if abs(row.get("velocity_3cp_atr", 0.0)) >= 
                                THRESHOLDS[symbol]["velocity_strong"] else 0,
            
            # Scores
            "TrendExpansionScore": round(raw_trend_score, 2),
            "KalmanSmoothedScore": round(kalman_score, 2),
            "ConflictScore": round(conflict_score, 4),
            
            # Phase context
            "Phase": row.get("phase", ""),
            "PhaseMultiplier": PHASE_MULTIPLIERS.get(
                row.get("phase", ""), DEFAULT_MULTIPLIERS
            )["trend"],
            
            # Final classification
            "FinalRegime": final_regime,
            "FinalDirection": final_direction,
            "RegimeConfidence": regime_confidence,
            
            # Bot permissions (flags)
            **bot_perms,
            
            # Bot sizing percentages (both canonical and legacy alias schemas)
            **size_outputs,
            
            # Directional permissions
            **dir_perms,
            
            # Diagnostics / metadata
            "ReasonCode": reason_code,
            "OverrideSource": override_source,
            "BlockedReason": blocked_reason,
            "BotPermissionGateReason": bot_gate_reason,
            "BotPermissionSummary": bot_summary,
            "AnyDirectionalBotAllowed": any_directional,
            "AnySizePctPositive": any_size_positive,
            "SimTestingMode": 1 if sim_test else 0,
            "StateAgeBars": state_age,
            "RegimeFlipCount10Bar": flip_count_10bar,
            "StaleDataFlag": 0,  # Always fresh in batch mode
        }
        
        output_rows.append(output_row)
    
    # Build output DataFrame
    output_df = pd.DataFrame(output_rows)
    
    log.info(f"[{symbol}] Processed {len(output_df)} rows")
    log.info(f"[{symbol}] Regime distribution:\n{output_df['FinalRegime'].value_counts()}")
    
    return output_df


def write_output(
    df: pd.DataFrame,
    symbol: str,
    mode: str,
    shadow: bool = False
):
    """
    Write output to appropriate file(s) based on mode.
    
    Args:
        df: Output DataFrame
        symbol: "NQ" or "ES"
        mode: "batch" or "live"
        shadow: If True, write with _SHADOW suffix
    """
    if df.empty:
        log.warning(f"[{symbol}] No data to write.")
        return
    
    suffix = "_SHADOW" if shadow else ""
    
    if mode == "batch":
        # Write full history to Backtest folder
        os.makedirs(BACKTEST_DIR, exist_ok=True)
        full_path = FULL_FILES[symbol].replace(".csv", f"{suffix}.csv")
        df.to_csv(full_path, index=False)
        log.info(f"[{symbol}] Written full history: {full_path} ({len(df)} rows)")
        
        # Also write to History folder for analysis
        os.makedirs(HISTORY_DIR, exist_ok=True)
        history_path = HISTORY_FILES[symbol].replace(".csv", f"{suffix}.csv")
        df.to_csv(history_path, index=False)
        log.info(f"[{symbol}] Written history copy: {history_path}")
    
    elif mode == "live":
        # Write latest row only (atomic)
        latest_path = LATEST_FILES[symbol].replace(".csv", f"{suffix}.csv")
        tmp_path = latest_path + ".tmp"
        
        last_row = df.iloc[[-1]]  # Keep as DataFrame (single row)
        last_row.to_csv(tmp_path, index=False)
        os.replace(tmp_path, latest_path)
        
        log.info(f"[{symbol}] Updated latest: {latest_path}")
        
        # Append to history
        os.makedirs(HISTORY_DIR, exist_ok=True)
        history_path = HISTORY_FILES[symbol].replace(".csv", f"{suffix}.csv")
        
        if os.path.exists(history_path):
            existing_header = list(pd.read_csv(history_path, nrows=0).columns)
            if existing_header == list(last_row.columns):
                last_row.to_csv(history_path, mode='a', header=False, index=False)
            else:
                new_header = list(last_row.columns)
                extra_cols = [c for c in existing_header if c not in new_header]
                canonical_header = new_header + extra_cols
                existing = pd.read_csv(history_path, dtype=str, low_memory=False)
                existing = existing.reindex(columns=canonical_header)
                aligned_last_row = last_row.reindex(columns=canonical_header)
                combined = pd.concat([existing, aligned_last_row], ignore_index=True, sort=False)
                combined.to_csv(history_path, index=False)
                log.info(f"[{symbol}] History schema aligned: {history_path}")
        else:
            last_row.to_csv(history_path, index=False)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description="RegimeSupervisor V3D — Stage C")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--batch", action="store_true",
                      help="Process full history, write RegimeMatrix_Full.csv")
    mode.add_argument("--live", action="store_true",
                      help="Continuous loop, write RegimeMatrix_Latest.csv")
    p.add_argument("--symbol", choices=["NQ", "ES", "BOTH"], default="BOTH")
    p.add_argument("--interval", type=int, default=30,
                   help="Sleep seconds between live cycles (default: 30)")
    p.add_argument("--shadow", action="store_true",
                   help="Write with _SHADOW suffix for testing")
    p.add_argument("--sim-test", action="store_true",
                   help="Enable SIM validation thresholds and scout bot permissions")
    return p.parse_args()


def get_symbols(arg: str) -> list:
    return ["NQ", "ES"] if arg == "BOTH" else [arg]


def main():
    args = parse_args()
    symbols = get_symbols(args.symbol)
    
    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BACKTEST_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    
    mode = "batch" if args.batch else "live"
    if args.sim_test:
        log.info("=== SIM TESTING MODE ENABLED: compression=50, emerging=30, ADX_DI/Sniper scout lane on ===")
    
    if args.batch:
        log.info("=== RegimeSupervisor V3D — BATCH MODE ===")
        for sym in symbols:
            try:
                df = process_symbol(sym, mode="batch", shadow=args.shadow, sim_test=args.sim_test)
                write_output(df, sym, mode="batch", shadow=args.shadow)
            except Exception as e:
                log.error(f"[{sym}] Batch processing failed: {e}", exc_info=True)
        log.info("=== Batch complete ===")
    
    elif args.live:
        log.info(f"=== RegimeSupervisor V3D — LIVE MODE (interval={args.interval}s) ===")
        while True:
            for sym in symbols:
                try:
                    df = process_symbol(sym, mode="live", shadow=args.shadow, sim_test=args.sim_test)
                    write_output(df, sym, mode="live", shadow=args.shadow)
                except Exception as e:
                    log.error(f"[{sym}] Live cycle error: {e}", exc_info=True)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
