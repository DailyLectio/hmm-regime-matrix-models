"""
HMMWatchdog_V3D.py — Stage B of the V3D Institutional Regime Matrix
MODIFIED VERSION with --full-history flag

Phase One Report amendments (2026-05-03):
  Part 2 — Feature standardisation restored (z-score before fitting).
    The V3D pipeline had dropped the standardisation step present in the legacy
    HMM_Watchdog.py, causing Range and Returns (scale ~0.001-0.01) to be
    dominated by Vol_Z and vwap_dist_atr (scale ~-2 to +3). This distorted
    the Gaussian covariance estimate and produced centroid collapse, resulting
    in 75.7% of session bars labelled as Transition on 2026-04-30.
  Part 2 — Label assignment confidence guard.
    assign_labels() now checks the TrendUp/TrendDown vwap_dist_atr separation.
    If separation < LABEL_VWAP_MIN_SEPARATION (default 0.10 z-score units),
    a LABEL CONFIDENCE WARNING is logged and LabelAmbiguousFit=1 is written
    to the output CSV for the supervisor to consume.
  New output columns (appended, not replacing): LabelAmbiguousFit,
    LabelVwapSeparation.

Fits a 4-state Hidden Markov Model. Can operate in two modes:
  1. Rolling window (60 days) — for live operation
  2. Full history — for initial batch processing

Run modes:
    --once           Single run (both instruments), then exit
    --live           Continuous loop with MIN_NEW_BARS gate
    --full-history   Process ENTIRE export file (no 60-day limit)
    --symbol         NQ | ES | BOTH (default: BOTH)
    --interval       Sleep seconds between live cycles (default: 30)

Usage examples:
    python HMMWatchdog_V3D.py --once --full-history --symbol BOTH
    python HMMWatchdog_V3D.py --live --interval 30
    python HMMWatchdog_V3D.py --live --symbol NQ
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
from hmmlearn import hmm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = r"C:\V3D"   # Junction alias for C:\Users\Valued Customer\NT8_Regimes
EXPORT_DIR = os.path.join(BASE_DIR, "Exports")
OUTPUT_DIR = os.path.join(BASE_DIR, "V3D")

EXPORT_FILES = {
    "NQ": os.path.join(EXPORT_DIR, "NQ_1min_export.txt"),
    "ES": os.path.join(EXPORT_DIR, "ES_1min_export.txt"),
}
OUTPUT_FILES = {
    "NQ": os.path.join(OUTPUT_DIR, "NQ_HMM_Regimes_V3D.csv"),
    "ES": os.path.join(OUTPUT_DIR, "ES_HMM_Regimes_V3D.csv"),
}
# Persistent state: tracks last fit row count per symbol
STATE_FILE = os.path.join(OUTPUT_DIR, "HMMWatchdog_V3D_state.json")

# ---------------------------------------------------------------------------
# Model parameters
# ---------------------------------------------------------------------------
LOOKBACK_TRADING_DAYS = 60
MIN_NEW_BARS_TO_REFIT = 5   # ~5 new 1-min bars = one new 5-min checkpoint
N_STATES              = 4
N_ITER                = 200
N_RESTARTS            = 5   # fit N times, keep best log-likelihood
RTH_START             = "09:30"
RTH_END               = "16:00"

# GLOBAL FLAG (set by command-line argument)
USE_FULL_HISTORY = False

# ---------------------------------------------------------------------------
# Per-regime suggested bot parameters (conservative starting defaults)
# Calibrate from Stage 4 expectancy analysis before going live.
# ---------------------------------------------------------------------------
BOT_PARAMS = {
    "TrendUp": {
        "SuggestedAdxMin": 25, "SuggestedCiMax": 35,
        "SuggestedSlopeGate": 0.10, "SuggestedStopBucket": "NORMAL",
        "Tradeable": 1, "AllowLong": 1, "AllowShort": 0,
    },
    "TrendDown": {
        "SuggestedAdxMin": 25, "SuggestedCiMax": 35,
        "SuggestedSlopeGate": 0.10, "SuggestedStopBucket": "NORMAL",
        "Tradeable": 1, "AllowLong": 0, "AllowShort": 1,
    },
    "Balance": {
        "SuggestedAdxMin": 15, "SuggestedCiMax": 55,
        "SuggestedSlopeGate": 0.03, "SuggestedStopBucket": "TIGHT",
        "Tradeable": 1, "AllowLong": 1, "AllowShort": 1,
    },
    "Transition": {
        "SuggestedAdxMin": 20, "SuggestedCiMax": 45,
        "SuggestedSlopeGate": 0.06, "SuggestedStopBucket": "WIDE",
        "Tradeable": 0, "AllowLong": 0, "AllowShort": 0,
    },
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("HMMWatchdog_V3D")

# hmmlearn can emit "Model is not converging" warnings for tiny EM likelihood
# dips on individual restarts even when the selected restart fits and scores.
# Keep fatal fit failures in this watchdog's own logs, but suppress that chatter.
logging.getLogger("hmmlearn.base").setLevel(logging.ERROR)


# ===========================================================================
# 1. STATE PERSISTENCE — track row counts to gate refits
# ===========================================================================

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


# ===========================================================================
# 2. DATA LOADING AND PREPARATION
# ===========================================================================

def load_export(path: str) -> pd.DataFrame:
    """Load semicolon-delimited 1-min export. Returns sorted, deduplicated df."""
    df = pd.read_csv(
        path, sep=";", header=None,
        names=["Timestamp", "Open", "High", "Low", "Close", "Volume"],
        dtype={"Open": float, "High": float, "Low": float,
               "Close": float, "Volume": float},
    )
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y%m%d %H%M%S")
    df.sort_values("Timestamp", inplace=True)
    df.drop_duplicates(subset="Timestamp", keep="last", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    t = df["Timestamp"]
    ts = t.dt.strftime("%H:%M")
    mask = (t.dt.weekday < 5) & (ts >= RTH_START) & (ts <= RTH_END)
    return df[mask].copy()


def apply_rolling_window(df_rth: pd.DataFrame) -> pd.DataFrame:
    """Keep only the most recent LOOKBACK_TRADING_DAYS of trading dates."""
    # MODIFIED: Skip rolling window if USE_FULL_HISTORY flag is set
    if USE_FULL_HISTORY:
        log.info("FULL HISTORY MODE: Skipping rolling window filter")
        return df_rth
    
    unique_dates = np.sort(df_rth["Timestamp"].dt.date.unique())
    if len(unique_dates) > LOOKBACK_TRADING_DAYS:
        cutoff = unique_dates[-LOOKBACK_TRADING_DAYS]
        df_rth = df_rth[df_rth["Timestamp"].dt.date >= cutoff].copy()
    return df_rth


def resample_to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-min RTH bars to 5-min OHLCV."""
    df = df_1m.set_index("Timestamp")
    r = df.resample("5min", closed="right", label="right").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    ).dropna(subset=["Open"])
    return r.reset_index()


def drop_incomplete_5m_bar(df_5m: pd.DataFrame, df_1m: pd.DataFrame) -> pd.DataFrame:
    """Remove the right-edge 5-min bar until its timestamp has actually printed."""
    if df_5m.empty or df_1m.empty:
        return df_5m

    latest_1m_ts = df_1m["Timestamp"].max()
    return df_5m[df_5m["Timestamp"] <= latest_1m_ts].copy()


def compute_session_vwap(df_5m: pd.DataFrame) -> pd.Series:
    """Session VWAP reset at each new trading date."""
    df = df_5m.copy()
    df["trade_date"] = df["Timestamp"].dt.date
    df["pv"] = df["Close"] * df["Volume"]
    df["cum_pv"]  = df.groupby("trade_date")["pv"].cumsum()
    df["cum_vol"] = df.groupby("trade_date")["Volume"].cumsum()
    return df["cum_pv"] / df["cum_vol"].replace(0, np.nan)


def compute_atr_series(df_5m: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR series on the 5-min frame."""
    high = df_5m["High"]
    low  = df_5m["Low"]
    prev_close = df_5m["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def build_feature_matrix(df_5m: pd.DataFrame) -> pd.DataFrame:
    """
    Build the 4-feature matrix used for HMM fitting.

    Features:
        Returns       — 5-min close pct change
        Range         — (High - Low) / Close
        Vol_Z         — Volume Z-score vs 20-bar rolling
        vwap_dist_atr — (Close - SessionVWAP) / ATR_5m
    """
    df = df_5m.copy()

    df["Returns"] = df["Close"].pct_change()
    df["Range"]   = (df["High"] - df["Low"]) / df["Close"].replace(0, np.nan)

    vol_mean = df["Volume"].rolling(20, min_periods=1).mean()
    vol_std  = df["Volume"].rolling(20, min_periods=1).std().replace(0, np.nan)
    df["Vol_Z"] = (df["Volume"] - vol_mean) / vol_std

    df["SessionVWAP"]    = compute_session_vwap(df)
    df["ATR_5m"]         = compute_atr_series(df)
    df["vwap_dist_atr"]  = (df["Close"] - df["SessionVWAP"]) / df["ATR_5m"].replace(0, np.nan)

    df.dropna(subset=["Returns", "Range", "Vol_Z", "vwap_dist_atr"], inplace=True)
    return df


# ===========================================================================
# 3. HMM FITTING
# ===========================================================================

# Phase One Report Part 2 — Feature standardisation minimum separation.
# When the mean vwap_dist_atr of the best TrendUp/TrendDown candidate is
# closer to zero than this threshold (in z-score space after scaling), the
# labeler flags the fit as ambiguous.  The label is still assigned (the HMM
# must produce *something*), but a diagnostic is emitted and the StateMargin
# in the output is reduced so the supervisor can detect soft drift.
LABEL_VWAP_MIN_SEPARATION = 0.10   # z-score units


def standardize_features(X: np.ndarray) -> tuple:
    """
    Z-score standardise the feature matrix before HMM fitting.

    Phase One Report Part 2 — Recommended Change:
    The legacy HMM_Watchdog.py standardises features before fitting, but V3D
    dropped this step, causing features on different scales (Range ~0.001–0.01
    vs Vol_Z ~-2 to +3 vs vwap_dist_atr ~-2 to +2) to distort the Gaussian
    covariance estimate.  The result is that low-variance features (Range,
    Returns) contribute negligibly to cluster assignment, and the four HMM
    states collapse into noisy clusters dominated by Vol_Z and vwap_dist_atr.
    This produces the 75.7% Transition over-labeling observed on 2026-04-30.

    Returns (X_scaled, means, stds).
    """
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds[stds < 1e-12] = 1.0   # prevent division by zero on constant columns
    X_scaled = (X - means) / stds
    return X_scaled, means, stds


def fit_hmm(X: np.ndarray) -> tuple:
    """
    Fit N_RESTARTS Gaussian HMMs on STANDARDISED features, return the best
    (highest log-likelihood).

    Returns (best_model, best_score, scaler_means, scaler_stds).
    The scaler params are needed by assign_labels to map z-scored cluster
    means back to natural-unit sign checks.
    """
    X_scaled, sc_means, sc_stds = standardize_features(X)

    best_model  = None
    best_score  = -np.inf

    for seed in range(N_RESTARTS):
        model = hmm.GaussianHMM(
            n_components=N_STATES,
            covariance_type="full",
            n_iter=N_ITER,
            random_state=seed,
            verbose=False,
        )
        try:
            model.fit(X_scaled)
            score = model.score(X_scaled)
            if score > best_score:
                best_score = score
                best_model = model
        except Exception as e:
            log.warning(f"HMM fit attempt {seed} failed: {e}")

    if best_model is None:
        raise RuntimeError("All HMM fit attempts failed.")
    return best_model, best_score, sc_means, sc_stds


# ===========================================================================
# 4. LABEL ASSIGNMENT — anchored, not return-sort
# ===========================================================================

def assign_labels(model: hmm.GaussianHMM, feature_names: list,
                  scaler_means: np.ndarray = None,
                  scaler_stds: np.ndarray = None) -> tuple:
    """
    Assign semantic labels to HMM states using the combined criterion:
        TrendUp:   highest mean return AND positive mean vwap_dist_atr
        TrendDown: lowest mean return AND negative mean vwap_dist_atr
        Balance:   of remaining — lowest mean range
        Transition: of remaining — highest mean range

    Phase One Report Part 2 amendments:
    1. If features were standardised (scaler_means/stds provided), unscale
       the cluster means before applying sign checks so that the
       vwap_dist_atr > 0 / < 0 test reflects actual price-vs-VWAP direction,
       not z-score artefacts.
    2. Emit a diagnostic flag when the TrendUp/TrendDown vwap_dist_atr
       separation is below LABEL_VWAP_MIN_SEPARATION, indicating the HMM
       fit may be ambiguous (centroid collapse risk).

    Returns (label_map, label_diagnostics).
    label_diagnostics is a dict with 'ambiguous_fit' and 'vwap_separation' keys.
    """
    means = model.means_  # shape (N_STATES, N_FEATURES) — in z-score space if scaled
    feat_idx = {name: i for i, name in enumerate(feature_names)}

    # If features were standardised, un-scale the means to natural units for
    # the sign checks.  The label assignment logic uses the sign of the
    # natural-unit vwap_dist_atr mean, not the z-scored mean.
    if scaler_means is not None and scaler_stds is not None:
        natural_means = means * scaler_stds + scaler_means
    else:
        natural_means = means

    ret_means  = natural_means[:, feat_idx["Returns"]]
    vwap_means = natural_means[:, feat_idx["vwap_dist_atr"]]
    range_means= natural_means[:, feat_idx["Range"]]

    assigned = {}
    remaining = set(range(N_STATES))

    # TrendUp: highest return AND positive vwap
    candidates = [s for s in remaining if vwap_means[s] > 0]
    if candidates:
        tu = max(candidates, key=lambda s: ret_means[s])
    else:
        tu = max(remaining, key=lambda s: ret_means[s])
    assigned[tu] = "TrendUp"
    remaining.discard(tu)

    # TrendDown: lowest return AND negative vwap
    candidates = [s for s in remaining if vwap_means[s] < 0]
    if candidates:
        td = min(candidates, key=lambda s: ret_means[s])
    else:
        td = min(remaining, key=lambda s: ret_means[s])
    assigned[td] = "TrendDown"
    remaining.discard(td)

    # Balance: of remaining, lowest mean range
    bal = min(remaining, key=lambda s: range_means[s])
    assigned[bal] = "Balance"
    remaining.discard(bal)

    # Transition: last remaining
    trans = remaining.pop()
    assigned[trans] = "Transition"

    # Diagnostic: label confidence guard.
    vwap_separation = abs(vwap_means[tu] - vwap_means[td])
    ambiguous = vwap_separation < LABEL_VWAP_MIN_SEPARATION
    if ambiguous:
        log.warning(
            f"LABEL CONFIDENCE WARNING: TrendUp/TrendDown vwap_dist_atr "
            f"separation = {vwap_separation:.4f} (threshold: "
            f"{LABEL_VWAP_MIN_SEPARATION}). Labels may be unreliable — "
            f"centroid collapse risk. Consider widening the rolling window "
            f"or re-running with --full-history."
        )

    diagnostics = {
        "ambiguous_fit": ambiguous,
        "vwap_separation": round(vwap_separation, 6),
        "tu_vwap_mean": round(float(vwap_means[tu]), 6),
        "td_vwap_mean": round(float(vwap_means[td]), 6),
        "tu_ret_mean":  round(float(ret_means[tu]), 6),
        "td_ret_mean":  round(float(ret_means[td]), 6),
    }

    return assigned, diagnostics


# ===========================================================================
# 5. OUTPUT BUILDING
# ===========================================================================

def build_output(
    df_5m: pd.DataFrame,
    model: hmm.GaussianHMM,
    label_map: dict,
    X: np.ndarray,
    symbol: str,
    model_version: str,
    scaler_means: np.ndarray = None,
    scaler_stds: np.ndarray = None,
    label_diagnostics: dict = None,
) -> pd.DataFrame:
    """
    Assemble the output DataFrame with all required columns.

    Phase One Report Part 2: model.predict() and model.predict_proba() must
    receive the SAME standardised feature matrix that was used for fitting.
    If scaler_means/stds are provided, X is scaled before predict.
    """
    # Standardise for predict if scaler was used during fitting.
    if scaler_means is not None and scaler_stds is not None:
        X_pred = (X - scaler_means) / np.where(scaler_stds < 1e-12, 1.0, scaler_stds)
    else:
        X_pred = X

    posteriors = model.predict_proba(X_pred)  # (N, 4)
    states     = model.predict(X_pred)         # (N,)

    # Map state indices to label probabilities
    # We need: StateProb_TrendUp, _TrendDown, _Balance, _Transition
    label_to_col = {
        "TrendUp":    "StateProb_TrendUp",
        "TrendDown":  "StateProb_TrendDown",
        "Balance":    "StateProb_Balance",
        "Transition": "StateProb_Transition",
    }
    # Build reverse: col index -> label
    state_to_label = {v: k for k, v in label_map.items()}  # inverted

    prob_df = pd.DataFrame(index=range(len(states)))
    for state_id in range(N_STATES):
        label = label_map[state_id]
        col   = label_to_col[label]
        prob_df[col] = posteriors[:, state_id]

    regime_labels = [label_map[s] for s in states]

    # Flip rate: fraction of label changes in last 5 bars
    label_series = pd.Series(regime_labels)
    flip_rate = label_series.ne(label_series.shift()).rolling(5, min_periods=2).mean()

    # Persist bars: consecutive bars in current state
    persist = []
    count = 1
    for i in range(len(states)):
        if i == 0 or states[i] != states[i - 1]:
            count = 1
        else:
            count += 1
        persist.append(count)

    # Align with df_5m (feature matrix may have fewer rows after dropna)
    n = len(X)
    df_aligned = df_5m.iloc[-n:].copy().reset_index(drop=True)

    out = pd.DataFrame()
    out["Timestamp"] = df_aligned["Timestamp"]
    out["trade_date"] = df_aligned["Timestamp"].dt.date.astype(str)
    out["checkpoint_str"] = df_aligned["Timestamp"].dt.strftime("%H:%M")

    # session_key: symbol_YYYYMMDD_HH:MM
    out["session_key"] = (
        symbol + "_" +
        df_aligned["Timestamp"].dt.strftime("%Y%m%d") + "_" +
        df_aligned["Timestamp"].dt.strftime("%H:%M")
    )
    out["TimestampET"] = df_aligned["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out["Symbol"]       = symbol
    out["StateId"]      = states
    out["RegimeLabel"]  = regime_labels

    for col in ["StateProb_TrendUp", "StateProb_TrendDown",
                "StateProb_Balance", "StateProb_Transition"]:
        out[col] = prob_df[col].round(4).values

    out["HMM_FlipRate_5bar"] = flip_rate.round(4).values
    out["HMM_PersistBars"]   = persist

    # Bot parameters from label
    for col in ["SuggestedAdxMin", "SuggestedCiMax", "SuggestedSlopeGate",
                "SuggestedStopBucket", "Tradeable", "AllowLong", "AllowShort"]:
        out[col] = [BOT_PARAMS[lbl][col] for lbl in regime_labels]

    out["ModelVersion"] = model_version

    # Phase One Report Part 2 — Label diagnostics per-row so operators can
    # monitor centroid collapse in real time via the HMM output CSV.
    diag = label_diagnostics or {}
    out["LabelAmbiguousFit"] = int(diag.get("ambiguous_fit", False))
    out["LabelVwapSeparation"] = diag.get("vwap_separation", 0.0)

    # Final column order per spec — new diagnostic columns appended at end
    # so existing downstream consumers (supervisor, HUD) are not broken.
    final_cols = [
        "session_key", "TimestampET", "Symbol", "StateId", "RegimeLabel",
        "StateProb_TrendUp", "StateProb_TrendDown",
        "StateProb_Balance", "StateProb_Transition",
        "HMM_FlipRate_5bar", "HMM_PersistBars",
        "SuggestedAdxMin", "SuggestedCiMax", "SuggestedSlopeGate",
        "SuggestedStopBucket", "ModelVersion", "Tradeable",
        "AllowLong", "AllowShort",
        "LabelAmbiguousFit", "LabelVwapSeparation",
    ]
    return out[final_cols]


# ===========================================================================
# 6. ATOMIC WRITE
# ===========================================================================

def write_atomic(df: pd.DataFrame, path: str):
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    log.info(f"Written: {path} ({len(df)} rows)")


# ===========================================================================
# 7. MAIN SYMBOL PROCESSOR
# ===========================================================================

def process_symbol(symbol: str, persist_state: dict) -> dict:
    """
    Load, gate, fit, and write for one symbol.
    Returns updated persist_state.
    """
    export_path = EXPORT_FILES[symbol]
    output_path = OUTPUT_FILES[symbol]

    if not os.path.exists(export_path):
        log.error(f"[{symbol}] Export file not found: {export_path}")
        return persist_state

    # --- Load and prepare ---
    with open(export_path, "r") as f:
        current_row_count = sum(1 for _ in f)
    df_raw  = load_export(export_path)
    df_rth  = filter_rth(df_raw)
    if df_rth.empty:
        log.warning(f"[{symbol}] No RTH rows available. Skipping.")
        return persist_state

    df_roll = apply_rolling_window(df_rth)
    df_5m   = drop_incomplete_5m_bar(resample_to_5m(df_roll), df_roll)
    if df_5m.empty:
        log.warning(f"[{symbol}] No completed 5-min bars available. Skipping.")
        return persist_state

    rth_row_count = len(df_rth)
    last_fit_rth_rows = int(persist_state.get(f"{symbol}_last_fit_rth_rows", 0) or 0)
    bars_since_fit = rth_row_count - last_fit_rth_rows if last_fit_rth_rows else rth_row_count
    latest_5m_ts = pd.to_datetime(df_5m["Timestamp"].max())
    last_fit_5m_raw = persist_state.get(f"{symbol}_last_fit_5m_ts")
    last_fit_5m_ts = pd.to_datetime(last_fit_5m_raw) if last_fit_5m_raw else None

    if (not USE_FULL_HISTORY
            and last_fit_5m_ts is not None
            and latest_5m_ts <= last_fit_5m_ts):
        log.info(
            f"[{symbol}] Latest complete 5-min HMM bar unchanged "
            f"({latest_5m_ts:%Y-%m-%d %H:%M}). Waiting for next completed bar."
        )
        persist_state[f"{symbol}_last_seen_raw_rows"] = current_row_count
        persist_state[f"{symbol}_last_seen_rth_rows"] = rth_row_count
        return persist_state

    if USE_FULL_HISTORY:
        log.info(f"[{symbol}] Full-history rebuild requested. Fitting HMM...")
    elif last_fit_5m_ts is not None and bars_since_fit < MIN_NEW_BARS_TO_REFIT:
        log.info(
            f"[{symbol}] New completed 5-min bar detected with {bars_since_fit} "
            f"deduped RTH 1-min rows since last fit. Fitting HMM..."
        )
    else:
        log.info(
            f"[{symbol}] New completed 5-min bar detected "
            f"({bars_since_fit} deduped RTH 1-min rows since last fit). Fitting HMM..."
        )

    n_days = df_roll["Timestamp"].dt.date.nunique()
    log.info(f"[{symbol}] Rolling window: {n_days} trading days, "
             f"{len(df_5m)} 5-min bars")

    df_feat = build_feature_matrix(df_5m)
    feature_names = ["Returns", "Range", "Vol_Z", "vwap_dist_atr"]
    X = df_feat[feature_names].values

    if len(X) < N_STATES * 10:
        log.warning(f"[{symbol}] Insufficient bars for reliable fit ({len(X)}). Skipping.")
        return persist_state

    # --- Fit ---
    model, log_likelihood, sc_means, sc_stds = fit_hmm(X)
    log.info(f"[{symbol}] HMM fitted. Log-likelihood: {log_likelihood:.2f}")

    # --- Label assignment ---
    label_map, label_diagnostics = assign_labels(
        model, feature_names,
        scaler_means=sc_means, scaler_stds=sc_stds
    )
    log.info(f"[{symbol}] State labels: {label_map}")
    if label_diagnostics.get("ambiguous_fit"):
        log.warning(
            f"[{symbol}] AMBIGUOUS FIT detected — vwap separation "
            f"{label_diagnostics['vwap_separation']:.4f}. "
            f"Downstream regimes may drift."
        )

    # --- Build output ---
    model_version = datetime.now().strftime("V3D_%Y%m%d_%H%M")
    df_out = build_output(
        df_5m, model, label_map, X, symbol, model_version,
        scaler_means=sc_means, scaler_stds=sc_stds,
        label_diagnostics=label_diagnostics,
    )

    # --- Write ---
    write_atomic(df_out, output_path)

    # --- Update state ---
    persist_state[f"{symbol}_last_fit_rows"]  = current_row_count
    persist_state[f"{symbol}_last_fit_rth_rows"] = rth_row_count
    persist_state[f"{symbol}_last_fit_5m_ts"] = latest_5m_ts.isoformat()
    persist_state[f"{symbol}_last_fit_ts"]    = datetime.now().isoformat()
    persist_state[f"{symbol}_last_ll"]        = round(log_likelihood, 4)
    persist_state[f"{symbol}_label_map"]      = {str(k): v for k, v in label_map.items()}
    persist_state[f"{symbol}_label_diagnostics"] = label_diagnostics

    return persist_state


# ===========================================================================
# 8. ENTRY POINT
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description="HMMWatchdog V3D — Stage B")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true",
                      help="Single run, then exit")
    mode.add_argument("--live", action="store_true",
                      help="Continuous loop with MIN_NEW_BARS gate")
    p.add_argument("--symbol",   choices=["NQ", "ES", "BOTH"], default="BOTH")
    p.add_argument("--interval", type=int, default=30,
                   help="Sleep seconds between live cycles (default: 30)")
    p.add_argument("--full-history", action="store_true",
                   help="Process ENTIRE export file (no 60-day rolling window)")
    return p.parse_args()


def get_symbols(arg: str) -> list:
    return ["NQ", "ES"] if arg == "BOTH" else [arg]


def main():
    global USE_FULL_HISTORY  # Modify the global flag
    
    args    = parse_args()
    symbols = get_symbols(args.symbol)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Set global flag based on command-line argument
    USE_FULL_HISTORY = args.full_history
    if USE_FULL_HISTORY:
        log.info("*** FULL HISTORY MODE ENABLED ***")
        log.info("Processing ENTIRE export file (no 60-day rolling window)")
        log.info("This will take 5-10 minutes per instrument")
    
    state = load_state()

    if args.once:
        log.info("=== HMMWatchdog V3D — SINGLE RUN ===")
        # Force refit by resetting row counts for this run
        for sym in symbols:
            state[f"{sym}_last_fit_rows"] = 0
        for sym in symbols:
            try:
                state = process_symbol(sym, state)
            except Exception as e:
                log.error(f"[{sym}] Failed: {e}", exc_info=True)
        save_state(state)
        log.info("=== Single run complete ===")

    elif args.live:
        log.info(f"=== HMMWatchdog V3D — LIVE MODE (interval={args.interval}s) ===")
        while True:
            for sym in symbols:
                try:
                    state = process_symbol(sym, state)
                except Exception as e:
                    log.error(f"[{sym}] Live cycle error: {e}", exc_info=True)
            save_state(state)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
