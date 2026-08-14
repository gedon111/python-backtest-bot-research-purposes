"""
Benchmark & risk metrics: strategy vs. BTC buy-and-hold.

Ablation arms (Arm 2 / entry-ATR stop, Arm 3 / swing-pivot stop) are NOT
included here. The scratch script that originally produced their published
trade-level numbers (140 trades / 138 trades, docs/ablation_*.md) was never
committed -- same situation as the deleted 190-signal script. A best-effort
reconstruction from the current production entry/exit code matches trade
count and average return closely but diverges on win rate by >10 points and
on SD by ~0.3-0.5pp, meaning the underlying per-trade outcomes are NOT the
same trades the paper reports, even though the aggregate looks superficially
close. Do not extend this file to the ablation arms without first resolving
that discrepancy -- see the chat writeup for the reconciliation attempts.
"""
import numpy as np
import pandas as pd
from scipy import stats as sstats
import importlib.util

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PERIODS_PER_YEAR = 6 * 365.25  # 4H bars/year, leap-year-averaged

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)

N_BARS = len(df)
sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
trades = sim.attrs.get("trades_df")


def max_drawdown(equity):
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max * 100
    return dd.min()


def sharpe_sortino(bar_returns, periods_per_year=PERIODS_PER_YEAR):
    mean_r = bar_returns.mean()
    std_r = bar_returns.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(periods_per_year) if std_r > 0 else float("nan")

    downside = np.minimum(bar_returns, 0.0)
    downside_dev = np.sqrt((downside ** 2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(periods_per_year) if downside_dev > 0 else float("nan")
    return sharpe, sortino


# ─── Buy-and-hold ────────────────────────────────────────────────────────────
close = df["close"]
bh_total_return = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100
bh_equity = close / close.iloc[0] * 100
bh_bar_returns = bh_equity.pct_change().dropna()
bh_time_in_market = 1.0
bh_exposure_bars = N_BARS - 1  # bars spanned, matching trade hold_bars = exit_idx - entry_idx
bh_return_per_bar = bh_total_return / bh_exposure_bars
bh_max_dd = max_drawdown(bh_equity)
bh_sharpe, bh_sortino = sharpe_sortino(bh_bar_returns)

# ─── Strategy (baseline, min_ob_quality=0, N=27) ────────────────────────────
total_net_return = trades["pnl_pct"].sum()
hold_bars_sum = trades["hold_bars"].sum()
strat_time_in_market = hold_bars_sum / N_BARS
strat_return_per_bar = total_net_return / hold_bars_sum

# Event-driven equity curve: flat between trades, compounds at each exit bar.
# Trades never overlap (verified: simulate_trades only opens a new position
# when position is None), so a simple sequential walk is valid.
equity_by_bar = np.full(N_BARS, np.nan)
equity_by_bar[0] = 100.0
eq = 100.0
trades_by_exit = trades.sort_values("exit_idx")
exit_map = dict(zip(trades_by_exit["exit_idx"], trades_by_exit["pnl_pct"]))
for i in range(1, N_BARS):
    if i in exit_map:
        eq *= (1 + exit_map[i] / 100)
    equity_by_bar[i] = eq
strat_equity = pd.Series(equity_by_bar)
strat_bar_returns = strat_equity.pct_change().dropna()
strat_max_dd = max_drawdown(strat_equity)
strat_sharpe, strat_sortino = sharpe_sortino(strat_bar_returns)

# ─── Correlation: per-trade return vs. BTC's return over the same window ───
btc_window_return = (
    close.iloc[trades["exit_idx"].values].values - close.iloc[trades["entry_idx"].values].values
) / close.iloc[trades["entry_idx"].values].values * 100
r, p_corr = sstats.pearsonr(trades["pnl_pct"].values, btc_window_return)
n_corr = len(trades)

# ─── Report ──────────────────────────────────────────────────────────────────
print("=" * 100)
print("  STRATEGY (Q0 BASELINE, N=27) vs. BTC BUY-AND-HOLD -- SAME WINDOW (8,767 bars)")
print(f"  Methodology: equity curves are event-driven (strategy) / bar-close (buy-and-hold);")
print(f"  Sharpe/Sortino computed on per-bar equity returns, annualized by sqrt({PERIODS_PER_YEAR:.1f}) periods/year.")
print("=" * 100)
print(f"{'Metric':<38} | {'Strategy (Q0)':<20} | {'BTC Buy-and-Hold':<20}")
print("-" * 100)
print(f"{'Total return':<38} | {total_net_return:>+18.2f}% | {bh_total_return:>+18.2f}%")
print(f"{'Time-in-market':<38} | {strat_time_in_market*100:>18.2f}% | {bh_time_in_market*100:>18.2f}%")
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
print("NOTE: Ablation arms (entry-ATR stop / swing-pivot stop) omitted -- see module docstring.")
