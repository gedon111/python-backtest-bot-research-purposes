import pandas as pd
import numpy as np
import sys
import os

# Set up module mock
import types
binance_mod = types.ModuleType('binance')
binance_client_mod = types.ModuleType('binance.client')
class DummyClient:
    KLINE_INTERVAL_4HOUR = '4h'
    def __init__(self, *args, **kwargs): pass
    def ping(self): pass
    def get_klines(self, *args, **kwargs): return []
binance_client_mod.Client = DummyClient
binance_mod.client = binance_client_mod
sys.modules['binance'] = binance_mod
sys.modules['binance.client'] = binance_client_mod

import importlib.util
spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

def compare_indicators():
    sheet_df = pd.read_csv("scratch/Quality_1.csv")
    sheet_df.columns = [c.strip() for c in sheet_df.columns]
    
    # Load local raw candles
    local_raw = pd.read_csv("artifacts/candles.csv")
    local_raw["open_time"] = pd.to_datetime(local_raw["open_time"])
    
    # Compute indicators locally
    local_df = bot.compute_indicators(local_raw)
    
    # Standardize times
    sheet_df["Date/Time"] = pd.to_datetime(sheet_df["Date/Time"])
    
    # Merge on Date/Time
    merged = pd.merge(sheet_df, local_df, left_on="Date/Time", right_on="open_time", suffixes=("_sheet", "_local"))
    
    print(f"Merged rows: {len(merged)}")
    
    # Compare key columns
    cols_to_compare = [
        ("MACD", "MACD"),
        ("MACD_hist", "MACD_hist"),
        ("K", "K"),
        ("D", "D"),
        ("J", "J"),
        ("ATR (14)", "ATR"),
        ("ATR (200)", "ATR_200")
    ]
    
    for s_col, l_col in cols_to_compare:
        s_key = s_col + "_sheet" if (s_col in sheet_df.columns and s_col in local_df.columns) else s_col
        l_key = l_col + "_local" if (l_col in sheet_df.columns and l_col in local_df.columns) else l_col
        s_vals = merged[s_key].astype(float)
        l_vals = merged[l_key].astype(float)
        diff = (s_vals - l_vals).abs()
        max_diff = diff.max()
        mean_diff = diff.mean()
        print(f"Column {s_col} vs {l_col}:")
        print(f"  Max Diff: {max_diff:.6f}")
        print(f"  Mean Diff: {mean_diff:.6f}")
        # Show a few sample rows where diff is largest
        if max_diff > 1e-4:
            largest_diff_idx = diff.nlargest(3).index
            print("  Largest differences:")
            for idx in largest_diff_idx:
                row = merged.loc[idx]
                print(f"    Date: {row['Date/Time']} | Sheet: {row[s_col]:.4f} | Local: {row[l_col]:.4f} | Diff: {diff.loc[idx]:.4f}")

if __name__ == "__main__":
    compare_indicators()
