"""
ONE-TIME audit: extend history back to 2018-01-01 (~8 years) and check two
separate things:

(1) METHODOLOGICAL SOUNDNESS: does prepending ~4 years of prior bars change
    the locked 2022-2026 baseline at all? This is NOT guaranteed the way the
    forward-extension test was. MACD's EMAs and the static KDJ's EWM(K)/
    EWM(D) are recursive with unbounded memory back to the first row of
    whatever df is passed to compute_indicators() -- prepending bars changes
    what "the first row" is, hence changes the warm-up trajectory. OB/
    structure detection (compute_smc) uses bounded rolling windows
    (INTERNAL_SIZE=5, SWING_SIZE=50) so should be locally determined once far
    enough from the new start boundary, but the ENTRY CONDITIONS reference
    the (potentially shifted) K/D/J/MACD_hist values directly, so a
    boundary-sensitive comparison could in principle flip a trade in or out.
    Checked by matching trades by open_time (not raw bar index, which shifts
    when bars are prepended) against the locked 27-trade regression fixture.

(2) IS THE 2018-2022 ADDITION ACTUALLY GOOD FOR THE PAPER: per this
    session's disclosure, the rule STRUCTURE was originally formulated
    against 2018-2022 data, so trades generated in that window are NOT
    out-of-sample evidence -- reported here for audit/completeness only,
    explicitly not framed as validation.

Does NOT overwrite artifacts/candles.csv, backtest_results.db, or any
committed artifact. Output written to scratch/ only. Pre-registered:
run once, report as-is.
"""
import importlib.util
import json
import pandas as pd
import numpy as np

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

print("=" * 100)
print("  8-YEAR BACKFILL AUDIT -- pulling BTCUSDT 4H from 2018-01-01 through now")
print("=" * 100)

full = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR,
                        start_time="2018-01-01 00:00:00", end_time=None)
print(f"Pulled: {len(full)} bars, {full['open_time'].iloc[0]} .. {full['open_time'].iloc[-1]}")
full.to_csv("scratch/oos_extended_candles_2018_2026.csv", index=False)

locked = pd.read_csv("artifacts/candles.csv")
locked["open_time"] = pd.to_datetime(locked["open_time"])
print(f"Locked baseline: {len(locked)} bars, {locked['open_time'].iloc[0]} .. {locked['open_time'].iloc[-1]}")

# ─── Run the FROZEN, unmodified pipeline on the full 2018-2026 series ──────
df_full = bot.compute_indicators(full.copy())
sim_full = bot.simulate_trades(df_full.copy(), min_ob_quality=0)
trades_full = sim_full.attrs.get("trades_df").copy()
trades_full["entry_time"] = df_full.loc[trades_full["entry_idx"], "open_time"].values
trades_full["exit_time"] = df_full.loc[trades_full["exit_idx"], "open_time"].values

print(f"\nTotal trades, full 2018-2026 series: {len(trades_full)}")

# ─── (1) Methodological check: do the locked 27 trades still reproduce, matched by open_time? ──
with open("scratch/fixtures/baseline_trades.json") as f:
    fixture = json.load(f)
fixture_df = pd.DataFrame(fixture)
fixture_df["entry_time"] = locked.loc[fixture_df["entry_idx"], "open_time"].values

window_trades = trades_full[
    (trades_full["entry_time"] >= locked["open_time"].iloc[0]) &
    (trades_full["entry_time"] <= locked["open_time"].iloc[-1])
].reset_index(drop=True)

print(f"\nTrades within the original 2022-01-01..2026-01-01 window, from the 8yr run: {len(window_trades)}")
print(f"Trades in the locked regression fixture: {len(fixture_df)}")

merged = fixture_df.merge(window_trades, on="entry_time", how="outer", suffixes=("_locked", "_8yr"), indicator=True)
only_locked = merged[merged["_merge"] == "left_only"]
only_8yr = merged[merged["_merge"] == "right_only"]
both = merged[merged["_merge"] == "both"]

print(f"Matched by entry_time in both runs: {len(both)}")
print(f"In locked fixture but MISSING from 8yr run: {len(only_locked)}")
print(f"In 8yr run but NOT in locked fixture (new trades inside the same window): {len(only_8yr)}")

if not only_locked.empty:
    print("\n  Trades that disappeared:")
    for _, r in only_locked.iterrows():
        print(f"    entry_time={r['entry_time']} side={r['side_locked']} pnl={r['pnl_pct_locked']:+.4f}%")
if not only_8yr.empty:
    print("\n  New trades that appeared (same window, previously absent):")
    for _, r in only_8yr.iterrows():
        print(f"    entry_time={r['entry_time']} side={r['side_8yr']} pnl={r['pnl_pct_8yr']:+.4f}%")

if len(both) > 0:
    pnl_diff = (both["pnl_pct_locked"] - both["pnl_pct_8yr"]).abs()
    max_diff = pnl_diff.max()
    print(f"\nFor the {len(both)} matched trades: max |pnl_pct difference| = {max_diff:.10f}")
    exact = np.allclose(both["pnl_pct_locked"], both["pnl_pct_8yr"], atol=1e-9)
    print(f"Byte-identical (atol=1e-9)? {'YES' if exact else 'NO -- indicator warm-up shift caused numeric drift'}")
    if not exact:
        drifted = both[pnl_diff > 1e-9]
        print(f"  {len(drifted)} trade(s) show numeric drift:")
        for _, r in drifted.iterrows():
            print(f"    entry_time={r['entry_time']} locked_pnl={r['pnl_pct_locked']:+.8f}% 8yr_pnl={r['pnl_pct_8yr']:+.8f}%")

integrity_verdict = only_locked.empty and only_8yr.empty and (len(both) == 0 or np.allclose(both["pnl_pct_locked"], both["pnl_pct_8yr"], atol=1e-9))
print(f"\nMETHODOLOGICAL VERDICT: locked 2022-2026 baseline "
      f"{'REPRODUCES EXACTLY under the 8yr extension' if integrity_verdict else 'DOES NOT reproduce exactly -- see drift/additions/removals above'}")

# ─── (2) 2018-2022 trades: reported for completeness, NOT as OOS evidence ──
pre_window = trades_full[trades_full["entry_time"] < locked["open_time"].iloc[0]]
print("\n" + "=" * 100)
print("  2018-01-01 .. 2022-01-01 TRADES (NOT out-of-sample -- disclosed as the period the")
print("  rule structure was originally formulated against; reported for completeness only)")
print("=" * 100)
print(f"n={len(pre_window)}")
if not pre_window.empty:
    wins = int((pre_window["pnl_pct"] > 0).sum())
    print(f"wins={wins}, win_rate={wins/len(pre_window)*100:.2f}%, "
          f"total_pnl={pre_window['pnl_pct'].sum():+.4f}%, avg_pnl={pre_window['pnl_pct'].mean():+.4f}%")
    print(f"\n{'Side':<6} | {'Entry time':<20} | {'Exit time':<20} | {'PnL %':<10} | {'Exit reason'}")
    for _, r in pre_window.iterrows():
        print(f"{r['side']:<6} | {str(r['entry_time']):<20} | {str(r['exit_time']):<20} | {r['pnl_pct']:>+8.4f}% | {r['exit_reason']}")

print("\nFull 8yr-run combined stats (2018-2026, all trades, for reference only):")
stats = sim_full.attrs.get("trade_stats", {})
print(f"  Total Trades: {stats.get('Total Trades')}")
print(f"  Win Rate (%): {stats.get('Win Rate (%)'):.4f}")
print(f"  Total Net Return (%): {stats.get('Total Net Return (%)'):.4f}")
