"""
MacroRegimeBuilder_V3D.py — Stage A of the V3D Institutional Regime Matrix
Reads 1-minute export files, resamples to 5-minute RTH checkpoints, computes
all derived columns, and writes NQ_Macro_Regimes_V3D.csv / ES_Macro_Regimes_V3D.csv.

Run modes:
    --batch     Process the full export file (historical or catch-up)
    --live      Continuous loop: append only new checkpoints as they form
    --symbol    NQ | ES | BOTH (default: BOTH)
    --interval  Loop sleep seconds in live mode (default: 30)

Usage examples:
    python MacroRegimeBuilder_V3D.py --batch
    python MacroRegimeBuilder_V3D.py --live --interval 30
    python MacroRegimeBuilder_V3D.py --batch --symbol NQ
"""

import argparse
import os
import sys
import time
import logging
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths — edit BASE_DIR only if your folder root changes
# ---------------------------------------------------------------------------
BASE_DIR   = r"C:\V3D"   # Junction alias for C:\Users\Valued Customer\NT8_Regimes
EXPORT_DIR = os.path.join(BASE_DIR, "Exports")
OUTPUT_DIR = os.path.join(BASE_DIR, "V3D")

EXPORT_FILES = {
    "NQ": os.path.join(EXPORT_DIR, "NQ_1min_export.txt"),
    "ES": os.path.join(EXPORT_DIR, "ES_1min_export.txt"),
}
OUTPUT_FILES = {
    "NQ": os.path.join(OUTPUT_DIR, "NQ_Macro_Regimes_V3D.csv"),
    "ES": os.path.join(OUTPUT_DIR, "ES_Macro_Regimes_V3D.csv"),
}

# Value Area export files written by ValueAreaExporter.cs NT8 indicator
VALUE_AREA_FILES = {
    "NQ": os.path.join(EXPORT_DIR, "ValueArea_NQ.csv"),
    "ES": os.path.join(EXPORT_DIR, "ValueArea_ES.csv"),
}

# ---------------------------------------------------------------------------
# RTH checkpoint times (ET) — 5-minute resolution
# ---------------------------------------------------------------------------
CHECKPOINT_TIMES = [
    "09:35", "09:45", "09:55", "10:05", "10:15", "10:25",
    "10:35", "10:45", "10:55", "11:05", "11:35", "12:05",
    "12:35", "13:05", "13:35", "14:05", "14:35", "15:05",
    "15:35", "16:00",
]
RTH_START = "09:30"
RTH_END   = "16:00"

# Phase map: checkpoint str -> phase label
PHASE_MAP = {
    "09:35": "OPENING_AUCTION",
    "09:45": "EARLY_TEST",
    "09:55": "FIRST_ACCEPTANCE",
    "10:05": "FIRST_ACCEPTANCE",
    "10:15": "PRE_IB_MATURATION",
    "10:25": "PRE_IB_MATURATION",
    "10:35": "POST_IB_MACRO",
    "10:45": "POST_IB_MACRO",
    "10:55": "MID_MORNING_DISCOVERY",
    "11:05": "MID_MORNING_DISCOVERY",
    "11:35": "MID_MORNING_DISCOVERY",
    "12:05": "LUNCH_AUCTION",
    "12:35": "LUNCH_AUCTION",
    "13:05": "POST_LUNCH_ROTATION",
    "13:35": "POST_LUNCH_ROTATION",
    "14:05": "AFTERNOON_TREND_TEST",
    "14:35": "AFTERNOON_TREND_TEST",
    "15:05": "LATE_DAY_CONVICTION",
    "15:35": "LATE_DAY_CONVICTION",
    "16:00": "CASH_CLOSE",
}

# ---------------------------------------------------------------------------
# Per-symbol thresholds
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "NQ": {
        "ib_strong":          0.85,
        "ib_expanding":       0.45,
        "vwap_confirm":       0.40,
        "net_move_confirm":   0.60,
        "velocity_strong":    0.85,
    },
    "ES": {
        "ib_strong":          1.00,
        "ib_expanding":       0.75,
        "vwap_confirm":       0.50,
        "net_move_confirm":   0.75,
        "velocity_strong":    1.00,
    },
}

# Lookback for ATR percentile ranking (trading days)
ATR_PCTILE_LOOKBACK_DAYS = 20

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("MacroRegimeBuilder_V3D")


# ===========================================================================
# 1. DATA LOADING
# ===========================================================================

def load_export(path: str) -> pd.DataFrame:
    """
    Load a semicolon-delimited 1-minute export file.
    Format: YYYYMMDD HHmmss;Open;High;Low;Close;Volume
    No header row.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Export file not found: {path}")

    df = pd.read_csv(
        path,
        sep=";",
        header=None,
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
    """Keep only weekday RTH bars 09:30–16:00 ET."""
    t = df["Timestamp"]
    time_str = t.dt.strftime("%H:%M")
    mask = (
        (t.dt.weekday < 5) &
        (time_str >= RTH_START) &
        (time_str <= RTH_END)
    )
    return df[mask].copy()


# ===========================================================================
# 2. SESSION BUILDING — one DataFrame per trading day
# ===========================================================================

def build_sessions(df_rth: pd.DataFrame, symbol: str, live_guard: bool = False) -> pd.DataFrame:
    """
    Resample 1-min bars into 5-min checkpoint bars per trading session.
    Returns a DataFrame with one row per (date, checkpoint).

    When live_guard is True, checkpoint rows later than the latest actual
    timestamp for that trade_date are skipped. This prevents a partial live
    session from projecting later checkpoints from the same last observed bar.
    """
    thr = THRESHOLDS[symbol]
    rows = []

    for trade_date, day_df in df_rth.groupby(df_rth["Timestamp"].dt.date):
        day_df = day_df.sort_values("Timestamp").copy()
        latest_actual_ts = day_df["Timestamp"].max()

        # Session VWAP (price * volume sum / volume sum)
        pv = (day_df["Close"] * day_df["Volume"]).cumsum()
        vol_cum = day_df["Volume"].cumsum()
        day_df["session_vwap"] = pv / vol_cum.replace(0, np.nan)

        rth_open = day_df["Open"].iloc[0]

        # IB definition: first 60 minutes = 09:30–10:30 (bars with time < 10:30)
        ib_mask = day_df["Timestamp"].dt.strftime("%H:%M") < "10:30"
        if ib_mask.sum() > 0:
            ib_df = day_df[ib_mask]
            ib_high = ib_df["High"].max()
            ib_low  = ib_df["Low"].min()
        else:
            ib_high = ib_low = rth_open  # fallback if data starts late

        # ATR-5m for the day using all 1-min bars resampled to 5-min
        day_5m = resample_to_5m(day_df)
        atr_5m = compute_atr(day_5m, period=14)  # scalar — last bar

        # Resample to checkpoints
        for cp_str in CHECKPOINT_TIMES:
            cp_h, cp_m = int(cp_str.split(":")[0]), int(cp_str.split(":")[1])
            checkpoint_ts = pd.Timestamp(
                year=trade_date.year,
                month=trade_date.month,
                day=trade_date.day,
                hour=cp_h,
                minute=cp_m,
            )
            if live_guard and checkpoint_ts > latest_actual_ts:
                continue

            # Window: bars where time <= checkpoint (up to and including)
            cp_mask = day_df["Timestamp"].dt.strftime("%H:%M") <= cp_str
            if not cp_mask.any():
                continue

            window = day_df[cp_mask]
            last_bar = window.iloc[-1]

            last_price      = last_bar["Close"]
            session_vwap    = last_bar["session_vwap"]

            # IB state so far at this checkpoint
            ib_high_sofar = window["High"].max()
            ib_low_sofar  = window["Low"].min()
            ib_width_sofar = ib_high_sofar - ib_low_sofar

            # ATR at this checkpoint (use day atr_5m — constant per day)
            atr = atr_5m if atr_5m > 0 else 1.0

            # ib_width_atr
            ib_width_atr = ib_width_sofar / atr

            # ib_extension_pct: how far beyond IB high/low has price gone?
            above_ib = max(0, last_price - ib_high)
            below_ib = max(0, ib_low - last_price)
            ib_extension_pct = max(above_ib, below_ib) / max(ib_width_sofar, 0.001)

            # Net move since open in ATR units
            net_move_atr = (last_price - rth_open) / atr

            # close vs VWAP in ATR units
            close_vs_vwap_atr = (last_price - session_vwap) / atr

            # Directional efficiency — cumulative
            total_path = window["Close"].diff().abs().sum()
            net_move_abs = abs(last_price - rth_open)
            de_cumulative = net_move_abs / max(total_path, 0.001)

            # Directional efficiency — recent 3-bar (5-min windows)
            cp_5m = resample_to_5m(window)
            if len(cp_5m) >= 3:
                recent_3 = cp_5m.iloc[-3:]
                path_3 = recent_3["Close"].diff().abs().sum()
                net_3  = abs(recent_3["Close"].iloc[-1] - recent_3["Close"].iloc[0])
                de_recent = net_3 / max(path_3, 0.001)
            else:
                de_recent = de_cumulative

            de_effective = max(de_cumulative, de_recent * 0.85)

            # Velocity: 3-checkpoint price change / ATR
            if len(cp_5m) >= 3:
                vel_3cp = (cp_5m["Close"].iloc[-1] - cp_5m["Close"].iloc[-3]) / atr
            else:
                vel_3cp = net_move_atr

            # Two-sided trade flag: did price visit both sides of VWAP today?
            above_vwap = (window["High"] > session_vwap).any()
            below_vwap = (window["Low"]  < session_vwap).any()
            two_sided_raw = int(above_vwap and below_vwap)

            # same_side_vwap_minutes: consecutive minutes price has stayed on
            # one side of VWAP counting from the most recent bar backward.
            # Used by the IB/VWAP acceptance override in the supervisor.
            same_side_vwap_minutes = 0
            if len(window) >= 1:
                # Determine current side
                current_above = window["Close"].iloc[-1] > session_vwap
                count = 0
                for _, bar in window.iloc[::-1].iterrows():
                    bar_above = bar["Close"] > session_vwap
                    if bar_above == current_above:
                        count += 1
                    else:
                        break
                same_side_vwap_minutes = count  # 1-min bars = minutes

            # IB acceptance override decay: clear two_sided_trade_flag when
            # price has sustained one-sided acceptance post-IB breakout.
            # Conditions: IB clearly broken (ext >= 0.85 ATR-normalised width),
            # price has been same-side VWAP for >= 15 consecutive minutes,
            # and close is > 1.5 ATR above/below VWAP.
            # This prevents the flag from staying sticky the entire session
            # after a clean breakout, which permanently blocks expansion lanes.
            ib_clear_threshold = thr.get("ib_strong", 0.85)
            if (two_sided_raw == 1
                    and ib_extension_pct >= ib_clear_threshold
                    and same_side_vwap_minutes >= 15
                    and abs(close_vs_vwap_atr) >= 1.50):
                two_sided_trade_flag = 0  # override — breakout acceptance confirmed
            else:
                two_sided_trade_flag = two_sided_raw

            # Returned to open flag
            returned_to_open_flag = int(
                (window["Low"].min() <= rth_open <= window["High"].max()) and
                abs(last_price - rth_open) < atr * 0.25
            )

            # Value break + accept (price spent 2+ bars outside IB)
            outside_ib = (window["Close"] > ib_high) | (window["Close"] < ib_low)
            value_break_accept_flag = int(outside_ib.rolling(2).sum().max() >= 2)

            # RVOL vs 20d — filled in post-processing pass (needs cross-day volume sum)
            rvol_vs_20d = np.nan

            # Daily volume sum for this day so far (used in post-process for rvol)
            daily_volume_so_far = float(window["Volume"].sum())

            # Regime labels — rule-based from thresholds
            official_regime, official_bias, checkpoint_state, volatility_state, playbook_state = \
                classify_regime(
                    net_move_atr=net_move_atr,
                    de_effective=de_effective,
                    close_vs_vwap_atr=close_vs_vwap_atr,
                    ib_width_atr=ib_width_atr,
                    ib_extension_pct=ib_extension_pct,
                    vel_3cp=vel_3cp,
                    two_sided=two_sided_trade_flag,
                    thr=thr,
                    cp_str=cp_str,
                )

            session_key = f"{symbol}_{trade_date.strftime('%Y%m%d')}_{cp_str}"

            rows.append({
                "session_key":                  session_key,
                "trade_date":                   trade_date.strftime("%Y-%m-%d"),
                "checkpoint_time":              cp_str,
                "phase":                        PHASE_MAP.get(cp_str, "UNKNOWN"),
                "symbol":                       symbol,
                "last_price":                   round(last_price, 4),
                "rth_open":                     round(rth_open, 4),
                "session_vwap":                 round(session_vwap, 4),
                "close_vs_vwap_atr":            round(close_vs_vwap_atr, 4),
                "net_move_since_open_atr":      round(net_move_atr, 4),
                "directional_efficiency_since_open": round(de_cumulative, 4),
                "de_recent_3bar":               round(de_recent, 4),
                "de_effective":                 round(de_effective, 4),
                "ib_extension_pct":             round(ib_extension_pct, 4),
                "ib_high_so_far":                round(ib_high_sofar, 4),
                "ib_low_so_far":                 round(ib_low_sofar, 4),
                "ib_width_so_far":              round(ib_width_sofar, 4),
                "ib_width_atr":                 round(ib_width_atr, 4),
                "atr_5m":                       round(atr, 4),
                "velocity_3cp_atr":             round(vel_3cp, 4),
                "atr_pctile_20d":               np.nan,  # filled post-process
                "rvol_vs_20d":                  np.nan,  # filled post-process
                "daily_volume":                 daily_volume_so_far,  # used for rvol calc
                "two_sided_trade_flag":         two_sided_trade_flag,
                "same_side_vwap_minutes":       same_side_vwap_minutes,
                "returned_to_open_flag":        returned_to_open_flag,
                "value_break_accept_flag":      value_break_accept_flag,
                "open_in_pd_value_flag":        0,  # filled post-process from ValueArea file
                "open_in_on_value_flag":        0,  # filled post-process from ValueArea file
                "close_in_pd_value_flag":       0,  # filled post-process from ValueArea file
                "close_in_on_value_flag":       0,  # filled post-process from ValueArea file
                "inside_value_score":           0,  # filled post-process from ValueArea file
                "pd_vah":                       0.0,  # filled post-process from ValueArea file
                "pd_val":                       0.0,  # filled post-process from ValueArea file
                "prior_day_type":               "",  # filled post-process
                "on_type":                      "",  # stub — requires ON data
                "official_regime_label":        official_regime,
                "official_bias_label":          official_bias,
                "checkpoint_state":             checkpoint_state,
                "volatility_state":             volatility_state,
                "playbook_state":               playbook_state,
            })

    result = pd.DataFrame(rows)
    return result


# ===========================================================================
# 3. HELPERS — resampling, ATR, classification
# ===========================================================================

def resample_to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-min bars to 5-min OHLCV."""
    df = df_1m.set_index("Timestamp")
    resampled = df.resample("5min", closed="right", label="right").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    ).dropna(subset=["Open"])
    return resampled.reset_index()


def compute_atr(df_5m: pd.DataFrame, period: int = 14) -> float:
    """Return the last ATR value from a 5-min OHLCV DataFrame."""
    if len(df_5m) < 2:
        return (df_5m["High"].iloc[-1] - df_5m["Low"].iloc[-1]) if len(df_5m) == 1 else 1.0
    high = df_5m["High"]
    low  = df_5m["Low"]
    prev_close = df_5m["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return float(atr.iloc[-1]) if not np.isnan(atr.iloc[-1]) else float(tr.mean())


def classify_regime(
    net_move_atr: float,
    de_effective: float,
    close_vs_vwap_atr: float,
    ib_width_atr: float,
    ib_extension_pct: float,
    vel_3cp: float,
    two_sided: int,
    thr: dict,
    cp_str: str,
) -> tuple:
    """
    Rule-based regime classification.
    Returns: (official_regime, bias, checkpoint_state, volatility_state, playbook_state)
    """
    abs_net = abs(net_move_atr)
    abs_vel = abs(vel_3cp)
    abs_vwap = abs(close_vs_vwap_atr)
    direction = "LONG" if net_move_atr > 0 else "SHORT"

    # Checkpoint state: how far into session
    cp_h, cp_m = int(cp_str.split(":")[0]), int(cp_str.split(":")[1])
    cp_minutes = cp_h * 60 + cp_m
    if cp_minutes <= 10 * 60 + 30:
        checkpoint_state = "IB_FORMING"
    elif cp_minutes <= 12 * 60:
        checkpoint_state = "POST_IB"
    elif cp_minutes <= 14 * 60:
        checkpoint_state = "MIDDAY"
    else:
        checkpoint_state = "AFTERNOON"

    # Volatility state
    if ib_width_atr >= thr["ib_strong"]:
        volatility_state = "HIGH_VOL"
    elif ib_width_atr >= thr["ib_expanding"]:
        volatility_state = "MED_VOL"
    else:
        volatility_state = "LOW_VOL"

    # Trend conditions
    is_trending = (
        abs_net >= thr["net_move_confirm"] and
        de_effective >= 0.50 and
        abs_vwap >= thr["vwap_confirm"]
    )
    is_strong_trend = (
        is_trending and
        abs_vel >= thr["velocity_strong"] and
        ib_extension_pct > 0.25
    )

    # Regime logic
    if is_strong_trend:
        official_regime = "TREND"
        official_bias   = direction
        playbook_state  = "TREND_STRONG"
    elif is_trending:
        official_regime = "TREND"
        official_bias   = direction
        playbook_state  = "TREND_MODERATE"
    elif two_sided and ib_width_atr >= thr["ib_expanding"]:
        official_regime = "ROTATION"
        official_bias   = "NEUTRAL"
        playbook_state  = "ROTATION_LIQUID"
    elif two_sided:
        official_regime = "ROTATION"
        official_bias   = "NEUTRAL"
        playbook_state  = "ROTATION_CHOP"
    else:
        official_regime = "BALANCE"
        official_bias   = "NEUTRAL"
        playbook_state  = "BALANCE_TIGHT"

    return official_regime, official_bias, checkpoint_state, volatility_state, playbook_state


# ===========================================================================
# 4. POST-PROCESSING — rolling metrics across days
# ===========================================================================

def load_value_area(symbol: str) -> pd.DataFrame:
    """
    Load the ValueArea CSV written by ValueAreaExporter.cs.
    Returns a DataFrame indexed by date with POC, VAH, VAL, DailyVolume,
    ONHigh, ONLow columns.  Returns empty DataFrame if file not found.

    File format (with header):
        Date,Symbol,POC,VAH,VAL,DailyVolume,ONHigh,ONLow
    """
    path = VALUE_AREA_FILES.get(symbol, "")
    if not path or not os.path.exists(path):
        log.warning(
            f"[{symbol}] Value area file not found: {path}\n"
            f"  open_in_pd_value_flag and close_in_pd_value_flag will remain 0.\n"
            f"  Apply ValueAreaExporter.cs to a {symbol} Daily chart in NT8 to enable."
        )
        return pd.DataFrame()

    try:
        va = pd.read_csv(path)
        va.columns = [c.strip() for c in va.columns]
        va["Date"] = pd.to_datetime(va["Date"]).dt.date
        va = va.sort_values("Date").drop_duplicates(subset="Date", keep="last")
        va = va.set_index("Date")
        log.info(f"[{symbol}] Value area loaded: {len(va)} days "
                 f"({va.index.min()} to {va.index.max()})")
        return va
    except Exception as e:
        log.warning(f"[{symbol}] Could not load value area file: {e}")
        return pd.DataFrame()


def compute_rolling_metrics(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Compute atr_pctile_20d, rvol_vs_20d, prior_day_type.
    Populate open_in_pd_value_flag, close_in_pd_value_flag,
    open_in_on_value_flag, close_in_on_value_flag, inside_value_score
    from the ValueAreaExporter file.

    Operates on the 16:00 (CASH_CLOSE) checkpoint row per day for the
    day-level aggregates, then joins back to all checkpoints.
    """
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    # ------------------------------------------------------------------
    # End-of-day rows only (for day-level rolling metrics)
    # ------------------------------------------------------------------
    eod = df[df["checkpoint_time"] == "16:00"].copy()
    eod = eod.sort_values("trade_date").reset_index(drop=True)

    # ATR percentile over 20 trading days
    eod["atr_pctile_20d"] = (
        eod["atr_5m"]
        .rolling(ATR_PCTILE_LOOKBACK_DAYS, min_periods=1)
        .rank(pct=True)
        .round(4)
    )

    # ------------------------------------------------------------------
    # RVOL vs 20d — computed from daily_volume column (summed per-day
    # from 1-min bars; the 16:00 row carries the full-day total).
    # Ratio = today's volume / 20-day rolling median volume.
    # > 1.0 means above-average participation; < 1.0 means quiet.
    # ------------------------------------------------------------------
    vol_20d_median = (
        eod["daily_volume"]
        .rolling(ATR_PCTILE_LOOKBACK_DAYS, min_periods=5)
        .median()
    )
    eod["rvol_vs_20d"] = (eod["daily_volume"] / vol_20d_median.replace(0, np.nan)).round(4)

    # ------------------------------------------------------------------
    # Prior day type
    # ------------------------------------------------------------------
    def get_day_type(row):
        r = row["official_regime_label"]
        if r == "TREND":
            return "TREND_UP" if row["official_bias_label"] == "LONG" else "TREND_DOWN"
        elif r == "ROTATION":
            return "ROTATION"
        elif r == "BALANCE":
            return "INSIDE"
        return "UNKNOWN"

    eod["day_type"]      = eod.apply(get_day_type, axis=1)
    eod["prior_day_type"] = eod["day_type"].shift(1).fillna("")

    # ------------------------------------------------------------------
    # Merge day-level metrics back to all checkpoint rows
    # ------------------------------------------------------------------
    eod_cols = eod[["trade_date", "atr_pctile_20d", "rvol_vs_20d", "prior_day_type"]]
    df = df.drop(columns=["atr_pctile_20d", "rvol_vs_20d", "prior_day_type"], errors="ignore")
    df = df.merge(eod_cols, on="trade_date", how="left")

    # ------------------------------------------------------------------
    # Value area flags — join from ValueAreaExporter file
    # ------------------------------------------------------------------
    va = load_value_area(symbol)

    if not va.empty:
        df["_date"] = df["trade_date"].dt.date

        # Prior-day value area: shift by 1 day — today's open is compared
        # against YESTERDAY's POC/VAH/VAL
        va_shifted = va[["POC", "VAH", "VAL", "ONHigh", "ONLow"]].copy()
        va_shifted.index.name = "_pd_date"

        # Build a date->prev_date lookup
        all_dates = sorted(df["_date"].unique())
        prev_date_map = {d: all_dates[i - 1] if i > 0 else None
                         for i, d in enumerate(all_dates)}

        def get_va_row(trade_date):
            pd_date = prev_date_map.get(trade_date)
            if pd_date is None or pd_date not in va.index:
                return None
            return va.loc[pd_date]

        def open_in_pd_value(row):
            va_row = get_va_row(row["_date"])
            if va_row is None:
                return 0
            return int(float(va_row["VAL"]) <= row["rth_open"] <= float(va_row["VAH"]))

        def close_in_pd_value(row):
            va_row = get_va_row(row["_date"])
            if va_row is None:
                return 0
            return int(float(va_row["VAL"]) <= row["last_price"] <= float(va_row["VAH"]))

        def open_in_on_value(row):
            """Price opened within overnight high/low range."""
            va_row = get_va_row(row["_date"])
            if va_row is None:
                return 0
            on_h = float(va_row["ONHigh"])
            on_l = float(va_row["ONLow"])
            return int(on_l <= row["rth_open"] <= on_h)

        def close_in_on_value(row):
            """Current price is within overnight range (measures reach-back to ON range)."""
            va_row = get_va_row(row["_date"])
            if va_row is None:
                return 0
            on_h = float(va_row["ONHigh"])
            on_l = float(va_row["ONLow"])
            return int(on_l <= row["last_price"] <= on_h)

        def prior_day_value(row, col_name):
            va_row = get_va_row(row["_date"])
            if va_row is None or col_name not in va_row:
                return 0.0
            return float(va_row[col_name])

        log.info(f"[{symbol}] Computing value area flags across {len(df)} checkpoint rows...")
        df["open_in_pd_value_flag"]  = df.apply(open_in_pd_value,  axis=1)
        df["close_in_pd_value_flag"] = df.apply(close_in_pd_value, axis=1)
        df["open_in_on_value_flag"]  = df.apply(open_in_on_value,  axis=1)
        df["close_in_on_value_flag"] = df.apply(close_in_on_value, axis=1)
        df["pd_vah"] = df.apply(lambda row: prior_day_value(row, "VAH"), axis=1).round(4)
        df["pd_val"] = df.apply(lambda row: prior_day_value(row, "VAL"), axis=1).round(4)

        # inside_value_score: 0-4 composite (how many value conditions are true)
        df["inside_value_score"] = (
            df["open_in_pd_value_flag"] +
            df["close_in_pd_value_flag"] +
            df["open_in_on_value_flag"] +
            df["close_in_on_value_flag"]
        )
        df.drop(columns=["_date"], inplace=True)
        log.info(f"[{symbol}] Value area flags populated.")
    else:
        log.info(f"[{symbol}] Value area file unavailable — flags remain 0. "
                 f"Pipeline will continue without them.")

    for col in ["pd_vah", "pd_val", "ib_high_so_far", "ib_low_so_far"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)

    df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")
    return df


# ===========================================================================
# 5. ATOMIC WRITE
# ===========================================================================

def write_atomic(df: pd.DataFrame, output_path: str):
    """Write DataFrame to a .tmp file then rename — prevents partial reads."""
    tmp_path = output_path + ".tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, output_path)
    log.info(f"Written: {output_path} ({len(df)} rows)")


# ===========================================================================
# 6. LAST-WRITTEN TRACKING — for live incremental mode
# ===========================================================================

def load_last_written_key(output_path: str) -> str | None:
    """Return the last session_key written to the output file, or None."""
    if not os.path.exists(output_path):
        return None
    try:
        tail = pd.read_csv(output_path, usecols=["session_key"])
        if tail.empty:
            return None
        return tail["session_key"].iloc[-1]
    except Exception:
        return None


def get_last_export_date(output_path: str) -> date | None:
    """Return the most recent trade_date in the output CSV."""
    if not os.path.exists(output_path):
        return None
    try:
        col = pd.read_csv(output_path, usecols=["trade_date"])
        if col.empty:
            return None
        return pd.to_datetime(col["trade_date"].iloc[-1]).date()
    except Exception:
        return None


# ===========================================================================
# 7. MAIN PROCESSING FUNCTIONS
# ===========================================================================

def process_symbol_batch(symbol: str):
    """Full reprocess of the export file — overwrites output CSV."""
    log.info(f"[{symbol}] Batch mode — loading export file...")
    df_raw = load_export(EXPORT_FILES[symbol])
    df_rth = filter_rth(df_raw)
    log.info(f"[{symbol}] RTH bars loaded: {len(df_rth)} across "
             f"{df_rth['Timestamp'].dt.date.nunique()} trading days")

    log.info(f"[{symbol}] Building session checkpoints...")
    df_out = build_sessions(df_rth, symbol)

    log.info(f"[{symbol}] Computing rolling metrics...")
    df_out = compute_rolling_metrics(df_out, symbol)

    write_atomic(df_out, OUTPUT_FILES[symbol])
    log.info(f"[{symbol}] Batch complete. Total checkpoint rows: {len(df_out)}")


def process_symbol_live(symbol: str):
    """
    Incremental live update: load only new dates from export, append to output.
    Skips days already written. Reprocesses the current trading day fully
    (to update intraday checkpoints as session progresses).
    """
    output_path = OUTPUT_FILES[symbol]
    last_date = get_last_export_date(output_path)

    df_raw = load_export(EXPORT_FILES[symbol])
    df_rth = filter_rth(df_raw)

    today = datetime.now().date()

    if last_date is not None:
        # Keep only dates >= last_date (reprocess current day, append new days)
        cutoff = last_date
        df_rth = df_rth[df_rth["Timestamp"].dt.date >= cutoff].copy()
        if df_rth.empty:
            log.info(f"[{symbol}] No new data since {last_date}. Skipping.")
            return
    # else: first run, process all

    df_new = build_sessions(df_rth, symbol, live_guard=True)

    if df_new.empty:
        return

    # Rolling metrics require full history context — merge ATR pctile from full file
    if last_date is not None and os.path.exists(output_path):
        df_existing = pd.read_csv(output_path)
        # Drop existing rows for dates being reprocessed
        dates_in_new = set(df_new["trade_date"].unique())
        df_existing = df_existing[~df_existing["trade_date"].isin(dates_in_new)]
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined = compute_rolling_metrics(df_combined, symbol)
    write_atomic(df_combined, output_path)
    log.info(f"[{symbol}] Live update complete. Output rows: {len(df_combined)}")


# ===========================================================================
# 8. ENTRY POINT
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description="MacroRegimeBuilder V3D — Stage A")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--batch", action="store_true",
                      help="Process full export history and overwrite output")
    mode.add_argument("--live",  action="store_true",
                      help="Continuous loop: append new checkpoints only")
    p.add_argument("--symbol",   choices=["NQ", "ES", "BOTH"], default="BOTH")
    p.add_argument("--interval", type=int, default=30,
                   help="Sleep seconds between live cycles (default: 30)")
    return p.parse_args()


def get_symbols(arg: str) -> list:
    return ["NQ", "ES"] if arg == "BOTH" else [arg]


def main():
    args = parse_args()
    symbols = get_symbols(args.symbol)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.batch:
        log.info("=== MacroRegimeBuilder V3D — BATCH MODE ===")
        for sym in symbols:
            try:
                process_symbol_batch(sym)
            except Exception as e:
                log.error(f"[{sym}] Batch failed: {e}", exc_info=True)
        log.info("=== Batch complete ===")

    elif args.live:
        log.info(f"=== MacroRegimeBuilder V3D — LIVE MODE (interval={args.interval}s) ===")
        while True:
            for sym in symbols:
                try:
                    process_symbol_live(sym)
                except Exception as e:
                    log.error(f"[{sym}] Live cycle error: {e}", exc_info=True)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
