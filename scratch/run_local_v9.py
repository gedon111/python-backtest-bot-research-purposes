import pandas as pd
import numpy as np
import sys
import os

# Add workspace root to python path to import functions
sys.path.append(os.path.abspath("."))
from importlib import import_module

# Import from 'Binance backtest bot.py'
# Since the filename has spaces, we can use import_module or just copy/paste the functions we need,
# but import_module is cleaner if we can import it.
# Mock binance client before importing bot
import sys
from unittest.mock import MagicMock
mock_binance = MagicMock()
mock_client = MagicMock()
# Make sure client.ping() doesn't fail or do anything
mock_client.return_value = MagicMock()
mock_binance.client.Client = mock_client
sys.modules['binance'] = mock_binance
sys.modules['binance.client'] = mock_binance.client

import importlib.util
spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

def run_local_simulation():
    # Load cached candles
    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    
    # Run simulation for all quality levels
    for q in [0, 1, 2, 3]:
        # Copy df to avoid modification side effects
        df_run = df.copy()
        
        # Run simulate_trades
        out_df = bot.simulate_trades(df_run, min_ob_quality=q)
        
        # Extract trade list from out_df.attrs
        trades_df = out_df.attrs.get("trades_df", pd.DataFrame())
        stats = out_df.attrs.get("trade_stats", {})
        
        print(f"\n=== Local v9 Quality {q} ===")
        print(f"Total Trades: {stats.get('Total Trades')}")
        print(f"Net Return (%): {stats.get('Total Net Return (%)'):.4f}%")
        print(f"Win Rate (%): {stats.get('Win Rate (%)'):.4f}%")
        
        if not trades_df.empty:
            # Map index to time for printing
            trades_df["entry_time"] = trades_df["entry_idx"].apply(lambda x: df.at[int(x), "open_time"])
            trades_df["exit_time"] = trades_df["exit_idx"].apply(lambda x: df.at[int(x), "open_time"])
            print(trades_df[["side", "entry_time", "entry_price" if "entry_price" in trades_df else "entry", 
                             "exit_time", "exit_price" if "exit_price" in trades_df else "exit", "pnl_pct", "hold_bars"]].head(5))

if __name__ == "__main__":
    run_local_simulation()
