import sys
import os
import pandas as pd

sys.path.append(os.path.abspath("."))
import importlib.util
spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)
df["time"] = df["open_time"].apply(lambda x: int(x.timestamp()))

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

print("==================================================================================")
print("  PERFORMANCE STATS ACROSS ALL OB QUALITY LEVELS (SWEPT PARAMETERS)")
print("==================================================================================")
print(f"{'Quality':<8} | {'Trades':<8} | {'Win Rate':<10} | {'Simple Net PnL':<15} | {'Compounded PnL':<15}")
print("-" * 70)

for q in [0, 1, 2, 3]:
    sim_df = bot.simulate_trades(df.copy(), min_ob_quality=q, iteration_parameters=swept_params)
    trades = sim_df.attrs.get("trades_df", pd.DataFrame())
    
    if trades.empty:
        print(f"{q:<8} | {'0':<8} | {'0.00%':<10} | {'0.00%':<15} | {'0.00%':<15}")
        continue
        
    total_trades = len(trades)
    wins = (trades['pnl_pct'] > 0).sum()
    wr = (wins / total_trades) * 100
    simple_pnl = trades['pnl_pct'].sum()
    
    compounded = 100.0
    for p in trades['pnl_pct'].values:
        compounded *= (1 + p/100)
    compounded_pnl = compounded - 100.0
    
    # Adjusted calculations (subtracting 0.15% drag per trade)
    adj_simple = simple_pnl - total_trades * 0.15
    adj_compounded = 100.0
    for p in trades['pnl_pct'].values:
        adj_compounded *= (1 + (p - 0.15)/100)
    adj_compounded_pnl = adj_compounded - 100.0
    
    print(f"{q:<8} | {total_trades:<8} | {wr:.2f}% | {simple_pnl:+.2f}% ({adj_simple:+.2f}%) | {compounded_pnl:+.2f}% ({adj_compounded_pnl:+.2f}%)")

print("==================================================================================")
