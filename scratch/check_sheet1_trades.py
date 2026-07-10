import sys
import os
sys.path.append(os.path.abspath("."))
import pandas as pd
from scratch.parse_sheet_trades import extract_trades_from_csv

if __name__ == "__main__":
    try:
        trades_df = extract_trades_from_csv("scratch/Sheet1.csv")
        print(f"--- Sheet1 Trades: {len(trades_df)} ---")
        if not trades_df.empty:
            print("First 5 trades in Sheet1:")
            print(trades_df[["side", "entry_time", "entry_price", "exit_time", "exit_type", "pnl_pct"]].head(5))
            print("Last 5 trades in Sheet1:")
            print(trades_df[["side", "entry_time", "entry_price", "exit_time", "exit_type", "pnl_pct"]].tail(5))
    except Exception as e:
        print("Error checking Sheet1 trades:", e)
