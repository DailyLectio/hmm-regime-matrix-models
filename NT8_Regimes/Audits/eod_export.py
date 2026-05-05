"""
Build the unified daily trade export for V1A, V1B, V3C, V3D, OG, and standalone accounts.

This script normally treats the account registry as authoritative for model
taxonomy, while preserving raw OG rows so legacy strategies stay labeled OG.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
REGISTRY_PATH = BASE_DIR / "accounts_registry.json"   # must exist at this path
UNIFIED_DIR = BASE_DIR / "UNIFIED"

RAW_TRADE_LOGS = [
    # These are the master per-model logs written by the NT8 TradeLogExporter.
    # V3C is intentionally included here — its strategies write to V3C\TradeLog\.
    # If V3C strategies do not yet have Stage 1 logging, this path will not exist
    # and discover_raw_trade_logs() will skip it gracefully.
    BASE_DIR / "V1A" / "TradeLog" / "V1A_TradeLog.csv",
    BASE_DIR / "V1B" / "TradeLog" / "V1B_TradeLog.csv",
    BASE_DIR / "V3C" / "TradeLog" / "V3C_TradeLog.csv",
    BASE_DIR / "V3D" / "TradeLog" / "V3D_TradeLog.csv",
    BASE_DIR / "OG"  / "TradeLog" / "OG_TradeLog.csv",
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
    "initial_stop_price",
    "initial_stop_distance",
    "entry_regime",
    "entry_macro",
    "entry_hmm",
    "entry_phase",
    "entry_confidence",
    "entry_reason_code",
    "broad_agree",
    "v3c_regime_at_entry",
    "trade_duration_min",
    "r_multiple",
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
    roots = ["V1A", "V1B", "V3C", "V3D", "OG", "UNIFIED"]
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
    """Load accounts_registry.json.

    If the file does not exist, raise a clear FileNotFoundError that tells the
    operator exactly which file to place and where.  The accounts_registry.json
    is generated from the Master Accounts Registry CSV by the build_registry.py
    helper — run that first if the file is missing.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"\n\n  accounts_registry.json not found at:\n"
            f"    {path}\n\n"
            f"  Fix: copy the delivered accounts_registry.json to that exact path.\n"
            f"  It is generated from the Master Accounts Registry CSV.\n"
        )
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


def discover_raw_trade_logs(base_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for rel in RAW_TRADE_LOGS:
        paths.append(base_dir / rel.relative_to(BASE_DIR))
    for model in ("V1A", "V1B", "V3C", "V3D", "OG"):
        trade_dir = base_dir / model / "TradeLog"
        if trade_dir.exists():
            paths.extend(sorted(trade_dir.glob("*_TradeLog.csv")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        key = path.resolve() if path.exists() else path
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


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

    for col in (
        "contracts",
        "entry_price",
        "exit_price",
        "gross_pnl",
        "net_pnl",
        "ticks",
        "initial_stop_price",
        "initial_stop_distance",
    ):
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
    raw_model = (
        df["model_version"].astype(str).str.upper()
        if "model_version" in df.columns
        else pd.Series("", index=df.index)
    )

    def lookup(account: Any, key: str, default: str) -> str:
        return str(registry.get(str(account), {}).get(key, default))

    registry_model = df["account"].map(lambda x: lookup(x, "model", "UNKNOWN"))
    known_raw_model = raw_model.isin(["V1A", "V1B", "V3C", "V3D", "OG"])
    weak_registry_model = registry_model.astype(str).str.upper().isin(["UNKNOWN", "STANDALONE", ""])
    df["model_version"] = registry_model
    df.loc[known_raw_model & weak_registry_model, "model_version"] = raw_model[known_raw_model & weak_registry_model]
    df["strategy_name"] = df["account"].map(lambda x: lookup(x, "strategy", "UNKNOWN"))
    df["ab_mode"] = df["account"].map(lambda x: lookup(x, "ab_mode", "N/A"))
    if "bot_name" not in df.columns:
        df["bot_name"] = "UNMAPPED"
    df["bot_name"] = df["bot_name"].replace({"Unknown_Bot": "UNMAPPED", "": "UNMAPPED"}).fillna("UNMAPPED")
    og_mask = raw_model.eq("OG")
    if og_mask.any():
        df.loc[og_mask, "model_version"] = "OG"
        df.loc[og_mask, "ab_mode"] = "OG"
        strategy_text = df["strategy_name"].astype(str).str.strip()
        unmapped_strategy = df["strategy_name"].isna() | strategy_text.isin(["UNKNOWN", "", "nan", "None"])
        df.loc[og_mask & unmapped_strategy, "strategy_name"] = df.loc[og_mask & unmapped_strategy, "bot_name"]

    # Drop EXCLUDE accounts (DEMO/live brokerage accounts that must not appear in SIM analysis).
    # These are flagged in accounts_registry.json with model="EXCLUDE".
    exclude_mask = df["model_version"].astype(str).str.upper() == "EXCLUDE"
    if exclude_mask.any():
        n_excluded = exclude_mask.sum()
        excluded_accounts = df.loc[exclude_mask, "account"].unique()
        print(
            f"  [apply_registry] Dropped {n_excluded} rows from EXCLUDE accounts: "
            f"{list(excluded_accounts)}"
        )
        df = df[~exclude_mask].copy()

    return df


def dedupe_trades(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    signature_cols = [
        "trade_date",
        "entry_time",
        "exit_time",
        "account",
        "symbol",
        "instrument",
        "direction",
        "contracts",
        "entry_price",
        "exit_price",
        "net_pnl",
        "exit_reason",
    ]
    signature_cols = [col for col in signature_cols if col in df.columns]
    if not signature_cols:
        return df

    score = pd.Series(0, index=df.index)
    if "initial_stop_distance" in df.columns:
        score += df["initial_stop_distance"].notna().astype(int) * 4
    if "initial_stop_price" in df.columns:
        score += df["initial_stop_price"].notna().astype(int) * 2
    if "bot_name" in df.columns:
        bot_text = df["bot_name"].fillna("").astype(str).str.strip()
        score += (~bot_text.isin(["", "Unknown_Bot", "UNMAPPED", "UNKNOWN"])).astype(int)

    df["_stage1_quality_score"] = score
    df = df.sort_values("_stage1_quality_score", ascending=False, kind="mergesort")
    df = df.drop_duplicates(subset=signature_cols, keep="first")
    return df.drop(columns=["_stage1_quality_score"])


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
    if "initial_stop_distance" not in df.columns:
        df["initial_stop_distance"] = pd.NA
    df["initial_stop_distance"] = pd.to_numeric(df["initial_stop_distance"], errors="coerce")
    df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce")
    df["r_multiple"] = pd.NA
    valid_r = df["initial_stop_distance"].notna() & (df["initial_stop_distance"] > 0)
    df.loc[valid_r, "r_multiple"] = (
        df.loc[valid_r, "net_pnl"] / df.loc[valid_r, "initial_stop_distance"]
    ).round(2)
    if "risk_reward_actual" not in df.columns:
        df["risk_reward_actual"] = pd.NA
    df["risk_reward_actual"] = df["risk_reward_actual"].combine_first(df["r_multiple"])
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

    for model in ("V1A", "V1B", "V3C", "V3D", "OG"):
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
    raw_paths = discover_raw_trade_logs(base_dir)
    print(f"Discovered {len(raw_paths)} trade log path(s):")
    for p in raw_paths:
        exists = p.exists()
        if exists:
            import os
            rows = sum(1 for _ in p.open(encoding="utf-8")) - 1
            print(f"  {'OK  ' if rows > 0 else 'EMPTY'} ({rows:>6} rows) {p}")
        else:
            print(f"  MISS           {p}")
    print()

    trades = read_trade_logs(raw_paths)
    if trades.empty:
        print("No raw trade logs found or all are empty.")
        print(
            "  Next step: confirm NT8 strategy TradeLogExporters are compiled and\n"
            "  AccountNameFilter matches the exact account name on each strategy tab.\n"
            "  Per-account log files must exist in V3D\\TradeLog\\ (or V3C\\TradeLog\\ etc.)\n"
            "  after the first trade closes."
        )
        return 1

    trades = normalize_trades(trades)

    # -------------------------------------------------------------------------
    # Contamination guard: correct model_version for any row whose account
    # is registered under a different model.  This fixes the bug where the
    # NT8 TradeLogExporter writes to V3D_TradeLog.csv regardless of which
    # account is active, stamping all rows as "V3D" even for V3C/V1A accounts.
    # -------------------------------------------------------------------------
    if "account" in trades.columns:
        registry_models = trades["account"].map(
            lambda a: registry.get(str(a), {}).get("model", "")
        )
        # Only override when the registry has a definite model and the row
        # has a raw model_version that conflicts.
        has_registry = registry_models.astype(str).str.upper().isin(
            ["V1A", "V1B", "V3C", "V3D", "OG", "EXCLUDE"]
        )
        if has_registry.any():
            before = trades["model_version"].copy() if "model_version" in trades.columns else None
            trades["model_version"] = trades["model_version"].where(~has_registry, registry_models)
            if before is not None:
                changed = (trades["model_version"] != before) & has_registry
                if changed.any():
                    print(
                        f"  [contamination guard] Corrected model_version on {changed.sum()} rows "
                        f"based on registry (e.g., V3C/V1A accounts were stamped V3D)."
                    )

    if export_date is not None:
        date_str = export_date.strftime("%Y-%m-%d")
        trades = trades[trades["trade_date"] == date_str].copy()
    if trades.empty:
        print("No trades matched the requested date.")
        return 1

    trades = dedupe_trades(trades)
    trades = apply_registry(trades, registry)

    # After apply_registry, EXCLUDE rows have been dropped.
    # Print a quick account distribution so the operator can confirm
    # the output only contains intended accounts.
    if "model_version" in trades.columns:
        dist = trades.groupby("model_version").size()
        print("Rows by model after registry and EXCLUDE filter:")
        for model, n in dist.items():
            print(f"  {model}: {n}")
        print()

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
