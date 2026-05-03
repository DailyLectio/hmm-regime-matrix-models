"""
Generate daily and end-of-week markdown performance reports from unified trade logs.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
UNIFIED_DIR = BASE_DIR / "UNIFIED"
REPORT_DIR = UNIFIED_DIR / "Reports"


def parse_date_token(value: str) -> date:
    token = value.strip().lower()
    today = date.today()
    if token == "today":
        return today
    if token == "yesterday":
        return today - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unsupported date value: {value}")


def default_week_ending() -> date:
    today = date.today()
    days_since_friday = (today.weekday() - 4) % 7
    return today - timedelta(days=days_since_friday)


def parse_week_ending(value: str) -> date:
    token = value.strip().lower()
    if token in ("auto", "today"):
        return default_week_ending()
    return parse_date_token(value)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_daily(base_dir: Path, report_date: date) -> tuple[pd.DataFrame, list[Path]]:
    stamp = report_date.strftime("%Y%m%d")
    daily_path = base_dir / "UNIFIED" / f"AllModels_TradeLog_{stamp}.csv"
    df = read_csv(daily_path)
    sources = [daily_path]
    if df.empty:
        all_path = base_dir / "UNIFIED" / "AllModels_TradeLog_ALL.csv"
        df = read_csv(all_path)
        sources = [all_path]
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
            df = df[df["trade_date"] == report_date].copy()
    return normalize(df), sources


def load_week(base_dir: Path, week_ending: date) -> tuple[pd.DataFrame, list[Path], date]:
    week_start = week_ending - timedelta(days=4)
    all_path = base_dir / "UNIFIED" / "AllModels_TradeLog_ALL.csv"
    df = read_csv(all_path)
    sources = [all_path]

    if df.empty:
        frames: list[pd.DataFrame] = []
        sources = []
        for offset in range(5):
            day = week_start + timedelta(days=offset)
            path = base_dir / "UNIFIED" / f"AllModels_TradeLog_{day:%Y%m%d}.csv"
            day_df = read_csv(path)
            if not day_df.empty:
                frames.append(day_df)
                sources.append(path)
        df = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()

    df = normalize(df)
    if not df.empty:
        df = df[(df["trade_date"] >= week_start) & (df["trade_date"] <= week_ending)].copy()
    return df, sources, week_start


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df.get("trade_date"), errors="coerce").dt.date
    for col in ("entry_time", "exit_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ("net_pnl", "gross_pnl", "ticks", "contracts", "r_multiple", "initial_stop_distance"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("model_version", "strategy_name", "bot_name", "exit_reason", "entry_regime", "data_quality_flag"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)
    return df


def fmt_money(value: float) -> str:
    if pd.isna(value):
        value = 0.0
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def fmt_num(value: float, digits: int = 2) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}"


def win_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float((pd.to_numeric(series, errors="coerce").fillna(0) > 0).mean() * 100)


def summary_table(df: pd.DataFrame, group_cols: list[str], limit: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    rows = []
    grouped = df.groupby(group_cols, dropna=False)
    for key, group in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        net = group["net_pnl"].sum()
        r_avg = group["r_multiple"].dropna().mean() if "r_multiple" in group.columns else pd.NA
        rows.append({
            **{group_cols[i]: key[i] for i in range(len(group_cols))},
            "trades": len(group),
            "win_rate": win_rate(group["net_pnl"]),
            "net_pnl": net,
            "avg_r": r_avg,
        })
    out = pd.DataFrame(rows).sort_values(["net_pnl", "trades"], ascending=[False, False]).head(limit)
    headers = group_cols + ["trades", "win_rate", "net_pnl", "avg_r"]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join([":--"] * len(headers)) + " |"]
    for _, row in out.iterrows():
        values = [str(row[c]) for c in group_cols]
        values.extend([
            str(int(row["trades"])),
            f"{row['win_rate']:.1f}%",
            fmt_money(row["net_pnl"]),
            fmt_num(row["avg_r"]),
        ])
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def headline(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["- Trades: 0"]
    risk_rows = int(df["initial_stop_distance"].notna().sum()) if "initial_stop_distance" in df.columns else 0
    r_rows = int(df["r_multiple"].notna().sum()) if "r_multiple" in df.columns else 0
    avg_r = df["r_multiple"].dropna().mean() if "r_multiple" in df.columns else pd.NA
    return [
        f"- Trades: {len(df):,}",
        f"- Win rate: {win_rate(df['net_pnl']):.1f}%",
        f"- Net P&L: {fmt_money(df['net_pnl'].sum())}",
        f"- Average ticks: {fmt_num(df['ticks'].mean()) if 'ticks' in df.columns else 'n/a'}",
        f"- Average R: {fmt_num(avg_r)}",
        f"- R-ready rows: {r_rows:,} of {len(df):,}",
        f"- Initial-stop rows: {risk_rows:,} of {len(df):,}",
    ]


def data_quality(df: pd.DataFrame) -> str:
    if df.empty or "data_quality_flag" not in df.columns:
        return "_No data quality rows._"
    counts = df["data_quality_flag"].replace("", "UNKNOWN").value_counts(dropna=False)
    return "\n".join(f"- {flag}: {count}" for flag, count in counts.items())


def source_lines(paths: list[Path]) -> str:
    return "\n".join(f"- `{path}`" for path in paths)


def write_daily(base_dir: Path, report_date: date) -> Path:
    df, sources = load_daily(base_dir, report_date)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"Daily_Trade_Performance_{report_date:%Y%m%d}.md"
    lines = [
        f"# Daily Trade Performance - {report_date:%Y-%m-%d}",
        "",
        "## Headline",
        *headline(df),
        "",
        "## By Model",
        summary_table(df, ["model_version"]),
        "",
        "## By Strategy / Bot",
        summary_table(df, ["model_version", "strategy_name", "bot_name"]),
        "",
        "## By Exit Reason",
        summary_table(df, ["exit_reason"]),
        "",
        "## By Entry Regime",
        summary_table(df, ["entry_regime"]),
        "",
        "## Data Quality",
        data_quality(df),
        "",
        "## Source Files",
        source_lines(sources),
        "",
        "## Performance Review Inputs",
        f"- Unified CSV: `{base_dir / 'UNIFIED' / f'AllModels_TradeLog_{report_date:%Y%m%d}.csv'}`",
        f"- Data quality report: `{base_dir / 'UNIFIED' / f'DataQuality_Report_{report_date:%Y%m%d}.txt'}`",
        f"- Daily markdown: `{path}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_weekly(base_dir: Path, week_ending: date) -> Path:
    df, sources, week_start = load_week(base_dir, week_ending)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"EOW_Trade_Performance_{week_ending:%Y%m%d}.md"
    lines = [
        f"# End-of-Week Trade Performance - Week Ending {week_ending:%Y-%m-%d}",
        "",
        f"Week window: {week_start:%Y-%m-%d} through {week_ending:%Y-%m-%d}",
        "",
        "## Weekly Headline",
        *headline(df),
        "",
        "## By Model",
        summary_table(df, ["model_version"]),
        "",
        "## By Strategy / Bot",
        summary_table(df, ["model_version", "strategy_name", "bot_name"]),
        "",
        "## By Day",
        summary_table(df, ["trade_date"]),
        "",
        "## By Exit Reason",
        summary_table(df, ["exit_reason"]),
        "",
        "## By Entry Regime",
        summary_table(df, ["entry_regime"]),
        "",
        "## Data Quality",
        data_quality(df),
        "",
        "## Source Files",
        source_lines(sources),
        "",
        "## Performance Review Inputs",
        f"- Unified all-history CSV: `{base_dir / 'UNIFIED' / 'AllModels_TradeLog_ALL.csv'}`",
        f"- Weekly markdown: `{path}`",
        f"- Model histories: `{base_dir}\\<MODEL>\\History\\<MODEL>_TradeLog_<stamp>.csv`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily or weekly trade performance markdown.")
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--date", default="today", help="Daily report date.")
    parser.add_argument("--week-ending", default="auto", help="Weekly report ending date, default is latest Friday.")
    parser.add_argument("--base-dir", default=str(BASE_DIR))
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if args.mode == "daily":
        out = write_daily(base_dir, parse_date_token(args.date))
    else:
        out = write_weekly(base_dir, parse_week_ending(args.week_ending))
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
