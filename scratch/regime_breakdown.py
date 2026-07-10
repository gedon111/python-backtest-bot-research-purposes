import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Load bot module
sys.path.append(os.path.abspath("."))
import importlib.util
spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

def parse_regime(entry_dt):
    y, m, d = entry_dt.year, entry_dt.month, entry_dt.day
    # Bear Market: 2022-01-01 to 2022-12-31
    if y == 2022:
        return "Bear Market"
    # Bull Market: 2023-01-01 to 2024-03-31 and 2024-10-01 to 2025-03-31
    elif (y == 2023) or (y == 2024 and m <= 3) or (y == 2024 and m >= 10) or (y == 2025 and m <= 3):
        return "Bull Market"
    # Choppy / Sideways: 2024-04-01 to 2024-09-30 and 2025-04-01 to 2025-12-31
    elif (y == 2024 and m >= 4 and m <= 9) or (y == 2025 and m >= 4 and m <= 12):
        return "Choppy / Sideways"
    return "Other"

def get_stats_dict(trades_df):
    if trades_df.empty:
        return {"trades": 0, "wr": 0.0, "pnl": 0.0, "avg": 0.0}
    total_trades = len(trades_df)
    wins = (trades_df['pnl_pct'] > 0).sum()
    win_rate = (wins / total_trades) * 100
    net_return = trades_df['pnl_pct'].sum()
    avg_return = trades_df['pnl_pct'].mean()
    return {"trades": total_trades, "wr": win_rate, "pnl": net_return, "avg": avg_return}

def get_regime_breakdown(trades_df):
    if trades_df.empty:
        return {}
    trades_df = trades_df.copy()
    trades_df['entry_datetime'] = pd.to_datetime(trades_df['entry_idx'].apply(lambda x: df.at[int(x), 'open_time']))
    trades_df['regime'] = trades_df['entry_datetime'].apply(parse_regime)
    
    breakdown = {}
    for r in ["Bear Market", "Bull Market", "Choppy / Sideways"]:
        r_df = trades_df[trades_df['regime'] == r]
        breakdown[r] = get_stats_dict(r_df)
    return breakdown

# Load cached candles
csv_path = "artifacts/candles.csv"
if not os.path.isfile(csv_path):
    print(f"Error: {csv_path} not found. Please run export_gui_data.py first.")
    sys.exit(1)

df = pd.read_csv(csv_path)
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)
df["time"] = df["open_time"].apply(lambda x: int(x.timestamp()))

# 1. Simulate Original Heuristic Parameters
original_params = {
    "sl_ratio_min": 0.015,
    "kdj_j_long_cap": 60.0,
    "kdj_k_long_cap": 50.0,
    "kdj_k_short_floor": 70.0,
    "kdj_j_short_cap": 100.0,
    "atr_mult_exit": 1.8,
    "atr_mult_be": 2.0,
    "rr_min": 1.5
}
sim_orig = bot.simulate_trades(df.copy(), min_ob_quality=1, iteration_parameters=original_params)
trades_orig = sim_orig.attrs.get("trades_df", pd.DataFrame())

# 2. Simulate Swept/Optimized Parameters
swept_params = {
    "sl_ratio_min": 0.017616664900842346,
    "kdj_j_long_cap": 68.6640127278245,
    "kdj_k_long_cap": 44.43514424742912,
    "kdj_k_short_floor": 67.6273137366968,
    "kdj_j_short_cap": 108.09108014739797,
    "atr_mult_exit": 2.2360351617902396,
    "atr_mult_be": 1.5837844460426838,
    "rr_min": 1.4592970215721577
}
sim_swept = bot.simulate_trades(df.copy(), min_ob_quality=1, iteration_parameters=swept_params)
trades_swept = sim_swept.attrs.get("trades_df", pd.DataFrame())

# Calculate metrics
orig_overall = get_stats_dict(trades_orig)
swept_overall = get_stats_dict(trades_swept)

orig_regimes = get_regime_breakdown(trades_orig)
swept_regimes = get_regime_breakdown(trades_swept)

# Helper to format warning
def fmt_warn(count):
    return " (Warning: Insufficient sample)" if count < 5 else ""

print("==================================================================================")
print("  SIDE-BY-SIDE PARAMETER SET COMPARISON (BUG-FIXED PIPELINE)")
print("==================================================================================")

print(f"\n{'Metric / Regime':<25} | {'Original Parameters':<30} | {'Swept/Optimized Parameters':<30}")
print("-" * 90)

# Overall stats
print(f"{'Overall Trade Count':<25} | {orig_overall['trades']:<30} | {swept_overall['trades']:<30}")
print(f"{'Overall Win Rate':<25} | {orig_overall['wr']:.2f}% | {swept_overall['wr']:.2f}%")
print(f"{'Overall Net Return':<25} | {orig_overall['pnl']:.2f}% | {swept_overall['pnl']:.2f}%")
print(f"{'Overall Avg Return/Trade':<25} | {orig_overall['avg']:.2f}% | {swept_overall['avg']:.2f}%")

print("-" * 90)
print("Regime breakdowns:")

for r in ["Bear Market", "Bull Market", "Choppy / Sideways"]:
    orig_r = orig_regimes.get(r, {"trades": 0, "wr": 0.0, "pnl": 0.0})
    swept_r = swept_regimes.get(r, {"trades": 0, "wr": 0.0, "pnl": 0.0})
    
    orig_str = f"{orig_r['trades']} tr | {orig_r['wr']:.2f}% WR | {orig_r['pnl']:.2f}% PnL" + fmt_warn(orig_r['trades'])
    swept_str = f"{swept_r['trades']} tr | {swept_r['wr']:.2f}% WR | {swept_r['pnl']:.2f}% PnL" + fmt_warn(swept_r['trades'])
    
    print(f"Regime: {r:<17} | {orig_str:<30} | {swept_str:<30}")

print("==================================================================================")
