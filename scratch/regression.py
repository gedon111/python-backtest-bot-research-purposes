import os
import json
import sys
import pandas as pd
import numpy as np
import importlib.util

# Load the strategy engine. As of the single-file consolidation,
# research_analysis.py (repo root) is the canonical copy of compute_
# indicators()/compute_smc()/simulate_trades() -- the former
# src/Binance backtest bot.py is retired to legacy_pre_consolidation/ and no
# longer used at runtime. Still loaded dynamically (not a plain `import`)
# for consistency with this repo's established pattern, even though
# research_analysis.py's filename would now support a normal import.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bot_path = os.path.join(BASE_DIR, "research_analysis.py")
spec = importlib.util.spec_from_file_location("bot", bot_path)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

FIXTURES_DIR = os.path.join(BASE_DIR, "scratch", "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)

TRADES_FIXTURE_PATH = os.path.join(FIXTURES_DIR, "baseline_trades.json")
BARS_FIXTURE_PATH = os.path.join(FIXTURES_DIR, "baseline_bars.parquet")
CANDLES_CACHE_PATH = os.path.join(BASE_DIR, "artifacts", "candles.csv")

def generate_fixtures():
    print("Reading cached candles snapshot...")
    df = pd.read_csv(CANDLES_CACHE_PATH)
    df["open_time"] = pd.to_datetime(df["open_time"])
    
    print("Computing indicators...")
    df = bot.compute_indicators(df)
    
    print("Detecting Order Blocks...")
    obs = bot.compute_smc(df)
    
    print("Simulating baseline trades (min_ob_quality=0)...")
    sim_df = bot.simulate_trades(df.copy(), min_ob_quality=0)
    stats = sim_df.attrs.get("trade_stats", {})
    trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
    
    print("\n--- Headline Results ---")
    print(f"Total Trades:           {stats.get('Total Trades')}")
    print(f"Win Rate:               {stats.get('Win Rate (%)'):.2f}%")
    print(f"Total Net Return:       {stats.get('Total Net Return (%)'):+.2f}%")
    print(f"Avg Return/Trade:       {stats.get('Avg Return/Trade (%)'):+.2f}%")
    if not trades_df.empty:
        print(f"SD Return/Trade:        {trades_df['pnl_pct'].std():.2f}%")
    print(f"Total Order Blocks:     {len(obs)}")
    fvg_count = sum(1 for ob in obs if ob.get('quality_fvg'))
    print(f"FVG Criterion True:     {fvg_count} / {len(obs)} ({fvg_count/len(obs)*100:.1f}%)")
    
    # Assert exact match to paper headline numbers
    assert stats.get('Total Trades') == 27, f"Expected 27 trades, got {stats.get('Total Trades')}"
    assert abs(stats.get('Win Rate (%)') - 70.37037) < 0.01, f"Unexpected Win Rate: {stats.get('Win Rate (%)')}"
    assert abs(stats.get('Total Net Return (%)') - 30.30645) < 0.05, f"Unexpected Total Net Return: {stats.get('Total Net Return (%)')}"
    assert abs(stats.get('Avg Return/Trade (%)') - 1.12246) < 0.01, f"Unexpected Avg Return/Trade: {stats.get('Avg Return/Trade (%)')}"
    assert abs(trades_df['pnl_pct'].std() - 2.4101) < 0.02, f"Unexpected SD: {trades_df['pnl_pct'].std()}"
    assert len(obs) == 761, f"Expected 761 OBs, got {len(obs)}"
    assert fvg_count == 253, f"Expected 253 FVG OBs, got {fvg_count}"

    # Serialize baseline_trades.json
    trades_records = trades_df.to_dict(orient="records")
    with open(TRADES_FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(trades_records, f, indent=2, default=str)
    print(f"\nSuccessfully serialized baseline trades to {TRADES_FIXTURE_PATH}")
    
    # Serialize baseline_bars.parquet
    bars_df = df[["open_time", "close", "MACD_hist", "K", "D", "J", "ATR", "ATR_200"]].copy()
    bars_df.to_parquet(BARS_FIXTURE_PATH, index=False)
    print(f"Successfully serialized baseline bars & indicators to {BARS_FIXTURE_PATH}")

def run_regression_check():
    if not os.path.exists(TRADES_FIXTURE_PATH) or not os.path.exists(BARS_FIXTURE_PATH):
        print("Fixtures not found. Generating initial fixtures...")
        generate_fixtures()
        print("Fixtures generated successfully.")
        return True

    print("Executing regression comparison against baseline fixtures...")
    df = pd.read_csv(CANDLES_CACHE_PATH)
    df["open_time"] = pd.to_datetime(df["open_time"])
    df = bot.compute_indicators(df)
    obs = bot.compute_smc(df)
    sim_df = bot.simulate_trades(df.copy(), min_ob_quality=0)
    current_trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())

    # Load fixtures
    with open(TRADES_FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixture_trades = json.load(f)
    fixture_trades_df = pd.DataFrame(fixture_trades)

    fixture_bars_df = pd.read_parquet(BARS_FIXTURE_PATH)

    # 1. Compare bars & indicators
    for col in ["MACD_hist", "K", "D", "J", "ATR", "ATR_200"]:
        diff = np.abs(df[col].values - fixture_bars_df[col].values)
        max_diff_idx = np.argmax(diff)
        if diff[max_diff_idx] > 1e-6:
            print(f"FAIL: Indicator {col} diverged at bar index {max_diff_idx}: current={df[col].iloc[max_diff_idx]}, fixture={fixture_bars_df[col].iloc[max_diff_idx]}")
            sys.exit(1)

    # 2/3. Align trades by entry_idx (not list position) and report the first
    # divergent trade. A bare trade-count mismatch is reported only as
    # supplementary context, never as the sole diagnostic.
    fixture_by_entry = {int(row["entry_idx"]): row for _, row in fixture_trades_df.iterrows()}
    current_by_entry = {int(row["entry_idx"]): row for _, row in current_trades_df.iterrows()}

    fixture_entries = sorted(fixture_by_entry.keys())
    current_entries = sorted(current_by_entry.keys())

    missing_in_current = [e for e in fixture_entries if e not in current_by_entry]
    extra_in_current = [e for e in current_entries if e not in fixture_by_entry]

    check_cols = ["side", "entry_idx", "exit_idx", "entry", "exit", "stop_loss", "take_profit", "pnl_pct", "exit_reason"]

    first_divergence = None
    for entry_idx in fixture_entries:
        if entry_idx not in current_by_entry:
            continue  # reported via missing_in_current below
        cur = current_by_entry[entry_idx]
        fix = fixture_by_entry[entry_idx]
        for field in check_cols:
            c_val = cur[field]
            f_val = fix[field]
            if isinstance(c_val, (int, np.integer, str)):
                match = str(c_val) == str(f_val)
            else:
                match = abs(float(c_val) - float(f_val)) <= 1e-5
            if not match:
                first_divergence = (entry_idx, field, c_val, f_val)
                break
        if first_divergence:
            break

    if missing_in_current or extra_in_current or first_divergence:
        print("FAIL: Trade-level divergence detected (aligned by entry_idx).")
        if first_divergence:
            entry_idx, field, c_val, f_val = first_divergence
            print(f"  First divergent trade: entry_idx={entry_idx}, field='{field}', current={c_val}, fixture={f_val}")
        if missing_in_current:
            print(f"  Trades in fixture but MISSING from current run (first: entry_idx={missing_in_current[0]}): {missing_in_current}")
        if extra_in_current:
            print(f"  Trades in current run but NOT in fixture (first: entry_idx={extra_in_current[0]}): {extra_in_current}")
        if len(current_trades_df) != len(fixture_trades_df):
            print(f"  (Trade count also differs: current={len(current_trades_df)}, fixture={len(fixture_trades_df)})")
        sys.exit(1)

    print("PASS: Fresh run matches golden-master fixture EXACTLY across all bars, indicators, and 27 trades!")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        generate_fixtures()
    else:
        run_regression_check()
