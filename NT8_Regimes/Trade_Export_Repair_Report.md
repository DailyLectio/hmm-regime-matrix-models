# Trade Export System — Repair Report & Next Steps

**Date:** 2026-05-04 | **Session:** Post-audit repair delivery

---

## What Was Delivered

| File | Type | Purpose |
|---|---|---|
| `accounts_registry.json` | JSON | **Drop to:** `C:\Users\Valued Customer\NT8_Regimes\accounts_registry.json` — fixes the crash |
| `eod_export.py` | Python | Repaired EOD exporter — contamination guard + EXCLUDE filter + diagnostics |
| `V3CTradeLogger.cs` | NinjaScript | New shared logger helper for all V3C strategies |
| `V3_Expansion_Rider_V3C.cs` | NinjaScript | Stage 1 logging patch + `AccountNameFilter` parameter |
| `V3_Value_Fader_V3C.cs` | NinjaScript | Stage 1 logging patch + `AccountNameFilter` parameter |
| `ADXDIV3C.cs` | NinjaScript | Stage 1 logging patch + `AccountNameFilter` parameter |
| `MomoV3C.cs` | NinjaScript | Stage 1 logging patch + `AccountNameFilter` parameter |

---

## Root Causes — Final Diagnosis

### 1. Crash: `accounts_registry.json` Not Found
The file didn't exist at the path `eod_export.py` expected. **Fixed:** `accounts_registry.json` is generated fresh from the master CSV registry with all 38 accounts (V1A/V1B: 9, V3C: 13, V3D: 11, OG: 3, EXCLUDE: 1, UNKNOWN: 1). Drop it at the root of `NT8_Regimes\`.

### 2. Account Contamination (93.3% of V3D_TradeLog.csv is non-V3D)
The NT8 `TradeLogExporter` wrote to `V3D_TradeLog.csv` regardless of which account the strategy was loaded on. `AccountNameFilter` was not set or not enforced per tab.

**Fixed two ways:**
- **eod_export.py contamination guard:** before deduplication, any row whose account is in the registry under a different model gets its `model_version` corrected. A console message tells the operator how many rows were corrected.
- **EXCLUDE filter in `apply_registry()`:** DEMO1419193 and any other EXCLUDE-class account is dropped before any output is written, with a console message.

**What you also need to do in NT8 (cannot be fixed in Python):** Set `AccountNameFilter` on each strategy tab to the exact account name. This stops contamination at the source so future logs are clean without needing the Python guard.

### 3. V3C TradeLog Folder Is Empty — No V3C Trade Data At All
The `V3C\TradeLog\` folder is empty because V3C strategy files never had Stage 1 trade-close logging. The Stage 1 runbook explicitly said V3C strategies were not patched. The `eod_export.py` correctly looks for `V3C\TradeLog\V3C_TradeLog.csv` — it just doesn't exist yet.

**Fixed:** All four V3C strategies now have Stage 1 logging via the shared `V3CTradeLogger.cs` helper. Each strategy has two new parameters in group "0b. Trade Logging": `AccountNameFilter` (set to the exact NT8 account name) and `TradeLogFolder` (default path is correct). Trades write to `V3C\TradeLog\{AccountName}_TradeLog.csv` — one file per account, matching V3D's pattern.

### 4. Per-Bot Logs Empty (V3D_Sniper_A_TradeLog.csv, V3D_Momentum_A_TradeLog.csv)
These files are header-only. This means the V3D Stage 1 logging inside the NT8 strategy files is either not compiling or `AccountNameFilter` is not matching any running account. The fix is not in the Python layer — it requires confirming the NT8 compile succeeded and that `AccountNameFilter` is set correctly per tab.

### 5. 100% UNAVAILABLE Regime Enrichment
The enrichment join in `eod_export.py` tries to merge trade rows with the regime matrix history CSV. The join fails silently because the per-bot logs are empty (nothing to join against). Once the NT8 logging is writing actual rows, and once `AccountNameFilter` is set correctly, the enrichment will work on the next EOD run.

### 6. 715 "NQ V3D" Trades on 2026-05-04 at PF=0.84 — Contamination
The EOD comparison script consumed the contaminated V3D log and reported those figures. Actual V3D NQ trades on 2026-05-04: 13 (from SimV3D-NQ-3A only). After the contamination guard is working, the comparison script will see the correct 13-row V3D trade set.

---

## accounts_registry.json — What Changed

The prior version had incorrect entries, mixed-up model labels, and was missing accounts. The new version:
- Built directly from the master CSV registry (not hand-typed)
- Correctly labels V1B Mode B accounts as `"model": "V1B"`
- Labels DEMO1419193 as `"model": "EXCLUDE"` — dropped by `apply_registry()` before any output
- Includes `session`, `tab_name`, `template`, `ab_mode` fields derived from the registry
- Contains 38 accounts: V1A (6), V1B (3), V3C (13), V3D (11), OG (3), EXCLUDE (1), UNKNOWN (1)
- **Going forward:** any time the Master Accounts Registry CSV is updated, regenerate this JSON using the `build_registry.py` script or re-run the same logic

---

## eod_export.py — What Changed

Three surgical changes, all backward-compatible:

**1. `load_registry()` — clear error message instead of cryptic crash:**
If `accounts_registry.json` is missing, the error now says exactly which file to place and where.

**2. `apply_registry()` — EXCLUDE filter:**
After model assignment, rows where `model_version == "EXCLUDE"` are dropped before any output. A console line reports how many rows and which accounts were dropped.

**3. `main()` — contamination guard + diagnostics:**
Before deduplication, any row whose account is in the registry under a different model gets its `model_version` corrected to the registry value. The console shows how many rows were corrected. After `apply_registry()`, the console prints row counts by model so the operator can verify the output only contains intended accounts. Log file discovery now shows each file's row count and existence status.

---

## V3C Stage 1 Logging — How to Deploy

### Step 1: Compile V3CTradeLogger.cs
Copy `V3CTradeLogger.cs` to:
```
C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Indicators\
```
Open NinjaScript Editor → Compile. This must succeed before the patched strategies will compile.

### Step 2: Copy patched V3C strategy files
Copy all four patched .cs files to:
```
C:\Users\Valued Customer\Documents\NinjaTrader 8\bin\Custom\Strategies\
```
Compile in NinjaScript Editor. No changes to strategy logic — only `OnExecutionUpdate` and `OnOrderUpdate` hooks added.

### Step 3: Set AccountNameFilter on every V3C strategy tab
**This is the most critical step.** For each V3C strategy tab, open the strategy parameters and set:
- `Account Name Filter` = exact account name (e.g., `SimV3C-NQ-1A`)
- `Trade Log Folder` = `C:\Users\Valued Customer\NT8_Regimes\V3C\TradeLog`

| Account | AccountNameFilter value |
|---|---|
| SimV3C-NQ-1A | `SimV3C-NQ-1A` |
| SimV3C-NQ-1B | `SimV3C-NQ-1B` |
| SimV3C-NQ-2A | `SimV3C-NQ-2A` |
| SimV3C-NQ-2B | `SimV3C-NQ-2B` |
| SimV3C-NQ-2C | `SimV3C-NQ-2C` |
| SimV3C-NQ-3A | `SimV3C-NQ-3A` |
| SimV3C-NQ-3B | `SimV3C-NQ-3B` |
| SimV3C-NQ-4A | `SimV3C-NQ-4A` |
| SimV3C-NQ-4B | `SimV3C-NQ-4B` |
| SimV3C-NQ-5A | `SimV3C-NQ-5A` |
| SimV3C-NQ-5B | `SimV3C-NQ-5B` |

### Step 4: Verify after first trade closes
After the first live session with the patched strategies:
1. Open `C:\Users\Valued Customer\NT8_Regimes\V3C\TradeLog\`
2. Confirm per-account CSV files exist (e.g., `SimV3C_NQ_1A_TradeLog.csv`)
3. Open one file — confirm rows exist with correct account, model_version=V3C, real prices

### Step 5: Run the EOD export
```
ALL_MODELS_EXPORT.bat
```
The console should now show:
- V3C\TradeLog\ discovered with row counts > 0
- "Rows by model" showing V3C count alongside V3D and V1A
- No contamination messages (or small count if filters need tuning)

---

## Remaining Items That Require NT8 Action (Cannot Be Fixed in Python)

| Item | What to Do | Priority |
|---|---|---|
| V3D `AccountNameFilter` not set | Open each V3D strategy tab, set `AccountNameFilter` to exact account name | **BEFORE NEXT SESSION** |
| V3D Stage 1 compile unconfirmed | Open NinjaScript Editor → Compile → confirm no errors → spot-check that per-account V3D logs write after first trade | **BEFORE NEXT SESSION** |
| SimV3D-NQ-5C dedicated account | Create separate SIM account; 5B currently shares two strategies | P1 |
| ExitCooldownBars=3 on Kalman Fader 3 | Confirm Mode B patch is deployed — account is now active with live footprint | P2 |

---

## What the EOD Export Now Produces (When Everything Is Wired)

```
ALL_MODELS_EXPORT.bat
  → eod_export.py --date today
        reads:  V1A\TradeLog\*.csv
                V1B\TradeLog\*.csv
                V3C\TradeLog\{AccountName}_TradeLog.csv   ← NEW
                V3D\TradeLog\V3D_TradeLog.csv
                OG\TradeLog\OG_TradeLog.csv
        corrects: model_version contamination via registry
        drops:  DEMO1419193 and other EXCLUDE accounts
        enriches: entry_regime, entry_macro, entry_hmm from RegimeMatrix history
        writes: UNIFIED\AllModels_TradeLog_YYYYMMDD.csv
                V1A\History\V1A_TradeLog_YYYYMMDD.csv
                V3C\History\V3C_TradeLog_YYYYMMDD.csv
                V3D\History\V3D_TradeLog_YYYYMMDD.csv
                UNIFIED\DataQuality_Report_YYYYMMDD.txt
  → trade_performance_report.py --mode daily --date today
        reads:  UNIFIED\AllModels_TradeLog_YYYYMMDD.csv
        writes: UNIFIED\Reports\Daily_Trade_Performance_YYYYMMDD.md
```
