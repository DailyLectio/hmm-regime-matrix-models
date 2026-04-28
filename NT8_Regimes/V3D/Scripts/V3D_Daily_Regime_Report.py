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
V3D_DIR = BASE_DIR / "V3D"
REPORTS_DIR = V3D_DIR / "Reports"
HISTORY_DIR = V3D_DIR / "History"
ARCHIVE_DIR = HISTORY_DIR / "Archives"
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


def iter_history_rows(symbol: str) -> Iterable[dict[str, str]]:
    path = HISTORY_DIR / f"{symbol}_RegimeMatrix_History.csv"
    if not path.exists():
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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
        ts = parse_timestamp(row.get("TimestampET", ""))
        if ts and ts.date() == report_day:
            rows.append(row)
    rows.sort(key=lambda r: r.get("TimestampET", ""))
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
                    "time": row.get("TimestampET", ""),
                    "final_regime": regime,
                    "macro_regime": row.get("MacroRegime", ""),
                    "hmm_regime": row.get("HMMRegime", ""),
                    "reason": reason,
                    "phase": row.get("Phase", ""),
                    "confidence": row.get("RegimeConfidence", ""),
                    "stale": row.get("StaleDataFlag", ""),
                }
            )
        prior_regime = regime
        prior_reason = reason
    return events


def summarize_symbol(symbol: str, rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {"symbol": symbol, "rows": 0}

    latest = rows[-1]
    stale_rows = [r for r in rows if str(r.get("StaleDataFlag", "")).lower() in {"true", "1"}]

    bot_keys = ("AllowExpansion", "AllowMomo", "AllowPine", "AllowADX_DI", "AllowSniper")
    bot_counts = {
        key: sum(1 for r in rows if str(r.get(key, "")).strip() in {"1", "true", "True"})
        for key in bot_keys
    }

    return {
        "symbol": symbol,
        "rows": len(rows),
        "first_snapshot": rows[0].get("TimestampET", ""),
        "last_snapshot": latest.get("TimestampET", ""),
        "latest_final_regime": latest.get("FinalRegime", ""),
        "latest_macro_regime": latest.get("MacroRegime", ""),
        "latest_hmm_regime": latest.get("HMMRegime", ""),
        "latest_reason": latest.get("ReasonCode", ""),
        "latest_phase": latest.get("Phase", ""),
        "latest_confidence": latest.get("RegimeConfidence", ""),
        "latest_stale_flag": latest.get("StaleDataFlag", ""),
        "final_regime_counts": Counter(r.get("FinalRegime", "UNKNOWN") for r in rows),
        "macro_regime_counts": Counter(r.get("MacroRegime", "UNKNOWN") for r in rows),
        "hmm_regime_counts": Counter(r.get("HMMRegime", "UNKNOWN") for r in rows),
        "reason_counts": Counter(r.get("ReasonCode", "") for r in rows),
        "phase_counts": Counter(r.get("Phase", "UNKNOWN") for r in rows),
        "stale_count": len(stale_rows),
        "final_regime_changes": count_changes(rows, "FinalRegime"),
        "macro_regime_changes": count_changes(rows, "MacroRegime"),
        "hmm_regime_changes": count_changes(rows, "HMMRegime"),
        "reason_changes": count_changes(rows, "ReasonCode"),
        "bot_allowed_counts": bot_counts,
        "timeline": timeline(rows),
    }


def write_text_report(report_day: date, summaries: list[dict]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"V3D_Regime_Report_{report_day:%Y%m%d}.txt"

    lines = [
        "V3D Daily Regime Report",
        f"Date: {report_day:%Y-%m-%d}",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
    ]

    for summary in summaries:
        lines.append("=" * 78)
        lines.append(f"{summary['symbol']} Summary")
        lines.append("=" * 78)
        if summary.get("rows", 0) == 0:
            lines.append("No V3D rows found for this date.")
            lines.append("")
            continue

        lines.extend(
            [
                f"Rows: {summary['rows']}",
                f"Window: {summary['first_snapshot']} -> {summary['last_snapshot']}",
                f"Latest FinalRegime: {summary['latest_final_regime']}",
                f"Latest MacroRegime: {summary['latest_macro_regime']}",
                f"Latest HMMRegime: {summary['latest_hmm_regime']}",
                f"Latest Reason: {summary['latest_reason']}",
                f"Latest Phase: {summary['latest_phase']}",
                f"Latest Confidence: {summary['latest_confidence']}",
                f"Latest Stale Flag: {summary['latest_stale_flag']}",
                f"Stale Rows: {summary['stale_count']}",
                f"FinalRegime Changes: {summary['final_regime_changes']}",
                f"MacroRegime Changes: {summary['macro_regime_changes']}",
                f"HMMRegime Changes: {summary['hmm_regime_changes']}",
                f"Reason Changes: {summary['reason_changes']}",
                "",
                "Bot Allowed Counts:",
            ]
        )
        lines.extend(f"  {k}: {v}" for k, v in summary["bot_allowed_counts"].items())
        lines.append("")
        lines.append("FinalRegime Counts:")
        lines.extend(f"  {k}: {v}" for k, v in summary["final_regime_counts"].most_common())
        lines.append("")
        lines.append("MacroRegime Counts:")
        lines.extend(f"  {k}: {v}" for k, v in summary["macro_regime_counts"].most_common())
        lines.append("")
        lines.append("HMMRegime Counts:")
        lines.extend(f"  {k}: {v}" for k, v in summary["hmm_regime_counts"].most_common())
        lines.append("")
        lines.append("Top Reasons:")
        lines.extend(f"  {k or '(blank)'}: {v}" for k, v in summary["reason_counts"].most_common(10))
        lines.append("")
        lines.append("Change Timeline:")
        for event in summary["timeline"][-40:]:
            lines.append(
                "  "
                f"{event['time']} | Final={event['final_regime']} | Macro={event['macro_regime']} | "
                f"HMM={event['hmm_regime']} | Reason={event['reason']} | "
                f"Phase={event['phase']} | Conf={event['confidence']} | Stale={event['stale']}"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_json_report(report_day: date, summaries: list[dict]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"V3D_Regime_Report_{report_day:%Y%m%d}.json"
    normalized = []
    for summary in summaries:
        item = dict(summary)
        for key in ("final_regime_counts", "macro_regime_counts", "hmm_regime_counts", "reason_counts", "phase_counts"):
            if key in item:
                item[key] = dict(item[key])
        normalized.append(item)
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return path


def archive_latest(report_day: date) -> list[Path]:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived = []
    for symbol in SYMBOLS:
        sources = [
            (V3D_DIR / f"{symbol}_RegimeMatrix_Latest.csv", "Latest"),
            (HISTORY_DIR / f"{symbol}_RegimeMatrix_History.csv", "History"),
            (V3D_DIR / f"{symbol}_Macro_Regimes_V3D.csv", "Macro"),
            (V3D_DIR / f"{symbol}_HMM_Regimes_V3D.csv", "HMM"),
        ]
        for source, suffix in sources:
            if not source.exists():
                continue
            target = ARCHIVE_DIR / f"{symbol}_V3D_{suffix}_{report_day:%Y%m%d}_{stamp}.csv"
            shutil.copy2(source, target)
            archived.append(target)
    return archived


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate V3D daily regime reports and archives.")
    parser.add_argument("--date", default="today", help="today, previous-business-day, or YYYY-MM-DD")
    parser.add_argument("--archive-latest", action="store_true", help="Copy V3D latest/history/stage files to V3D\\History\\Archives.")
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
