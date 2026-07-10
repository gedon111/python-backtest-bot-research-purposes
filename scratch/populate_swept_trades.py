import sys
import os
import sqlite3
import pandas as pd

# Load bot module
sys.path.append(os.path.abspath("."))
import importlib.util
spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

# Load candles
df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)
df["time"] = df["open_time"].apply(lambda x: int(x.timestamp()))

# Swept parameters
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

# Run simulation
sim_df = bot.simulate_trades(df.copy(), min_ob_quality=1, iteration_parameters=swept_params)
trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())

# Save to SQL
conn = sqlite3.connect("backtest_results.db")
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS swept_trades")
c.execute("""
    CREATE TABLE swept_trades (
        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        side TEXT,
        entry_time INTEGER,
        exit_time INTEGER,
        entry_price REAL,
        exit_price REAL,
        pnl_pct REAL,
        exit_reason TEXT
    )
""")

for _, t in trades_df.iterrows():
    # Find timestamps from entry_idx and exit_idx
    entry_idx = int(t["entry_idx"])
    exit_idx = int(t["exit_idx"])
    entry_time = int(df.at[entry_idx, "time"])
    exit_time = int(df.at[exit_idx, "time"])
    
    c.execute("""
        INSERT INTO swept_trades (side, entry_time, exit_time, entry_price, exit_price, pnl_pct, exit_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        t["side"],
        entry_time,
        exit_time,
        float(t["entry"]),
        float(t["exit"]),
        float(t["pnl_pct"]),
        t["exit_reason"]
    ))

conn.commit()
print(f"Successfully populated swept_trades table with {len(trades_df)} rows.")
conn.close()
