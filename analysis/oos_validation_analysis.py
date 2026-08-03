"""
Out-of-sample and extended-history validation for the min_ob_quality=0
baseline strategy. Permanent, git-tracked home for two one-time checks run
earlier this session as scratch/oos_live_pull_2026_08.py and
scratch/eightyr_backfill_audit.py -- promoted here so they're a reproducible
part of the toolchain instead of throwaway scripts.

DISCLOSED EXCEPTION TO CLAUDE.md's OFFLINE-ONLY RULE: this script makes live
Binance API calls (bot.get_candles()), unlike every other analysis/*.py
script, which are strictly offline against artifacts/candles.csv. This is
the same disclosed, deliberate exception the two source scratch scripts
already carried -- the entire point is testing the frozen rule set against
data it could not have been shaped against, which is only possible with a
live pull.

REPRODUCIBILITY DESIGN: both sections pull through a FIXED, closed
historical end date (--oos-end-date, default 2026-07-31) rather than
"through now." A closed historical range is safely re-runnable -- Binance
does not revise historical candles (verified this session via a byte-exact
integrity check against the locked artifacts/candles.csv snapshot) -- so
running this script again next week reproduces the same numbers, unlike an
open-ended "now" pull which would drift every run. If --oos-end-date is
ever moved forward to extend the window with new data, BOTH the old and new
results must be reported side by side (matching CLAUDE.md's existing
convention for revised locked figures), never silently swapped.

SECTION 1 (forward OOS): pulls BTCUSDT 4H from --start-date (default
2022-01-01, matching the locked baseline) through --oos-end-date. Confirms
the locked 27-trade baseline reproduces byte-identically, then reports any
trades entered after the locked window's end as genuinely out-of-sample --
they postdate every commit to src/Binance backtest bot.py.

SECTION 2 (8-year backfill audit): pulls BTCUSDT 4H from
--backfill-start-date (default 2018-01-01) through --oos-end-date. Confirms
the locked 2022-2026 baseline reproduces byte-identically even with several
extra years of indicator warm-up prepended -- NOT guaranteed a priori, since
MACD's EMAs and the static KDJ's EWM(K)/EWM(D) are recursive with unbounded
memory back to the first row of whatever df is passed to
compute_indicators(). Reports pre-2022 trades explicitly labeled NOT
out-of-sample -- disclosed this session as the period the strategy's rule
structure was originally formulated against -- for completeness only, plus
combined 2018-2026 stats with the same caveat attached every time they are
cited.

Does NOT overwrite artifacts/candles.csv, backtest_results.db, or any
committed artifact. Never touches simulate_trades()/compute_smc()/
compute_indicators() themselves -- calls them unmodified.

Usage (run from repo root):
    python analysis/oos_validation_analysis.py
    python analysis/oos_validation_analysis.py --section 1
    python analysis/oos_validation_analysis.py --section 2
    python analysis/oos_validation_analysis.py --oos-end-date 2026-09-30   # only when deliberately extending the window
"""
import argparse
import importlib.util
import json

import numpy as np
import pandas as pd


def load_bot():
    spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def section_1_forward_oos(bot, start_date: str, oos_end_date: str) -> None:
    print("=" * 100)
    print(f"  SECTION 1: FORWARD OUT-OF-SAMPLE TEST -- {start_date} .. {oos_end_date}")
    print("=" * 100)

    fresh = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR,
                             start_time=start_date, end_time=oos_end_date)
    print(f"Pulled: {len(fresh)} bars, {fresh['open_time'].iloc[0]} .. {fresh['open_time'].iloc[-1]}")

    locked = pd.read_csv("artifacts/candles.csv")
    locked["open_time"] = pd.to_datetime(locked["open_time"])
    print(f"Locked baseline: {len(locked)} bars, {locked['open_time'].iloc[0]} .. {locked['open_time'].iloc[-1]}")

    n_locked = len(locked)
    overlap = fresh.iloc[:n_locked].reset_index(drop=True)
    locked_cmp = locked[["open_time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    overlap_cmp = overlap[["open_time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    integrity_ok = overlap_cmp["open_time"].equals(locked_cmp["open_time"]) and np.allclose(
        overlap_cmp[["open", "high", "low", "close", "volume"]].values,
        locked_cmp[["open", "high", "low", "close", "volume"]].values, atol=1e-8)
    print(f"\nIntegrity check (first {n_locked} bars byte-identical to locked snapshot): "
          f"{'PASS' if integrity_ok else 'FAIL -- STOP, investigate before trusting anything below'}")

    df = bot.compute_indicators(fresh.copy())
    sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
    trades = sim.attrs.get("trades_df").copy()

    original_trades = trades[trades["entry_idx"] < n_locked]
    new_trades = trades[trades["entry_idx"] >= n_locked]
    regression_ok = (len(original_trades) == 27) and np.isclose(
        original_trades["pnl_pct"].sum(), 30.306456356031937, atol=1e-6)
    print(f"Regression check vs. locked baseline (n=27, total return +30.3065%): "
          f"{'PASS' if regression_ok else 'FAIL -- investigate'}")

    print(f"\nOOS trades (entry_idx >= {n_locked}, entered on data postdating every commit "
          f"to the strategy file): {len(new_trades)}")
    if not new_trades.empty:
        print(f"\n{'Side':<6} | {'Entry time':<20} | {'Exit time':<20} | {'PnL %':<10} | {'Exit reason'}")
        for _, r in new_trades.iterrows():
            entry_time = fresh.iloc[int(r['entry_idx'])]['open_time']
            exit_time = fresh.iloc[int(r['exit_idx'])]['open_time']
            print(f"{r['side']:<6} | {str(entry_time):<20} | {str(exit_time):<20} | "
                  f"{r['pnl_pct']:>+8.4f}% | {r['exit_reason']}")
        wins = int((new_trades['pnl_pct'] > 0).sum())
        print(f"\nOOS summary: n={len(new_trades)}, wins={wins}, "
              f"win_rate={wins / len(new_trades) * 100:.2f}%, "
              f"total_pnl={new_trades['pnl_pct'].sum():+.4f}%, "
              f"avg_pnl={new_trades['pnl_pct'].mean():+.4f}%")
    else:
        print("No OOS trades triggered in this window.")
    print()


def section_2_backfill_audit(bot, backfill_start_date: str, oos_end_date: str) -> None:
    print("=" * 100)
    print(f"  SECTION 2: 8-YEAR BACKFILL AUDIT -- {backfill_start_date} .. {oos_end_date}")
    print("=" * 100)

    full = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR,
                            start_time=backfill_start_date, end_time=oos_end_date)
    print(f"Pulled: {len(full)} bars, {full['open_time'].iloc[0]} .. {full['open_time'].iloc[-1]}")

    locked = pd.read_csv("artifacts/candles.csv")
    locked["open_time"] = pd.to_datetime(locked["open_time"])

    df_full = bot.compute_indicators(full.copy())
    sim_full = bot.simulate_trades(df_full.copy(), min_ob_quality=0)
    trades_full = sim_full.attrs.get("trades_df").copy()
    trades_full["entry_time"] = df_full.loc[trades_full["entry_idx"], "open_time"].values
    trades_full["exit_time"] = df_full.loc[trades_full["exit_idx"], "open_time"].values

    with open("scratch/fixtures/baseline_trades.json") as f:
        fixture_df = pd.DataFrame(json.load(f))
    fixture_df["entry_time"] = locked.loc[fixture_df["entry_idx"], "open_time"].values

    window_trades = trades_full[
        (trades_full["entry_time"] >= locked["open_time"].iloc[0]) &
        (trades_full["entry_time"] <= locked["open_time"].iloc[-1])
    ].reset_index(drop=True)

    merged = fixture_df.merge(window_trades, on="entry_time", how="outer",
                               suffixes=("_locked", "_ext"), indicator=True)
    only_locked = merged[merged["_merge"] == "left_only"]
    only_ext = merged[merged["_merge"] == "right_only"]
    both = merged[merged["_merge"] == "both"]
    exact = len(both) > 0 and np.allclose(both["pnl_pct_locked"], both["pnl_pct_ext"], atol=1e-9)
    integrity_verdict = only_locked.empty and only_ext.empty and exact
    print(f"\nMethodological check: {len(both)}/27 locked trades matched by entry_time, "
          f"{len(only_locked)} missing, {len(only_ext)} unexpected new trades inside the locked window, "
          f"max pnl diff = {(both['pnl_pct_locked'] - both['pnl_pct_ext']).abs().max() if len(both) else float('nan'):.10f}")
    print(f"METHODOLOGICAL VERDICT: locked 2022-2026 baseline "
          f"{'REPRODUCES EXACTLY under the extended lookback' if integrity_verdict else 'DOES NOT reproduce exactly -- investigate'}")

    pre_window = trades_full[trades_full["entry_time"] < locked["open_time"].iloc[0]]
    print("\n" + "-" * 100)
    print("  Pre-2022 trades -- NOT out-of-sample. Disclosed as the period the strategy's rule")
    print("  structure was originally formulated against. Reported for completeness only.")
    print("-" * 100)
    print(f"n={len(pre_window)}")
    if not pre_window.empty:
        wins = int((pre_window["pnl_pct"] > 0).sum())
        print(f"wins={wins}, win_rate={wins / len(pre_window) * 100:.2f}%, "
              f"total_pnl={pre_window['pnl_pct'].sum():+.4f}%, avg_pnl={pre_window['pnl_pct'].mean():+.4f}%")

    print(f"\nCombined full-window stats ({backfill_start_date}..{oos_end_date}, all trades -- MIXES "
          f"formulation-period and OOS data, do not cite as a clean validation figure):")
    stats = sim_full.attrs.get("trade_stats", {})
    print(f"  Total Trades: {stats.get('Total Trades')}")
    print(f"  Win Rate (%): {stats.get('Win Rate (%)'):.4f}")
    print(f"  Total Net Return (%): {stats.get('Total Net Return (%)'):.4f}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--section", choices=["1", "2", "both"], default="both",
                         help="1=forward OOS, 2=8yr backfill audit, both=default")
    parser.add_argument("--start-date", type=str, default="2022-01-01 00:00:00",
                         help="Locked-baseline start date for section 1 (default: 2022-01-01, matching the locked baseline)")
    parser.add_argument("--backfill-start-date", type=str, default="2018-01-01 00:00:00",
                         help="Backfill start date for section 2 (default: 2018-01-01)")
    parser.add_argument("--oos-end-date", type=str, default="2026-07-31 23:59:59",
                         help="Fixed historical end date for the live pull (default: 2026-07-31, a closed "
                              "historical boundary chosen for safe re-runnability -- see module docstring)")
    args = parser.parse_args()

    bot = load_bot()

    if args.section in ("1", "both"):
        section_1_forward_oos(bot, args.start_date, args.oos_end_date)
    if args.section in ("2", "both"):
        section_2_backfill_audit(bot, args.backfill_start_date, args.oos_end_date)


if __name__ == "__main__":
    main()
