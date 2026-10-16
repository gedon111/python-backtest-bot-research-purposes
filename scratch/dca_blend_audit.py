"""
Item 4 (investigation session): extends scratch/02_benchmark_and_risk.py's
already-existing (and, per that script's correlation output, encouraging --
Pearson r=-0.3688, p=0.0584 between per-trade strategy return and BTC's
return over the same holding window) strategy-vs-BTC comparison into a
"complementary sleeve" framing: a weekly-DCA-into-BTC investor who ALSO
allocates a separate, non-competing slice of new capital to the strategy,
versus a 100%-DCA-only baseline. Read-only against artifacts/candles.csv and
the unmodified strategy; no pipeline rerun, no changes to simulate_trades()
or any committed artifact.

MODEL (explicitly approximate -- stated so results can be recomputed under
different assumptions):
  - A fixed $1 of new capital arrives at the start of every calendar week
    across the full 2022-01-01..2026-01-01 window (~209 weeks).
  - DCA-ONLY baseline: all $1/week buys BTC at that week's first-bar close.
  - COMBINED portfolio: each week's $1 splits (1-s) to a BTC-DCA sub-sleeve
    (identical mechanics to the baseline, just smaller) and s to a
    "strategy capital" sub-sleeve. s=0.20 (80/20 split) is the primary case;
    s=0.10 and s=0.30 are also reported for sensitivity.
  - Strategy sub-sleeve: contributed cash accumulates un-invested between
    trades (mirrors the existing project's own strategy equity curve, which
    is flat between trades -- see 02_benchmark_and_risk.py). At each trade's
    EXIT bar, 100% of the sub-sleeve's current balance is compounded by that
    trade's realized pnl_pct. This assumes full redeployment of the sleeve's
    whole balance into every trade (same assumption the project's own
    strategy equity curve already makes) -- a simplification, not a real
    position-sizing model.
  - Returns are computed at the weekly contribution checkpoints, netting out
    that week's own contribution before computing the period return
    (r_t = (V_t - contribution_t) / V_{t-1} - 1), so injected capital is not
    misread as investment return. Sharpe annualized by sqrt(52).
  - Max drawdown is reported two ways because DCA drawdown is inherently
    ambiguous while principal keeps growing: (i) on raw portfolio value
    (principal-inclusive, the number most DCA return calculators show) and
    (ii) on cumulative-P&L-only (value minus cumulative contributions to
    date), which isolates market/strategy risk from the mechanical effect of
    still adding new cash every week.
"""
import importlib.util
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)

sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
trades = sim.attrs.get("trades_df").copy()
assert len(trades) == 27

N_BARS = len(df)
close = df["close"].values
open_time = df["open_time"]

# Map exit bar -> pnl_pct (trades never overlap, verified elsewhere in this repo's audit trail)
exit_pnl = dict(zip(trades["exit_idx"].astype(int), trades["pnl_pct"].astype(float)))

# Weekly contribution bars: first bar index of each ISO calendar week
week_key = open_time.dt.isocalendar().year.astype(str) + "-W" + open_time.dt.isocalendar().week.astype(str)
contribution_bars = df.groupby(week_key).apply(lambda g: g.index.min()).sort_values().values
contribution_bars = np.array(sorted(set(int(x) for x in contribution_bars)))


def run_split(s, label):
    dca_only_units = 0.0
    btc_sub_units = 0.0
    strat_cash = 0.0

    dca_only_value = np.empty(N_BARS)
    combined_value = np.empty(N_BARS)
    contrib_this_bar = np.zeros(N_BARS)

    contribution_set = set(contribution_bars.tolist())

    for i in range(N_BARS):
        px = close[i]
        if i in contribution_set:
            dca_only_units += 1.0 / px
            btc_sub_units += (1.0 - s) / px
            strat_cash += s
            contrib_this_bar[i] = 1.0
        if i in exit_pnl:
            strat_cash *= (1.0 + exit_pnl[i] / 100.0)
        dca_only_value[i] = dca_only_units * px
        combined_value[i] = btc_sub_units * px + strat_cash

    # Snapshot at each weekly contribution checkpoint
    idx = contribution_bars
    V_dca = dca_only_value[idx]
    V_comb = combined_value[idx]
    C = contrib_this_bar[idx]  # == 1.0 at every checkpoint by construction

    def period_returns(V, C):
        r = np.empty(len(V) - 1)
        for k in range(1, len(V)):
            r[k - 1] = (V[k] - C[k]) / V[k - 1] - 1.0
        return r

    r_dca = period_returns(V_dca, C)
    r_comb = period_returns(V_comb, C)

    def sharpe_ratio(r, periods_per_year=52):
        mean_r, std_r = r.mean(), r.std(ddof=1)
        return (mean_r / std_r) * np.sqrt(periods_per_year) if std_r > 0 else float("nan")

    def max_dd_pct(V):
        running_max = np.maximum.accumulate(V)
        dd = (V - running_max) / running_max * 100
        return dd.min()

    def max_dd_dollars(pnl):
        # pnl can be negative (portfolio underwater vs. contributions) early on,
        # so a % drawdown on it is ill-defined (division by ~0 or negative peak).
        # Report the largest peak-to-trough DOLLAR retracement instead, per $1/wk
        # contributed, which stays well-defined regardless of sign.
        running_max = np.maximum.accumulate(pnl)
        return (pnl - running_max).min()

    cum_contrib = np.cumsum(C)
    pnl_dca = V_dca - cum_contrib
    pnl_comb = V_comb - cum_contrib

    sh_dca = sharpe_ratio(r_dca)
    sh_comb = sharpe_ratio(r_comb)

    print(f"--- Split: {label} (s={s:.2f} to strategy sleeve) ---")
    print(f"  {'Metric':<42} | {'DCA-only (100% BTC)':<22} | {'Combined':<22}")
    print(f"  {'Final value ($1/wk, ' + str(len(idx)) + ' wks)':<42} | {V_dca[-1]:>20.2f}  | {V_comb[-1]:>20.2f}")
    print(f"  {'Total contributed':<42} | {cum_contrib[-1]:>20.2f}  | {cum_contrib[-1]:>20.2f}")
    print(f"  {'Final cumulative P&L ($)':<42} | {pnl_dca[-1]:>20.2f}  | {pnl_comb[-1]:>20.2f}")
    print(f"  {'Sharpe (weekly, annualized)':<42} | {sh_dca:>20.3f}  | {sh_comb:>20.3f}")
    print(f"  {'Max drawdown, principal-inclusive':<42} | {max_dd_pct(V_dca):>19.2f}%  | {max_dd_pct(V_comb):>19.2f}%")
    print(f"  {'Max peak-to-trough P&L retracement ($)':<42} | {max_dd_dollars(pnl_dca):>20.2f}  | {max_dd_dollars(pnl_comb):>20.2f}")
    print()


print("=" * 100)
print("  DCA-INTO-BTC + INDEPENDENTLY-CAPITALIZED STRATEGY SLEEVE, vs. 100%-DCA-ONLY BASELINE")
print(f"  {len(contribution_bars)} weekly $1 contributions, 2022-01-01 .. 2026-01-01")
print("=" * 100)
for s, label in [(0.10, "90/10"), (0.20, "80/20 (primary)"), (0.30, "70/30")]:
    run_split(s, label)
