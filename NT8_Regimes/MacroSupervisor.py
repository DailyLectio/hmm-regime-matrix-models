import pandas as pd
import time
import os
from datetime import datetime

# ==========================================
# 1. MULTI-INSTRUMENT PATHS
# ==========================================
INSTRUMENTS = {
    "NQ": {
        "micro": r"C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Regimes.csv",
        "macro": r"C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Macro_Regimes.csv"
    },
    "ES": {
        "micro": r"C:\Users\Valued Customer\NT8_Regimes\Active\ES_Regimes.csv",
        "macro": r"C:\Users\Valued Customer\NT8_Regimes\Active\ES_Macro_Regimes.csv"
    }
}
FOOTPRINT_CSV = r"C:\Users\Valued Customer\NT8_Regimes\Active\Footprint_Export.csv"

# The specific structural checkpoints
CHECKPOINTS = [
    "09:25", "09:35", "09:45", "09:55", "10:05", "10:15", "10:25", "10:35", 
    "11:05", "12:05", "13:05", "14:05", "15:05", "16:00"
]
processed_checkpoints = set()

def get_latest_row(filepath):
    """Safely reads the last line of a CSV without locking the file from NT8."""
    if not os.path.exists(filepath):
        return None
    try:
        df = pd.read_csv(filepath, engine='python', on_bad_lines='skip')
        if df.empty:
            return None
        return df.iloc[-1]
    except Exception as e:
        return None

def calculate_macro_bias(micro_state, footprint_signal):
    """The Trinity Logic Matrix: Fusing the Trees and the X-Ray."""
    
    # --- LEVEL 1: THE EXHAUSTION KILL-SWITCH ---
    if footprint_signal in ["DEIA", "EEMDF"]:
        return "EXIT: Exhaustion Alert (Flatten Runners)"

    # --- LEVEL 2: THE MANDATORY SIT-ON-HANDS ---
    if micro_state == "Transition":
        return "HALTED: Transition Chop Detected"
        
    # --- LEVEL 3: TREND & BREAKOUT SHAPES (B, P, b) ---
    if micro_state in ["TrendUp", "TrendDown"]:
        if footprint_signal in ["SIB", "DEB"]:
            return f"INSTITUTIONAL BREAKOUT: {micro_state} Extension"
        if footprint_signal in ["PAR", "ABS"]:
            return f"TREND RECLAIM: {micro_state} VWAP Retest"
            
    # --- LEVEL 4: ROTATIONAL SHAPE (D) ---
    if micro_state == "Balance":
        if footprint_signal in ["ABS", "TF", "DT"]:
            return "STRUCTURAL ROTATION: Mean Reversion"
            
    # Default State
    return "AWAITING ALIGNMENT"

def write_macro_csv(filepath, timestamp, bias):
    """Writes the specific bias to the specific instrument macro file."""
    header = ["TimestampET", "MacroBias"]
    file_exists = os.path.isfile(filepath)
    
    try:
        with open(filepath, 'a', newline='') as f:
            df = pd.DataFrame([[timestamp, bias]])
            df.to_csv(f, header=not file_exists, index=False)
    except Exception as e:
        print(f"Error writing to Macro CSV ({filepath}): {e}")

print("Dual Python Macro Supervisor Started. Monitoring NT8 feeds...")

# ==========================================
# 2. THE SUPERVISOR LOOP
# ==========================================
while True:
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    # Execute only at the exact checkpoints
    if current_time_str in CHECKPOINTS and current_time_str not in processed_checkpoints:
        
        footprint_row = get_latest_row(FOOTPRINT_CSV)
        
        # Process both ES and NQ sequentially
        for inst, paths in INSTRUMENTS.items():
            micro_row = get_latest_row(paths["micro"])
            
            if micro_row is not None and footprint_row is not None:
                micro_state = micro_row['RegimeLabel']
                footprint_signal = footprint_row['Signal']
                
                final_bias = calculate_macro_bias(micro_state, footprint_signal)
                write_macro_csv(paths["macro"], now.strftime("%Y-%m-%d %H:%M:00"), final_bias)
                print(f"[{current_time_str}] {inst} Published: {final_bias}")
            else:
                print(f"[{current_time_str}] {inst} Waiting for valid CSV data...")

        processed_checkpoints.add(current_time_str)

    # Reset checkpoints at midnight
    if current_time_str == "00:00":
        processed_checkpoints.clear()
        
    time.sleep(5)