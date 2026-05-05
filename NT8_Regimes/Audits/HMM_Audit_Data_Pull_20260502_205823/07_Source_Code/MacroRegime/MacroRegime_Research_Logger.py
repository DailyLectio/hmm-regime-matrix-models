import pandas as pd
import os

print("--- STARTING MACRO REGIME RESEARCH LOGGER ---")

ACTIVE_DIR = r"C:\Users\Valued Customer\NT8_Regimes\Active"
RESEARCH_DIR = r"C:\Users\Valued Customer\NT8_Regimes\Research"

# Create the Research folder if it doesn't exist
if not os.path.exists(RESEARCH_DIR):
    os.makedirs(RESEARCH_DIR)

for symbol in ["NQ", "ES"]:
    csv_path = os.path.join(ACTIVE_DIR, f"{symbol}_Macro_Regimes.csv")
    output_path = os.path.join(RESEARCH_DIR, f"{symbol}_Research_Log.csv")
    
    if not os.path.exists(csv_path):
        print(f"Skipping {symbol}: Could not find {csv_path}")
        continue
        
    print(f"Processing 30-Day Data for {symbol}...")
    try:
        df = pd.read_csv(csv_path)
        
        # Smart Data Extraction: 
        # The 09:25 pre-market print holds its value in the 'bias' column.
        # The 09:35+ RTH prints hold their value in the 'regime' column.
        def get_display_value(row):
            if row['checkpoint_time'] == '09:25':
                return row['official_bias_label']
            else:
                return row['official_regime_label']
                
        df['Log_Output'] = df.apply(get_display_value, axis=1)
        
        # Pivot the table: 1 Row Per Trade Date
        pivot_df = df.pivot(index='trade_date', columns='checkpoint_time', values='Log_Output').reset_index()
        
        # Reorder columns chronologically for the Excel output
        target_cols = ['trade_date', '09:25', '09:35', '10:05', '10:35', '11:05', '12:05', '13:05', '14:05', '15:05', '16:00']
        
        # Only select columns that actually exist to prevent errors
        final_cols = [col for col in target_cols if col in pivot_df.columns]
        
        # Add any unexpected columns at the end (just in case)
        extra_cols = [col for col in pivot_df.columns if col not in final_cols]
        pivot_df = pivot_df[final_cols + extra_cols]
        
        # Save to the Research folder
        pivot_df.to_csv(output_path, index=False)
        print(f"SUCCESS: Extracted {len(pivot_df)} days of formatted research to {output_path}")
        
    except Exception as e:
        print(f"Error processing {symbol}: {e}")

print("\n--- PROCESS COMPLETE ---")