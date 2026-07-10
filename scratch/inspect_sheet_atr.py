import pandas as pd
import numpy as np

sheet_df = pd.read_csv("scratch/Quality_1.csv")
sheet_df.columns = [c.strip() for c in sheet_df.columns]

# Print first 20 rows of Close, ATR (14), ATR (200)
print("First 20 rows in Google Sheet:")
cols = ["Date/Time", "Close", "ATR (14)", "ATR (200)"]
print(sheet_df[cols].head(20))

# Calculate True Range manually for the first 20 rows
high = sheet_df["High"].values
low = sheet_df["Low"].values
close = sheet_df["Close"].values

tr = [high[0] - low[0]]
for i in range(1, len(sheet_df)):
    prev_c = close[i-1]
    tr_val = max(high[i] - low[i], abs(high[i] - prev_c), abs(low[i] - prev_c))
    tr.append(tr_val)

sheet_df["Manual_TR"] = tr
print("\nFirst 20 rows with Manual TR and ATR:")
print(sheet_df[["Date/Time", "Close", "Manual_TR", "ATR (14)", "ATR (200)"]].head(20))
