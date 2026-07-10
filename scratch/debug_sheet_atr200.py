import pandas as pd
import numpy as np

sheet_df = pd.read_csv("scratch/Quality_1.csv")
sheet_df.columns = [c.strip() for c in sheet_df.columns]

high = sheet_df["High"].values
low = sheet_df["Low"].values
close = sheet_df["Close"].values

tr = [high[0] - low[0]]
for i in range(1, len(sheet_df)):
    prev_c = close[i-1]
    tr_val = max(high[i] - low[i], abs(high[i] - prev_c), abs(low[i] - prev_c))
    tr.append(tr_val)
tr = np.array(tr)

sheet_atr_14 = sheet_df["ATR (14)"].values

print("Row index, Manual TR, Sheet ATR(14), SMA(i+1), SMA(14), Wilder_prev_14")
for i in range(10, 25):
    sma_all = np.mean(tr[:i+1])
    sma_14 = np.mean(tr[i-13:i+1]) if i >= 13 else np.nan
    wilder_from_prev = (sheet_atr_14[i-1] * 13 + tr[i]) / 14 if i > 0 else np.nan
    
    print(f"Row {i:3d} | TR: {tr[i]:7.2f} | Sheet: {sheet_atr_14[i]:7.2f} | SMA_all: {sma_all:7.2f} | SMA_14: {sma_14:7.2f} | Wilder_prev: {wilder_from_prev:7.2f}")

