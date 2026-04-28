import pandas as pd
import numpy as np
import time
import os
import traceback
from hmmlearn import hmm
import warnings

warnings.filterwarnings("ignore")

# --- PATHS (MULTI-INSTRUMENT CONFIG) ---
INSTRUMENTS = {
    "NQ": {
        "input": r"C:\Users\Valued Customer\NT8_Regimes\Exports\NQ_1min_export.txt",
        "output": r"C:\Users\Valued Customer\NT8_Regimes\Active\NQ_Regimes.csv",
        "last_mod": 0
    },
    "ES": {
        "input": r"C:\Users\Valued Customer\NT8_Regimes\Exports\ES_1min_export.txt",
        "output": r"C:\Users\Valued Customer\NT8_Regimes\Active\ES_Regimes.csv",
        "last_mod": 0
    }
}

def run_hmm_pipeline(instrument, input_file, output_file):
    print(f"[{time.strftime('%H:%M:%S')}] {instrument} Pulse Detected. Running Math...")
    
    try:
        columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # FIXED: Restored sep=';' and header=None to match NT8 exports
        df = pd.read_csv(input_file, sep=';', header=None, names=columns, engine='python')

        # 1. Cleaning & Resampling (5-Min)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y%m%d %H%M%S')
        df = df.sort_values('Timestamp').drop_duplicates(subset=['Timestamp'], keep='last')
        df.set_index('Timestamp', inplace=True)
        
        df_5m = df.resample('5min').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()

        # 2. Feature Engineering
        df_5m['Returns'] = df_5m['Close'].pct_change()
        df_5m['Range'] = (df_5m['High'] - df_5m['Low']) / df_5m['Close']
        df_5m['Vol_Z'] = (df_5m['Volume'] - df_5m['Volume'].rolling(20).mean()) / df_5m['Volume'].rolling(20).std()
        
        features = df_5m[['Returns', 'Range', 'Vol_Z']].dropna()

        if features.empty:
            print("Error: Not enough data to calculate features.")
            return

        # Feature Scaling
        features_scaled = (features - features.mean()) / features.std()

        # 3. Fit HMM
        model = hmm.GaussianHMM(n_components=4, covariance_type="full", n_iter=100, random_state=42, min_covar=0.001)
        model.fit(features_scaled)
        states = model.predict(features_scaled)
        features['StateId'] = states

        # 4. ROBUST AUTO-LABEL LOGIC
        state_means = features.groupby('StateId')['Returns'].mean().sort_values()
        state_ranges = features.groupby('StateId')['Range'].mean().sort_values()
        
        actual_states = list(state_means.index)
        label_map = {}
        
        if len(actual_states) >= 4:
            trend_down_id = actual_states[0]  
            trend_up_id = actual_states[-1]   
            
            rem_states = [s for s in actual_states if s not in (trend_down_id, trend_up_id)]
            rem_ranges = state_ranges.loc[rem_states].sort_values()
            
            balance_id = rem_ranges.index[0]      
            transition_id = rem_ranges.index[-1]  
        else:
            trend_down_id = actual_states[0] if len(actual_states) > 0 else 0
            trend_up_id = actual_states[-1] if len(actual_states) > 0 else 0
            balance_id = actual_states[1] if len(actual_states) > 1 else trend_down_id
            transition_id = actual_states[2] if len(actual_states) > 2 else trend_up_id

        label_map[trend_up_id] = 'TrendUp'
        label_map[trend_down_id] = 'TrendDown'
        label_map[balance_id] = 'Balance'
        label_map[transition_id] = 'Transition'

        # 5. Export for HUD
        hud_df = pd.DataFrame(index=features.index)
        hud_df.index.name = 'TimestampET'
        
        hud_df['StateId'] = features['StateId']
        hud_df['RegimeLabel'] = hud_df['StateId'].map(label_map).fillna('Balance')
        hud_df['Tradeable'] = "True"
        hud_df['AllowLong'] = "True"
        hud_df['AllowShort'] = "True"
        
        adx_map = {'TrendUp': 24, 'TrendDown': 24, 'Balance': 0, 'Transition': 18}
        ci_map = {'TrendUp': 45, 'TrendDown': 45, 'Balance': 60, 'Transition': 50}
        slope_map = {'TrendUp': 'True', 'TrendDown': 'True', 'Balance': 'False', 'Transition': 'False'}
        stop_map = {'TrendUp': 'Trend-Trailing', 'TrendDown': 'Trend-Trailing', 'Balance': 'Mean-Reversion', 'Transition': 'Wide'}
        
        hud_df['SuggestedAdxMin'] = hud_df['RegimeLabel'].map(adx_map).fillna(0)
        hud_df['SuggestedCiMax'] = hud_df['RegimeLabel'].map(ci_map).fillna(0)
        hud_df['SuggestedSlopeGate'] = hud_df['RegimeLabel'].map(slope_map).fillna('False')
        hud_df['SuggestedStopBucket'] = hud_df['RegimeLabel'].map(stop_map).fillna('N/A')
        hud_df['ModelVersion'] = "1.2-Dual"
        
        hud_df.to_csv(output_file)
        
        current_regime = hud_df['RegimeLabel'].iloc[-1] if not hud_df.empty else "Unknown"
        print(f"[{time.strftime('%H:%M:%S')}] {instrument}_Regimes.csv updated. (Current: {current_regime})")

    except Exception as e:
        print(f"\n--- CRITICAL WATCHDOG ERROR ({instrument}) ---")
        traceback.print_exc()
        print("-------------------------------\n")

# --- WATCHDOG LOOP ---
print("Dual HMM Watchdog started. Waiting for unified NinjaTrader data (NQ & ES)...")

while True:
    try:
        for inst, paths in INSTRUMENTS.items():
            if os.path.exists(paths["input"]):
                current_mod_time = os.path.getmtime(paths["input"])
                if current_mod_time != paths["last_mod"]:
                    run_hmm_pipeline(inst, paths["input"], paths["output"])
                    INSTRUMENTS[inst]["last_mod"] = current_mod_time
        time.sleep(2) 
    except Exception as e:
        print("Watchdog loop error. Retrying...")
        time.sleep(5)