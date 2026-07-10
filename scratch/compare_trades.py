import pandas as pd
import numpy as np
import sys
import os
import types

sys.path.append(os.path.abspath("."))

# Robust mock of binance and binance.client modules
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

from scratch.parse_sheet_trades import extract_trades_from_csv

def compare_for_quality(q):
    sheet_file = f"scratch/Quality_{q}.csv"
    sheet_trades = extract_trades_from_csv(sheet_file)
    
    # Run local simulation
    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    out_df = bot.simulate_trades(df.copy(), min_ob_quality=q)
    local_trades = out_df.attrs.get("trades_df", pd.DataFrame())
    
    if not local_trades.empty:
        local_trades["entry_time"] = local_trades["entry_idx"].apply(lambda x: df.at[int(x), "open_time"].strftime('%Y-%m-%d %H:%M:%S'))
        local_trades["exit_time"] = local_trades["exit_idx"].apply(lambda x: df.at[int(x), "open_time"].strftime('%Y-%m-%d %H:%M:%S'))
        local_trades["exit_type"] = local_trades["exit_idx"].apply(lambda x: out_df.at[int(x), "Trade_Status"])
        local_trades.rename(columns={"entry": "entry_price", "exit": "exit_price"}, inplace=True)
    else:
        local_trades = pd.DataFrame(columns=["side", "entry_time", "entry_price", "exit_time", "exit_price", "exit_type", "pnl_pct", "hold_bars"])
        
    print(f"\n==========================================")
    print(f"COMPARISON FOR QUALITY {q}")
    print(f"Sheet trades count: {len(sheet_trades)}")
    print(f"Local trades count: {len(local_trades)}")
    
    # Standardize times
    sheet_trades["entry_time"] = pd.to_datetime(sheet_trades["entry_time"]).dt.strftime('%Y-%m-%d %H:%M:%S')
    if not local_trades.empty:
        local_trades["entry_time"] = pd.to_datetime(local_trades["entry_time"]).dt.strftime('%Y-%m-%d %H:%M:%S')
        
    # Find matching trades by entry_time
    sheet_set = set(sheet_trades["entry_time"])
    local_set = set(local_trades["entry_time"])
    
    only_sheet = sheet_set - local_set
    only_local = local_set - sheet_set
    common = sheet_set & local_set
    
    print(f"Trades only in Sheet ({len(only_sheet)}):")
    for t in sorted(list(only_sheet)):
        row = sheet_trades[sheet_trades["entry_time"] == t].iloc[0]
        print(f"  {row['side']} Entry: {t} | Exit: {row['exit_time']} | Type: {row['exit_type']} | PnL: {row['pnl_pct']}%")
        
    print(f"Trades only in Local v9 ({len(only_local)}):")
    for t in sorted(list(only_local)):
        row = local_trades[local_trades["entry_time"] == t].iloc[0]
        print(f"  {row['side']} Entry: {t} | Exit: {row['exit_time']} | Type: {row['exit_type']} | PnL: {row['pnl_pct']:.2f}%")
        
    print(f"Common Trades Differences ({len(common)}):")
    diffs_found = 0
    for t in sorted(list(common)):
        s_row = sheet_trades[sheet_trades["entry_time"] == t].iloc[0]
        l_row = local_trades[local_trades["entry_time"] == t].iloc[0]
        
        diff = []
        if s_row["side"] != l_row["side"]:
            diff.append(f"Side: Sheet={s_row['side']} vs Local={l_row['side']}")
        if abs(s_row["entry_price"] - l_row["entry_price"]) > 1.0:
            diff.append(f"EntryPrice: Sheet={s_row['entry_price']:.2f} vs Local={l_row['entry_price']:.2f}")
        if s_row["exit_time"] != l_row["exit_time"]:
            diff.append(f"ExitTime: Sheet={s_row['exit_time']} vs Local={l_row['exit_time']}")
        if s_row["exit_type"] != l_row["exit_type"]:
            diff.append(f"ExitType: Sheet={s_row['exit_type']} vs Local={l_row['exit_type']}")
        if abs(s_row["pnl_pct"] - l_row["pnl_pct"]) > 0.05:
            diff.append(f"PnL: Sheet={s_row['pnl_pct']}% vs Local={l_row['pnl_pct']:.2f}%")
            
        if diff:
            diffs_found += 1
            print(f"  Entry: {t} ({s_row['side']}):")
            for d in diff:
                print(f"    - {d}")
    if diffs_found == 0:
        print("  No differences in common trades.")

if __name__ == "__main__":
    for q in [0, 1, 2, 3]:
        compare_for_quality(q)
