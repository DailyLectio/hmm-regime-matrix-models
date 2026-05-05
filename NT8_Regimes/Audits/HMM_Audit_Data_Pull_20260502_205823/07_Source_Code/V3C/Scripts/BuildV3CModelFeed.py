from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
V3C_DIR = BASE_DIR / "V3C"
MODEL_FEED_DIR = V3C_DIR / "ModelFeed"
MODELS_DIR = V3C_DIR / "Models"
LIVE_WINDOW_DIR = V3C_DIR / "LiveWindow"
RAW_DIR = BASE_DIR / "MacroRegime" / "data" / "raw"
MACRO_DIR = BASE_DIR / "MacroRegime"
LIVE_LOOKBACK_DAYS = 100

MODEL_FEED_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
LIVE_WINDOW_DIR.mkdir(parents=True, exist_ok=True)

CONTINUOUS_FILES: Dict[str, Path] = {
    "ES": RAW_DIR / "ES" / "ES_Continuous_20230601_20260424.Last.txt",
    "NQ": RAW_DIR / "NQ" / "NQ_Continuous_20230101_20260424.Last.txt",
}

MACRO_BUILDERS: Dict[str, Path] = {
    "ES": MACRO_DIR / "MacroRegimeBuilder_ES.py",
    "NQ": MACRO_DIR / "MacroRegimeBuilder_NQ.py",
}

HMM_FEATURE_COLUMNS = [
    "ret_1",
    "ret_3",
    "range_atr",
    "vol_z",
    "vwap_dist_atr",
    "close_pos",
    "phase_code",
]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _phase_bucket(minutes_from_open: float) -> str:
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


def _phase_code_from_timestamp(ts: pd.Series) -> pd.Series:
    minutes = ts.dt.hour * 60 + ts.dt.minute - (9 * 60 + 30)
    buckets = minutes.map(_phase_bucket)
    mapping = {
        "PREMARKET": -1,
        "OPEN": 0,
        "EARLY_AM": 1,
        "POST_IB_AM": 2,
        "LUNCH": 3,
        "PM": 4,
        "POWER_HOUR": 5,
        "CLOSE": 6,
    }
    return buckets.map(mapping).fillna(-1).astype(float)


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_nt_export(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=";",
        header=None,
        names=["Timestamp", "Open", "High", "Low", "Close", "Volume"],
        engine="python",
    )
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y%m%d %H%M%S", errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().sort_values("Timestamp").drop_duplicates("Timestamp", keep="last")
    return df.reset_index(drop=True)


def _write_nt_export(df: pd.DataFrame, path: Path) -> Path:
    out = df.copy()
    out["Timestamp"] = out["Timestamp"].dt.strftime("%Y%m%d %H%M%S")
    out[["Timestamp", "Open", "High", "Low", "Close", "Volume"]].to_csv(
        path,
        sep=";",
        header=False,
        index=False,
    )
    return path


def _live_window_export_path(symbol: str, source_path: Path, lookback_days: int | None) -> Path:
    if lookback_days is None or lookback_days <= 0:
        return source_path

    raw = _load_nt_export(source_path)
    if raw.empty:
        return source_path

    end_ts = raw["Timestamp"].max()
    start_ts = end_ts - pd.Timedelta(days=lookback_days)
    window = raw[raw["Timestamp"] >= start_ts].copy()
    if window.empty:
        window = raw.tail(1).copy()

    output_path = LIVE_WINDOW_DIR / f"{symbol}_V3C_LiveWindow_{lookback_days}d.txt"
    return _write_nt_export(window, output_path)


def _safe_localize_timestamp(df: pd.DataFrame, timezone_str: str) -> pd.DataFrame:
    out = df.copy()
    if out["Timestamp"].dt.tz is None:
        out["Timestamp"] = out["Timestamp"].dt.tz_localize(
            timezone_str,
            nonexistent="shift_forward",
            ambiguous="NaT",
        )
        out = out.dropna(subset=["Timestamp"])
    else:
        out["Timestamp"] = out["Timestamp"].dt.tz_convert(timezone_str)
    return out


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    return pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _add_v3c_macro_features(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    out = df.copy()
    out["phase_bucket"] = out["minutes_from_open"].map(_phase_bucket)

    numeric_cols = [
        "last_price",
        "atr_5m",
        "close_vs_vwap_atr",
        "net_move_since_open_atr",
        "ib_extension_pct",
        "directional_efficiency_since_open",
        "returned_to_open_flag",
        "two_sided_trade_flag",
        "value_break_accept_flag",
    ]
    for col in numeric_cols:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["MacroTimestamp"] = pd.to_datetime(
        out["trade_date"].astype(str) + " " + out["checkpoint_time"].astype(str),
        errors="coerce",
    )
    out = out.sort_values(["trade_date", "checkpoint_time"]).reset_index(drop=True)

    enriched = []
    for _, day in out.groupby("trade_date", sort=False):
        d = day.copy().sort_values("minutes_from_open")
        price = d["last_price"]
        atr = d["atr_5m"].replace(0, np.nan).ffill().bfill().fillna(1.0)
        delta = price.diff()
        path_10 = delta.abs().rolling(2, min_periods=1).sum()
        path_20 = delta.abs().rolling(4, min_periods=1).sum()
        move_10 = price - price.shift(2)
        move_20 = price - price.shift(4)

        d["rolling_efficiency_10m"] = (move_10.abs() / path_10.replace(0, np.nan)).fillna(0.0).clip(0, 1)
        d["rolling_efficiency_20m"] = (move_20.abs() / path_20.replace(0, np.nan)).fillna(0.0).clip(0, 1)
        d["local_net_move_10m_atr"] = (move_10 / atr).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        d["local_net_move_20m_atr"] = (move_20 / atr).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        vwap_side = np.sign(d["close_vs_vwap_atr"]).where(d["close_vs_vwap_atr"].abs() >= 0.25, 0)
        hold_count = []
        hold_minutes = []
        count = 0
        mins = 0.0
        last_side = 0
        last_minute = None
        for side, minute in zip(vwap_side, d["minutes_from_open"]):
            if side != 0 and side == last_side:
                count += 1
                if last_minute is not None:
                    mins += max(0.0, min(15.0, float(minute) - float(last_minute)))
            elif side != 0:
                count = 1
                mins = 0.0
            else:
                count = 0
                mins = 0.0
            hold_count.append(count)
            hold_minutes.append(mins)
            last_side = side
            last_minute = minute

        d["vwap_side"] = vwap_side.astype(int)
        d["vwap_hold_count"] = hold_count
        d["same_side_vwap_minutes"] = hold_minutes
        enriched.append(d)

    out = pd.concat(enriched, ignore_index=True).sort_values(["trade_date", "checkpoint_time"])

    ib_norm = 0.85 if symbol == "NQ" else 1.00
    ib_pressure = (out["ib_extension_pct"] / ib_norm).clip(0, 1)
    local_eff = out[["rolling_efficiency_10m", "rolling_efficiency_20m"]].max(axis=1)
    local_move = out[["local_net_move_10m_atr", "local_net_move_20m_atr"]].abs().max(axis=1)
    vwap_hold = (out["same_side_vwap_minutes"] / 20.0).clip(0, 1)
    vwap_distance = (out["close_vs_vwap_atr"].abs() / 1.2).clip(0, 1)
    value_accept = (out["value_break_accept_flag"].clip(lower=0) / 1.0).clip(0, 1)

    penalty = (
        0.18 * out["returned_to_open_flag"].clip(0, 1)
        + 0.10 * out["two_sided_trade_flag"].clip(0, 1)
        + 0.10 * (out["phase_bucket"] == "LUNCH").astype(float)
    )
    base_score = (
        0.30 * local_eff
        + 0.22 * vwap_hold
        + 0.18 * (local_move / 1.0).clip(0, 1)
        + 0.14 * vwap_distance
        + 0.10 * ib_pressure
        + 0.06 * value_accept
        - penalty
    )
    out["ib_escape_pressure"] = (ib_pressure * 100.0).round(2)
    out["value_acceptance_pressure"] = (value_accept * 100.0).round(2)
    out["developing_initiative_score"] = (base_score.clip(0, 1) * 100.0).round(2)

    direction_basis = (
        0.45 * np.sign(out["local_net_move_10m_atr"])
        + 0.35 * np.sign(out["close_vs_vwap_atr"])
        + 0.20 * np.sign(out["net_move_since_open_atr"])
    )
    out["initiative_direction"] = np.select(
        [direction_basis >= 0.35, direction_basis <= -0.35],
        ["LONG", "SHORT"],
        default="NONE",
    )

    late_phase = out["phase_bucket"].isin(["PM", "POWER_HOUR", "CLOSE"]).astype(float)
    stretch = (out["close_vs_vwap_atr"].abs() / 1.6).clip(0, 1)
    late_ext = (late_phase * stretch * (0.50 + 0.50 * (out["ib_extension_pct"] / max(ib_norm, 0.1)).clip(0, 1))).clip(0, 1)
    out["late_extension_penalty"] = (late_ext * 100.0).round(2)
    out["macro_logic_version"] = out["macro_logic_version"].astype(str) + "_V3C_EarlyInitiative"

    return out.drop(columns=["MacroTimestamp"], errors="ignore")


def build_macro_feed(symbol: str, input_path: Path | None = None, lookback_days: int | None = None) -> Path:
    source_path = Path(input_path) if input_path is not None else CONTINUOUS_FILES[symbol]
    source_path = _live_window_export_path(symbol, source_path, lookback_days)
    builder_mod = _load_module(MACRO_BUILDERS[symbol], f"macro_builder_{symbol.lower()}")
    builder_mod.localize_timestamp = _safe_localize_timestamp
    builder = builder_mod.MacroRegimeBuilder(builder_mod.CONFIGS[symbol])
    out = builder.build_from_nt_export(source_path)
    out = _add_v3c_macro_features(out, symbol)
    output_path = MODEL_FEED_DIR / f"{symbol}_Macro_Regimes_V3C.csv"
    out.to_csv(output_path, index=False)
    return output_path


def _prepare_hmm_features(
    symbol: str,
    input_path: Path | None = None,
    require_forward_labels: bool = True,
    lookback_days: int | None = None,
) -> pd.DataFrame:
    source_path = Path(input_path) if input_path is not None else CONTINUOUS_FILES[symbol]
    source_path = _live_window_export_path(symbol, source_path, lookback_days)
    raw = _load_nt_export(source_path)
    bars = (
        raw.set_index("Timestamp")
        .resample("5min")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )

    tr = _true_range(bars)
    atr = tr.rolling(14, min_periods=5).mean()
    typical = (bars["High"] + bars["Low"] + bars["Close"]) / 3.0
    rolling_pv = (typical * bars["Volume"]).rolling(20, min_periods=5).sum()
    rolling_vol = bars["Volume"].rolling(20, min_periods=5).sum().replace(0, np.nan)
    rvwap = rolling_pv / rolling_vol

    feat = bars.copy()
    feat["atr"] = atr
    feat["ret_1"] = feat["Close"].pct_change(1)
    feat["ret_3"] = feat["Close"].pct_change(3)
    feat["range_atr"] = ((feat["High"] - feat["Low"]) / feat["atr"].replace(0, np.nan)).clip(0, 8)
    feat["vol_z"] = (
        (feat["Volume"] - feat["Volume"].rolling(50, min_periods=20).mean())
        / feat["Volume"].rolling(50, min_periods=20).std().replace(0, np.nan)
    ).clip(-5, 5)
    feat["vwap_dist_atr"] = ((feat["Close"] - rvwap) / feat["atr"].replace(0, np.nan)).clip(-8, 8)
    feat["close_pos"] = ((feat["Close"] - feat["Low"]) / (feat["High"] - feat["Low"]).replace(0, np.nan)).clip(0, 1)
    feat["phase_code"] = _phase_code_from_timestamp(pd.Series(feat.index, index=feat.index))
    feat["fwd_6"] = feat["Close"].shift(-6) / feat["Close"] - 1.0
    feat["fwd_3"] = feat["Close"].shift(-3) / feat["Close"] - 1.0
    feat = feat.replace([np.inf, -np.inf], np.nan)

    required_columns = list(HMM_FEATURE_COLUMNS)
    if require_forward_labels:
        required_columns += ["fwd_6", "fwd_3"]

    feat = feat.dropna(subset=required_columns).copy()
    return feat


def _label_hmm_states(model_df: pd.DataFrame) -> Dict[int, str]:
    stats = model_df.groupby("StateId").agg(
        fwd_6=("fwd_6", "median"),
        fwd_3=("fwd_3", "median"),
        ret_3=("ret_3", "median"),
        range_atr=("range_atr", "median"),
        vwap_dist_atr=("vwap_dist_atr", "median"),
        vol_z=("vol_z", "median"),
    )
    stats["trend_score"] = stats["fwd_6"] + 0.5 * stats["fwd_3"] + 0.0005 * stats["vwap_dist_atr"]
    up_state = int(stats["trend_score"].idxmax())
    down_state = int(stats["trend_score"].idxmin())
    remaining = [int(s) for s in stats.index if int(s) not in {up_state, down_state}]
    if len(remaining) == 1:
        return {up_state: "TrendUp", down_state: "TrendDown", remaining[0]: "Balance"}
    rem_stats = stats.loc[remaining].copy()
    rem_stats["transition_score"] = rem_stats["range_atr"].rank() + rem_stats["vol_z"].abs().rank()
    transition_state = int(rem_stats["transition_score"].idxmax())
    balance_state = int([s for s in remaining if s != transition_state][0])
    return {
        up_state: "TrendUp",
        down_state: "TrendDown",
        balance_state: "Balance",
        transition_state: "Transition",
    }


def build_hmm_feed(
    symbol: str,
    input_path: Path | None = None,
    train: bool = True,
    lookback_days: int | None = None,
) -> Tuple[Path, Path]:
    feat = _prepare_hmm_features(
        symbol,
        input_path=input_path,
        require_forward_labels=train,
        lookback_days=lookback_days,
    )
    artifact_path = MODELS_DIR / f"{symbol}_Anchored_HMM_V3C.joblib"

    if train:
        scaler = StandardScaler()
        x = scaler.fit_transform(feat[HMM_FEATURE_COLUMNS])
        model = GaussianHMM(
            n_components=4,
            covariance_type="full",
            n_iter=500,
            random_state=42,
            min_covar=0.001,
        )
        model.fit(x)
        states = model.predict(x)
        probs = model.predict_proba(x)
        state_map = None
    else:
        if not artifact_path.exists():
            raise FileNotFoundError(f"Missing anchored HMM artifact: {artifact_path}")
        artifact = joblib.load(artifact_path)
        model = artifact["model"]
        scaler = artifact["scaler"]
        state_map = artifact["state_map"]
        x = scaler.transform(feat[HMM_FEATURE_COLUMNS])
        states = model.predict(x)
        probs = model.predict_proba(x)

    out = feat.copy()
    out["StateId"] = states
    if state_map is None:
        state_map = _label_hmm_states(out)
    out["RegimeLabel"] = out["StateId"].map(state_map).fillna("Balance")
    out["StateProb"] = probs.max(axis=1)
    sorted_probs = np.sort(probs, axis=1)
    out["StateMargin"] = sorted_probs[:, -1] - sorted_probs[:, -2]
    with np.errstate(divide="ignore", invalid="ignore"):
        entropy = -(probs * np.log(np.clip(probs, 1e-12, 1.0))).sum(axis=1) / math.log(probs.shape[1])
    out["StateEntropy"] = entropy
    out["StateAge"] = out.groupby((out["StateId"] != out["StateId"].shift()).cumsum()).cumcount() + 1

    out["Tradeable"] = out["RegimeLabel"].isin(["TrendUp", "TrendDown", "Transition"])
    out["AllowLong"] = out["RegimeLabel"].isin(["TrendUp", "Transition"])
    out["AllowShort"] = out["RegimeLabel"].isin(["TrendDown", "Transition"])
    out["SuggestedAdxMin"] = np.where(out["RegimeLabel"].isin(["TrendUp", "TrendDown"]), 18, np.where(out["RegimeLabel"] == "Transition", 22, 0))
    out["SuggestedCiMax"] = np.where(out["RegimeLabel"] == "Balance", 60, np.where(out["RegimeLabel"] == "Transition", 55, 50))
    out["SuggestedSlopeGate"] = out["RegimeLabel"].eq("Transition")
    out["SuggestedStopBucket"] = np.select(
        [out["RegimeLabel"].isin(["TrendUp", "TrendDown"]), out["RegimeLabel"].eq("Balance")],
        ["Trend-Trailing", "Mean-Reversion"],
        default="Wide",
    )
    out["ModelVersion"] = "Anchored_HMM_V3C_20260425"

    regime_out = out.reset_index().rename(columns={"Timestamp": "TimestampET"})
    keep_cols = [
        "TimestampET",
        "StateId",
        "RegimeLabel",
        "Tradeable",
        "AllowLong",
        "AllowShort",
        "SuggestedAdxMin",
        "SuggestedCiMax",
        "SuggestedSlopeGate",
        "SuggestedStopBucket",
        "ModelVersion",
        "StateProb",
        "StateMargin",
        "StateEntropy",
        "StateAge",
        "ret_1",
        "ret_3",
        "range_atr",
        "vol_z",
        "vwap_dist_atr",
        "phase_code",
    ]
    output_path = MODEL_FEED_DIR / f"{symbol}_Regimes_HMM_V3C.csv"
    regime_out[keep_cols].to_csv(output_path, index=False)

    if train:
        joblib.dump(
            {
                "symbol": symbol,
                "model": model,
                "scaler": scaler,
                "feature_columns": HMM_FEATURE_COLUMNS,
                "state_map": state_map,
                "model_version": "Anchored_HMM_V3C_20260425",
            },
            artifact_path,
        )
    return output_path, artifact_path


def main() -> None:
    print("Building V3C sidecar ModelFeed from stitched ES/NQ histories...")
    for symbol in ["ES", "NQ"]:
        if not CONTINUOUS_FILES[symbol].exists():
            raise FileNotFoundError(CONTINUOUS_FILES[symbol])
        macro_path = build_macro_feed(symbol)
        hmm_path, artifact_path = build_hmm_feed(symbol)
        print(f"{symbol}: Macro -> {macro_path}")
        print(f"{symbol}: HMM   -> {hmm_path}")
        print(f"{symbol}: Model -> {artifact_path}")
    print("V3C ModelFeed build complete.")


if __name__ == "__main__":
    main()
