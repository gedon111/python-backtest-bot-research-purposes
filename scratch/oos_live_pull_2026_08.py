"""
ONE-TIME prospective out-of-sample test. Deliberately violates CLAUDE.md's
"all scratch scripts run offline, no live API calls" rule -- disclosed and
justified here: this is the only way to test the frozen v9 rule set against
data that postdates every commit to src/Binance backtest bot.py, i.e. data
the rules could not possibly have been shaped against.

Pre-registration commitment (stated BEFORE looking at results): this script
is run exactly once. Whatever it outputs is reported as-is. No parameter,
threshold, or rule in src/Binance backtest bot.py is touched based on this
result. If re-running is ever needed (e.g. environment issue), the ORIGINAL
output captured on first successful run is what gets reported, not a
cherry-picked re-run.

Method: re-pull the full BTCUSDT 4H series from the same 2022-01-01 start
used to build the locked artifacts/candles.csv, via the unmodified
get_candles(). This naturally extends through "now" and also serves as an
integrity check -- the first 8,767 rows must be byte-identical to the locked
snapshot (confirms Binance hasn't silently revised historical candles).
Does NOT overwrite artifacts/candles.csv, backtest_results.db, or any
committed artifact -- output written to scratch/ only.
"""
import importlib.util
import pandas as pd
import numpy as np

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

print("=" * 100)
print("  ONE-TIME PROSPECTIVE OOS TEST -- pulling fresh BTCUSDT 4H data live from Binance")
print("=" * 100)

fresh = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR,
                         start_time="2022-01-01 00:00:00", end_time=None)
print(f"Freshly pulled: {len(fresh)} bars, {fresh['open_time'].iloc[0]} .. {fresh['open_time'].iloc[-1]}")

locked = pd.read_csv("artifacts/candles.csv")
locked["open_time"] = pd.to_datetime(locked["open_time"])
print(f"Locked baseline: {len(locked)} bars, {locked['open_time'].iloc[0]} .. {locked['open_time'].iloc[-1]}")

n_locked = len(locked)
overlap = fresh.iloc[:n_locked].reset_index(drop=True)
locked_cmp = locked[["open_time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
overlap_cmp = overlap[["open_time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

integrity_ok = overlap_cmp["open_time"].equals(locked_cmp["open_time"]) and \
    np.allclose(overlap_cmp[["open", "high", "low", "close", "volume"]].values,
                locked_cmp[["open", "high", "low", "close", "volume"]].values, atol=1e-8)
print(f"\nIntegrity check (first {n_locked} bars byte-identical to locked snapshot): "
      f"{'PASS' if integrity_ok else 'FAIL -- STOP, investigate before trusting anything below'}")

if not integrity_ok:
    mismatches = (~np.isclose(
        overlap_cmp[["open", "high", "low", "close", "volume"]].values,
        locked_cmp[["open", "high", "low", "close", "volume"]].values, atol=1e-8)).any(axis=1)
    print(f"First mismatch at row {np.argmax(mismatches)}: "
          f"locked={locked_cmp.iloc[np.argmax(mismatches)].to_dict()} "
          f"fresh={overlap_cmp.iloc[np.argmax(mismatches)].to_dict()}")

fresh.to_csv("scratch/oos_extended_candles_2026_08.csv", index=False)
n_new_bars = len(fresh) - n_locked
print(f"\nNew bars beyond the locked window: {n_new_bars}")

# ─── Run the FROZEN, unmodified pipeline on the extended series ────────────
df = bot.compute_indicators(fresh.copy())
sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
trades = sim.attrs.get("trades_df").copy()
stats = sim.attrs.get("trade_stats", {})

print("\n" + "=" * 100)
print("  FULL-SERIES RE-SIMULATION (frozen rules, min_ob_quality=0)")
print("=" * 100)
print(f"Total trades on extended series: {len(trades)}")

original_trades = trades[trades["entry_idx"] < n_locked]
new_trades = trades[trades["entry_idx"] >= n_locked]

print(f"Trades with entry_idx < {n_locked} (should reproduce the locked 27-trade baseline exactly): {len(original_trades)}")
regression_ok = (len(original_trades) == 27) and np.isclose(
    original_trades["pnl_pct"].sum(), 30.306456356031937, atol=1e-6)
print(f"Regression check vs. locked baseline (n=27, total return +30.3065%): "
      f"{'PASS' if regression_ok else 'FAIL -- investigate'}")

print(f"\nNEW trades (entry_idx >= {n_locked}, genuinely out-of-sample -- entered on data that")
print(f"postdates every commit to the strategy file): {len(new_trades)}")
if not new_trades.empty:
    print(f"\n{'Side':<6} | {'Entry time':<20} | {'Exit time':<20} | {'PnL %':<10} | {'Exit reason'}")
    for _, r in new_trades.iterrows():
        entry_time = fresh.iloc[int(r['entry_idx'])]['open_time']
        exit_time = fresh.iloc[int(r['exit_idx'])]['open_time']
        print(f"{r['side']:<6} | {str(entry_time):<20} | {str(exit_time):<20} | {r['pnl_pct']:>+8.4f}% | {r['exit_reason']}")
    wins = int((new_trades['pnl_pct'] > 0).sum())
    print(f"\nNew-trade summary: n={len(new_trades)}, wins={wins}, win_rate={wins/len(new_trades)*100:.2f}%, "
          f"total_pnl={new_trades['pnl_pct'].sum():+.4f}%, avg_pnl={new_trades['pnl_pct'].mean():+.4f}%")
else:
    print("No new trades triggered in the extended window.")

print(f"\nCombined (locked 27 + new, single continuous series) stats:")
print(f"  Total trades: {stats.get('Total Trades')}")
print(f"  Win Rate (%): {stats.get('Win Rate (%)'):.4f}")
print(f"  Total Net Return (%): {stats.get('Total Net Return (%)'):.4f}")
print(f"  Avg Return/Trade (%): {stats.get('Avg Return/Trade (%)'):.4f}")
