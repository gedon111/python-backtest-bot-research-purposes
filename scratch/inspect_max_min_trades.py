import sqlite3
import pandas as pd

conn = sqlite3.connect("backtest_results.db")

print("==========================================================================================")
print("              MAX GAIN AND LOSS TRADES INSPECTOR ACROSS QUALITY THRESHOLDS")
print("==========================================================================================")

for q in [0, 1, 2, 3]:
    trades = pd.read_sql_query(f"SELECT * FROM trades WHERE min_ob_quality = {q} ORDER BY pnl_pct DESC", conn)
    
    if trades.empty:
        print(f"\nQuality {q}: No trades found.")
        continue
        
    max_gain_trade = trades.iloc[0]
    max_loss_trade = trades.iloc[-1]
    
    print(f"\n--- Quality {q} ---")
    print(f"  Max Gain Trade (+{max_gain_trade['pnl_pct']:.4f}%):")
    print(f"    - Trade ID:     {max_gain_trade['trade_id']}")
    print(f"    - Side:         {max_gain_trade['side']}")
    print(f"    - Entry Time:   {pd.to_datetime(max_gain_trade['entry_time'], unit='s') if max_gain_trade['entry_time'] > 1000000 else max_gain_trade['entry_time']}")
    print(f"    - Exit Time:    {pd.to_datetime(max_gain_trade['exit_time'], unit='s') if max_gain_trade['exit_time'] > 1000000 else max_gain_trade['exit_time']}")
    print(f"    - Entry Price:  {max_gain_trade['entry_price']:.2f}")
    print(f"    - Exit Price:   {max_gain_trade['exit_price']:.2f}")
    print(f"    - Exit Reason:  {max_gain_trade['exit_reason']}")
    print(f"    - Entry OB ID:  {max_gain_trade['entry_ob_id']}")

    print(f"  Max Loss Trade ({max_loss_trade['pnl_pct']:.4f}%):")
    print(f"    - Trade ID:     {max_loss_trade['trade_id']}")
    print(f"    - Side:         {max_loss_trade['side']}")
    print(f"    - Entry Time:   {pd.to_datetime(max_loss_trade['entry_time'], unit='s') if max_loss_trade['entry_time'] > 1000000 else max_loss_trade['entry_time']}")
    print(f"    - Exit Time:    {pd.to_datetime(max_loss_trade['exit_time'], unit='s') if max_loss_trade['exit_time'] > 1000000 else max_loss_trade['exit_time']}")
    print(f"    - Entry Price:  {max_loss_trade['entry_price']:.2f}")
    print(f"    - Exit Price:   {max_loss_trade['exit_price']:.2f}")
    print(f"    - Exit Reason:  {max_loss_trade['exit_reason']}")
    print(f"    - Entry OB ID:  {max_loss_trade['entry_ob_id']}")

print("==========================================================================================")
conn.close()
