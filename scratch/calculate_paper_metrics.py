import sqlite3
import pandas as pd

conn = sqlite3.connect("backtest_results.db")
c = conn.cursor()

print("==========================================================================================")
print("              DETAILED BASELINE PAPER STATS ACROSS QUALITY THRESHOLDS (0, 1, 2, 3)")
print("==========================================================================================")

for q in [0, 1, 2, 3]:
    trades = pd.read_sql_query(f"SELECT * FROM trades WHERE min_ob_quality = {q}", conn)
    
    if trades.empty:
        print(f"\n--- Quality {q} ---")
        print("  No trades recorded.")
        continue
        
    total_trades = len(trades)
    wins = (trades['pnl_pct'] > 0).sum()
    wr = (wins / total_trades) * 100
    
    simple_pnl = trades['pnl_pct'].sum()
    avg_pnl = trades['pnl_pct'].mean()
    max_gain = trades['pnl_pct'].max()
    max_loss = trades['pnl_pct'].min()
    
    # Exit reason distribution
    exit_counts = trades['exit_reason'].value_counts()
    exit_pcts = (exit_counts / total_trades) * 100
    
    print(f"\n--- Quality {q} ---")
    print(f"  Closed Trades:      {total_trades}")
    print(f"  Win Rate:           {wr:.2f}% ({wins} wins / {total_trades - wins} losses)")
    print(f"  Net Return (Simple): {simple_pnl:+.4f}%")
    print(f"  Average PnL / Trade: {avg_pnl:+.4f}%")
    print(f"  Max Single Gain:     {max_gain:+.4f}%")
    print(f"  Max Single Loss:     {max_loss:+.4f}%")
    print("  Exit Reason Distribution:")
    for reason, count in exit_counts.items():
        pct = (count / total_trades) * 100
        print(f"    - {reason:<28}: {count:<3} ({pct:.2f}%)")

print("==========================================================================================")
conn.close()
