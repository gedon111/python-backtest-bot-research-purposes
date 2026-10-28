"""
EXPERIMENTAL -- after-cost bootstrap intervals, power and cost threshold for
the paper's 27 baseline 4h trades (2022-2026).

Added 2026-10-28 for bitcoin (7) (review items M4, M15, m13). It does not
change any trade, rule or headline figure. Every input is the committed
baseline trade log rebuilt by simulate_trades(); every method is one the
paper already uses:

- Percentile (iid) bootstrap: run_bootstrap_ci() (B = 10,000, seed 42, the
  paper's headline settings) on pnl_pct minus the 0.20% round trip.
- Stationary block bootstrap: ml_meta_labeling.stationary_block_bootstrap(),
  the paper's Formula 4 (expected block length round(n^(1/3)) = 3,
  B = 10,000), with the same seed 42.
- Power of the one-sided exact binomial test at alpha = 0.05 for n = 27 at
  true win rates of 60%, 65% and 70% (scipy).
- Forward test: probability of 1 or fewer wins in 4 trades if the true win
  rate were the backtest's 19/27.
- Cost threshold: H1 stays significant only while the round-trip cost is
  below the smallest winning trade's gross return (wins = pnl_pct - cost > 0).

Output: experimental/results/bootstrap_net_4h.json
"""

import json
import os
import sys

from scipy import stats

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, EXPERIMENT_DIR)

import research_analysis as ra  # noqa: E402
import ml_meta_labeling as mml  # noqa: E402

OUT_PATH = os.path.join(EXPERIMENT_DIR, "results", "bootstrap_net_4h.json")
COST_PCT = ra.BENCHMARK_ROUND_TRIP_DRAG_PCT  # 0.20
SEED = 42
RESAMPLES = 10_000
ALPHA = 0.05


def critical_wins(n, alpha=ALPHA):
    """Smallest k with one-sided P(X >= k | n, 0.5) <= alpha."""
    return next(k for k in range(n + 1) if stats.binom.sf(k - 1, n, 0.5) <= alpha)


def main():
    df = ra.compute_indicators(ra.load_candles())
    trades = ra.simulate_trades(df.copy(), min_ob_quality=0).attrs["trades_df"]
    assert len(trades) == ra.LOCKED_BASELINE_TRADE_COUNT == 27
    gross = trades["pnl_pct"].astype(float)
    net = gross - COST_PCT

    gross_iid = ra.run_bootstrap_ci(trades, RESAMPLES, SEED)
    net_iid = ra.run_bootstrap_ci(trades.assign(pnl_pct=net), RESAMPLES, SEED)
    gross_block = mml.stationary_block_bootstrap(gross.values, RESAMPLES, SEED)
    net_block = mml.stationary_block_bootstrap(net.values, RESAMPLES, SEED)

    n = len(trades)
    k = critical_wins(n)
    power = {f"{p:.2f}": float(stats.binom.sf(k - 1, n, p)) for p in (0.60, 0.65, 0.70)}
    backtest_win_rate = float((gross > 0).mean())
    winners = gross[gross > 0].sort_values()

    out = {
        "n": n, "cost_pct": COST_PCT, "seed": SEED, "resamples": RESAMPLES,
        "observed": {"gross_total": float(gross.sum()), "gross_mean": float(gross.mean()),
                     "net_total": float(net.sum()), "net_mean": float(net.mean())},
        "percentile_bootstrap": {"gross": gross_iid, "net": net_iid},
        "stationary_block_bootstrap": {"gross": gross_block, "net": net_block},
        "binomial_power": {"alpha": ALPHA, "critical_wins": k,
                           "p_at_critical": float(stats.binom.sf(k - 1, n, 0.5)),
                           "p_at_one_fewer": float(stats.binom.sf(k - 2, n, 0.5)),
                           "power_by_true_win_rate": power},
        "forward_test_tail": {"trades": 4, "wins": 1, "assumed_win_rate": backtest_win_rate,
                              "p_le_1_win": float(stats.binom.cdf(1, 4, backtest_win_rate))},
        "cost_threshold": {
            "smallest_winners_gross_pct": [float(v) for v in winners.iloc[:3]],
            "smallest_winner_entry_idx": [int(trades.loc[i, "entry_idx"]) for i in winners.index[:3]],
            "h1_significant_while_cost_below_pct": float(winners.iloc[0]),
            "note": "With cost c, wins = #(pnl_pct > c). 19 wins (p = 0.0261) needs c below the smallest "
                    "winner; at 18 wins p exceeds 0.05.",
        },
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=ra.json_safe)
    print(json.dumps(out, indent=1, default=ra.json_safe))


if __name__ == "__main__":
    main()
