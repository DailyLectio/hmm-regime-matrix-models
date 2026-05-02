"""
Build the unified daily trade export for V1A, V3C, V3D, and standalone accounts.

This script intentionally does not trust model_version from raw logs. Account
registry mapping is authoritative, which fixes V3C rows previously stamped V3D.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
REGISTRY_PATH = BASE_DIR / "accounts_registry.json"
UNIFIED_DIR = BASE_DIR / "UNIFIED"

RAW_TRADE_LOGS = [
    BASE_DIR / "V1A" / "TradeLog" / "V1A_TradeLog.csv",
    BASE_DIR / "V1B" / "TradeLog" / "V1B_TradeLog.csv",
    BASE_DIR / "V3C" / "TradeLog" / "V3C_TradeLog.csv",
    BASE_DIR / "V3D" / "TradeLog" / "V3D_TradeLog.csv",
]

UNIFIED_COLUMNS = [
    "trade_date",
    "entry_time",
    "exit_time",
    "model_version",
    "account",
    "strategy_name",
    "bot_name",
    "ab_mode",
    "symbol",
    "instrument",
    "direction",
    "contracts",
    "entry_price",
    "exit_price",
    "gross_pnl",
    "net_pnl",
    "ticks",
    "win_loss",
    "exit_reason",
    "entry_regime",
    "entry_macro",
    "entry_hmm",
    "entry_phase",
    "entry_confidence",
    "entry_reason_code",
    "broad_agree",
    "v3c_regime_at_entry",
    "trade_duration_min",
    "risk_reward_actual",
    "session_trade_rank",
    "daily_pnl_running",
    "export_timestamp",
    "data_quality_flag",
]

V3D_BROAD_MAP = {
    "TREND_EXPANSION": "TREND",
    "TREND_COMPRESSION": "TREND",
    "ROTATION_LIQUID": "ROTATION",
    "ROTATION_ILLIQUID": "ROTATION",
    "TRANSITION": "TRANSITION",
}
V3C_BROAD_MAP = {
    "TREND_EXPANSION": "TREND",
    "TREND_COMPRESSION": "TREND",
    "TREND_UP": "TREND",
    "TREND_DOWN": "TREND",
    "TRENDUP": "TREND",
    "TRENDDOWN": "TREND",
    "TREND": "TREND",
    "ROTATION_LIQUID": "ROTATION",
    "ROTATION_ILLIQUID": "ROTATION",
    "ROTATION": "ROTATION",
    "BALANCE": "ROTATION",
    "TRANSITION": "TRANSITION",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate unified EOD trade exports.")
    parser.add_argument(
        "--date",
        default="today",
        help="Export date: today, yesterday, all, YYYY-MM-DD, or YYYYMMDD.",
    )
    parser.add_argument(
        "--base-dir",
        default=str(BASE_DIR),
        help="NT8_Regimes root path.",
    )
    parser.add_argument(
        "--regime-tolerance",
        default="35min",
        help="Maximum lookback for nearest-prior regime joins, for example 5min or 35min.",
    )
    return parser.parse_args()


def ensure_taxonomy(base_dir: Path) -> None:
    roots = ["V1A", "V1B", "V3C", "V3D", "UNIFIED"]
    subdirs = ["Config", "TradeLog", "History", "Regime", "Exports"]
    for root in roots:
        root_dir = base_dir / root
        root_dir.mkdir(exist_ok=True)
        if root != "UNIFIED":
            for subdir in subdirs:
                (root_dir / subdir).mkdir(exist_ok=True)
    (base_dir / "UNIFIED").mkdir(exist_ok=True)


def parse_export_date(value: str) -> date | None:
    token = value.strip().lower()
    if token == "all":
        return None
    if token == "today":
        return date.today()
    if token == "yesterday":
        return date.today() - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unsupported --date value: {value}")


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def clean_column_name(name: str) -> str:
    return (
        name.strip()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .lower()
    )


def read_trade_logs(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str)
        if df.empty:
            continue
        df.columns = [clean_column_name(c) for c in df.columns]
        df["source_file"] = str(path)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def normalize_trades(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    aliases = {
        "entry_datetime": "entry_time",
        "entry": "entry_time",
        "exit_datetime": "exit_time",
        "exit": "exit_time",
        "acct": "account",
        "quantity": "contracts",
        "qty": "contracts",
        "profit": "gross_pnl",
        "pnl": "gross_pnl",
        "instrument_name": "instrument",
    }
    for old, new in aliases.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    for col in ("entry_time", "exit_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "trade_date" not in df.columns:
        df["trade_date"] = df["entry_time"].dt.date.astype(str)
    else:
        parsed_dates = pd.to_datetime(df["trade_date"], errors="coerce")
        df["trade_date"] = parsed_dates.dt.date.astype(str)

    for col in ("contracts", "entry_price", "exit_price", "gross_pnl", "net_pnl", "ticks"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "net_pnl" not in df.columns and "gross_pnl" in df.columns:
        df["net_pnl"] = df["gross_pnl"]

    if "symbol" not in df.columns:
        df["symbol"] = df.get("instrument", "").astype(str).str.extract(r"\b(MNQ|MES|NQ|ES)\b", expand=False)
    df["symbol"] = df["symbol"].fillna("").astype(str).str.upper().replace({"MNQ": "NQ", "MES": "ES"})

    if "ticks" not in df.columns or df["ticks"].isna().all():
        tick_size = df["symbol"].map({"NQ": 0.25, "ES": 0.25}).fillna(0.25)
        signed_diff = df["exit_price"] - df["entry_price"]
        if "direction" in df.columns:
            short_mask = df["direction"].astype(str).str.upper().eq("SHORT")
            signed_diff = signed_diff.mask(short_mask, -signed_diff)
        df["ticks"] = signed_diff / tick_size

    if "win_loss" not in df.columns:
        df["win_loss"] = ""
    pnl = pd.to_numeric(df.get("gross_pnl", 0), errors="coerce").fillna(0)
    df["win_loss"] = df["win_loss"].where(df["win_loss"].astype(str).str.len() > 0)
    df["win_loss"] = df["win_loss"].fillna(
        pd.Series(["WIN" if x > 0 else "LOSS" if x < 0 else "SCRATCH" for x in pnl], index=df.index)
    )

    return df


def apply_registry(df: pd.DataFrame, registry: dict[str, dict[str, Any]]) -> pd.DataFrame:
    df = df.copy()

    def lookup(account: Any, key: str, default: str) -> str:
        return str(registry.get(str(account), {}).get(key, default))

    df["model_version"] = df["account"].map(lambda x: lookup(x, "model", "UNKNOWN"))
    df["strategy_name"] = df["account"].map(lambda x: lookup(x, "strategy", "UNKNOWN"))
    df["ab_mode"] = df["account"].map(lambda x: lookup(x, "ab_mode", "N/A"))
    if "bot_name" not in df.columns:
        df["bot_name"] = "UNMAPPED"
    df["bot_name"] = df["bot_name"].replace({"Unknown_Bot": "UNMAPPED", "": "UNMAPPED"}).fillna("UNMAPPED")
    return df


def select_time_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowered = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def load_regime_history(base_dir: Path, model: str, symbol: str, export_date: date | None) -> pd.DataFrame:
    if model == "V3C":
        candidates = [
            base_dir / "V3C" / f"{symbol}_Regimes_V3C.csv",
        ]
        if export_date is not None:
            stamp = export_date.strftime("%Y%m%d")
            candidates.extend(sorted((base_dir / "V3C" / "History").glob(f"{symbol}_Regimes_V3C_History_{stamp}_*.csv"), reverse=True))
        time_candidates = ["SnapshotTimestamp", "TimestampET", "Timestamp", "MicroTimestamp", "MacroTimestamp"]
    else:
        candidates = [
            base_dir / "V3D" / "History" / f"{symbol}_RegimeMatrix_History.csv",
        ]
        if export_date is not None:
            stamp = export_date.strftime("%Y%m%d")
            candidates.extend(sorted((base_dir / "V3D" / "History" / "Archives").glob(f"{symbol}_V3D_History_{stamp}_*.csv"), reverse=True))
        time_candidates = ["TimestampET", "Timestamp", "bar_time", "Time"]

    for path in candidates:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        time_col = select_time_column(df, time_candidates)
        if time_col is None:
            continue
        df = df.copy()
        df["_regime_time"] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=["_regime_time"]).sort_values("_regime_time")
        df = df.drop_duplicates(subset=["_regime_time"], keep="last")
        df["_regime_source_file"] = str(path)
        return df
    return pd.DataFrame()


def regime_columns(model: str) -> dict[str, str]:
    if model == "V3C":
        return {
            "FinalRegime": "entry_regime",
            "MacroRegime": "entry_macro",
            "HMM_Micro": "entry_hmm",
            "Phase": "entry_phase",
            "RegimeConfidence": "entry_confidence",
            "ReasonCode": "entry_reason_code",
        }
    return {
        "FinalRegime": "entry_regime",
        "MacroRegime": "entry_macro",
        "HMMRegime": "entry_hmm",
        "Phase": "entry_phase",
        "RegimeConfidence": "entry_confidence",
        "ReasonCode": "entry_reason_code",
    }


def enrich_with_regime(
    base_dir: Path,
    trades: pd.DataFrame,
    export_date: date | None,
    tolerance: str,
) -> pd.DataFrame:
    output: list[pd.DataFrame] = []
    for (model, symbol), group in trades.groupby(["model_version", "symbol"], dropna=False):
        model_for_regime = "V3C" if model == "V3C" else "V3D"
        regime = load_regime_history(base_dir, model_for_regime, str(symbol), export_date)
        group = group.copy().sort_values("entry_time")
        for col in ["entry_regime", "entry_macro", "entry_hmm", "entry_phase", "entry_confidence", "entry_reason_code"]:
            if col not in group.columns:
                group[col] = pd.NA
        if regime.empty or group["entry_time"].isna().all():
            output.append(group)
            continue

        mapping = regime_columns(model_for_regime)
        available = {src: dest for src, dest in mapping.items() if src in regime.columns}
        right = regime[["_regime_time", *available.keys()]].copy().sort_values("_regime_time")
        joined = pd.merge_asof(
            group,
            right,
            left_on="entry_time",
            right_on="_regime_time",
            direction="backward",
            tolerance=pd.Timedelta(tolerance),
        )
        for src, dest in available.items():
            joined[dest] = joined[src].combine_first(joined[dest])
            joined.drop(columns=[src], inplace=True)
        joined.drop(columns=["_regime_time"], inplace=True, errors="ignore")
        output.append(joined)

    if not output:
        return trades
    return pd.concat(output, ignore_index=True, sort=False)


def load_intraday_comparison(base_dir: Path) -> pd.DataFrame:
    paths = [
        base_dir / "UNIFIED" / "V3C_V3D_Intraday_Comparison.csv",
        base_dir / "V3D" / "History" / "V3C_V3D_Intraday_Comparison.csv",
    ]
    for path in paths:
        if path.exists():
            df = pd.read_csv(path)
            if "checkpoint_time" not in df.columns:
                continue
            df["checkpoint_time"] = pd.to_datetime(df["checkpoint_time"], errors="coerce")
            return df.dropna(subset=["checkpoint_time"]).sort_values("checkpoint_time")
    return pd.DataFrame()


def enrich_with_broad_agree(base_dir: Path, trades: pd.DataFrame) -> pd.DataFrame:
    comp = load_intraday_comparison(base_dir)
    trades = trades.copy()
    trades["broad_agree"] = pd.NA
    trades["v3c_regime_at_entry"] = pd.NA
    if comp.empty:
        return trades

    output: list[pd.DataFrame] = []
    for symbol, group in trades.groupby("symbol", dropna=False):
        right = comp[comp.get("symbol", "").astype(str).str.upper() == str(symbol).upper()].copy()
        if right.empty:
            output.append(group)
            continue
        right = right[["checkpoint_time", "broad_agree", "v3c_final_regime"]].sort_values("checkpoint_time")
        joined = pd.merge_asof(
            group.sort_values("entry_time"),
            right,
            left_on="entry_time",
            right_on="checkpoint_time",
            direction="backward",
            tolerance=pd.Timedelta("30min"),
            suffixes=("", "_comparison"),
        )
        joined["broad_agree"] = joined["broad_agree_comparison"].combine_first(joined["broad_agree"])
        joined["v3c_regime_at_entry"] = joined["v3c_final_regime"].combine_first(joined["v3c_regime_at_entry"])
        joined.drop(columns=["checkpoint_time", "broad_agree_comparison", "v3c_final_regime"], inplace=True, errors="ignore")
        output.append(joined)
    return pd.concat(output, ignore_index=True, sort=False)


def derive_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["trade_duration_min"] = ((df["exit_time"] - df["entry_time"]).dt.total_seconds() / 60).round(2)
    df["risk_reward_actual"] = pd.NA
    df = df.sort_values(["account", "trade_date", "entry_time"], na_position="last")
    df["session_trade_rank"] = df.groupby(["account", "trade_date"], dropna=False).cumcount() + 1
    df["daily_pnl_running"] = (
        df.groupby(["account", "trade_date"], dropna=False)["net_pnl"]
        .cumsum()
        .round(2)
    )
    df["export_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for col in ["entry_regime", "entry_macro", "entry_hmm", "entry_phase", "entry_reason_code"]:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = df[col].replace({"UNAVAILABLE": pd.NA, "": pd.NA})

    def flags(row: pd.Series) -> str:
        found: list[str] = []
        if row.get("model_version") == "UNKNOWN" or row.get("strategy_name") == "UNKNOWN":
            found.append("UNMAPPED_ACCOUNT")
        if pd.isna(row.get("entry_regime")):
            found.append("UNAVAILABLE_REGIME")
        if pd.isna(row.get("exit_reason")) or str(row.get("exit_reason")).strip() in ("", "UNKNOWN"):
            found.append("MISSING_EXITREASON")
        if str(row.get("bot_name", "")).strip() == "UNMAPPED":
            found.append("UNMAPPED_BOT")
        return ";".join(found) if found else "OK"

    df["data_quality_flag"] = df.apply(flags, axis=1)
    return df


def final_shape(df: pd.DataFrame) -> pd.DataFrame:
    for col in UNIFIED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    out = df[UNIFIED_COLUMNS].copy()
    for col in ("entry_time", "exit_time"):
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return out


def write_outputs(base_dir: Path, df: pd.DataFrame, export_date: date | None) -> list[Path]:
    stamp = "ALL" if export_date is None else export_date.strftime("%Y%m%d")
    written: list[Path] = []

    unified_path = base_dir / "UNIFIED" / f"AllModels_TradeLog_{stamp}.csv"
    df.to_csv(unified_path, index=False)
    written.append(unified_path)

    for model in ("V1A", "V1B", "V3C", "V3D"):
        subset = df[df["model_version"] == model]
        if subset.empty:
            continue
        model_path = base_dir / model / "History" / f"{model}_TradeLog_{stamp}.csv"
        subset.to_csv(model_path, index=False)
        written.append(model_path)

    report_path = base_dir / "UNIFIED" / f"DataQuality_Report_{stamp}.txt"
    counts = df["data_quality_flag"].value_counts(dropna=False)
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(f"Data Quality Report {stamp}\n")
        handle.write(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        handle.write(f"Rows: {len(df)}\n\n")
        handle.write("Flag counts:\n")
        for flag, count in counts.items():
            handle.write(f"  {flag}: {count}\n")
        handle.write("\nNon-OK rows:\n")
        problem_cols = ["trade_date", "entry_time", "account", "model_version", "strategy_name", "bot_name", "data_quality_flag"]
        for _, row in df[df["data_quality_flag"] != "OK"][problem_cols].iterrows():
            handle.write("  " + " | ".join(str(row[c]) for c in problem_cols) + "\n")
    written.append(report_path)
    return written


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir)
    export_date = parse_export_date(args.date)
    ensure_taxonomy(base_dir)

    registry = load_registry(base_dir / REGISTRY_PATH.name)
    raw_paths = [base_dir / p.relative_to(BASE_DIR) for p in RAW_TRADE_LOGS]
    trades = read_trade_logs(raw_paths)
    if trades.empty:
        print("No raw trade logs found.")
        return 1

    trades = normalize_trades(trades)
    if export_date is not None:
        date_str = export_date.strftime("%Y-%m-%d")
        trades = trades[trades["trade_date"] == date_str].copy()
    if trades.empty:
        print("No trades matched the requested date.")
        return 1

    trades = apply_registry(trades, registry)
    trades = enrich_with_regime(base_dir, trades, export_date, args.regime_tolerance)
    trades = enrich_with_broad_agree(base_dir, trades)
    trades = derive_columns(trades)
    shaped = final_shape(trades)
    written = write_outputs(base_dir, shaped, export_date)
    print("Wrote:")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
