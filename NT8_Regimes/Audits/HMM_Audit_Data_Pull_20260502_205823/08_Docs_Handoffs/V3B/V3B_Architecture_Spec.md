import os

# Content for the V3B Architecture Specification
content = """# V3B Institutional Regime Matrix: Architecture Specification

## 1. System Overview
The **V3B Institutional Regime Matrix** is a quantitative market-state supervisor designed for ES and NQ. It utilizes a decoupled Python-to-C# architecture to analyze Auction Market Theory (AMT) structure and volatility-driven "Playbooks." It acts as a real-time gatekeeper for automated trading strategies in NinjaTrader 8.

---

## 2. Technical Phasing
### **Version B (Current Live - Surgical Patch)**
* **Status:** Active Production / SIM Testing.
* **Primary Change:** Lowered IB expansion thresholds and implemented "Bracket Overrides."
* **Logic Goal:** Prevents "Structural Inertia" by allowing high-velocity moves to trigger Trend Playbooks even if the Macro state is stuck in a "Bracket."

### **Version C (Planned - Stage C Supervisor)**
* **Status:** Development.
* **Goal:** Unified architecture using a dedicated `RegimeMatrix.csv`.
* **Features:** 3-Period Rolling Velocity, State Persistence (Anti-Whipsaw), and centralized bot-gating in Python.

---

## 3. Folder Taxonomy & File Paths
* **Root Directory:** `C:\\Users\\Valued Customer\\NT8_Regimes`
* **Documentation:** `\\V3B\\V3B_Architecture_Spec.md`
* **Production CSVs:** `\\Active\\`
    * `ES_Macro_Regimes.csv`
    * `NQ_Macro_Regimes.csv`
* **Data Exports:** `\\Exports\\` (1-minute .txt files from NinjaTrader)
* **Source Code (Python):**
    * `MacroRegimeBuilder_ES.py`
    * `MacroRegimeBuilder_NQ.py`
* **Source Code (C#):**
    * `Indicators\\RegimeMatrixHUD.cs`
    * `Strategies\\ADXX.cs`, `Pine.cs`, `Momo.cs`, `ADX_DI.cs`

---

## 4. Python Engine Specifications (V3B)

### **Volatility Thresholds (IB Extension %)**
| Instrument | Compressed | Normal | Expanding |
| :--- | :--- | :--- | :--- |
| **NQ** | < 0.45 | 0.45 - 0.84 | >= 0.85 |
| **ES** | < 0.50 | 0.50 - 0.99 | >= 1.00 |

### **The Hierarchy Override (The Surgical Patch)**
The model breaks the rigid AMT hierarchy to prevent being trapped in "Bracket Prison."
* **Trend Confirmation:** `ABS(Close_vs_VWAP_ATR) > 0.50` AND `ABS(Net_Move_ATR) > 0.75`.
* **Rule:** If `Macro_State == BRACKET` AND `IB_Extension >= Expanding` AND `Trend_Confirmation == TRUE`, then `Playbook = TREND_EXPANSION`.

### **Ghosting Fix (Time-Sync)**
To prevent future checkpoints from populating with stale data, the engine uses:
`if cp > rth_df["time_str"].max(): continue`

---

## 5. C# HUD Gatekeeper & Bot Matrix

### **Gatekeeper Logic (Exact Match)**
The HUD uses exact string matching to prevent the "Liquid/Illiquid" overlap bug.
* **Hard Blocks:** `ROTATION_ILLIQUID`, `ROTATION_LIQUID`, `TRANSITION`.

### **The Trinity Bot Lanes**
| Bot | Lane | Primary Playbooks | Context |
| :--- | :--- | :--- | :--- |
| **MOMO** | 1 | Expansion, Compression, Rotation | All-Weather Anchor |
| **ADXX** | 2 | Expansion, Compression | Trend Rider |
| **PINE** | 3 | Expansion, Compression | Structural Exhaustion |
| **ADX_DI** | 5 | Rotation_Illiquid, Balance | Bracket Sniper |

---

## 6. Target Column Schema (V3B Macro CSV)
1.  `trade_date`
2.  `symbol`
3.  `checkpoint_time`
4.  `last_price`
5.  `ib_extension_pct`
6.  `checkpoint_state` (Macro Rolling State)
7.  `official_regime_label` (AMT Structure)
8.  `volatility_state` (Compressed/Normal/Expanding)
9.  `playbook_state` (Final Gatekeeper Output)

---

## 7. Next Phase: Stage C Redesign Goals
1.  **Decoupling:** Create `RegimeMatrix.csv` as the single source of truth.
2.  **Velocity:** Implement `3-Period Rolling Velocity (Price Change / ATR)`.
3.  **Persistence:** Require 2-checkpoint hold for regime upgrades (e.g., Expansion).
4.  **HMM Integration:** Formalize the vote from Stage B (Hidden Markov Model).
"""

# Create the directory if it doesn't exist
path = "/mnt/data/V3B_Architecture_Spec.md"

with open(path, "w") as f:
    f.write(content)