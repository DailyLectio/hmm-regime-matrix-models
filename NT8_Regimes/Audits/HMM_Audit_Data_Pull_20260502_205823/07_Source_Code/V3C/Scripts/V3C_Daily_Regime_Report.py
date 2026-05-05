from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
V3C_DIR = BASE_DIR / "V3C"
REPORTS_DIR = V3C_DIR / "Reports"
HISTORY_DIR = V3C_DIR / "History"
SYMBOLS = ("ES", "NQ")


def previous_business_day(today: date | None = None) -> date:
    d = (today or date.today()) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def parse_report_date(value: str) -> date:
    if value == "today":
        return date.today()
    if value == "previous-business-day":
        return previous_business_day()
    return datetime.strptime(value, "%Y-%m-%d").date()


def read_latest_header(symbol: str) -> list[str]:
    latest = V3C_DIR / f"{symbol}_Regimes_V3C_Latest.csv"
    if latest.exists():
        with latest.open("r", newline="", encoding="utf-8") as f:
            row = next(csv.reader(f), [])
        if row:
            return row
    return []


def iter_history_rows(symbol: str) -> Iterable[dict[str, str]]:
    path = V3C_DIR / f"{symbol}_Regimes_V3C.csv"
    if not path.exists():
        return

    latest_header = read_latest_header(symbol)
    active_header: list[str] | None = None

    with path.open("r", newline="", encoding="utf-8") as f:
        for raw in csv.reader(f):
            if not raw:
                continue

            if raw[0] == "SnapshotTimestamp":
                active_header = raw
                continue

            header = active_header or latest_header
            if not header:
                continue

            if len(raw) != len(header) and latest_header and len(raw) == len(latest_header):
                header = latest_header

            row = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
            yield row


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def rows_for_day(symbol: str, report_day: date) -> list[dict[str, str]]:
    rows = []
    for row in iter_history_rows(symbol):
        ts = parse_timestamp(row.get("SnapshotTimestamp", ""))
        if ts and ts.date() == report_day:
            rows.append(row)
    rows.sort(key=lambda r: r.get("SnapshotTimestamp", ""))
    return rows


def count_changes(rows: list[dict[str, str]], key: str) -> int:
    changes = 0
    prior = None
    for row in rows:
        value = row.get(key, "")
        if prior is not None and value != prior:
            changes += 1
        prior = value
    return changes


def timeline(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    events = []
    prior_regime = None
    prior_reason = None
    for row in rows:
        regime = row.get("FinalRegime", "")
        reason = row.get("ReasonCode", "")
        if regime != prior_regime or reason != prior_reason:
            events.append(
                {
                    "time": row.get("SnapshotTimestamp", ""),
                    "macro_time": row.get("MacroTimestamp", ""),
                    "micro_time": row.get("MicroTimestamp", ""),
                    "final_regime": regime,
                    "macro_regime": row.get("MacroRegime", ""),
                    "reason": reason,
                    "stale": row.get("StaleDataFlag", ""),
                    "phase": row.get("Phase", ""),
                }
            )
        prior_regime = regime
        prior_reason = reason
    return events


def summarize_symbol(symbol: str, rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {"symbol": symbol, "rows": 0}

    latest = rows[-1]
    stale_rows = [r for r in rows if str(r.get("StaleDataFlag", "")).lower() == "true"]

    return {
        "symbol": symbol,
        "rows": len(rows),
        "first_snapshot": rows[0].get("SnapshotTimestamp", ""),
        "last_snapshot": latest.get("SnapshotTimestamp", ""),
        "latest_final_regime": latest.get("FinalRegime", ""),
        "latest_macro_regime": latest.get("MacroRegime", ""),
        "latest_reason": latest.get("ReasonCode", ""),
        "latest_stale_reason": latest.get("StaleReason", ""),
        "latest_stale_flag": latest.get("StaleDataFlag", ""),
        "final_regime_counts": Counter(r.get("FinalRegime", "UNKNOWN") for r in rows),
        "macro_regime_counts": Counter(r.get("MacroRegime", "UNKNOWN") for r in rows),
        "reason_counts": Counter(r.get("ReasonCode", "") for r in rows),
        "phase_counts": Counter(r.get("Phase", "UNKNOWN") for r in rows),
        "stale_count": len(stale_rows),
        "final_regime_changes": count_changes(rows, "FinalRegime"),
        "macro_regime_changes": count_changes(rows, "MacroRegime"),
        "reason_changes": count_changes(rows, "ReasonCode"),
        "timeline": timeline(rows),
    }


def write_text_report(report_day: date, summaries: list[dict]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"V3C_Regime_Report_{report_day:%Y%m%d}.txt"

    lines = [
        "V3C Daily Regime Report",
        f"Date: {report_day:%Y-%m-%d}",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
    ]

    for summary in summaries:
        lines.append("=" * 78)
        lines.append(f"{summary['symbol']} Summary")
        lines.append("=" * 78)
        if summary.get("rows", 0) == 0:
            lines.append("No V3C rows found for this date.")
            lines.append("")
            continue

        lines.extend(
            [
                f"Rows: {summary['rows']}",
                f"Window: {summary['first_snapshot']} -> {summary['last_snapshot']}",
                f"Latest FinalRegime: {summary['latest_final_regime']}",
                f"Latest MacroRegime: {summary['latest_macro_regime']}",
                f"Latest Reason: {summary['latest_reason']}",
                f"Latest Stale: {summary['latest_stale_flag']} / {summary['latest_stale_reason']}",
                f"Stale Rows: {summary['stale_count']}",
                f"FinalRegime Changes: {summary['final_regime_changes']}",
                f"MacroRegime Changes: {summary['macro_regime_changes']}",
                f"Reason Changes: {summary['reason_changes']}",
                "",
                "FinalRegime Counts:",
            ]
        )
        lines.extend(f"  {k}: {v}" for k, v in summary["final_regime_counts"].most_common())
        lines.append("")
        lines.append("MacroRegime Counts:")
        lines.extend(f"  {k}: {v}" for k, v in summary["macro_regime_counts"].most_common())
        lines.append("")
        lines.append("Top Reasons:")
        lines.extend(f"  {k or '(blank)'}: {v}" for k, v in summary["reason_counts"].most_common(10))
        lines.append("")
        lines.append("Change Timeline:")
        for event in summary["timeline"][-40:]:
            lines.append(
                "  "
                f"{event['time']} | Final={event['final_regime']} | Macro={event['macro_regime']} | "
                f"Reason={event['reason']} | Phase={event['phase']} | Stale={event['stale']}"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_json_report(report_day: date, summaries: list[dict]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"V3C_Regime_Report_{report_day:%Y%m%d}.json"
    normalized = []
    for summary in summaries:
        item = dict(summary)
        for key in ("final_regime_counts", "macro_regime_counts", "reason_counts", "phase_counts"):
            if key in item:
                item[key] = dict(item[key])
        normalized.append(item)
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return path


def archive_latest(report_day: date) -> list[Path]:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived = []
    for symbol in SYMBOLS:
        for suffix in ("Latest", "History"):
            source = (
                V3C_DIR / f"{symbol}_Regimes_V3C_Latest.csv"
                if suffix == "Latest"
                else V3C_DIR / f"{symbol}_Regimes_V3C.csv"
            )
            if not source.exists():
                continue
            target = HISTORY_DIR / f"{symbol}_Regimes_V3C_{suffix}_{report_day:%Y%m%d}_{stamp}.csv"
            shutil.copy2(source, target)
            archived.append(target)
    return archived


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate V3C daily regime reports and archives.")
    parser.add_argument("--date", default="today", help="today, previous-business-day, or YYYY-MM-DD")
    parser.add_argument("--archive-latest", action="store_true", help="Copy V3C latest/history files to V3C\\History.")
    args = parser.parse_args()

    report_day = parse_report_date(args.date)
    summaries = [summarize_symbol(symbol, rows_for_day(symbol, report_day)) for symbol in SYMBOLS]

    text_path = write_text_report(report_day, summaries)
    json_path = write_json_report(report_day, summaries)
    print(f"Report written: {text_path}")
    print(f"JSON written:   {json_path}")

    if args.archive_latest:
        archived = archive_latest(report_day)
        for path in archived:
            print(f"Archived:       {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
