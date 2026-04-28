from __future__ import annotations

import os
import time
import traceback
from pathlib import Path

from BuildV3CModelFeed import build_hmm_feed, build_macro_feed


BASE_DIR = Path(r"C:\Users\Valued Customer\NT8_Regimes")
EXPORT_DIR = BASE_DIR / "Exports"
LOOKBACK_DAYS = 100
POLL_SECONDS = 10

INSTRUMENTS = {
    "ES": {
        "input": EXPORT_DIR / "ES_1min_export.txt",
        "last_mod": 0.0,
    },
    "NQ": {
        "input": EXPORT_DIR / "NQ_1min_export.txt",
        "last_mod": 0.0,
    },
}


def update_symbol(symbol: str, input_path: Path) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {symbol} V3C ModelFeed update started. Lookback={LOOKBACK_DAYS} days.")
    macro_path = build_macro_feed(symbol, input_path=input_path, lookback_days=LOOKBACK_DAYS)
    hmm_path, artifact_path = build_hmm_feed(symbol, input_path=input_path, train=False, lookback_days=LOOKBACK_DAYS)
    print(f"[{time.strftime('%H:%M:%S')}] {symbol} V3C Macro -> {macro_path}")
    print(f"[{time.strftime('%H:%M:%S')}] {symbol} V3C HMM   -> {hmm_path}")
    print(f"[{time.strftime('%H:%M:%S')}] {symbol} anchored model used: {artifact_path}")


def main() -> None:
    print("=" * 90)
    print("V3C ModelFeed Watchdog started.")
    print("Reads live NT exports, uses fixed anchored HMM artifacts, writes only V3C\\ModelFeed.")
    print(f"Uses a V3C-only {LOOKBACK_DAYS}-day live window so V3D can keep long history.")
    print("This does not write to NT8_Regimes\\Active.")
    print("=" * 90)

    while True:
        try:
            for symbol, paths in INSTRUMENTS.items():
                input_path = Path(paths["input"])
                if not input_path.exists():
                    continue

                current_mod = os.path.getmtime(input_path)
                if current_mod == paths["last_mod"]:
                    continue

                update_symbol(symbol, input_path)
                paths["last_mod"] = current_mod

            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("V3C ModelFeed Watchdog stopped by user.")
            break
        except Exception:
            print("--- V3C MODELFEED WATCHDOG ERROR ---")
            traceback.print_exc()
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
