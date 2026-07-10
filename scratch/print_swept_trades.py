import sqlite3

conn = sqlite3.connect("backtest_results.db")
c = conn.cursor()
query = """
    SELECT trade_id, side, datetime(entry_time, 'unixepoch') AS entry_date, 
           datetime(exit_time, 'unixepoch') AS exit_date, entry_price, exit_price, 
           pnl_pct, exit_reason 
    FROM swept_trades 
    ORDER BY entry_time
"""
rows = c.execute(query).fetchall()

print(f"{'ID':<4} | {'Side':<5} | {'Entry Time (UTC)':<19} | {'Exit Time (UTC)':<19} | {'Entry Px':<10} | {'Exit Px':<10} | {'PnL%':<7} | {'Exit Reason':<25}")
print("-" * 115)
for r in rows:
    print(f"{r[0]:<4} | {r[1]:<5} | {r[2]:<19} | {r[3]:<19} | {r[4]:<10.2f} | {r[5]:<10.2f} | {r[6]:<+7.2f} | {r[7]:<25}")
conn.close()
