import pandas as pd
import os

# --- CONFIGURATION ---
MACRO_CSV = r"C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Macro_Regimes.csv"
HMM_CSV = r"C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Regimes.csv"
SYMBOL = "NQ"

def get_volatility_state(ib_ext):
    if pd.isna(ib_ext) or ib_ext == 0.0:
        return "COMPRESSED" # Default to compressed if IB hasn't formed or extended
    if ib_ext > 1.25:
        return "EXPANDING"
    elif ib_ext < 0.75:
        return "COMPRESSED"
    else:
        return "NORMAL"

def get_playbook_state(row):
    regime = str(row.get('official_regime_label', ''))
    vol = row.get('volatility_state', 'NORMAL')

    if "TREND" in regime:
        return "TREND_EXPANSION" if vol == "EXPANDING" else "TREND_COMPRESSION"
    elif regime in ["BRACKET_MACRO", "REVERSION_STRUCTURE", "MEAN_REVERSION_MACRO"]:
        return "ROTATION_ILLIQUID" if vol == "COMPRESSED" else "ROTATION_LIQUID"
    else: 
        # BALANCE_STRUCTURE, OPENING_AUCTION, CHOP, TRANSITION
        return "ROTATION_ILLIQUID" if vol == "COMPRESSED" else "TRANSITION"

def run_health_check():
    print(f"==================================================")
    print(f"   V3 REGIME TRANSLATION ENGINE - DAILY AUDIT     ")
    print(f"==================================================\n")

    if not os.path.exists(MACRO_CSV):
        print(f"[ERROR] Macro file not found at: {MACRO_CSV}")
        return

    # 1. Load Data
    try:
        macro_df = pd.read_csv(MACRO_CSV)
    except Exception as e:
        print(f"[ERROR] Failed to read CSV: {e}")
        return

    if macro_df.empty:
        print("[WARNING] Macro CSV is empty.")
        return

    # Isolate the latest session
    latest_date = macro_df['trade_date'].max()
    today_df = macro_df[macro_df['trade_date'] == latest_date].copy()
    
    print(f"TARGET DATE: {latest_date} | INSTRUMENT: {SYMBOL}")
    print(f"TOTAL CHECKPOINTS LOGGED: {len(today_df)}\n")

    # Calculate Derived States
    today_df['volatility_state'] = today_df['ib_extension_pct'].apply(get_volatility_state)
    today_df['derived_playbook'] = today_df.apply(get_playbook_state, axis=1)

    # 2. Raw Regime Distribution (What the math sees)
    print("--- 1. RAW MACRO STRUCTURE DISTRIBUTION ---")
    if 'official_regime_label' in today_df.columns:
        counts = today_df['official_regime_label'].value_counts()
        for state, count in counts.items():
            print(f" > {state.ljust(25)}: {count * 5} mins")
    print("")

    # 3. Derived Playbook Distribution (What the bots do)
    print("--- 2. DERIVED PLAYBOOK DISTRIBUTION ---")
    playbook_counts = today_df['derived_playbook'].value_counts(normalize=True) * 100
    p_counts = today_df['derived_playbook'].value_counts()
    
    for state, count in p_counts.items():
        pct = playbook_counts[state]
        print(f" > {state.ljust(25)}: {count * 5} mins ({pct:.1f}%)")
    print("")

    # 4. The Volatility Axis (IB Expansion)
    print("--- 3. VOLATILITY AXIS (IB EXPANSION) ---")
    if 'ib_extension_pct' in today_df.columns:
        max_ib = today_df['ib_extension_pct'].max()
        min_ib = today_df['ib_extension_pct'].min()
        latest_ib = today_df['ib_extension_pct'].iloc[-1]
        
        print(f" > Peak IB Expansion: {max_ib:.3f}")
        print(f" > Floor IB Expansion: {min_ib:.3f}")
        print(f" > Closing IB Expansion: {latest_ib:.3f}")
    else:
        print("[!] 'ib_extension_pct' column not found in CSV.")
    print("")

    # 5. Gatekeeper Diagnostics
    print("--- 4. GATEKEEPER DIAGNOSTICS ---")
    green_light_states = ['TREND_EXPANSION', 'TREND_COMPRESSION', 'ROTATION_LIQUID']
    green_lights = today_df[today_df['derived_playbook'].isin(green_light_states)]
    
    print(f" > HUD Green-Lit Gates: {len(green_lights)} checkpoints (approx {len(green_lights)*5} mins)")
    
    if 'tradable_flag' in today_df.columns:
        conflicts = today_df[(today_df['derived_playbook'].isin(green_light_states)) & (today_df['tradable_flag'] == 0)]
        if not conflicts.empty:
            print(f" > [WARNING] Found {len(conflicts)} checkpoints where Playbook was green-lit but Python tradable_flag was 0.")
        else:
            print(" > System Logic Sync: CLEAN (No flag conflicts)")
            
    print(f"\n==================================================")

if __name__ == "__main__":
    run_health_check()
    input("Press Enter to close...")