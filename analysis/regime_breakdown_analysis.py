"""
Macro-regime breakdown for the min_ob_quality=0 baseline trade log.

Read-only, additive analysis: loads artifacts/candles.csv, runs the
UNMODIFIED src/Binance backtest bot.py strategy, and only reads from the
resulting trades_df. Never touches simulate_trades(), never writes to
backtest_results.db or any artifacts/* file, never changes a
locked/reported headline number.

Tags each baseline trade by the macro market regime active at its entry
bar, using TWO independent methods, both reported (never collapsed to
one) because they measure genuinely different things and disagree on a
meaningful fraction of trades:

1. CALENDAR METHOD: 2022 = bear, 2023 = chop, 2024-2025 = bull, per the
   standard, widely-cited BTC cycle narrative for this exact window (cycle
   low November 2022; prior-ATH breakout March 2024).

2. DRAWDOWN-FROM-ATH METHOD: running ATH is seeded at $69,000 (BTC's
   actual all-time high, 2021-11-10, which predates this dataset's
   2022-01-01 start by seven weeks -- seeding from the dataset's own first
   bar would incorrectly read early-2022, already ~32% off the real ATH,
   as "at the high"). From there, running ATH = cummax(seed, close).
   Thresholds (a judgment call, stated so they can be re-argued): BEAR =
   drawdown <= -40% (deep, established downtrend), CHOP = -40% to -12%
   (recovering / rangebound, not yet re-testing highs), BULL = drawdown
   > -12% (at or making new highs).

Neither method is not used elsewhere in this codebase (ADX/EMA200, used
for a similar breakdown in docs/ablation_unconfounding_analysis.md's
indicators-only Arm 3, are not persisted anywhere in artifacts/candles.csv
or backtest_results.db -- confirmed absent from both schemas).

Usage (run from repo root):
    python analysis/regime_breakdown_analysis.py
    python analysis/regime_breakdown_analysis.py --ath-seed 69000 --bear-threshold -40 --chop-threshold -12
    python analysis/regime_breakdown_analysis.py --bear-year 2022 --chop-year 2023

Promoted from scratch/regime_breakdown_audit.py (verified byte-for-byte
identical numbers at default args before promotion).
"""
import argparse
import importlib.util

import numpy as np
import pandas as pd


def load_data(min_ob_quality: int):
    spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)

    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    df = bot.compute_indicators(df)

    sim = bot.simulate_trades(df.copy(), min_ob_quality=min_ob_quality)
    trades = sim.attrs.get("trades_df").copy()
    return df, trades


def tag_regimes(df: pd.DataFrame, ath_seed: float, bear_threshold: float, chop_threshold: float,
                 bear_year: int, chop_year: int) -> pd.DataFrame:
    running_ath = np.maximum.accumulate(np.concatenate([[ath_seed], df["close"].values]))[1:]
    drawdown_pct = (df["close"].values / running_ath - 1.0) * 100.0

    def dd_regime(dd):
        if dd <= bear_threshold:
            return "BEAR"
        elif dd <= chop_threshold:
            return "CHOP"
        else:
            return "BULL"

    df = df.copy()
    df["_dd_pct"] = drawdown_pct
    df["_dd_regime"] = [dd_regime(x) for x in drawdown_pct]

    def cal_regime(ts):
        y = ts.year
        if y == bear_year:
            return "BEAR"
        elif y == chop_year:
            return "CHOP"
        else:
            return "BULL"

    df["_cal_regime"] = df["open_time"].apply(cal_regime)
    return df


def summarize(trades: pd.DataFrame, label: str, group_col: str) -> None:
    print("=" * 100)
    print(f"  REGIME BREAKDOWN -- {label}")
    print("=" * 100)
    print(f"  {'Regime':<8} | {'N':<4} | {'Wins':<5} | {'Win rate':<9} | {'Total PnL contrib':<18} | {'Avg PnL/trade':<14}")
    total_pnl = trades["pnl_pct"].sum()
    for regime in ["BEAR", "CHOP", "BULL"]:
        g = trades[trades[group_col] == regime]
        if g.empty:
            print(f"  {regime:<8} | {'0':<4} | {'-':<5} | {'-':<9} | {'-':<18} | {'-':<14}")
            continue
        n = len(g)
        wins = int((g["pnl_pct"] > 0).sum())
        wr = wins / n * 100
        total = g["pnl_pct"].sum()
        avg = g["pnl_pct"].mean()
        pct_of_total = total / total_pnl * 100
        print(f"  {regime:<8} | {n:<4} | {wins:<5} | {wr:<8.2f}% | {total:>+8.4f}% ({pct_of_total:>+6.1f}% of total) | {avg:>+12.4f}%")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-ob-quality", type=int, default=0,
                         help="OB quality threshold to simulate (default: 0, the locked baseline)")
    parser.add_argument("--ath-seed", type=float, default=69000.0,
                         help="Pre-window all-time-high seed for the drawdown method (default: 69000, BTC's 2021-11-10 ATH)")
    parser.add_argument("--bear-threshold", type=float, default=-40.0,
                         help="Drawdown %% at/below which a bar is BEAR (default: -40.0)")
    parser.add_argument("--chop-threshold", type=float, default=-12.0,
                         help="Drawdown %% at/below which a bar is CHOP (default: -12.0)")
    parser.add_argument("--bear-year", type=int, default=2022, help="Calendar year labeled BEAR (default: 2022)")
    parser.add_argument("--chop-year", type=int, default=2023, help="Calendar year labeled CHOP (default: 2023)")
    parser.add_argument("--top-n", type=int, default=3, help="How many top-return trades to spotlight (default: 3)")
    args = parser.parse_args()

    df, trades = load_data(args.min_ob_quality)
    expected_n = 27 if args.min_ob_quality == 0 else None
    if expected_n is not None:
        assert len(trades) == expected_n, f"expected {expected_n} baseline trades, got {len(trades)}"

    df = tag_regimes(df, args.ath_seed, args.bear_threshold, args.chop_threshold, args.bear_year, args.chop_year)

    trades["entry_time"] = df.loc[trades["entry_idx"], "open_time"].values
    trades["entry_dd_pct"] = df.loc[trades["entry_idx"], "_dd_pct"].values
    trades["dd_regime"] = df.loc[trades["entry_idx"], "_dd_regime"].values
    trades["cal_regime"] = df.loc[trades["entry_idx"], "_cal_regime"].values

    summarize(trades, f"Drawdown-from-ATH method (BEAR<={args.bear_threshold:.0f}%, "
                       f"CHOP<={args.chop_threshold:.0f}%, BULL>{args.chop_threshold:.0f}%)", "dd_regime")
    summarize(trades, f"Calendar method ({args.bear_year}=BEAR, {args.chop_year}=CHOP, "
                       f"{args.chop_year + 1}-{str(df['open_time'].max().year)[-2:]}=BULL)", "cal_regime")

    agree = (trades["dd_regime"] == trades["cal_regime"]).sum()
    print(f"  Method agreement: {agree}/{len(trades)} trades assigned the same regime by both methods")
    disagree = trades[trades["dd_regime"] != trades["cal_regime"]]
    if not disagree.empty:
        print("  Disagreements:")
        for _, r in disagree.iterrows():
            print(f"    entry_idx={int(r['entry_idx']):<6} {r['entry_time']} dd%={r['entry_dd_pct']:+.1f}  "
                  f"dd_method={r['dd_regime']:<5} cal_method={r['cal_regime']:<5}")
    print()

    print("=" * 100)
    print(f"  THE {args.top_n} CONCENTRATED WINNING TRADES -- REGIME CHECK")
    print("=" * 100)
    top_n = trades.nlargest(args.top_n, "pnl_pct")
    for _, r in top_n.iterrows():
        print(f"  entry_idx={int(r['entry_idx']):<6} {str(r['entry_time']):<20} pnl={r['pnl_pct']:+.2f}%  "
              f"drawdown-from-ATH={r['entry_dd_pct']:+.1f}% -> {r['dd_regime']:<5}   calendar -> {r['cal_regime']}")
    regimes_hit = set(top_n["dd_regime"]).union(set(top_n["cal_regime"]))
    print(f"\n  Distinct regimes among the top {args.top_n} winners (either method, union): {sorted(regimes_hit)}")
    print(f"  Clustered in a single regime? {'YES' if len(set(top_n['dd_regime'])) == 1 else 'NO'} (drawdown method)")
    print(f"  Clustered in a single regime? {'YES' if len(set(top_n['cal_regime'])) == 1 else 'NO'} (calendar method)")


if __name__ == "__main__":
    main()
