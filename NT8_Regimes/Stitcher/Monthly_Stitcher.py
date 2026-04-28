import pandas as pd
import glob
import os

print("--- Starting Local NT8 Data Stitching ---")

# --- STRICT PATHS ---
INCOMING_DIR = r"C:\Users\Valued Customer\NT8_Regimes\Incoming"
OUTPUT_DIR = r"C:\Users\Valued Customer\NT8_Regimes"

# Look explicitly inside the Incoming folder for the raw exports
search_path = os.path.join(INCOMING_DIR, "*.txt")
file_list = glob.glob(search_path)

# Safety check: ignore live files just in case they ended up here
file_list = [f for f in file_list if "Live_NQ_Data" not in f and "Stitched" not in f]

if not file_list:
    print(f"ERROR: No raw .txt files found in {INCOMING_DIR}.")
else:
    df_list = []
    columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']

    for file in file_list:
        try:
            temp_df = pd.read_csv(file, sep=';', header=None, names=columns)
            df_list.append(temp_df)
            print(f"Loaded: {os.path.basename(file)} ({len(temp_df)} rows)")
        except Exception as e:
            print(f"Failed to read {file}: {e}")

    if df_list:
        merged_df = pd.concat(df_list, ignore_index=True)
        merged_df['Datetime'] = pd.to_datetime(merged_df['Timestamp'], format='%Y%m%d %H%M%S')
        merged_df = merged_df.sort_values('Datetime').drop_duplicates(subset=['Timestamp'], keep='last')
        merged_df = merged_df.drop(columns=['Datetime'])

        # Save the stitched file back out to the main directory
        output_filename = os.path.join(OUTPUT_DIR, "NQ_Stitched_Continuous_Data.txt")
        merged_df.to_csv(output_filename, sep=';', index=False, header=False)

        print(f"\nSuccess! Created 90-day base file at:\n{output_filename}")