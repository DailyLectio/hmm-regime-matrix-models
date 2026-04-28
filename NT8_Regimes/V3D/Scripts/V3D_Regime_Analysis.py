"""
V3D Regime Analysis Suite — Daily Report Generator
Analyzes RegimeMatrix_Full.csv and generates daily pre-market reports

Usage:
    python V3D_Regime_Analysis.py --date 2026-04-26
    python V3D_Regime_Analysis.py --last-session
    python V3D_Regime_Analysis.py --full-history

Output:
    - Daily regime distribution by instrument
    - Intraday regime timeline (phase-by-phase breakdown)
    - Bot opportunity analysis
    - Regime transition statistics
"""

import argparse
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np

# Paths
BASE_DIR = r"C:\V3D"
BACKTEST_DIR = os.path.join(BASE_DIR, "Backtest")
REPORTS_DIR = os.path.join(BASE_DIR, "Reports")

MATRIX_FILES = {
    "NQ": os.path.join(BACKTEST_DIR, "NQ_RegimeMatrix_Full.csv"),
    "ES": os.path.join(BACKTEST_DIR, "ES_RegimeMatrix_Full.csv"),
}

# RTH Phases (from architecture spec)
PHASE_ORDER = [
    "OPENING_AUCTION",
    "EARLY_TEST", 
    "FIRST_ACCEPTANCE",
    "PRE_IB_MATURATION",
    "POST_IB_MACRO",
    "MID_MORNING_DISCOVERY",
    "LUNCH_AUCTION",
    "POST_LUNCH_ROTATION",
    "AFTERNOON_TREND_TEST",
    "LATE_DAY_CONVICTION",
    "CASH_CLOSE",
]

REGIME_ORDER = [
    "TREND_EXPANSION",
    "TREND_COMPRESSION", 
    "ROTATION_LIQUID",
    "ROTATION_ILLIQUID",
    "TRANSITION",
]

# ===========================================================================
# DATA LOADING
# ===========================================================================

def load_regime_matrix(symbol: str, date_filter: str = None) -> pd.DataFrame:
    """Load and filter regime matrix data."""
    path = MATRIX_FILES[symbol]
    if not os.path.exists(path):
        raise FileNotFoundError(f"Matrix file not found: {path}")
    
    df = pd.read_csv(path)
    df["TimestampET"] = pd.to_datetime(df["TimestampET"])
    df["trade_date"] = df["TimestampET"].dt.date
    
    if date_filter == "last":
        # Get most recent trading date
        last_date = df["trade_date"].max()
        df = df[df["trade_date"] == last_date]
    elif date_filter:
        # Specific date
        filter_date = pd.to_datetime(date_filter).date()
        df = df[df["trade_date"] == filter_date]
    
    return df


# ===========================================================================
# REGIME DISTRIBUTION ANALYSIS
# ===========================================================================

def analyze_regime_distribution(df: pd.DataFrame, symbol: str) -> Dict:
    """Compute regime distribution statistics."""
    total_bars = len(df)
    
    dist = df["FinalRegime"].value_counts()
    
    results = {
        "symbol": symbol,
        "total_bars": total_bars,
        "date_range": f"{df['trade_date'].min()} to {df['trade_date'].max()}",
        "trading_days": df["trade_date"].nunique(),
        "regimes": {}
    }
    
    for regime in REGIME_ORDER:
        count = dist.get(regime, 0)
        pct = (count / total_bars * 100) if total_bars > 0 else 0
        results["regimes"][regime] = {
            "count": int(count),
            "percent": round(pct, 1),
        }
    
    return results


# ===========================================================================
# INTRADAY TIMELINE ANALYSIS
# ===========================================================================

def analyze_intraday_timeline(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Regime distribution by phase across the trading day."""
    
    # Group by phase and regime
    phase_regime = df.groupby(["Phase", "FinalRegime"]).size().unstack(fill_value=0)
    
    # Reorder columns and rows
    phase_regime = phase_regime.reindex(
        index=PHASE_ORDER, 
        columns=REGIME_ORDER,
        fill_value=0
    )
    
    # Add percentage columns
    phase_totals = phase_regime.sum(axis=1)
    for regime in REGIME_ORDER:
        pct_col = f"{regime}_pct"
        phase_regime[pct_col] = (phase_regime[regime] / phase_totals * 100).round(1)
    
    return phase_regime


# ===========================================================================
# BOT OPPORTUNITY ANALYSIS
# ===========================================================================

def analyze_bot_opportunities(df: pd.DataFrame, symbol: str) -> Dict:
    """Compute how often each bot had permission to trade."""
    
    bots = ["Expansion", "Momo", "Pine", "ADX_DI", "Sniper"]
    total_bars = len(df)
    
    results = {}
    
    for bot in bots:
        allow_col = f"Allow{bot}"
        if allow_col in df.columns:
            allowed_bars = df[allow_col].sum()
            pct = (allowed_bars / total_bars * 100) if total_bars > 0 else 0
            
            # Average SizePct when allowed
            size_col = f"{bot}SizePct"
            if size_col in df.columns:
                avg_size = df[df[allow_col] == 1][size_col].mean()
            else:
                avg_size = 0
            
            results[bot] = {
                "allowed_bars": int(allowed_bars),
                "percent_time": round(pct, 1),
                "avg_size_pct": round(avg_size, 1),
                "setups_per_day": round(allowed_bars / df["trade_date"].nunique(), 1),
            }
    
    return results


# ===========================================================================
# REGIME TRANSITION MATRIX
# ===========================================================================

def analyze_regime_transitions(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Compute transition probabilities between regimes."""
    
    # Get current and next regime
    df_sorted = df.sort_values("TimestampET").copy()
    df_sorted["NextRegime"] = df_sorted["FinalRegime"].shift(-1)
    
    # Drop last row (no next regime)
    df_sorted = df_sorted[df_sorted["NextRegime"].notna()]
    
    # Count transitions
    transitions = df_sorted.groupby(["FinalRegime", "NextRegime"]).size()
    
    # Build transition matrix
    trans_matrix = pd.DataFrame(0, index=REGIME_ORDER, columns=REGIME_ORDER)
    
    for (curr, next_), count in transitions.items():
        trans_matrix.loc[curr, next_] = count
    
    # Convert to probabilities
    row_sums = trans_matrix.sum(axis=1)
    trans_prob = (trans_matrix.div(row_sums, axis=0) * 100).round(1)
    
    return trans_prob


# ===========================================================================
# REGIME DURATION ANALYSIS
# ===========================================================================

def analyze_regime_durations(df: pd.DataFrame, symbol: str) -> Dict:
    """Compute average duration of each regime state."""
    
    df_sorted = df.sort_values("TimestampET").copy()
    
    # Identify regime runs (consecutive bars in same regime)
    df_sorted["RegimeChange"] = (df_sorted["FinalRegime"] != df_sorted["FinalRegime"].shift()).cumsum()
    
    # Group by regime run
    runs = df_sorted.groupby(["FinalRegime", "RegimeChange"]).size()
    
    results = {}
    
    for regime in REGIME_ORDER:
        regime_runs = runs[runs.index.get_level_values(0) == regime]
        if len(regime_runs) > 0:
            results[regime] = {
                "avg_duration_bars": round(regime_runs.mean(), 1),
                "median_duration_bars": int(regime_runs.median()),
                "max_duration_bars": int(regime_runs.max()),
                "total_occurrences": len(regime_runs),
            }
        else:
            results[regime] = {
                "avg_duration_bars": 0,
                "median_duration_bars": 0,
                "max_duration_bars": 0,
                "total_occurrences": 0,
            }
    
    return results


# ===========================================================================
# REPORT GENERATION
# ===========================================================================

def generate_daily_report(symbol: str, date_filter: str = None) -> str:
    """Generate complete daily report."""
    
    df = load_regime_matrix(symbol, date_filter)
    
    if df.empty:
        return f"No data found for {symbol} on {date_filter}"
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append(f"V3D REGIME ANALYSIS — {symbol}")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    # Section 1: Regime Distribution
    report_lines.append("=" * 80)
    report_lines.append("1. REGIME DISTRIBUTION")
    report_lines.append("=" * 80)
    
    dist = analyze_regime_distribution(df, symbol)
    report_lines.append(f"Date Range: {dist['date_range']}")
    report_lines.append(f"Trading Days: {dist['trading_days']}")
    report_lines.append(f"Total Bars: {dist['total_bars']}")
    report_lines.append("")
    
    report_lines.append(f"{'Regime':<25} {'Count':>10} {'Percent':>10}")
    report_lines.append("-" * 50)
    for regime in REGIME_ORDER:
        data = dist["regimes"][regime]
        report_lines.append(f"{regime:<25} {data['count']:>10} {data['percent']:>9.1f}%")
    report_lines.append("")
    
    # Section 2: Bot Opportunities
    report_lines.append("=" * 80)
    report_lines.append("2. BOT OPPORTUNITY ANALYSIS")
    report_lines.append("=" * 80)
    
    bots = analyze_bot_opportunities(df, symbol)
    report_lines.append(f"{'Bot':<15} {'Allowed %':>12} {'Avg Size %':>12} {'Setups/Day':>12}")
    report_lines.append("-" * 60)
    for bot_name, data in bots.items():
        report_lines.append(
            f"{bot_name:<15} {data['percent_time']:>11.1f}% "
            f"{data['avg_size_pct']:>11.1f}% {data['setups_per_day']:>11.1f}"
        )
    report_lines.append("")
    
    # Section 3: Regime Durations
    report_lines.append("=" * 80)
    report_lines.append("3. REGIME DURATION STATISTICS (5-minute bars)")
    report_lines.append("=" * 80)
    
    durations = analyze_regime_durations(df, symbol)
    report_lines.append(f"{'Regime':<25} {'Avg':>8} {'Median':>8} {'Max':>8} {'Count':>8}")
    report_lines.append("-" * 65)
    for regime in REGIME_ORDER:
        data = durations[regime]
        report_lines.append(
            f"{regime:<25} {data['avg_duration_bars']:>8.1f} "
            f"{data['median_duration_bars']:>8} {data['max_duration_bars']:>8} "
            f"{data['total_occurrences']:>8}"
        )
    report_lines.append("")
    
    # Section 4: Intraday Timeline
    report_lines.append("=" * 80)
    report_lines.append("4. INTRADAY REGIME TIMELINE")
    report_lines.append("=" * 80)
    report_lines.append("Regime distribution by session phase (percentage of bars in each phase)")
    report_lines.append("")
    
    timeline = analyze_intraday_timeline(df, symbol)
    
    # Print header
    header = f"{'Phase':<25}"
    for regime in REGIME_ORDER:
        header += f" {regime[:8]:>8}"
    report_lines.append(header)
    report_lines.append("-" * (25 + 9 * len(REGIME_ORDER)))
    
    # Print data
    for phase in PHASE_ORDER:
        if phase in timeline.index:
            line = f"{phase:<25}"
            for regime in REGIME_ORDER:
                pct_col = f"{regime}_pct"
                val = timeline.loc[phase, pct_col]
                line += f" {val:>7.1f}%"
            report_lines.append(line)
    report_lines.append("")
    
    # Section 5: Transition Matrix
    report_lines.append("=" * 80)
    report_lines.append("5. REGIME TRANSITION PROBABILITIES (%)")
    report_lines.append("=" * 80)
    report_lines.append("Rows = current regime | Columns = next regime")
    report_lines.append("")
    
    trans = analyze_regime_transitions(df, symbol)
    
    # Print header
    header = f"{'From \\ To':<20}"
    for regime in REGIME_ORDER:
        header += f" {regime[:8]:>8}"
    report_lines.append(header)
    report_lines.append("-" * (20 + 9 * len(REGIME_ORDER)))
    
    # Print data
    for curr_regime in REGIME_ORDER:
        line = f"{curr_regime:<20}"
        for next_regime in REGIME_ORDER:
            val = trans.loc[curr_regime, next_regime]
            line += f" {val:>7.1f}%"
        report_lines.append(line)
    report_lines.append("")
    
    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)


# ===========================================================================
# MAIN
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description="V3D Regime Analysis")
    p.add_argument("--symbol", choices=["NQ", "ES", "BOTH"], default="BOTH")
    p.add_argument("--date", help="Specific date (YYYY-MM-DD)")
    p.add_argument("--last-session", action="store_true",
                   help="Analyze most recent trading session")
    p.add_argument("--full-history", action="store_true",
                   help="Analyze entire dataset")
    p.add_argument("--output", help="Output file path (optional)")
    return p.parse_args()


def main():
    args = parse_args()
    
    # Determine date filter
    if args.last_session:
        date_filter = "last"
    elif args.date:
        date_filter = args.date
    elif args.full_history:
        date_filter = None
    else:
        # Default: yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_filter = yesterday
    
    # Create reports directory
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    # Generate reports
    symbols = ["NQ", "ES"] if args.symbol == "BOTH" else [args.symbol]
    
    all_reports = []
    
    for sym in symbols:
        print(f"\nGenerating report for {sym}...")
        report = generate_daily_report(sym, date_filter)
        all_reports.append(report)
        print(report)
        print("\n")
    
    # Save to file if requested
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(REPORTS_DIR, f"V3D_Regime_Report_{timestamp}.txt")
    
    with open(output_path, "w") as f:
        f.write("\n\n".join(all_reports))
    
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
