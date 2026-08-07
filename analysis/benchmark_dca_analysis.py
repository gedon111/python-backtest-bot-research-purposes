"""
Strategy-vs-BTC benchmark comparison and DCA-blend "complementary sleeve"
analysis for the min_ob_quality=0 baseline trade log.

Read-only, additive analysis: loads artifacts/candles.csv, runs the
UNMODIFIED src/Binance backtest bot.py strategy, and only reads from the
resulting trades_df. Never touches simulate_trades(), never writes to
backtest_results.db or any artifacts/* file, never changes a
locked/reported headline number.

Combines two previously separate scratch scripts into one permanent module,
since they're the same analysis family:

SECTION 1 -- Strategy vs. BTC buy-and-hold, same window (from
scratch/02_benchmark_and_risk.py): event-driven strategy equity curve (flat
between trades, compounds at each exit -- valid because trades never
overlap), buy-and-hold equity curve, Sharpe/Sortino (annualized), max
drawdown, and the Pearson correlation between per-trade strategy return and
BTC's own return over the identical holding window.

SECTION 2 -- DCA-blend "complementary sleeve" model (from
scratch/dca_blend_audit.py): a fixed amount of new capital arrives every
week; a 100%-BTC-DCA baseline is compared against portfolios that instead
split each week's contribution between a BTC-DCA sub-sleeve and an
independently-capitalized strategy sub-sleeve (full-balance redeployment
into each realized trade, mirrors the strategy's own flat-between-trades
equity curve). Configurable contribution amount and split ratios (90/10,
80/20, 70/30 reported by default). Returns are computed net of each
period's own contribution, so injected capital isn't misread as investment
return. Max drawdown is reported two ways: principal-inclusive (the
conventional DCA-calculator presentation) and as a peak-to-trough
cumulative-P&L dollar retracement (avoids the divide-by-~0-or-negative
issue a %-drawdown on cumulative P&L hits early in the series, before
enough capital has accumulated -- FIXED here relative to the scratch
predecessor's first draft, which produced NaN on that metric).

Usage (run from repo root):
    python analysis/benchmark_dca_analysis.py
    python analysis/benchmark_dca_analysis.py --contribution-amount 50
    python analysis/benchmark_dca_analysis.py --splits 0.1,0.2,0.3,0.5

Promoted from scratch/02_benchmark_and_risk.py and scratch/dca_blend_audit.py
(verified byte-for-byte identical numbers at default args before promotion).
"""
import argparse
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats as sstats

from _json_utils import write_json

PERIODS_PER_YEAR_4H = 6 * 365.25  # 4H bars/year, leap-year-averaged
PERIODS_PER_YEAR_WEEKLY = 52


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


def max_drawdown_pct(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max * 100
    return dd.min()


def sharpe_sortino(bar_returns, periods_per_year: float):
    mean_r = bar_returns.mean()
    std_r = bar_returns.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(periods_per_year) if std_r > 0 else float("nan")
    downside = np.minimum(bar_returns, 0.0)
    downside_dev = np.sqrt((downside ** 2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(periods_per_year) if downside_dev > 0 else float("nan")
    return sharpe, sortino


# ─────────────────────────────────────────────────────────────────────────
# Section 1: strategy vs. BTC buy-and-hold
# ─────────────────────────────────────────────────────────────────────────

def section_1_benchmark(df: pd.DataFrame, trades: pd.DataFrame) -> dict:
    n_bars = len(df)
    close = df["close"]

    # Buy-and-hold
    bh_total_return = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100
    bh_equity = close / close.iloc[0] * 100
    bh_bar_returns = bh_equity.pct_change().dropna()
    bh_exposure_bars = n_bars - 1
    bh_return_per_bar = bh_total_return / bh_exposure_bars
    bh_max_dd = max_drawdown_pct(bh_equity)
    bh_sharpe, bh_sortino = sharpe_sortino(bh_bar_returns, PERIODS_PER_YEAR_4H)

    # Strategy: event-driven equity curve, flat between trades, compounds at each exit.
    # Trades never overlap (simulate_trades only opens a new position when
    # position is None), so a simple sequential walk is valid.
    total_net_return = trades["pnl_pct"].sum()
    hold_bars_sum = trades["hold_bars"].sum()
    strat_time_in_market = hold_bars_sum / n_bars
    strat_return_per_bar = total_net_return / hold_bars_sum

    equity_by_bar = np.full(n_bars, np.nan)
    equity_by_bar[0] = 100.0
    eq = 100.0
    trades_by_exit = trades.sort_values("exit_idx")
    exit_map = dict(zip(trades_by_exit["exit_idx"], trades_by_exit["pnl_pct"]))
    for i in range(1, n_bars):
        if i in exit_map:
            eq *= (1 + exit_map[i] / 100)
        equity_by_bar[i] = eq
    strat_equity = pd.Series(equity_by_bar)
    strat_bar_returns = strat_equity.pct_change().dropna()
    strat_max_dd = max_drawdown_pct(strat_equity)
    strat_sharpe, strat_sortino = sharpe_sortino(strat_bar_returns, PERIODS_PER_YEAR_4H)

    # Correlation: per-trade return vs. BTC's return over the same holding window
    btc_window_return = (
        close.iloc[trades["exit_idx"].values].values - close.iloc[trades["entry_idx"].values].values
    ) / close.iloc[trades["entry_idx"].values].values * 100
    r, p_corr = sstats.pearsonr(trades["pnl_pct"].values, btc_window_return)
    n_corr = len(trades)

    print("=" * 100)
    print(f"  SECTION 1: STRATEGY vs. BTC BUY-AND-HOLD -- SAME WINDOW ({n_bars} bars)")
    print(f"  Methodology: equity curves are event-driven (strategy) / bar-close (buy-and-hold);")
    print(f"  Sharpe/Sortino computed on per-bar equity returns, annualized by sqrt({PERIODS_PER_YEAR_4H:.1f}) periods/year.")
    print("=" * 100)
    print(f"{'Metric':<38} | {'Strategy':<20} | {'BTC Buy-and-Hold':<20}")
    print("-" * 100)
    print(f"{'Total return':<38} | {total_net_return:>+18.2f}% | {bh_total_return:>+18.2f}%")
    print(f"{'Time-in-market':<38} | {strat_time_in_market * 100:>18.2f}% | {100.0:>18.2f}%")
    print(f"{'Bars of exposure':<38} | {hold_bars_sum:>19d} | {bh_exposure_bars:>19d}")
    print(f"{'Return per bar of exposure':<38} | {strat_return_per_bar:>+18.4f}% | {bh_return_per_bar:>+18.4f}%")
    print(f"{'Max drawdown (realized equity)':<38} | {strat_max_dd:>18.2f}% | {bh_max_dd:>18.2f}%")
    print(f"{'Sharpe (annualized)':<38} | {strat_sharpe:>19.3f} | {bh_sharpe:>19.3f}")
    print(f"{'Sortino (annualized)':<38} | {strat_sortino:>19.3f} | {bh_sortino:>19.3f}")
    print("-" * 100)
    print(f"Correlation (strategy per-trade return vs. BTC return over same holding window):")
    print(f"  Pearson r = {r:+.4f}, n = {n_corr}, p = {p_corr:.4f}")
    print("=" * 100)
    print()

    return {
        "n_bars": n_bars,
        "strategy": {
            "total_return_pct": total_net_return, "time_in_market_pct": strat_time_in_market * 100,
            "bars_of_exposure": int(hold_bars_sum), "return_per_bar_pct": strat_return_per_bar,
            "max_drawdown_pct": strat_max_dd, "sharpe": strat_sharpe, "sortino": strat_sortino,
        },
        "buy_and_hold": {
            "total_return_pct": bh_total_return, "time_in_market_pct": 100.0,
            "bars_of_exposure": bh_exposure_bars, "return_per_bar_pct": bh_return_per_bar,
            "max_drawdown_pct": bh_max_dd, "sharpe": bh_sharpe, "sortino": bh_sortino,
        },
        "correlation": {"pearson_r": r, "n": n_corr, "p": p_corr},
    }


# ─────────────────────────────────────────────────────────────────────────
# Section 2: DCA-blend complementary-sleeve model
# ─────────────────────────────────────────────────────────────────────────

def section_2_dca_blend(df: pd.DataFrame, trades: pd.DataFrame, contribution: float, splits) -> dict:
    n_bars = len(df)
    close = df["close"].values
    open_time = df["open_time"]

    exit_pnl = dict(zip(trades["exit_idx"].astype(int), trades["pnl_pct"].astype(float)))

    # Weekly contribution bars: first bar index of each ISO calendar week
    week_key = open_time.dt.isocalendar().year.astype(str) + "-W" + open_time.dt.isocalendar().week.astype(str)
    contribution_bars = df.groupby(week_key).apply(lambda g: g.index.min()).sort_values().values
    contribution_bars = np.array(sorted(set(int(x) for x in contribution_bars)))

    def run_split(s: float, label: str) -> dict:
        dca_only_units = 0.0
        btc_sub_units = 0.0
        strat_cash = 0.0

        dca_only_value = np.empty(n_bars)
        combined_value = np.empty(n_bars)
        contrib_this_bar = np.zeros(n_bars)

        contribution_set = set(contribution_bars.tolist())

        for i in range(n_bars):
            px = close[i]
            if i in contribution_set:
                dca_only_units += contribution / px
                btc_sub_units += contribution * (1.0 - s) / px
                strat_cash += contribution * s
                contrib_this_bar[i] = contribution
            if i in exit_pnl:
                strat_cash *= (1.0 + exit_pnl[i] / 100.0)
            dca_only_value[i] = dca_only_units * px
            combined_value[i] = btc_sub_units * px + strat_cash

        idx = contribution_bars
        V_dca = dca_only_value[idx]
        V_comb = combined_value[idx]
        C = contrib_this_bar[idx]

        def period_returns(V, C):
            r = np.empty(len(V) - 1)
            for k in range(1, len(V)):
                r[k - 1] = (V[k] - C[k]) / V[k - 1] - 1.0
            return r

        r_dca = period_returns(V_dca, C)
        r_comb = period_returns(V_comb, C)

        def max_dd_pct(V):
            running_max = np.maximum.accumulate(V)
            dd = (V - running_max) / running_max * 100
            return dd.min()

        def max_dd_dollars(pnl):
            # pnl can be negative (portfolio underwater vs. contributions) early
            # on, so a % drawdown on it is ill-defined (division by ~0 or
            # negative peak). Report the largest peak-to-trough DOLLAR
            # retracement instead, which stays well-defined regardless of sign.
            running_max = np.maximum.accumulate(pnl)
            return (pnl - running_max).min()

        cum_contrib = np.cumsum(C)
        pnl_dca = V_dca - cum_contrib
        pnl_comb = V_comb - cum_contrib

        sh_dca, so_dca = sharpe_sortino(r_dca, PERIODS_PER_YEAR_WEEKLY)
        sh_comb, so_comb = sharpe_sortino(r_comb, PERIODS_PER_YEAR_WEEKLY)

        print(f"--- Split: {label} (s={s:.2f} to strategy sleeve) ---")
        print(f"  {'Metric':<42} | {'DCA-only (100% BTC)':<22} | {'Combined':<22}")
        print(f"  {'Final value (' + str(contribution) + '/wk, ' + str(len(idx)) + ' wks)':<42} | {V_dca[-1]:>20.2f}  | {V_comb[-1]:>20.2f}")
        print(f"  {'Total contributed':<42} | {cum_contrib[-1]:>20.2f}  | {cum_contrib[-1]:>20.2f}")
        print(f"  {'Final cumulative P&L ($)':<42} | {pnl_dca[-1]:>20.2f}  | {pnl_comb[-1]:>20.2f}")
        print(f"  {'Sharpe (weekly, annualized)':<42} | {sh_dca:>20.3f}  | {sh_comb:>20.3f}")
        print(f"  {'Sortino (weekly, annualized)':<42} | {so_dca:>20.3f}  | {so_comb:>20.3f}")
        print(f"  {'Max drawdown, principal-inclusive':<42} | {max_dd_pct(V_dca):>19.2f}%  | {max_dd_pct(V_comb):>19.2f}%")
        print(f"  {'Max peak-to-trough P&L retracement ($)':<42} | {max_dd_dollars(pnl_dca):>20.2f}  | {max_dd_dollars(pnl_comb):>20.2f}")
        print()

        return {
            "split_label": label, "strategy_sleeve_fraction": s,
            "dca_only": {
                "final_value": float(V_dca[-1]), "total_contributed": float(cum_contrib[-1]),
                "final_pnl": float(pnl_dca[-1]), "sharpe": sh_dca, "sortino": so_dca,
                "max_drawdown_principal_inclusive_pct": max_dd_pct(V_dca),
                "max_pnl_retracement_dollars": max_dd_dollars(pnl_dca),
            },
            "combined": {
                "final_value": float(V_comb[-1]), "total_contributed": float(cum_contrib[-1]),
                "final_pnl": float(pnl_comb[-1]), "sharpe": sh_comb, "sortino": so_comb,
                "max_drawdown_principal_inclusive_pct": max_dd_pct(V_comb),
                "max_pnl_retracement_dollars": max_dd_dollars(pnl_comb),
            },
        }

    print("=" * 100)
    print("  SECTION 2: DCA-INTO-BTC + INDEPENDENTLY-CAPITALIZED STRATEGY SLEEVE, vs. 100%-DCA-ONLY BASELINE")
    print(f"  {len(contribution_bars)} weekly {contribution}-unit contributions, "
          f"{open_time.iloc[0].date()} .. {open_time.iloc[-1].date()}")
    print("=" * 100)
    split_results = []
    for s in splits:
        label = f"{int(round((1 - s) * 100))}/{int(round(s * 100))}"
        split_results.append(run_split(s, label))

    return {"contribution_amount": contribution, "n_contribution_periods": len(contribution_bars),
            "splits": split_results}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-ob-quality", type=int, default=0,
                         help="OB quality threshold to simulate (default: 0, the locked baseline)")
    parser.add_argument("--contribution-amount", type=float, default=1.0,
                         help="New capital contributed per period in Section 2 (default: 1.0, i.e. relative units)")
    parser.add_argument("--splits", type=str, default="0.10,0.20,0.30",
                         help="Comma-separated strategy-sleeve allocation fractions for Section 2 "
                              "(default: 0.10,0.20,0.30 -> 90/10, 80/20, 70/30)")
    parser.add_argument("--section", choices=["1", "2", "both"], default="both",
                         help="Which section(s) to run (default: both)")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write results as JSON (does not change printed output)")
    args = parser.parse_args()

    splits = [float(x) for x in args.splits.split(",")]

    df, trades = load_data(args.min_ob_quality)
    expected_n = 27 if args.min_ob_quality == 0 else None
    if expected_n is not None:
        assert len(trades) == expected_n, f"expected {expected_n} baseline trades, got {len(trades)}"

    result = {"min_ob_quality": args.min_ob_quality}
    if args.section in ("1", "both"):
        result["section_1_benchmark"] = section_1_benchmark(df, trades)
    if args.section in ("2", "both"):
        result["section_2_dca_blend"] = section_2_dca_blend(df, trades, args.contribution_amount, splits)

    if args.json_out:
        write_json(result, args.json_out)


if __name__ == "__main__":
    main()
