import pandas as pd
import numpy as np

def compute_wilder_atr(tr, period):
    atr = np.zeros(len(tr))
    for i in range(period):
        atr[i] = np.mean(tr[:i+1])
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr

if __name__ == "__main__":
    sheet_df = pd.read_csv("scratch/Quality_1.csv")
    sheet_df.columns = [c.strip() for c in sheet_df.columns]
    
    # Compute manual TR
    high = sheet_df["High"].values
    low = sheet_df["Low"].values
    close = sheet_df["Close"].values
    
    tr = [high[0] - low[0]]
    for i in range(1, len(sheet_df)):
        prev_c = close[i-1]
        tr_val = max(high[i] - low[i], abs(high[i] - prev_c), abs(low[i] - prev_c))
        tr.append(tr_val)
    tr = np.array(tr)
    
    # Compute ATRs
    manual_atr_14 = compute_wilder_atr(tr, 14)
    manual_atr_200 = compute_wilder_atr(tr, 200)
    
    # Compare
    sheet_atr_14 = sheet_df["ATR (14)"].values
    sheet_atr_200 = sheet_df["ATR (200)"].values
    
    diff_14 = np.abs(manual_atr_14 - sheet_atr_14)
    diff_200 = np.abs(manual_atr_200 - sheet_atr_200)
    
    print("Wilder ATR 14 vs Sheet ATR (14):")
    print(f"  Max Diff: {np.max(diff_14):.6f}")
    print(f"  Mean Diff: {np.mean(diff_14):.6f}")
    
    print("\nWilder ATR 200 vs Sheet ATR (200):")
    print(f"  Max Diff: {np.max(diff_200):.6f}")
    print(f"  Mean Diff: {np.mean(diff_200):.6f}")
    
    # Print a few sample comparisons
    print("\nFirst 5 rows:")
    for i in range(5):
        print(f"  Row {i} | Sheet ATR14: {sheet_atr_14[i]:.4f} | Manual ATR14: {manual_atr_14[i]:.4f} | Sheet ATR200: {sheet_atr_200[i]:.4f} | Manual ATR200: {manual_atr_200[i]:.4f}")
        
    print("\nRows around 200:")
    for i in range(198, 203):
        print(f"  Row {i} | Sheet ATR200: {sheet_atr_200[i]:.4f} | Manual ATR200: {manual_atr_200[i]:.4f}")
