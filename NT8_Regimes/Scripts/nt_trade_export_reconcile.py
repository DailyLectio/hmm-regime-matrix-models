"""
Build the daily AllModels trade log from a NinjaTrader trade export.

This is the source-of-truth path for post-session reconciliation. The NT trade
export provides the executed trades and P&L; the local registry and regime
matrices only enrich those rows.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, time
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
DEFAULT_TRADE_EXPORT = Path(r"C:\Users\Valued Customer\Downloads\tradeexport.csv")
DEFAULT_ACCOUNTS_EXPORT = Path(r"C:\Users\Valued Customer\Downloads\accounts.csv")
BAD_TEXT = {"", "NAN", "NONE", "NULL", "NA", "N/A", "UNAVAILABLE", "UNKNOWN", "UNMAPPED"}

UNIFIED_COLUMNS = [
    "trade_date",
    "entry_time",
    "exit_time",
    "model_version",
    "account",
    "strategy_name",
    "bot_name",
    "exported_strategy_name",
    "exported_bot_name",
    "registry_strategy_name",
    "registry_bot_name",
    "registry_tab_name",
    "registry_chart_location",
    "source_file",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild AllModels from an NT trade export.")
    parser.add_argument("--date", default="2026-05-07", help="Session date, YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--base-dir", default=str(BASE_DIR))
    parser.add_argument("--trade-export", default=str(DEFAULT_TRADE_EXPORT))
    parser.add_argument("--accounts-export", default=str(DEFAULT_ACCOUNTS_EXPORT))
    parser.add_argument("--replace-unified", action="store_true", help="Replace UNIFIED/AllModels_TradeLog_DATE.csv after backing it up.")
    parser.add_argument(
        "--allow-account-delta",
        action="store_true",
        help="Allow replacing AllModels even when the NT accounts export does not reconcile to the trade export.",
    )
    parser.add_argument("--regime-tolerance", default="2h")
    return parser.parse_args()


def parse_date(value: str) -> tuple[str, str]:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%Y%m%d")
        except ValueError:
            pass
    raise ValueError(f"Unsupported date: {value}")


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.upper() in BAD_TEXT else text


def clean_account_key(value: Any) -> str:
    text = clean_text(value)
    text = re.sub(r"\s+-\s*|\s*-\s+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_money(value: Any) -> float:
    text = str(value or "").strip().replace("$", "").replace(",", "").replace("\u2212", "-")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if not text:
        return 0.0
    amount = float(text)
    return -amount if negative else amount


def normalize_exit(value: Any) -> str:
    text = clean_text(value)
    upper = text.upper().replace(" ", "_")
    aliases = {
        "PROFIT_TARGET": "TARGET_HIT",
        "TARGET": "TARGET_HIT",
        "STOP_LOSS": "STOP_HIT",
        "SLOPEX": "SLOPE_EXIT",
        "SLOPE_EXIT": "SLOPE_EXIT",
        "ENVELOPEBREAKEXIT": "ENVELOPE_BREAK_EXIT",
        "ENVELOPE_BREAK_EXIT": "ENVELOPE_BREAK_EXIT",
    }
    return aliases.get(upper, upper or "UNKNOWN")


def phase_from_time(dt: pd.Timestamp) -> str:
    if pd.isna(dt):
        return ""
    t = dt.time()
    if t < time(9, 30):
        return "PREMARKET"
    if t < time(9, 45):
        return "OPENING_AUCTION"
    if t < time(10, 10):
        return "EARLY_TEST"
    if t < time(10, 30):
        return "END_FIRST_WINDOW"
    if t < time(11, 0):
        return "PRE_IB_MATURATION"
    if t < time(12, 0):
        return "MID_MORNING_DISCOVERY"
    if t < time(13, 0):
        return "LUNCH_AUCTION"
    if t < time(14, 0):
        return "POST_LUNCH_ROTATION"
    if t < time(15, 30):
        return "AFTERNOON_TREND_TEST"
    if t < time(16, 0):
        return "LATE_DAY_CONVICTION"
    return "CASH_CLOSE"


def load_registry(base_dir: Path) -> dict[str, dict[str, Any]]:
    path = base_dir / "accounts_registry.json"
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    normalized = {clean_account_key(k): v for k, v in registry.items()}
    registry.update(normalized)
    return registry


def registry_entry(registry: dict[str, dict[str, Any]], account: Any) -> dict[str, Any]:
    exact = clean_text(account)
    normalized = clean_account_key(account)
    if exact in registry:
        return registry[exact]
    if normalized in registry:
        return registry[normalized]
    # Last-ditch inference for accounts missing from the delivered registry.
    if exact.startswith("SimV3C"):
        return {"model": "V3C", "strategy": "UNKNOWN", "ab_mode": "N/A"}
    if exact.startswith("SimV3D"):
        return {"model": "V3D", "strategy": "UNKNOWN", "ab_mode": "N/A"}
    if exact.startswith("SimV1A"):
        return {"model": "V1B" if "Fader 3" in exact else "V1A", "strategy": "KalmanPulse_Fader", "ab_mode": "UNKNOWN"}
    if exact.startswith(("SimADX", "SimPine")):
        return {"model": "OG", "strategy": "UNKNOWN", "ab_mode": "N/A"}
    return {"model": "UNKNOWN", "strategy": "UNKNOWN", "ab_mode": "UNKNOWN"}


def load_regime_history(base_dir: Path, model: str, symbol: str) -> pd.DataFrame:
    symbol = symbol or "NQ"
    if model == "V3D":
        path = base_dir / "V3D" / "History" / f"{symbol}_RegimeMatrix_History.csv"
        ts_col = "TimestampET"
        hmm_col = "HMMRegime"
    else:
        path = base_dir / "V3C" / f"{symbol}_Regimes_V3C.csv"
        ts_col = "SnapshotTimestamp"
        hmm_col = "HMM_Micro"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    if ts_col not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["regime_ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df[df["regime_ts"].notna()]
    for col in ("FinalRegime", "Phase", "MacroRegime", hmm_col, "RegimeConfidence", "ReasonCode"):
        if col not in df.columns:
            df[col] = ""
    df["entry_hmm_join"] = df[hmm_col].fillna("").astype(str)
    return df[["regime_ts", "FinalRegime", "Phase", "MacroRegime", "entry_hmm_join", "RegimeConfidence", "ReasonCode"]].sort_values("regime_ts")


def enrich_with_regimes(base_dir: Path, df: pd.DataFrame, tolerance: str) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for (model, symbol), group in df.groupby(["model_version", "symbol"], dropna=False):
        g = group.sort_values("entry_dt").copy()
        reg = load_regime_history(base_dir, str(model), str(symbol))
        if reg.empty:
            for col in ("entry_regime", "entry_macro", "entry_hmm", "entry_confidence", "entry_reason_code"):
                g[col] = ""
            g["entry_phase"] = g["entry_dt"].map(phase_from_time)
            g["regime_join_lag_min"] = ""
            g["regime_source"] = "TIME_BUCKET_ONLY"
            parts.append(g)
            continue
        merged = pd.merge_asof(
            g,
            reg,
            left_on="entry_dt",
            right_on="regime_ts",
            direction="backward",
            tolerance=pd.Timedelta(tolerance),
        )
        matched = merged["regime_ts"].notna()
        merged["entry_regime"] = merged["FinalRegime"].fillna("").str.upper()
        merged["entry_macro"] = merged["MacroRegime"].fillna("")
        merged["entry_hmm"] = merged["entry_hmm_join"].fillna("")
        merged["entry_phase"] = merged["Phase"].fillna("").str.upper()
        missing_phase = merged["entry_phase"].eq("")
        merged.loc[missing_phase, "entry_phase"] = merged.loc[missing_phase, "entry_dt"].map(phase_from_time)
        merged["entry_confidence"] = merged["RegimeConfidence"].fillna("")
        merged["entry_reason_code"] = merged["ReasonCode"].fillna("")
        merged["regime_join_lag_min"] = ((merged["entry_dt"] - merged["regime_ts"]).dt.total_seconds() / 60).round(2)
        merged["regime_source"] = "TIME_BUCKET_ONLY"
        source_name = "V3D_MATRIX_JOIN" if str(model) == "V3D" else "V3C_MATRIX_JOIN"
        merged.loc[matched, "regime_source"] = source_name
        parts.append(merged)
    return pd.concat(parts, ignore_index=True, sort=False)


def normalize_nt_trade_export(base_dir: Path, trade_export: Path, session_date: str, registry: dict[str, dict[str, Any]], tolerance: str) -> pd.DataFrame:
    raw = pd.read_csv(trade_export, dtype=str, encoding="utf-8-sig")
    raw = raw.loc[:, ~raw.columns.str.startswith("Unnamed")]
    raw["entry_dt"] = pd.to_datetime(raw["Entry time"], errors="coerce")
    raw["exit_dt"] = pd.to_datetime(raw["Exit time"], errors="coerce")
    raw = raw[raw["entry_dt"].dt.strftime("%Y-%m-%d") == session_date].copy()
    raw["profit_num"] = raw["Profit"].map(parse_money)
    raw["commission_num"] = raw.get("Commission", "0").map(parse_money)

    rows = []
    for _, row in raw.iterrows():
        account = clean_text(row.get("Account"))
        reg = registry_entry(registry, account)
        model = clean_text(reg.get("model", "UNKNOWN")).upper()
        strategy = clean_text(reg.get("strategy", "")) or clean_text(row.get("Strategy")) or "UNKNOWN"
        direction = clean_text(row.get("Market pos.")).upper()
        qty = pd.to_numeric(row.get("Qty"), errors="coerce")
        qty = 1 if pd.isna(qty) else int(qty)
        entry_price = pd.to_numeric(row.get("Entry price"), errors="coerce")
        exit_price = pd.to_numeric(row.get("Exit price"), errors="coerce")
        symbol = clean_text(row.get("Instrument")).upper()
        symbol = "NQ" if "NQ" in symbol else "ES" if "ES" in symbol else symbol
        tick_value = 5.0 if symbol == "NQ" else 12.5 if symbol == "ES" else 1.0
        ticks = row["profit_num"] / tick_value if tick_value else 0.0
        win_loss = "WIN" if row["profit_num"] > 0 else "LOSS" if row["profit_num"] < 0 else "SCRATCH"
        flags = ["NT_TRADE_EXPORT_SOURCE"]
        if clean_text(row.get("Strategy")) == "":
            flags.append("NT_STRATEGY_BLANK")
        if account not in registry and clean_account_key(account) not in registry:
            flags.append("REGISTRY_INFERRED")
        rows.append(
            {
                "trade_date": session_date,
                "entry_time": row["entry_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                "exit_time": row["exit_dt"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["exit_dt"]) else "",
                "entry_dt": row["entry_dt"],
                "model_version": model,
                "account": account,
                "strategy_name": strategy,
                "bot_name": clean_text(reg.get("bot_name", "")) or clean_text(reg.get("tab_name", "")) or strategy,
                "exported_strategy_name": clean_text(row.get("Strategy")),
                "exported_bot_name": clean_text(row.get("Entry name")),
                "registry_strategy_name": clean_text(reg.get("strategy", "")),
                "registry_bot_name": clean_text(reg.get("bot_name", "")),
                "registry_tab_name": clean_text(reg.get("tab_name", "")),
                "registry_chart_location": clean_text(reg.get("chart_location", "")),
                "source_file": str(trade_export),
                "ab_mode": clean_text(reg.get("ab_mode", "")),
                "symbol": symbol,
                "instrument": clean_text(row.get("Instrument")),
                "direction": "LONG" if direction == "LONG" else "SHORT" if direction == "SHORT" else direction,
                "contracts": qty,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_pnl": row["profit_num"],
                # NinjaTrader's Trade Performance export reports Profit net of
                # commission when the Commission column is populated. Keep the
                # exported Profit as source-of-truth P&L and do not subtract it
                # a second time.
                "net_pnl": row["profit_num"],
                "ticks": round(ticks, 2),
                "win_loss": win_loss,
                "exit_reason": normalize_exit(row.get("Exit name")),
                "initial_stop_price": "",
                "initial_stop_distance": "",
                "broad_agree": "",
                "v3c_regime_at_entry": "",
                "trade_duration_min": round((row["exit_dt"] - row["entry_dt"]).total_seconds() / 60, 2) if pd.notna(row["exit_dt"]) else "",
                "r_multiple": "",
                "risk_reward_actual": "",
                "session_trade_rank": row.get("Trade number", ""),
                "daily_pnl_running": parse_money(row.get("Cum. net profit")),
                "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_quality_flag": ";".join(flags),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)
    df = enrich_with_regimes(base_dir, df, tolerance)
    df["data_quality_flag"] = df["data_quality_flag"] + ";" + df["regime_source"].fillna("")
    missing_regime = df["entry_regime"].fillna("").eq("")
    df.loc[missing_regime, "data_quality_flag"] = df.loc[missing_regime, "data_quality_flag"] + ";NO_REGIME_MATCH"
    df["v3c_regime_at_entry"] = df["entry_regime"].where(df["model_version"] != "V3D", "")
    df = df.sort_values(["entry_dt", "session_trade_rank"], kind="stable")
    for col in UNIFIED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[UNIFIED_COLUMNS]


def write_reconciliation(unified: pd.DataFrame, accounts_export: Path, out_path: Path) -> pd.DataFrame:
    trade_sum = unified.groupby("account", dropna=False)["net_pnl"].sum().rename("trade_export_net_pnl")
    if accounts_export.exists():
        accounts = pd.read_csv(accounts_export, dtype=str, encoding="utf-8-sig")
        accounts["accounts_realized_pnl"] = accounts["Realized PnL"].map(parse_money)
        acct_sum = accounts.groupby("Display name", dropna=False)["accounts_realized_pnl"].sum()
    else:
        acct_sum = pd.Series(dtype=float, name="accounts_realized_pnl")
    recon = pd.concat([trade_sum, acct_sum], axis=1).fillna(0.0)
    recon["delta_trade_minus_accounts"] = recon["trade_export_net_pnl"] - recon["accounts_realized_pnl"]
    recon = recon.reset_index(names="account").sort_values("delta_trade_minus_accounts")
    recon.to_csv(out_path, index=False, encoding="utf-8-sig")
    return recon


def write_account_truth_summary(
    accounts_export: Path,
    registry: dict[str, dict[str, Any]],
    out_path: Path,
) -> pd.DataFrame:
    if not accounts_export.exists():
        summary = pd.DataFrame(columns=["model_version", "account_count", "accounts_realized_pnl"])
        summary.to_csv(out_path, index=False, encoding="utf-8-sig")
        return summary
    accounts = pd.read_csv(accounts_export, dtype=str, encoding="utf-8-sig")
    accounts["accounts_realized_pnl"] = accounts["Realized PnL"].map(parse_money)
    accounts["model_version"] = accounts["Display name"].map(
        lambda account: clean_text(registry_entry(registry, account).get("model", "UNKNOWN")).upper()
    )
    accounts = accounts[accounts["accounts_realized_pnl"].abs() > 0.01].copy()
    detail = accounts[["model_version", "Display name", "accounts_realized_pnl", "Filled Buys", "Filled Sells"]]
    detail_path = out_path.with_name(out_path.stem.replace("ModelSummary", "AccountDetail") + out_path.suffix)
    detail.rename(columns={"Display name": "account"}).to_csv(detail_path, index=False, encoding="utf-8-sig")
    summary = (
        accounts.groupby("model_version", dropna=False)["accounts_realized_pnl"]
        .agg(account_count="count", accounts_realized_pnl="sum")
        .reset_index()
        .sort_values("model_version")
    )
    summary.to_csv(out_path, index=False, encoding="utf-8-sig")
    return summary


def v3d_strategy_log_accounts(base_dir: Path, session_date: str) -> set[str]:
    trade_dir = base_dir / "V3D" / "TradeLog"
    accounts: set[str] = set()
    if not trade_dir.exists():
        return accounts
    paths = list(trade_dir.glob("SimV3D*_TradeLog.csv")) + [
        trade_dir / "V3D_INTERNAL_TradeLog.csv",
    ]
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        except Exception:
            continue
        if "trade_date" not in df.columns or "account" not in df.columns:
            continue
        hits = df[df["trade_date"].astype(str).str[:10].eq(session_date)]
        accounts.update(clean_text(account) for account in hits["account"] if clean_text(account))
    return accounts


def model_strategy_log_summary(base_dir: Path, model: str, session_date: str) -> pd.DataFrame:
    trade_dir = base_dir / model / "TradeLog"
    rows = []
    if not trade_dir.exists():
        return pd.DataFrame(columns=["account", "strategy_log_rows", "strategy_log_unique_rows", "strategy_log_net_pnl"])
    for path in trade_dir.glob("*.csv"):
        if model == "V3D" and path.name == "V3D_TradeLog.csv":
            # Legacy V3D chart exporter is known-contaminated and is not a clean
            # strategy-owned source for coverage checks.
            continue
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        except Exception:
            continue
        if "trade_date" not in df.columns or "account" not in df.columns:
            continue
        day = df[df["trade_date"].astype(str).str[:10].eq(session_date)].copy()
        if day.empty:
            continue
        day["account"] = day["account"].map(clean_text)
        day = day[day["account"] != ""].copy()
        if day.empty:
            continue
        day["net_pnl_num"] = pd.to_numeric(day.get("net_pnl", 0), errors="coerce").fillna(0.0)
        dedupe_cols = [
            col for col in ["entry_time", "exit_time", "account", "entry_price", "exit_price", "net_pnl"]
            if col in day.columns
        ]
        unique = day.drop_duplicates(subset=dedupe_cols) if dedupe_cols else day
        for account, group in day.groupby("account", dropna=False):
            unique_group = unique[unique["account"].eq(account)]
            rows.append(
                {
                    "account": account,
                    "strategy_log_rows": len(group),
                    "strategy_log_unique_rows": len(unique_group),
                    "strategy_log_net_pnl": pd.to_numeric(unique_group["net_pnl_num"], errors="coerce").fillna(0.0).sum(),
                    "strategy_log_files": ";".join(sorted(set(Path(x).name for x in [path]))),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["account", "strategy_log_rows", "strategy_log_unique_rows", "strategy_log_net_pnl"])
    out = pd.DataFrame(rows)
    return (
        out.groupby("account", dropna=False)
        .agg(
            strategy_log_rows=("strategy_log_rows", "sum"),
            strategy_log_unique_rows=("strategy_log_unique_rows", "sum"),
            strategy_log_net_pnl=("strategy_log_net_pnl", "sum"),
            strategy_log_files=("strategy_log_files", lambda s: ";".join(sorted(set(";".join(s).split(";"))))),
        )
        .reset_index()
    )


def write_model_coverage_report(
    base_dir: Path,
    unified: pd.DataFrame,
    accounts_export: Path,
    registry: dict[str, dict[str, Any]],
    session_date: str,
    model: str,
    out_path: Path,
) -> pd.DataFrame:
    model = model.upper()
    account_rows = []
    if accounts_export.exists():
        accounts = pd.read_csv(accounts_export, dtype=str, encoding="utf-8-sig")
        accounts["accounts_realized_pnl"] = accounts["Realized PnL"].map(parse_money)
        accounts["model_version"] = accounts["Display name"].map(
            lambda account: clean_text(registry_entry(registry, account).get("model", "UNKNOWN")).upper()
        )
        account_rows = [
            (clean_text(row["Display name"]), row["accounts_realized_pnl"])
            for _, row in accounts.iterrows()
            if row["model_version"] == model and abs(row["accounts_realized_pnl"]) > 0.01
        ]

    nt_model = unified[unified["model_version"].astype(str).str.upper().eq(model)].copy()
    nt_summary = (
        nt_model.groupby("account", dropna=False)["net_pnl"]
        .agg(nt_trade_export_rows="count", nt_trade_export_net_pnl="sum")
        .reset_index()
    )
    strategy_summary = model_strategy_log_summary(base_dir, model, session_date)
    account_pnl = dict(account_rows)
    all_accounts = sorted(
        set(account_pnl)
        | set(nt_summary["account"].map(clean_text) if not nt_summary.empty else [])
        | set(strategy_summary["account"].map(clean_text) if not strategy_summary.empty else [])
    )
    nt_by_account = nt_summary.set_index("account").to_dict("index") if not nt_summary.empty else {}
    strategy_by_account = strategy_summary.set_index("account").to_dict("index") if not strategy_summary.empty else {}
    rows = []
    for account in all_accounts:
        nt = nt_by_account.get(account, {})
        strat = strategy_by_account.get(account, {})
        nt_rows = int(nt.get("nt_trade_export_rows", 0))
        strat_unique = int(strat.get("strategy_log_unique_rows", 0))
        issue = "OK"
        if account in account_pnl and nt_rows == 0:
            issue = "MISSING_FROM_NT_TRADE_EXPORT"
        elif nt_rows > 0 and strat_unique == 0:
            issue = f"MISSING_FROM_{model}_STRATEGY_LOG"
        elif nt_rows != strat_unique:
            issue = "ROW_COUNT_MISMATCH"
        elif abs(float(nt.get("nt_trade_export_net_pnl", 0.0)) - float(strat.get("strategy_log_net_pnl", 0.0))) > 0.01:
            issue = "PNL_MISMATCH"
        rows.append(
            {
                "account": account,
                "accounts_realized_pnl": account_pnl.get(account, 0.0),
                "nt_trade_export_rows": nt_rows,
                "nt_trade_export_net_pnl": float(nt.get("nt_trade_export_net_pnl", 0.0)),
                "strategy_log_rows": int(strat.get("strategy_log_rows", 0)),
                "strategy_log_unique_rows": strat_unique,
                "strategy_log_net_pnl": float(strat.get("strategy_log_net_pnl", 0.0)),
                "strategy_log_files": strat.get("strategy_log_files", ""),
                "coverage_issue": issue,
            }
        )
    report = pd.DataFrame(rows)
    report.to_csv(out_path, index=False, encoding="utf-8-sig")
    return report


def write_v3d_coverage_report(
    base_dir: Path,
    unified: pd.DataFrame,
    accounts_export: Path,
    registry: dict[str, dict[str, Any]],
    session_date: str,
    out_path: Path,
) -> pd.DataFrame:
    account_rows = []
    if accounts_export.exists():
        accounts = pd.read_csv(accounts_export, dtype=str, encoding="utf-8-sig")
        accounts["accounts_realized_pnl"] = accounts["Realized PnL"].map(parse_money)
        accounts["model_version"] = accounts["Display name"].map(
            lambda account: clean_text(registry_entry(registry, account).get("model", "UNKNOWN")).upper()
        )
        account_rows = [
            (clean_text(row["Display name"]), row["accounts_realized_pnl"])
            for _, row in accounts.iterrows()
            if row["model_version"] == "V3D" and abs(row["accounts_realized_pnl"]) > 0.01
        ]

    nt_v3d = unified[unified["model_version"].astype(str).str.upper().eq("V3D")]
    nt_accounts = set(nt_v3d["account"].map(clean_text))
    strategy_accounts = v3d_strategy_log_accounts(base_dir, session_date)
    all_accounts = sorted({account for account, _ in account_rows} | nt_accounts | strategy_accounts)
    account_pnl = dict(account_rows)
    rows = []
    for account in all_accounts:
        in_accounts = account in account_pnl
        in_nt = account in nt_accounts
        in_strategy = account in strategy_accounts
        issue = "OK"
        if in_accounts and not in_nt:
            issue = "MISSING_FROM_NT_TRADE_EXPORT"
        elif in_nt and not in_strategy:
            issue = "MISSING_FROM_V3D_STRATEGY_LOG"
        elif in_accounts and not in_strategy:
            issue = "MISSING_FROM_V3D_STRATEGY_LOG"
        rows.append(
            {
                "account": account,
                "accounts_realized_pnl": account_pnl.get(account, 0.0),
                "nt_trade_export_rows": int((nt_v3d["account"].map(clean_text) == account).sum()),
                "present_in_accounts": in_accounts,
                "present_in_nt_trade_export": in_nt,
                "present_in_v3d_strategy_logs": in_strategy,
                "coverage_issue": issue,
            }
        )
    report = pd.DataFrame(rows)
    report.to_csv(out_path, index=False, encoding="utf-8-sig")
    return report


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_dir)
    trade_export = Path(args.trade_export)
    accounts_export = Path(args.accounts_export)
    session_date, stamp = parse_date(args.date)
    registry = load_registry(base_dir)
    unified = normalize_nt_trade_export(base_dir, trade_export, session_date, registry, args.regime_tolerance)

    unified_dir = base_dir / "UNIFIED"
    unified_dir.mkdir(exist_ok=True)
    corrected_path = unified_dir / f"AllModels_TradeLog_{stamp}_NT_VERIFIED.csv"
    unified.to_csv(corrected_path, index=False, encoding="utf-8-sig")

    target_path = unified_dir / f"AllModels_TradeLog_{stamp}.csv"
    recon_path = unified_dir / f"NT_TradeExport_Reconciliation_{stamp}.csv"
    recon = write_reconciliation(unified, accounts_export, recon_path)
    deltas = recon[recon["delta_trade_minus_accounts"].abs() > 0.01]

    if args.replace_unified:
        if not deltas.empty and not args.allow_account_delta:
            print(
                "Refusing to replace AllModels because tradeexport.csv does not "
                "reconcile to accounts.csv. Review the reconciliation file or rerun "
                "with --allow-account-delta to replace intentionally."
            )
        else:
            if target_path.exists():
                backup = unified_dir / "Archive" / f"AllModels_TradeLog_{stamp}_pre_nt_verified_{datetime.now():%Y%m%d_%H%M%S}.csv"
                backup.parent.mkdir(exist_ok=True)
                shutil.copy2(target_path, backup)
            shutil.copy2(corrected_path, target_path)

    summary = unified.groupby("model_version", dropna=False)["net_pnl"].agg(["count", "sum"]).reset_index()
    summary_path = unified_dir / f"NT_TradeExport_ModelSummary_{stamp}.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    account_truth_path = unified_dir / f"NT_Accounts_ModelSummary_{stamp}.csv"
    account_truth = write_account_truth_summary(accounts_export, registry, account_truth_path)
    v3d_coverage_path = unified_dir / f"V3D_Coverage_Reconciliation_{stamp}.csv"
    v3d_coverage = write_v3d_coverage_report(
        base_dir, unified, accounts_export, registry, session_date, v3d_coverage_path
    )
    v3c_coverage_path = unified_dir / f"V3C_Coverage_Reconciliation_{stamp}.csv"
    v3c_coverage = write_model_coverage_report(
        base_dir, unified, accounts_export, registry, session_date, "V3C", v3c_coverage_path
    )

    print(f"wrote={corrected_path}")
    if args.replace_unified:
        if deltas.empty or args.allow_account_delta:
            print(f"replaced={target_path}")
    print(f"reconciliation={recon_path}")
    print(f"summary={summary_path}")
    print(f"account_truth_summary={account_truth_path}")
    print(f"v3c_coverage={v3c_coverage_path}")
    print(f"v3d_coverage={v3d_coverage_path}")
    print(f"rows={len(unified)} net_pnl={unified['net_pnl'].sum():.2f}")
    print(summary.to_string(index=False))
    print("account_truth:")
    print(account_truth.to_string(index=False))
    if not deltas.empty:
        print("account_deltas:")
        print(deltas.to_string(index=False))
    v3d_issues = v3d_coverage[v3d_coverage["coverage_issue"] != "OK"]
    v3c_issues = v3c_coverage[v3c_coverage["coverage_issue"] != "OK"]
    if not v3c_issues.empty:
        print("v3c_coverage_issues:")
        print(v3c_issues.to_string(index=False))
    if not v3d_issues.empty:
        print("v3d_coverage_issues:")
        print(v3d_issues.to_string(index=False))


if __name__ == "__main__":
    main()
