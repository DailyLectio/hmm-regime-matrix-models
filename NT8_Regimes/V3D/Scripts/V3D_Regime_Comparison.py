"""
V3D_Regime_Comparison.py - V3C vs V3D Daily Regime Comparison + Trade Log
============================================================================
Reads:
  1. V3D JSON report   (Archives/V3D_Regime_Report_YYYYMMDD.json)
                        produced by V3D_Daily_Regime_Report.py
  2. V3C Active CSV    (Active/NQ_Regimes.csv / ES_Regimes.csv)
                        for day-level history; falls back to V3C Latest CSV
  3. Trade log CSV     Preferred: V3D/TradeLog/V3D_INTERNAL_TradeLog.csv
                        Fallback: clean SimV3D_*_TradeLog.csv per-account files
                        Legacy V3D_TradeLog.csv is skipped by default.

Appends (never overwrites; existing rows for a date are replaced on re-run):
  A. V3D/History/V3C_V3D_Regime_Comparison.csv
       One summary row per (trade_date, symbol) -- regime model comparison
       with daily trade statistics merged in.

  B. V3D/History/V3D_Trade_Log_Enriched.csv
       All trade rows with added enrichment columns (duration, regime stability,
       correct-regime flag, running PnL, etc.)

Run modes:
    python V3D_Regime_Comparison.py --date today
    python V3D_Regime_Comparison.py --date 2026-04-27
    python V3D_Regime_Comparison.py --date all      <- backfill from all archives
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR     = r"C:\Users\Valued Customer\NT8_Regimes"
V3D_DIR      = os.path.join(BASE_DIR, "V3D")
V3C_DIR      = os.path.join(BASE_DIR, "V3C")
ACTIVE_DIR   = os.path.join(BASE_DIR, "Active")
HISTORY_DIR  = os.path.join(V3D_DIR, "History")
ARCHIVE_DIR  = os.path.join(HISTORY_DIR, "Archives")
REPORTS_DIR  = os.path.join(V3D_DIR, "Reports")
TRADELOG_DIR = os.path.join(V3D_DIR, "TradeLog")

V3C_LATEST = {
    "NQ": os.path.join(V3C_DIR, "NQ_Regimes_V3C_Latest.csv"),
    "ES": os.path.join(V3C_DIR, "ES_Regimes_V3C_Latest.csv"),
}
V3C_HISTORY = {
    "NQ": os.path.join(V3C_DIR, "NQ_Regimes_V3C.csv"),
    "ES": os.path.join(V3C_DIR, "ES_Regimes_V3C.csv"),
}
V3C_ACTIVE = {
    "NQ": os.path.join(ACTIVE_DIR, "NQ_Regimes.csv"),
    "ES": os.path.join(ACTIVE_DIR, "ES_Regimes.csv"),
}

TRADELOG_INTERNAL_PATH = os.path.join(TRADELOG_DIR, "V3D_INTERNAL_TradeLog.csv")
TRADELOG_LEGACY_PATH   = os.path.join(TRADELOG_DIR, "V3D_TradeLog.csv")
REGIME_COMPARISON_PATH = os.path.join(HISTORY_DIR, "V3C_V3D_Regime_Comparison.csv")
INTRADAY_COMPARISON_PATH = os.path.join(HISTORY_DIR, "V3C_V3D_Intraday_Comparison.csv")
TRADE_ENRICHED_PATH    = os.path.join(HISTORY_DIR, "V3D_Trade_Log_Enriched.csv")

SYMBOLS              = ["ES", "NQ"]
EXPECTED_CHECKPOINTS = 20

# Broad-regime bucket maps for cross-model comparison
V3D_BROAD_MAP = {
    "TREND_EXPANSION":    "TREND",
    "TREND_COMPRESSION":  "TREND",
    "ROTATION_LIQUID":    "ROTATION",
    "ROTATION_ILLIQUID":  "ROTATION",
    "TRANSITION":         "TRANSITION",
}
V3C_BROAD_MAP = {
    "TREND_EXPANSION": "TREND",
    "TREND_COMPRESSION": "TREND",
    "TREND_UP":    "TREND",
    "TREND_DOWN":  "TREND",
    "TRENDUP":     "TREND",
    "TRENDDOWN":   "TREND",
    "TREND":       "TREND",
    "ROTATION_LIQUID": "ROTATION",
    "ROTATION_ILLIQUID": "ROTATION",
    "ROTATION":    "ROTATION",
    "BALANCE":     "ROTATION",
    "TRANSITION":  "TRANSITION",
}

# Bot to target regimes per V3D spec Section 10
BOT_TARGET_REGIMES = {
    "Expansion_V3D": ["TREND_EXPANSION"],
    "Momentum_V3D":  ["TREND_COMPRESSION", "TREND_EXPANSION"],
    "Fader_V3D":     ["ROTATION_LIQUID"],
    "Sniper_V3D":    ["TREND_COMPRESSION"],
    "ADX_DI_V3D":    ["ROTATION_LIQUID", "TREND_COMPRESSION"],
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("V3D_Regime_Comparison")

# ---------------------------------------------------------------------------
# Output column schemas
# ---------------------------------------------------------------------------
REGIME_COMPARISON_COLS = [
    # Identity
    "trade_date", "symbol", "generated_at",

    # V3D final state at close (16:00)
    "v3d_final_regime", "v3d_macro_regime", "v3d_hmm_regime",
    "v3d_reason", "v3d_confidence", "v3d_phase",

    # V3D session stats
    "v3d_total_checkpoints",
    "v3d_final_regime_changes", "v3d_macro_regime_changes", "v3d_hmm_regime_changes",
    "v3d_stale_count",

    # V3D regime time-share % of session
    "v3d_pct_trend_expansion", "v3d_pct_trend_compression",
    "v3d_pct_rotation_liquid", "v3d_pct_rotation_illiquid",
    "v3d_pct_transition",

    # V3D bot permission % of session
    "v3d_pct_allow_expansion", "v3d_pct_allow_momo",
    "v3d_pct_allow_pine",      "v3d_pct_allow_adx_di",
    "v3d_pct_allow_sniper",

    # V3C final state at close
    "v3c_regime", "v3c_hmm_regime", "v3c_direction", "v3c_confidence",
    "v3c_data_source",

    # V3C session stats
    "v3c_regime_changes",
    "v3c_pct_trend", "v3c_pct_rotation", "v3c_pct_balance", "v3c_pct_transition",

    # Stability scores (0=max instability, 100=zero regime flips)
    "v3d_stability_score", "v3c_stability_score",

    # Cross-model agreement
    "broad_agree",          # 1 = both classify as same broad bucket (TREND/ROTATION/TRANSITION)
    "hmm_agree",            # 1 = HMM labels match
    "direction_agree",      # 1 = directional bias matches
    "confidence_delta",     # v3d_confidence - v3c_confidence
    "regime_change_delta",  # v3d changes - v3c changes (negative = V3D more stable)

    # Daily trade summary
    "trade_count",
    "winning_trades", "losing_trades", "scratch_trades",
    "gross_pnl", "net_pnl",
    "win_rate_pct", "profit_factor",
    "avg_winner", "avg_loser", "avg_trade_pnl",
    "max_winner", "max_loser",
    "total_contracts",
    "bots_active",

    # Per-bot trade breakdown (each bot: count | gross_pnl | win_rate)
    "expansion_trades", "expansion_pnl", "expansion_win_rate",
    "momo_trades",      "momo_pnl",      "momo_win_rate",
    "fader_trades",     "fader_pnl",     "fader_win_rate",
    "sniper_trades",    "sniper_pnl",    "sniper_win_rate",
    "adx_di_trades",    "adx_di_pnl",    "adx_di_win_rate",

    # Regime-quality trade metrics
    "pct_trades_in_correct_regime",  # % of trades where bot was in its target regime
    "pct_trades_regime_held",        # % of trades where regime was stable entry to exit

    # Review flags
    "flag_review",     # 1 = models disagree on market character
    "flag_v3d_stale",  # 1 = any stale rows today
    "flag_loss_day",   # 1 = net_pnl < 0
    "notes",
]

TRADE_ENRICHED_COLS = [
    # Passthrough from V3DStrategyTradeLogger.cs or the legacy V3D exporter
    "trade_date", "entry_time", "exit_time", "symbol", "bot_name",
    "model_version", "direction", "contracts",
    "entry_price", "exit_price", "gross_pnl", "net_pnl", "ticks", "win_loss",
    "exit_reason",
    "entry_regime", "entry_macro", "entry_hmm", "entry_direction",
    "entry_confidence", "entry_conflict", "entry_phase", "entry_state_age",
    "exit_regime", "exit_macro", "exit_hmm", "exit_confidence",
    "entry_size_pct", "entry_velocity", "entry_reason_code",
    "account", "instrument",
    # Enrichment columns
    "trade_duration_min",
    "regime_held",              # 1 = regime unchanged from entry to exit
    "regime_changed_during",    # exit_regime when different; else blank
    "entry_broad_regime",       # TREND / ROTATION / TRANSITION
    "in_correct_regime",        # 1 = bot traded in its spec-assigned target regime
    "ticks_per_minute",
    "session_trade_rank",       # 1st, 2nd... trade of the day for this symbol+bot
    "daily_pnl_running",        # cumulative PnL for the day (symbol+bot)
    "risk_reward_actual",       # placeholder; NT8 commission not available at fill time
]

INTRADAY_COMPARISON_COLS = [
    "trade_date", "symbol", "checkpoint_time", "generated_at",
    "v3c_snapshot_time", "v3d_snapshot_time",
    "v3c_final_regime", "v3d_final_regime",
    "v3c_broad_regime", "v3d_broad_regime", "broad_agree",
    "v3c_hmm_regime", "v3d_hmm_regime", "hmm_agree",
    "v3c_direction", "v3d_direction", "direction_agree",
    "v3c_confidence", "v3d_confidence", "confidence_delta",
    "v3c_phase", "v3d_phase",
    "v3c_reason", "v3d_reason",
    "v3c_stale", "v3d_stale",
    "v3d_allow_expansion", "v3d_allow_momo", "v3d_allow_pine",
    "v3d_allow_adx_di", "v3d_allow_sniper",
]


# ===========================================================================
# 1.  V3D JSON REPORT
# ===========================================================================

def find_json_report(report_date: date) -> str | None:
    date_str = report_date.strftime("%Y%m%d")
    candidates = [
        os.path.join(ARCHIVE_DIR, f"V3D_Regime_Report_{date_str}.json"),
        os.path.join(REPORTS_DIR, f"V3D_Regime_Report_{date_str}.json"),
        os.path.join(V3D_DIR,     f"V3D_Regime_Report_{date_str}.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def load_v3d_json(report_date: date) -> list[dict] | None:
    path = find_json_report(report_date)
    if path is None:
        log.warning(f"No V3D JSON report found for {report_date}")
        return None
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return None


def extract_v3d_summary(sym_data: dict) -> dict:
    rows         = sym_data.get("rows", 0)
    final_counts = sym_data.get("final_regime_counts", {})
    bot_counts   = sym_data.get("bot_allowed_counts", {})

    def pct(label):
        return round(final_counts.get(label, 0) / rows * 100, 1) if rows > 0 else 0.0

    def bot_pct(label):
        return round(bot_counts.get(label, 0) / rows * 100, 1) if rows > 0 else 0.0

    changes = sym_data.get("final_regime_changes", 0)
    return {
        "v3d_final_regime":          sym_data.get("latest_final_regime", ""),
        "v3d_macro_regime":          sym_data.get("latest_macro_regime", ""),
        "v3d_hmm_regime":            sym_data.get("latest_hmm_regime", ""),
        "v3d_reason":                sym_data.get("latest_reason", ""),
        "v3d_confidence":            int(sym_data.get("latest_confidence", 0)),
        "v3d_phase":                 sym_data.get("latest_phase", ""),
        "v3d_total_checkpoints":     rows,
        "v3d_final_regime_changes":  changes,
        "v3d_macro_regime_changes":  sym_data.get("macro_regime_changes", 0),
        "v3d_hmm_regime_changes":    sym_data.get("hmm_regime_changes", 0),
        "v3d_stale_count":           sym_data.get("stale_count", 0),
        "v3d_pct_trend_expansion":   pct("TREND_EXPANSION"),
        "v3d_pct_trend_compression": pct("TREND_COMPRESSION"),
        "v3d_pct_rotation_liquid":   pct("ROTATION_LIQUID"),
        "v3d_pct_rotation_illiquid": pct("ROTATION_ILLIQUID"),
        "v3d_pct_transition":        pct("TRANSITION"),
        "v3d_pct_allow_expansion":   bot_pct("AllowExpansion"),
        "v3d_pct_allow_momo":        bot_pct("AllowMomo"),
        "v3d_pct_allow_pine":        bot_pct("AllowPine"),
        "v3d_pct_allow_adx_di":      bot_pct("AllowADX_DI"),
        "v3d_pct_allow_sniper":      bot_pct("AllowSniper"),
        "v3d_stability_score":       max(0, round(
            100 - (changes / max(rows, 1) * 100), 1)),
    }


# ===========================================================================
# 2.  V3C DATA
# ===========================================================================

def load_v3c_for_date(symbol: str, report_date: date) -> dict:
    default = {
        "v3c_regime": "UNAVAILABLE", "v3c_hmm_regime": "UNAVAILABLE",
        "v3c_direction": "UNAVAILABLE", "v3c_confidence": 0,
        "v3c_data_source": "unavailable",
        "v3c_regime_changes": 0,
        "v3c_pct_trend": 0.0, "v3c_pct_rotation": 0.0,
        "v3c_pct_balance": 0.0, "v3c_pct_transition": 0.0,
        "v3c_stability_score": 0.0,
    }
    date_str = report_date.strftime("%Y-%m-%d")

    # Prefer the V3C latest file for EOD final-state comparison. The full V3C
    # history can contain older rows with a different column count.
    latest_path = V3C_LATEST.get(symbol, "")
    if os.path.exists(latest_path):
        try:
            df = pd.read_csv(latest_path, nrows=5)
            if not df.empty:
                row = df.iloc[-1]
                def col_find(*names):
                    return next((c for c in df.columns if c.lower() in names), None)
                regime_col = col_find("regimefinal", "regime", "finalregime")
                hmm_col    = col_find("hmmlabel", "regimesignal", "hmmregime",
                                      "regimematrix", "hmm_micro")
                dir_col    = col_find("direction", "finaldirection", "officialbias")
                conf_col   = col_find("confidence", "regimeconfidence")
                return {
                    **default,
                    "v3c_regime":     str(row[regime_col]) if regime_col else "UNKNOWN",
                    "v3c_hmm_regime": str(row[hmm_col])    if hmm_col    else "UNKNOWN",
                    "v3c_direction":  str(row[dir_col])    if dir_col    else "UNKNOWN",
                    "v3c_confidence": int(float(row[conf_col])) if conf_col else 0,
                    "v3c_data_source": "latest",
                }
        except Exception as e:
            log.warning(f"[{symbol}] V3C latest CSV read failed: {e}")

    # Fallback: V3C history or legacy Active CSV.
    active_path = V3C_HISTORY.get(symbol, "")
    if not os.path.exists(active_path):
        active_path = V3C_ACTIVE.get(symbol, "")
    if os.path.exists(active_path):
        try:
            df = pd.read_csv(active_path, low_memory=False)
            # Detect date column
            date_col = next(
                (c for c in df.columns
                 if c.lower() in ("trade_date", "date", "timestampet", "timestamp")),
                None)
            if date_col:
                df[date_col] = df[date_col].astype(str).str[:10]
                day_df = df[df[date_col] == date_str]
                if not day_df.empty:
                    eod = day_df.iloc[-1]
                    total = len(day_df)

                    def col_find(*names):
                        return next(
                            (c for c in day_df.columns
                             if c.lower() in names), None)

                    regime_col = col_find("regimefinal", "regime", "finalregime",
                                          "official_regime_label", "regimelabel")
                    if not regime_col:
                        log.info(f"[{symbol}] Active CSV has rows for {date_str}, but no V3C regime column; trying latest V3C CSV")
                        raise ValueError("active CSV missing V3C regime column")

                    hmm_col    = col_find("hmmlabel", "regimesignal", "hmmregime",
                                          "regimematrix", "hmm_micro")
                    dir_col    = col_find("direction", "finaldirection",
                                          "officialbias", "official_bias_label")
                    conf_col   = col_find("confidence", "regimeconfidence")

                    regime     = str(eod[regime_col])              if regime_col else "UNKNOWN"
                    hmm        = str(eod[hmm_col])                 if hmm_col    else "UNKNOWN"
                    direction  = str(eod[dir_col])                 if dir_col    else "UNKNOWN"
                    confidence = int(float(eod[conf_col]))         if conf_col   else 0

                    changes = int((day_df[regime_col] != day_df[regime_col].shift()).sum() - 1) \
                              if regime_col and total > 1 else 0

                    def broad_pct(label):
                        if not regime_col:
                            return 0.0
                        n = day_df[regime_col].apply(
                            lambda x: V3C_BROAD_MAP.get(str(x).upper(), "OTHER") == label
                        ).sum()
                        return round(n / total * 100, 1) if total > 0 else 0.0

                    return {
                        "v3c_regime":          regime,
                        "v3c_hmm_regime":      hmm,
                        "v3c_direction":       direction,
                        "v3c_confidence":      confidence,
                        "v3c_data_source":     "history_eod",
                        "v3c_regime_changes":  changes,
                        "v3c_pct_trend":       broad_pct("TREND"),
                        "v3c_pct_rotation":    broad_pct("ROTATION"),
                        "v3c_pct_balance":     broad_pct("BALANCE"),
                        "v3c_pct_transition":  broad_pct("TRANSITION"),
                        "v3c_stability_score": max(0, round(
                            100 - changes / max(total, 1) * 100, 1)),
                    }
        except Exception as e:
            log.info(f"[{symbol}] V3C history/active CSV skipped: {e}")

    log.warning(f"[{symbol}] V3C data unavailable for {date_str}")
    return default


def load_v3c_history_tolerant(symbol: str, report_date: date) -> pd.DataFrame:
    path = V3C_HISTORY.get(symbol, "")
    latest_path = V3C_LATEST.get(symbol, "")
    if not os.path.exists(path):
        return pd.DataFrame()

    latest_header = []
    if os.path.exists(latest_path):
        try:
            with open(latest_path, "r", newline="") as f:
                latest_header = next(csv.reader(f))
        except Exception:
            latest_header = []

    rows = []
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        try:
            base_header = next(reader)
        except StopIteration:
            return pd.DataFrame()

        for values in reader:
            if not values:
                continue
            header = latest_header if latest_header and len(values) == len(latest_header) else base_header
            if len(values) < len(header):
                values = values + [""] * (len(header) - len(values))
            if len(values) > len(header):
                values = values[:len(header)]
            rows.append(dict(zip(header, values)))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    ts_col = "SnapshotTimestamp" if "SnapshotTimestamp" in df.columns else None
    if not ts_col:
        return pd.DataFrame()
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df[df[ts_col].dt.date == report_date].copy()
    df = df.dropna(subset=[ts_col]).sort_values(ts_col)
    return df


def build_intraday_comparison(symbol: str, report_date: date) -> list[dict]:
    v3d_path = os.path.join(HISTORY_DIR, f"{symbol}_RegimeMatrix_History.csv")
    if not os.path.exists(v3d_path):
        return []

    v3d_df = pd.read_csv(v3d_path, dtype=str, low_memory=False)
    if "TimestampET" not in v3d_df.columns:
        return []
    v3d_df["TimestampET"] = pd.to_datetime(v3d_df["TimestampET"], errors="coerce")
    v3d_df = v3d_df[v3d_df["TimestampET"].dt.date == report_date].copy()
    v3d_df = v3d_df.dropna(subset=["TimestampET"]).sort_values("TimestampET")
    v3d_df = v3d_df.drop_duplicates(subset=["TimestampET"], keep="last")
    if v3d_df.empty:
        return []

    v3c_df = load_v3c_history_tolerant(symbol, report_date)
    if v3c_df.empty:
        return []

    merged = pd.merge_asof(
        v3d_df,
        v3c_df,
        left_on="TimestampET",
        right_on="SnapshotTimestamp",
        direction="backward",
        suffixes=("_v3d", "_v3c"),
    )

    rows = []
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def clean_str(value):
        if pd.isna(value):
            return ""
        return str(value)

    def clean_int(value):
        if pd.isna(value) or value == "":
            return 0
        try:
            return int(float(value))
        except Exception:
            return 0

    for _, r in merged.iterrows():
        v3d_regime = clean_str(r.get("FinalRegime_v3d", r.get("FinalRegime", "")))
        v3c_regime = clean_str(r.get("FinalRegime_v3c", ""))
        v3d_hmm = clean_str(r.get("HMMRegime", ""))
        v3c_hmm = clean_str(r.get("HMM_Micro", ""))
        v3d_direction = clean_str(r.get("FinalDirection_v3d", r.get("FinalDirection", "")))
        v3c_direction = clean_str(r.get("FinalDirection_v3c", ""))
        v3d_conf = clean_int(r.get("RegimeConfidence_v3d", r.get("RegimeConfidence", 0)))
        v3c_conf = clean_int(r.get("RegimeConfidence_v3c", 0))
        v3d_broad = V3D_BROAD_MAP.get(v3d_regime.upper(), "UNKNOWN")
        v3c_broad = V3C_BROAD_MAP.get(v3c_regime.upper(), "UNKNOWN")

        agreement = compute_agreement(
            {"v3d_final_regime": v3d_regime, "v3d_hmm_regime": v3d_hmm,
             "v3d_confidence": v3d_conf},
            {"v3c_regime": v3c_regime, "v3c_hmm_regime": v3c_hmm,
             "v3c_direction": v3c_direction, "v3c_confidence": v3c_conf},
        )

        rows.append({
            "trade_date": report_date.strftime("%Y-%m-%d"),
            "symbol": symbol,
            "checkpoint_time": r["TimestampET"].strftime("%Y-%m-%d %H:%M:%S"),
            "generated_at": generated_at,
            "v3c_snapshot_time": "" if pd.isna(r.get("SnapshotTimestamp")) else r["SnapshotTimestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "v3d_snapshot_time": r["TimestampET"].strftime("%Y-%m-%d %H:%M:%S"),
            "v3c_final_regime": v3c_regime,
            "v3d_final_regime": v3d_regime,
            "v3c_broad_regime": v3c_broad,
            "v3d_broad_regime": v3d_broad,
            "broad_agree": agreement["broad_agree"],
            "v3c_hmm_regime": v3c_hmm,
            "v3d_hmm_regime": v3d_hmm,
            "hmm_agree": agreement["hmm_agree"],
            "v3c_direction": v3c_direction,
            "v3d_direction": v3d_direction,
            "direction_agree": agreement["direction_agree"],
            "v3c_confidence": v3c_conf,
            "v3d_confidence": v3d_conf,
            "confidence_delta": agreement["confidence_delta"],
            "v3c_phase": clean_str(r.get("Phase_v3c", "")),
            "v3d_phase": clean_str(r.get("Phase_v3d", r.get("Phase", ""))),
            "v3c_reason": clean_str(r.get("ReasonCode_v3c", "")),
            "v3d_reason": clean_str(r.get("ReasonCode_v3d", r.get("ReasonCode", ""))),
            "v3c_stale": clean_str(r.get("StaleDataFlag_v3c", "")),
            "v3d_stale": clean_str(r.get("StaleDataFlag_v3d", r.get("StaleDataFlag", ""))),
            "v3d_allow_expansion": clean_str(r.get("AllowExpansion", "")),
            "v3d_allow_momo": clean_str(r.get("AllowMomo", "")),
            "v3d_allow_pine": clean_str(r.get("AllowPine", "")),
            "v3d_allow_adx_di": clean_str(r.get("AllowADX_DI", "")),
            "v3d_allow_sniper": clean_str(r.get("AllowSniper", "")),
        })
    return rows


# ===========================================================================
# 3.  TRADE LOG - load, enrich, summarize
# ===========================================================================

def has_data_rows(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return sum(1 for _ in handle) > 1
    except OSError:
        return False


def discover_trade_log_paths() -> list[str]:
    if has_data_rows(TRADELOG_INTERNAL_PATH):
        if has_data_rows(TRADELOG_LEGACY_PATH):
            log.info(
                "Using V3D_INTERNAL_TradeLog.csv and skipping legacy "
                "V3D_TradeLog.csv."
            )
        return [TRADELOG_INTERNAL_PATH]

    account_paths = sorted(
        str(p) for p in Path(TRADELOG_DIR).glob("SimV3D*_TradeLog.csv")
        if has_data_rows(str(p))
    )
    if account_paths:
        if has_data_rows(TRADELOG_LEGACY_PATH):
            log.info(
                "Using clean SimV3D per-account trade logs and skipping "
                "legacy V3D_TradeLog.csv."
            )
        return account_paths

    if has_data_rows(TRADELOG_LEGACY_PATH):
        log.warning(
            "Legacy V3D_TradeLog.csv exists but was not loaded because it is "
            "treated as contaminated unless intentionally archived/regenerated."
        )
    return []


def load_trade_log() -> pd.DataFrame:
    paths = discover_trade_log_paths()
    if not paths:
        log.info(
            "No clean V3D trade log source found. Waiting for "
            "V3D_INTERNAL_TradeLog.csv or SimV3D_*_TradeLog.csv."
        )
        return pd.DataFrame()

    frames = []
    total_rows = 0
    for path in paths:
        try:
            df = pd.read_csv(path, dtype=str)
            if df.empty:
                continue
            df["source_file"] = path
            frames.append(df)
            total_rows += len(df)
            log.info(f"Trade log: {len(df)} rows loaded from {path}")
        except Exception as e:
            log.warning(f"Trade log read failed for {path}: {e}")

    if not frames:
        return pd.DataFrame()
    try:
        out = pd.concat(frames, ignore_index=True, sort=False)
        log.info(f"Trade log: {total_rows} clean V3D row(s) loaded")
        return out
    except Exception as e:
        log.warning(f"Trade log merge failed: {e}")
        return pd.DataFrame()


def enrich_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()

    # Coerce numerics
    for col in ["gross_pnl", "net_pnl", "ticks", "entry_confidence",
                "entry_conflict", "entry_state_age", "entry_size_pct",
                "entry_velocity", "contracts"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Timestamps
    for col in ("entry_time", "exit_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Duration
    if "entry_time" in df.columns and "exit_time" in df.columns:
        df["trade_duration_min"] = (
            (df["exit_time"] - df["entry_time"]).dt.total_seconds() / 60
        ).round(1)
    else:
        df["trade_duration_min"] = 0.0

    # Regime stability
    df["regime_held"] = (
        df["entry_regime"] == df["exit_regime"]
    ).astype(int) if "entry_regime" in df.columns else 1

    df["regime_changed_during"] = df.apply(
        lambda r: (r["exit_regime"]
                   if r.get("entry_regime") != r.get("exit_regime") else ""),
        axis=1
    ) if "entry_regime" in df.columns else ""

    # Broad regime bucket
    df["entry_broad_regime"] = df["entry_regime"].map(
        lambda x: V3D_BROAD_MAP.get(str(x), "UNKNOWN")
    ) if "entry_regime" in df.columns else "UNKNOWN"

    # In-correct-regime
    def correct_regime(row):
        bot     = str(row.get("bot_name", ""))
        regime  = str(row.get("entry_regime", ""))
        targets = BOT_TARGET_REGIMES.get(bot, [])
        return 1 if regime in targets else 0
    df["in_correct_regime"] = df.apply(correct_regime, axis=1)

    # Ticks per minute
    df["ticks_per_minute"] = df.apply(
        lambda r: round(abs(r["ticks"]) / max(r["trade_duration_min"], 0.1), 2), axis=1
    )

    # Rank within day/symbol/bot
    if "entry_time" in df.columns:
        df = df.sort_values("entry_time")
    df["session_trade_rank"] = (
        df.groupby(["trade_date", "symbol", "bot_name"]).cumcount() + 1
    )

    # Running PnL
    df["daily_pnl_running"] = (
        df.groupby(["trade_date", "symbol", "bot_name"])["gross_pnl"]
        .cumsum().round(2)
    )

    df["risk_reward_actual"] = ""  # requires stop distance from NT8 performance report

    return df


def per_bot_stats(day: pd.DataFrame, bot_key: str, bot_name: str) -> dict:
    """Return trade count, gross PnL, win rate for one bot on one day."""
    subset = day[day["bot_name"] == bot_name]
    if subset.empty:
        return {f"{bot_key}_trades": 0, f"{bot_key}_pnl": 0.0,
                f"{bot_key}_win_rate": 0.0}
    total  = len(subset)
    wins   = (subset["win_loss"] == "WIN").sum()
    pnl    = round(float(subset["gross_pnl"].sum()), 2)
    wr     = round(wins / total * 100, 1) if total > 0 else 0.0
    return {f"{bot_key}_trades": total,
            f"{bot_key}_pnl":    pnl,
            f"{bot_key}_win_rate": wr}


def compute_trade_summary(df: pd.DataFrame, symbol: str,
                          report_date: date) -> dict:
    empty = {
        "trade_count": 0, "winning_trades": 0, "losing_trades": 0,
        "scratch_trades": 0, "gross_pnl": 0.0, "net_pnl": 0.0,
        "win_rate_pct": 0.0, "profit_factor": 0.0,
        "avg_winner": 0.0, "avg_loser": 0.0, "avg_trade_pnl": 0.0,
        "max_winner": 0.0, "max_loser": 0.0,
        "total_contracts": 0, "bots_active": "",
        "expansion_trades": 0, "expansion_pnl": 0.0, "expansion_win_rate": 0.0,
        "momo_trades":      0, "momo_pnl":      0.0, "momo_win_rate":      0.0,
        "fader_trades":     0, "fader_pnl":     0.0, "fader_win_rate":     0.0,
        "sniper_trades":    0, "sniper_pnl":    0.0, "sniper_win_rate":    0.0,
        "adx_di_trades":    0, "adx_di_pnl":    0.0, "adx_di_win_rate":    0.0,
        "pct_trades_in_correct_regime": 0.0,
        "pct_trades_regime_held":       0.0,
    }
    if df.empty:
        return empty

    date_str = report_date.strftime("%Y-%m-%d")
    day = df[(df["trade_date"] == date_str) &
             (df["symbol"].str.upper() == symbol.upper())].copy()

    if day.empty:
        return empty

    for col in ["gross_pnl", "net_pnl", "contracts",
                "in_correct_regime", "regime_held"]:
        if col in day.columns:
            day[col] = pd.to_numeric(day[col], errors="coerce").fillna(0)

    wins    = day[day["win_loss"] == "WIN"]["gross_pnl"]
    losses  = day[day["win_loss"] == "LOSS"]["gross_pnl"]
    scratch = day[day["win_loss"] == "SCRATCH"]
    total   = len(day)

    sum_wins  = float(wins.sum())   if not wins.empty   else 0.0
    sum_loss  = abs(float(losses.sum())) if not losses.empty else 0.0
    pf        = (round(sum_wins / sum_loss, 2) if sum_loss > 0
                 else (round(sum_wins, 2) if sum_wins > 0 else 0.0))

    base = {
        "trade_count":     total,
        "winning_trades":  len(wins),
        "losing_trades":   len(losses),
        "scratch_trades":  len(scratch),
        "gross_pnl":       round(float(day["gross_pnl"].sum()), 2),
        "net_pnl":         round(float(day["net_pnl"].sum()),   2)
                           if "net_pnl" in day.columns else 0.0,
        "win_rate_pct":    round(len(wins) / total * 100, 1) if total > 0 else 0.0,
        "profit_factor":   pf,
        "avg_winner":      round(float(wins.mean()),    2) if not wins.empty   else 0.0,
        "avg_loser":       round(float(losses.mean()),  2) if not losses.empty else 0.0,
        "avg_trade_pnl":   round(float(day["gross_pnl"].mean()), 2),
        "max_winner":      round(float(wins.max()),     2) if not wins.empty   else 0.0,
        "max_loser":       round(float(losses.min()),   2) if not losses.empty else 0.0,
        "total_contracts": int(day["contracts"].sum())
                           if "contracts" in day.columns else 0,
        "bots_active":     ", ".join(sorted(day["bot_name"].dropna().unique()))
                           if "bot_name" in day.columns else "",
    }

    # Per-bot breakdown
    bot_map = {
        "expansion": "Expansion_V3D",
        "momo":      "Momentum_V3D",
        "fader":     "Fader_V3D",
        "sniper":    "Sniper_V3D",
        "adx_di":    "ADX_DI_V3D",
    }
    for key, name in bot_map.items():
        base.update(per_bot_stats(day, key, name))

    # Regime quality metrics
    base["pct_trades_in_correct_regime"] = (
        round(float(day["in_correct_regime"].mean()) * 100, 1)
        if "in_correct_regime" in day.columns else 0.0
    )
    base["pct_trades_regime_held"] = (
        round(float(day["regime_held"].mean()) * 100, 1)
        if "regime_held" in day.columns else 0.0
    )

    return base


# ===========================================================================
# 4.  CROSS-MODEL AGREEMENT
# ===========================================================================

def compute_agreement(v3d: dict, v3c: dict) -> dict:
    v3d_broad = V3D_BROAD_MAP.get(str(v3d.get("v3d_final_regime", "")), "UNKNOWN")
    v3c_broad = V3C_BROAD_MAP.get(str(v3c.get("v3c_regime", "")).upper(), "UNKNOWN")
    broad_agree = int(v3d_broad == v3c_broad and v3d_broad != "UNKNOWN")

    v3d_hmm = str(v3d.get("v3d_hmm_regime", "")).lower()
    v3c_hmm = str(v3c.get("v3c_hmm_regime", "")).lower()
    hmm_agree = int(
        v3d_hmm == v3c_hmm and v3d_hmm not in ("", "unavailable", "unknown"))

    v3c_dir = str(v3c.get("v3c_direction", "")).upper()
    v3d_hmm_upper = str(v3d.get("v3d_hmm_regime", "")).upper()
    direction_agree = int(
        (v3c_dir in ("LONG", "TREND_UP")   and "UP"   in v3d_hmm_upper) or
        (v3c_dir in ("SHORT", "TREND_DOWN") and "DOWN" in v3d_hmm_upper) or
        (v3c_dir in ("NEUTRAL", "")         and "ROTATION" in v3d_broad)
    )

    return {
        "broad_agree":         broad_agree,
        "hmm_agree":           hmm_agree,
        "direction_agree":     direction_agree,
        "confidence_delta":    int(v3d.get("v3d_confidence", 0)) -
                               int(v3c.get("v3c_confidence", 0)),
        "regime_change_delta": int(v3d.get("v3d_final_regime_changes", 0)) -
                               int(v3c.get("v3c_regime_changes", 0)),
    }


# ===========================================================================
# 5.  CSV WRITERS  (append-only, dedup by trade_date+symbol)
# ===========================================================================

def ensure_csv(path: str, columns: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        log.info(f"Created: {path}")


def append_rows(path: str, rows: list, columns: list):
    if not rows:
        return
    df_new = pd.DataFrame(rows, columns=columns)
    candidate_keys = ("trade_date", "symbol", "checkpoint_time") \
        if "checkpoint_time" in columns else ("trade_date", "symbol")
    key_cols = [c for c in candidate_keys if c in columns]
    if key_cols:
        df_new = df_new.drop_duplicates(subset=key_cols, keep="last")
    if os.path.exists(path) and os.path.getsize(path) > 10:
        df_ex = pd.read_csv(path, dtype=str)
        if key_cols:
            new_keys = set(df_new[key_cols].apply(tuple, axis=1))
            df_ex = df_ex[~df_ex[key_cols].apply(tuple, axis=1).isin(new_keys)]
        pd.concat([df_ex, df_new], ignore_index=True).to_csv(path, index=False)
    else:
        df_new.to_csv(path, index=False)
    log.info(f"Wrote {len(rows)} row(s) -> {path}")


def write_enriched_trades(df_new: pd.DataFrame):
    if df_new.empty:
        return
    path = TRADE_ENRICHED_PATH
    ensure_csv(path, TRADE_ENRICHED_COLS)
    for col in TRADE_ENRICHED_COLS:
        if col not in df_new.columns:
            df_new[col] = ""
    df_new = df_new[TRADE_ENRICHED_COLS]
    if os.path.exists(path) and os.path.getsize(path) > 10:
        df_ex = pd.read_csv(path, dtype=str)
        new_dates = set(df_new["trade_date"].unique())
        new_syms  = set(df_new["symbol"].str.upper().unique())
        mask = ~(df_ex["trade_date"].isin(new_dates) &
                 df_ex["symbol"].str.upper().isin(new_syms))
        pd.concat([df_ex[mask], df_new], ignore_index=True).to_csv(path, index=False)
    else:
        df_new.to_csv(path, index=False)
    log.info(f"Wrote {len(df_new)} enriched trade row(s) -> {path}")


# ===========================================================================
# 6.  PER-DATE PROCESSOR
# ===========================================================================

def process_date(report_date: date, raw_trades: pd.DataFrame,
                 enriched_trades: pd.DataFrame):
    log.info(f"=== Processing {report_date} ===")

    v3d_data = load_v3d_json(report_date)
    if v3d_data is None:
        log.warning(f"No V3D JSON for {report_date}. Skipping regime comparison.")
        return

    v3d_by_sym = {d["symbol"].upper(): d for d in v3d_data if "symbol" in d}
    comparison_rows = []
    intraday_rows = []

    for symbol in SYMBOLS:
        if symbol not in v3d_by_sym:
            log.warning(f"[{symbol}] missing from V3D JSON. Skipping.")
            continue

        v3d       = extract_v3d_summary(v3d_by_sym[symbol])
        v3c       = load_v3c_for_date(symbol, report_date)
        agreement = compute_agreement(v3d, v3c)
        trades    = compute_trade_summary(enriched_trades, symbol, report_date)

        flag_review   = int(agreement["broad_agree"] == 0)
        flag_stale    = int(v3d.get("v3d_stale_count", 0) > 0)
        flag_loss_day = int(float(trades.get("net_pnl", 0)) < 0 and
                            trades.get("trade_count", 0) > 0)

        row = {
            "trade_date":   report_date.strftime("%Y-%m-%d"),
            "symbol":       symbol,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **v3d, **v3c, **agreement, **trades,
            "flag_review":    flag_review,
            "flag_v3d_stale": flag_stale,
            "flag_loss_day":  flag_loss_day,
            "notes": "",
        }

        comparison_rows.append({c: row.get(c, "") for c in REGIME_COMPARISON_COLS})
        intraday_symbol_rows = build_intraday_comparison(symbol, report_date)
        intraday_rows.extend(
            {c: r.get(c, "") for c in INTRADAY_COMPARISON_COLS}
            for r in intraday_symbol_rows
        )

        log.info(
            f"  [{symbol}] V3D={v3d['v3d_final_regime']}  "
            f"V3C={v3c['v3c_regime']}  "
            f"BroadAgree={agreement['broad_agree']}  "
            f"Trades={trades['trade_count']}  "
            f"PnL=${trades['gross_pnl']}  "
            f"PF={trades['profit_factor']}"
        )

    ensure_csv(REGIME_COMPARISON_PATH, REGIME_COMPARISON_COLS)
    append_rows(REGIME_COMPARISON_PATH, comparison_rows, REGIME_COMPARISON_COLS)
    ensure_csv(INTRADAY_COMPARISON_PATH, INTRADAY_COMPARISON_COLS)
    append_rows(INTRADAY_COMPARISON_PATH, intraday_rows, INTRADAY_COMPARISON_COLS)

    # Write enriched trade rows for this date
    if not enriched_trades.empty:
        date_str = report_date.strftime("%Y-%m-%d")
        day_slice = enriched_trades[enriched_trades["trade_date"] == date_str]
        write_enriched_trades(day_slice)


# ===========================================================================
# 7.  DATE RESOLUTION
# ===========================================================================

def resolve_dates(date_arg: str) -> list:
    if date_arg.lower() == "today":
        return [date.today()]
    if date_arg.lower() == "all":
        if not os.path.exists(ARCHIVE_DIR):
            log.warning(f"Archive dir not found: {ARCHIVE_DIR}")
            return [date.today()]
        dates = []
        for f in sorted(Path(ARCHIVE_DIR).glob("V3D_Regime_Report_*.json")):
            try:
                d = datetime.strptime(f.stem.split("_")[-1], "%Y%m%d").date()
                dates.append(d)
            except ValueError:
                pass
        if not dates:
            log.warning("No JSON archives found - processing today only.")
            return [date.today()]
        log.info(f"Backfill: {len(dates)} dates ({dates[0]} -> {dates[-1]})")
        return dates
    try:
        return [datetime.strptime(date_arg, "%Y-%m-%d").date()]
    except ValueError:
        log.error(f"Invalid date: {date_arg}. Use YYYY-MM-DD.")
        sys.exit(1)


# ===========================================================================
# 8.  ENTRY POINT
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="V3D Regime Comparison + Trade Log Enrichment")
    p.add_argument("--date", default="today",
                   help="today | YYYY-MM-DD | all")
    return p.parse_args()


def main():
    args  = parse_args()
    dates = resolve_dates(args.date)

    # Load and enrich trade log once - shared across all dates
    raw_trades      = load_trade_log()
    enriched_trades = enrich_trades(raw_trades) if not raw_trades.empty \
                      else pd.DataFrame()
    ensure_csv(TRADE_ENRICHED_PATH, TRADE_ENRICHED_COLS)

    for d in dates:
        try:
            process_date(d, raw_trades, enriched_trades)
        except Exception as e:
            log.error(f"Failed {d}: {e}", exc_info=True)

    log.info("=== Done ===")
    log.info(f"  Regime comparison  : {REGIME_COMPARISON_PATH}")
    log.info(f"  Intraday comparison: {INTRADAY_COMPARISON_PATH}")
    log.info(f"  Enriched trade log : {TRADE_ENRICHED_PATH}")


if __name__ == "__main__":
    main()
