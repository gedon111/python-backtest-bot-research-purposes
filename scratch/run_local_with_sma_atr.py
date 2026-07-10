import pandas as pd
import numpy as np
import sys
import os
import types

sys.path.append(os.path.abspath("."))

# Set up module mock
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

# Let's monkey-patch compute_indicators in bot to use SMA for ATR
def compute_indicators_patched(df, kdj_period=9, atr_period=14):
    df = df.copy()
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # MACD (12, 26, 9)
    ema_fast         = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow         = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD']       = ema_fast - ema_slow
    df['MACD_signal']= df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist']  = df['MACD'] - df['MACD_signal']

    # KDJ
    n        = int(kdj_period)
    low_min  = df['low'].rolling(n,  min_periods=1).min()
    high_max = df['high'].rolling(n, min_periods=1).max()
    denom    = (high_max - low_min).replace(0, np.nan)
    rsv      = ((df['close'] - low_min) / denom * 100).fillna(50)
    alpha    = 1.0 / 3.0
    df['K']  = rsv.ewm(alpha=alpha, adjust=False).mean()
    df['D']  = df['K'].ewm(alpha=alpha, adjust=False).mean()
    df['J']  = 3 * df['K'] - 2 * df['D']
    df['RSV']= rsv

    # ATR — patched to use SMA matching the Google Sheet
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low']  - prev_close).abs()
    ], axis=1).max(axis=1)
    df['ATR']     = tr.rolling(atr_period, min_periods=1).mean()
    df['ATR_200'] = tr.rolling(200,         min_periods=1).mean()

    return df

# Apply monkey patch
bot.compute_indicators = compute_indicators_patched

from scratch.parse_sheet_trades import extract_trades_from_csv

def run_simulation_and_compare(q):
    # Load raw candles
    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    
    # Run simulation
    out_df = bot.simulate_trades(df.copy(), min_ob_quality=q)
    local_trades = out_df.attrs.get("trades_df", pd.DataFrame())
    
    if not local_trades.empty:
        local_trades["entry_time"] = local_trades["entry_idx"].apply(lambda x: df.at[int(x), "open_time"].strftime('%Y-%m-%d %H:%M:%S'))
        local_trades["exit_time"] = local_trades["exit_idx"].apply(lambda x: df.at[int(x), "open_time"].strftime('%Y-%m-%d %H:%M:%S'))
        local_trades["exit_type"] = local_trades["exit_idx"].apply(lambda x: out_df.at[int(x), "Trade_Status"])
        local_trades.rename(columns={"entry": "entry_price", "exit": "exit_price"}, inplace=True)
    else:
        local_trades = pd.DataFrame(columns=["side", "entry_time", "entry_price", "exit_time", "exit_price", "exit_type", "pnl_pct", "hold_bars"])
        
    sheet_file = f"scratch/Quality_{q}.csv"
    sheet_trades = extract_trades_from_csv(sheet_file)
    
    # Standardize times
    sheet_trades["entry_time"] = pd.to_datetime(sheet_trades["entry_time"]).dt.strftime('%Y-%m-%d %H:%M:%S')
    if not local_trades.empty:
        local_trades["entry_time"] = pd.to_datetime(local_trades["entry_time"]).dt.strftime('%Y-%m-%d %H:%M:%S')
        
    print(f"\n==========================================")
    print(f"SMA-ATR COMPARISON FOR QUALITY {q}")
    print(f"Sheet trades count: {len(sheet_trades)}")
    print(f"Local trades count: {len(local_trades)}")
    
    sheet_set = set(sheet_trades["entry_time"])
    local_set = set(local_trades["entry_time"])
    
    only_sheet = sheet_set - local_set
    only_local = local_set - sheet_set
    common = sheet_set & local_set
    
    print(f"Trades only in Sheet ({len(only_sheet)}):")
    for t in sorted(list(only_sheet)):
        row = sheet_trades[sheet_trades["entry_time"] == t].iloc[0]
        print(f"  {row['side']} Entry: {t} | Exit: {row['exit_time']} | Type: {row['exit_type']} | PnL: {row['pnl_pct']}%")
        
    print(f"Trades only in Local v9 with SMA-ATR ({len(only_local)}):")
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
        run_simulation_and_compare(q)
