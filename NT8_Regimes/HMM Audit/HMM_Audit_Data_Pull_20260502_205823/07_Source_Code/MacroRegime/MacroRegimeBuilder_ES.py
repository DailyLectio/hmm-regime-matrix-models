from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

EPS = 1e-9

@dataclass(frozen=True)
class InstrumentConfig:
    symbol: str
    session_timezone: str = "America/New_York"
    rth_start: str = "09:30"
    rth_end: str = "16:00"
    eth_start: str = "18:00"
    ib_end: str = "10:30"
    # 5-minute polling intervals for tighter AMT tracking + Hourly Research Prints
    checkpoints: Sequence[str] = (
        "09:25", "09:35", "09:40", "09:45", "09:50", "09:55",
        "10:00", "10:05", "10:10", "10:15", "10:20", "10:25", 
        "10:30", "10:35", "10:45", "10:55", "11:05", "11:15", 
        "11:25", "11:35", "11:45", "11:55", "12:05", "12:15",
        "12:25", "12:35", "12:45", "12:55", "13:05", "13:15",
        "13:25", "13:35", "13:45", "13:55", "14:05", "14:15",
        "14:25", "14:35", "14:45", "14:55", "15:05", "15:15",
        "15:25", "15:35", "15:45", "15:55", "16:00"
    )
    daily_atr_lookback: int = 20
    intraday_atr_lookback: int = 20
    rolling_baseline_lookback: int = 20
    macro_logic_version: str = "Macro_ESNQ_v2.2_Research"

CONFIGS: Dict[str, InstrumentConfig] = {
    "ES": InstrumentConfig(symbol="ES"),
    "NQ": InstrumentConfig(symbol="NQ"),
}

PHASE_MAP = {
    "09:25": "PREMARKET_CONTEXT",
    "09:35": "OPENING_AUCTION",
    "09:40": "EARLY_TEST",
    "09:45": "FIRST_ACCEPTANCE",
    "09:50": "EARLY_CONTINUATION",
    "09:55": "EARLY_CONTINUATION",
    "10:00": "PRE_DECISION",
    "10:05": "END_FIRST_WINDOW",
    "10:10": "PRE_IB_MATURATION",
    "10:15": "PRE_IB_MATURATION",
    "10:20": "PRE_IB_MATURATION",
    "10:25": "NEAR_IB_CONDITION",
    "10:30": "NEAR_IB_CONDITION",
    "10:35": "POST_IB_MACRO",
    "10:45": "POST_IB_MACRO",
    "10:55": "POST_IB_MACRO",
    "11:05": "MID_MORNING_DISCOVERY",
    "11:15": "MID_MORNING_DISCOVERY",
    "11:25": "MID_MORNING_DISCOVERY",
    "11:35": "MID_MORNING_DISCOVERY",
    "11:45": "MID_MORNING_DISCOVERY",
    "11:55": "MID_MORNING_DISCOVERY",
    "12:05": "LUNCH_AUCTION",
    "12:15": "LUNCH_AUCTION",
    "12:25": "LUNCH_AUCTION",
    "12:35": "LUNCH_AUCTION",
    "12:45": "LUNCH_AUCTION",
    "12:55": "LUNCH_AUCTION",
    "13:05": "POST_LUNCH_ROTATION",
    "13:15": "POST_LUNCH_ROTATION",
    "13:25": "POST_LUNCH_ROTATION",
    "13:35": "POST_LUNCH_ROTATION",
    "13:45": "POST_LUNCH_ROTATION",
    "13:55": "POST_LUNCH_ROTATION",
    "14:05": "AFTERNOON_TREND_TEST",
    "14:15": "AFTERNOON_TREND_TEST",
    "14:25": "AFTERNOON_TREND_TEST",
    "14:35": "AFTERNOON_TREND_TEST",
    "14:45": "AFTERNOON_TREND_TEST",
    "14:55": "AFTERNOON_TREND_TEST",
    "15:05": "LATE_DAY_CONVICTION",
    "15:15": "LATE_DAY_CONVICTION",
    "15:25": "LATE_DAY_CONVICTION",
    "15:35": "LATE_DAY_CONVICTION",
    "15:45": "LATE_DAY_CONVICTION",
    "15:55": "LATE_DAY_CONVICTION",
    "16:00": "CASH_CLOSE",
}

FINAL_COLUMNS: List[str] = [
    "trade_date", "symbol", "checkpoint_time", "minutes_from_open",
    "phase", "macro_logic_version", "pd_high", "pd_low", "pd_close",
    "pd_range", "pd_vah", "pd_val", "pd_poc", "on_high", "on_low",
    "on_close", "on_range", "on_vah", "on_val", "on_poc", "on_volume",
    "on_range_pct_of_pd", "rth_open", "gap_vs_pd_close_atr", 
    "open_in_pd_value_flag", "open_in_on_value_flag", "last_price",
    "close_in_pd_value_flag", "close_in_on_value_flag", "two_sided_trade_flag",
    "returned_to_open_flag", "value_break_accept_flag", "session_vwap", 
    "close_vs_vwap_atr", "atr_5m", "net_move_since_open_atr", 
    "directional_efficiency_since_open", "ib_width_so_far", "ib_extension_pct",
    "price_vs_ib_high_atr", "price_vs_ib_low_atr", "checkpoint_state", 
    "official_bias_label", "official_regime_label", "tradable_flag", "no_trade_reason",
    "volatility_state", "playbook_state"
]

# --- Helper Utilities ---

def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if abs(float(b)) > EPS else 0.0

def _time_to_minutes_from_open(checkpoint_time: str, rth_start: str = "09:30") -> int:
    cp_h, cp_m = map(int, checkpoint_time.split(":"))
    op_h, op_m = map(int, rth_start.split(":"))
    return (cp_h * 60 + cp_m) - (op_h * 60 + op_m)

def load_nt_export(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(
        path, sep=";", header=None,
        names=["Timestamp", "Open", "High", "Low", "Close", "Volume"],
    )
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y%m%d %H%M%S", errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna().sort_values("Timestamp").reset_index(drop=True)

def localize_timestamp(df: pd.DataFrame, timezone_str: str) -> pd.DataFrame:
    out = df.copy()
    if out["Timestamp"].dt.tz is None:
        out["Timestamp"] = out["Timestamp"].dt.tz_localize(timezone_str)
    else:
        out["Timestamp"] = out["Timestamp"].dt.tz_convert(timezone_str)
    return out

def add_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ts = out["Timestamp"]
    out["trade_date"] = ts.dt.date
    out["time_str"] = ts.dt.strftime("%H:%M")
    out["clock_hhmmss"] = ts.dt.strftime("%H%M%S")
    return out

def compute_true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    return pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

def resample_5m(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index("Timestamp").resample("5min").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna().reset_index()

# --- Core Logic ---

class MacroRegimeBuilder:
    def __init__(self, config: InstrumentConfig):
        self.config = config

    def build_from_nt_export(self, path: str | Path) -> pd.DataFrame:
        raw = load_nt_export(path)
        raw = localize_timestamp(raw, self.config.session_timezone)
        raw = add_time_columns(raw)

        print(f"RAW ROWS: {len(raw)} | START: {raw['Timestamp'].min()} | END: {raw['Timestamp'].max()}")

        rows: List[dict] = []
        unique_dates = sorted(pd.Series(raw["trade_date"].unique()).tolist())

        for trade_date in unique_dates:
            session_rows = self._build_day_rows(raw, trade_date)
            if session_rows:
                rows.extend(session_rows)

        out = pd.DataFrame(rows)
        if out.empty:
            return pd.DataFrame(columns=FINAL_COLUMNS)

        for col in FINAL_COLUMNS:
            if col not in out.columns:
                out[col] = np.nan

        return out[FINAL_COLUMNS].sort_values(["trade_date", "checkpoint_time"]).reset_index(drop=True)

    def _build_day_rows(self, raw: pd.DataFrame, trade_date) -> List[dict]:
        day_df = raw[raw["trade_date"] == trade_date].copy()
        if day_df.empty: return []

        rth_df = day_df[(day_df["time_str"] >= self.config.rth_start) & (day_df["time_str"] <= self.config.rth_end)].copy()
        if rth_df.empty: return []

        prior_dates = sorted(raw.loc[raw["trade_date"] < trade_date, "trade_date"].unique())
        if not prior_dates: return []

        # Find the most recent prior date that ACTUALLY has an RTH session (skipping Sundays/Holidays)
        prior_date = None
        pd_df = pd.DataFrame()
        
        for p_date in reversed(prior_dates):
            temp_pd_df = raw[(raw["trade_date"] == p_date) & (raw["time_str"] >= self.config.rth_start) & (raw["time_str"] <= self.config.rth_end)].copy()
            if not temp_pd_df.empty:
                prior_date = p_date
                pd_df = temp_pd_df
                break
                
        if prior_date is None or pd_df.empty:
            return []

        prev_evening = raw[(raw["trade_date"] == prior_date) & (raw["time_str"] >= self.config.eth_start)].copy()
        current_morning = raw[(raw["trade_date"] == trade_date) & (raw["time_str"] < self.config.rth_start)].copy()
        on_df = pd.concat([prev_evening, current_morning], axis=0).sort_values("Timestamp").reset_index(drop=True)
        
        if on_df.empty: return []

        pd_metrics = self._calc_session_metrics(pd_df)
        on_metrics = self._calc_session_metrics(on_df)
        
        # Calculate daily ATR using RTH sessions only
        daily_rth = raw[(raw["time_str"] >= self.config.rth_start) & (raw["time_str"] <= self.config.rth_end)].copy()
        daily_rth["trade_date"] = daily_rth["Timestamp"].dt.date
        daily_agg = daily_rth.groupby("trade_date").agg({"High": "max", "Low": "min", "Close": "last"}).reset_index()
        daily_agg["tr"] = compute_true_range(daily_agg)
        
        atr_series = daily_agg["tr"].rolling(self.config.daily_atr_lookback, min_periods=1).mean()
        daily_agg["atr"] = atr_series
        
        daily_atr = daily_agg.loc[daily_agg["trade_date"] < trade_date, "atr"]
        daily_atr_val = daily_atr.iloc[-1] if not daily_atr.empty else pd_metrics["range"]

        if daily_atr_val == 0: daily_atr_val = 1.0

        # Calculate Intraday Rolling ATR (5-minute basis)
        df_5m = resample_5m(rth_df)
        df_5m["tr_5m"] = compute_true_range(df_5m)
        df_5m["atr_5m"] = df_5m["tr_5m"].rolling(self.config.intraday_atr_lookback, min_periods=1).mean().bfill()

        def get_atr_5m(t_str: str) -> float:
            sub = df_5m[df_5m["Timestamp"].dt.strftime("%H:%M") <= t_str]
            return sub["atr_5m"].iloc[-1] if not sub.empty else 1.0

        rth_open_price = rth_df.iloc[0]["Open"]
        gap_ticks = rth_open_price - pd_metrics["close"]
        gap_atr = _safe_div(gap_ticks, daily_atr_val)
        
        open_in_pd = 1 if (pd_metrics["val"] <= rth_open_price <= pd_metrics["vah"]) else 0
        open_in_on = 1 if (on_metrics["val"] <= rth_open_price <= on_metrics["vah"]) else 0

        rows = []
        for cp in self.config.checkpoints:
            cp_df = rth_df[rth_df["time_str"] <= cp].copy()
            
            # PREMARKET CHECKPOINT LOGIC
            if cp == "09:25":
                row_0925 = {
                    "trade_date": trade_date,
                    "symbol": self.config.symbol,
                    "checkpoint_time": cp,
                    "minutes_from_open": _time_to_minutes_from_open(cp, self.config.rth_start),
                    "phase": PHASE_MAP.get(cp, "UNKNOWN"),
                    "macro_logic_version": self.config.macro_logic_version,
                    
                    "pd_high": pd_metrics["high"], "pd_low": pd_metrics["low"], "pd_close": pd_metrics["close"],
                    "pd_range": pd_metrics["range"], "pd_vah": pd_metrics["vah"], "pd_val": pd_metrics["val"], "pd_poc": pd_metrics["poc"],
                    
                    "on_high": on_metrics["high"], "on_low": on_metrics["low"], "on_close": on_metrics["close"],
                    "on_range": on_metrics["range"], "on_vah": on_metrics["vah"], "on_val": on_metrics["val"], "on_poc": on_metrics["poc"], "on_volume": on_metrics["volume"],
                    
                    "on_range_pct_of_pd": _safe_div(on_metrics["range"], pd_metrics["range"]) * 100.0,
                    
                    "rth_open": np.nan, "gap_vs_pd_close_atr": np.nan, "open_in_pd_value_flag": np.nan, "open_in_on_value_flag": np.nan,
                    "last_price": on_metrics["close"], "close_in_pd_value_flag": 1 if (pd_metrics["val"] <= on_metrics["close"] <= pd_metrics["vah"]) else 0,
                    "close_in_on_value_flag": 1 if (on_metrics["val"] <= on_metrics["close"] <= on_metrics["vah"]) else 0,
                    "two_sided_trade_flag": np.nan, "returned_to_open_flag": np.nan, "value_break_accept_flag": np.nan,
                    "session_vwap": np.nan, "close_vs_vwap_atr": np.nan, "atr_5m": np.nan, "net_move_since_open_atr": np.nan,
                    "directional_efficiency_since_open": np.nan, "ib_width_so_far": np.nan, "ib_extension_pct": np.nan,
                    "price_vs_ib_high_atr": np.nan, "price_vs_ib_low_atr": np.nan,
                    
                    "checkpoint_state": "Premarket", "official_bias_label": "WAIT_FOR_OPEN",
                    "official_regime_label": "UNRESOLVED", "tradable_flag": 0, "no_trade_reason": "PREMARKET"
                }
                
                # Default V3 fields for premarket
                row_0925["volatility_state"] = "COMPRESSED"
                row_0925["playbook_state"] = "TRANSITION"
                
                rows.append(row_0925)
                continue

            # RTH CHECKPOINTS
            # V3 FIX: Stop calculating future checkpoints if the data hasn't arrived yet
            if cp > rth_df["time_str"].max():
                continue
                
            if cp_df.empty: continue

            last_price = cp_df.iloc[-1]["Close"]
            
            cp_high = cp_df["High"].max()
            cp_low = cp_df["Low"].min()
            net_move = last_price - rth_open_price
            gross_path = (cp_df["High"] - cp_df["Low"]).sum()
            dir_eff = _safe_div(abs(net_move), gross_path)

            close_in_pd = 1 if (pd_metrics["val"] <= last_price <= pd_metrics["vah"]) else 0
            close_in_on = 1 if (on_metrics["val"] <= last_price <= on_metrics["vah"]) else 0
            
            two_sided = 1 if (cp_high > rth_open_price) and (cp_low < rth_open_price) else 0
            
            returned_to_open = 0
            if cp >= "09:40":
                max_dev = max(abs(cp_high - rth_open_price), abs(rth_open_price - cp_low))
                if max_dev > (daily_atr_val * 0.25) and abs(last_price - rth_open_price) < (daily_atr_val * 0.1):
                    returned_to_open = 1

            vb_accept = 0
            if open_in_pd == 1 and close_in_pd == 0: vb_accept = 1
            if open_in_pd == 0 and close_in_pd == 1: vb_accept = -1

            typ_price = (cp_df["High"] + cp_df["Low"] + cp_df["Close"]) / 3.0
            vol = cp_df["Volume"]
            cum_pv = (typ_price * vol).sum()
            cum_vol = vol.sum()
            vwap = _safe_div(cum_pv, cum_vol) if cum_vol > 0 else last_price

            curr_atr_5m = get_atr_5m(cp)

            ib_df = day_df[(day_df["time_str"] >= self.config.rth_start) & (day_df["time_str"] <= min(cp, self.config.ib_end))]
            ib_h = ib_df["High"].max() if not ib_df.empty else 0.0
            ib_l = ib_df["Low"].min()  if not ib_df.empty else 0.0
            ib_width = max(0.0, ib_h - ib_l)
            
            ib_ext_pct = 0.0
            if ib_width > 0 and cp >= "10:30":
                if last_price > ib_h: ib_ext_pct = _safe_div(last_price - ib_h, ib_width)
                elif last_price < ib_l: ib_ext_pct = _safe_div(ib_l - last_price, ib_width)

            p_vs_ibh = _safe_div(last_price - ib_h, curr_atr_5m) if ib_width > 0 else 0.0
            p_vs_ibl = _safe_div(last_price - ib_l, curr_atr_5m) if ib_width > 0 else 0.0

            row = {
                "trade_date": trade_date,
                "symbol": self.config.symbol,
                "checkpoint_time": cp,
                "minutes_from_open": _time_to_minutes_from_open(cp, self.config.rth_start),
                "phase": PHASE_MAP.get(cp, "UNKNOWN"),
                "macro_logic_version": self.config.macro_logic_version,
                
                "pd_high": pd_metrics["high"], "pd_low": pd_metrics["low"], "pd_close": pd_metrics["close"],
                "pd_range": pd_metrics["range"], "pd_vah": pd_metrics["vah"], "pd_val": pd_metrics["val"], "pd_poc": pd_metrics["poc"],
                
                "on_high": on_metrics["high"], "on_low": on_metrics["low"], "on_close": on_metrics["close"],
                "on_range": on_metrics["range"], "on_vah": on_metrics["vah"], "on_val": on_metrics["val"], "on_poc": on_metrics["poc"], "on_volume": on_metrics["volume"],
                
                "on_range_pct_of_pd": _safe_div(on_metrics["range"], pd_metrics["range"]) * 100.0,
                
                "rth_open": rth_open_price, "gap_vs_pd_close_atr": gap_atr, "open_in_pd_value_flag": open_in_pd, "open_in_on_value_flag": open_in_on,
                "last_price": last_price, "close_in_pd_value_flag": close_in_pd, "close_in_on_value_flag": close_in_on,
                "two_sided_trade_flag": two_sided, "returned_to_open_flag": returned_to_open, "value_break_accept_flag": vb_accept,
                
                "session_vwap": vwap, "close_vs_vwap_atr": _safe_div(last_price - vwap, curr_atr_5m),
                "atr_5m": curr_atr_5m, "net_move_since_open_atr": _safe_div(net_move, curr_atr_5m),
                "directional_efficiency_since_open": dir_eff, "ib_width_so_far": ib_width, "ib_extension_pct": ib_ext_pct,
                "price_vs_ib_high_atr": p_vs_ibh, "price_vs_ib_low_atr": p_vs_ibl
            }

            row = self._add_macro_labels(row, cp)
            rows.append(row)

        return rows

    def _calc_session_metrics(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {"high": 0, "low": 0, "close": 0, "range": 0, "vah": 0, "val": 0, "poc": 0, "volume": 0}
        
        h = df["High"].max()
        l = df["Low"].min()
        c = df.iloc[-1]["Close"]
        v = df["Volume"].sum()

        prices = []
        vols = []
        for _, r in df.iterrows():
            typ = (r["High"] + r["Low"] + r["Close"]) / 3.0
            prices.append(typ)
            vols.append(r["Volume"])
            
        if sum(vols) == 0:
            return {"high": h, "low": l, "close": c, "range": h - l, "vah": c, "val": c, "poc": c, "volume": v}
            
        hist, bin_edges = np.histogram(prices, bins=50, weights=vols)
        poc_idx = np.argmax(hist)
        poc = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2.0

        total_vol = sum(vols)
        target_vol = total_vol * 0.70
        
        current_vol = hist[poc_idx]
        lower_idx = poc_idx - 1
        upper_idx = poc_idx + 1
        
        while current_vol < target_vol and (lower_idx >= 0 or upper_idx < len(hist)):
            vol_lower = hist[lower_idx] if lower_idx >= 0 else 0
            vol_upper = hist[upper_idx] if upper_idx < len(hist) else 0
            
            if vol_lower >= vol_upper and lower_idx >= 0:
                current_vol += vol_lower
                lower_idx -= 1
            elif upper_idx < len(hist):
                current_vol += vol_upper
                upper_idx += 1
            elif lower_idx >= 0:
                current_vol += vol_lower
                lower_idx -= 1
                
        val = bin_edges[max(0, lower_idx + 1)]
        vah = bin_edges[min(len(bin_edges)-1, upper_idx)]

        return {"high": h, "low": l, "close": c, "range": h - l, "vah": vah, "val": val, "poc": poc, "volume": v}

    def _add_macro_labels(self, row: dict, cp: str) -> dict:
        de = float(row.get("directional_efficiency_since_open", 0.0))
        close_vs_vwap = float(row.get("close_vs_vwap_atr", 0.0))
        net_move = float(row.get("net_move_since_open_atr", 0.0))
        close_in_on = int(row.get("close_in_on_value_flag", 0))
        two_sided = int(row.get("two_sided_trade_flag", 0))
        vb_accept = int(row.get("value_break_accept_flag", 0))
        returned_to_open = int(row.get("returned_to_open_flag", 0))
        
        if de >= 0.55 and close_vs_vwap > 0.25 and net_move > 0.5: rolling_state = "Bull_Initiative"
        elif de >= 0.55 and close_vs_vwap < -0.25 and net_move < -0.5: rolling_state = "Bear_Initiative"
        elif returned_to_open == 1 and two_sided == 1 and de < 0.4: rolling_state = "Failure" if vb_accept == 0 else "Transition"
        elif close_in_on == 1 and abs(close_vs_vwap) < 0.35: rolling_state = "Balance"
        else: rolling_state = "Transition"

        row["checkpoint_state"] = rolling_state

        bias = "UNCLEAR"
        regime = "UNRESOLVED"
        tradable = 1
        no_trade_reason = ""

        if cp == "09:35":
            regime = "OPENING_AUCTION"
            bias = f"AUCTION_{rolling_state.upper()}"
            if rolling_state in ["Balance", "Transition"]:
                tradable = 0
                no_trade_reason = "AWAITING_ALIGNMENT"

        elif cp >= "09:40" and cp <= "10:05":
            if rolling_state in ["Bull_Initiative", "Bear_Initiative"]:
                regime = "TREND_STRUCTURE"
                bias = f"CONFIRMED_{rolling_state.upper()}"
            elif rolling_state == "Failure":
                regime = "REVERSION_STRUCTURE"
                bias = "FADE_THE_EXTREMES"
            else:
                regime = "BALANCE_STRUCTURE"
                bias = "CHOP"
                tradable = 0
                if cp == "10:05": no_trade_reason = "1005_CHOP_DETECTED"

        elif cp >= "10:10":
            if rolling_state == "Bull_Initiative":
                regime = "TREND_UP_MACRO"
                bias = "BUY_DIPS"
            elif rolling_state == "Bear_Initiative":
                regime = "TREND_DOWN_MACRO"
                bias = "SELL_RIPS"
            elif rolling_state == "Failure":
                regime = "MEAN_REVERSION_MACRO"
                bias = "FADE_EDGES"
            else:
                regime = "BRACKET_MACRO"
                bias = "TRADE_LEVELS"

        row["official_bias_label"] = bias
        row["official_regime_label"] = regime
        row["tradable_flag"] = tradable
        row["no_trade_reason"] = no_trade_reason

        # ==============================================================
        # V3 SURGICAL PATCH: BREAKING THE HIERARCHY
        # ==============================================================
        ib_ext = float(row.get("ib_extension_pct", 0.0))
        close_vs_vwap = float(row.get("close_vs_vwap_atr", 0.0))
        net_move = float(row.get("net_move_since_open_atr", 0.0))
        
        # 1. Lowered ES Thresholds
        if ib_ext >= 1.00:
            vol_state = "EXPANDING"
        elif ib_ext >= 0.50:
            vol_state = "NORMAL"
        else:
            vol_state = "COMPRESSED"
            
        row["volatility_state"] = vol_state

        # 2. Confirmation Overrides
        ib_strong = ib_ext >= 1.00
        ib_expanding = ib_ext >= 0.75
        vwap_confirmed = abs(close_vs_vwap) > 0.50 and abs(net_move) > 0.75
        
        macro_trending = "TREND" in regime
        macro_bracket = not macro_trending

        # 3. Playbook Logic with Bracket Override
        if macro_trending and ib_strong:
            playbook = "TREND_EXPANSION"
        elif macro_trending:
            playbook = "TREND_COMPRESSION"
        # THE OVERRIDE: If expanding and VWAP agrees, it's a trend even if Macro is a Bracket
        elif macro_bracket and ib_strong and vwap_confirmed:
            playbook = "TREND_EXPANSION"
        elif macro_bracket and ib_expanding and vwap_confirmed:
            playbook = "TREND_COMPRESSION"
        elif macro_bracket:
            playbook = "ROTATION_LIQUID" if vol_state != "COMPRESSED" else "ROTATION_ILLIQUID"
        else:
            playbook = "TRANSITION"
            
        row["playbook_state"] = playbook
        # ==============================================================

        return row

def build_macro_csv(input_path, output_path, symbol):
    builder = MacroRegimeBuilder(CONFIGS[symbol.upper()])
    out = builder.build_from_nt_export(input_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out

if __name__ == "__main__":
    print("STARTING ES MACRO REGIME BUILDER...")
    try:
        input_data_path = r"C:\Users\Valued Customer\NT8_Regimes\Exports\ES_1min_export.txt"
        output_csv_path = r"C:\Users\Valued Customer\NT8_Regimes\Active\ES_Macro_Regimes.csv"
        
        df_out = build_macro_csv(
            input_path=input_data_path,
            output_path=output_csv_path,
            symbol="ES"
        )
        print(f"Finished. Wrote {len(df_out)} rows to {output_csv_path}")
        if not df_out.empty:
            print(f"\n--- RECENT ES V3 OUTPUT SNAPSHOT ---")
            display_cols = ['trade_date', 'checkpoint_time', 'checkpoint_state', 'official_regime_label', 'official_bias_label', 'playbook_state']
            print(df_out[display_cols].tail(10).to_string(index=False))
    except Exception as e:
        print(f"Error during script execution: {e}")