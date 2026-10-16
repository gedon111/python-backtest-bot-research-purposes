"""
Post-hoc transaction-cost sensitivity analysis for the min_ob_quality=0
baseline trade log.

Read-only, additive analysis: loads artifacts/candles.csv, runs the
UNMODIFIED src/Binance backtest bot.py strategy, and mutates only an
in-memory COPY of the resulting trades_df. Never touches simulate_trades(),
never writes to backtest_results.db or any artifacts/* file, never changes
a locked/reported headline number.

Fee/slippage is applied as a flat round-trip percentage-of-notional drag,
identical for every trade regardless of side or size (standard backtest
fee-modeling practice for a fixed-percentage-return trade log).

Primary scenario (default CLI args):
  - Fee: 0.05% (5bps) per side -- Binance USDT-M Futures standard tier
    (VIP 0, no BNB discount) taker rate, confirmed against Binance's
    published fee schedule (binance.com/en/support/faq/detail/360033544231,
    cross-checked against independent fee-tracking sources, August 2026).
    The taker rate applies because entries/exits in this backtest are
    triggered at a bar-close price crossing a threshold -- a
    market-order-like fill, not a resting limit order.
  - Slippage: 0.05% (5bps) per side, a conservative estimate for BTC/USDT
    4H bar-close execution on a deep, liquid pair -- kept STRICTLY SEPARATE
    from the fee line item, since it is not a published exchange number.
  - Combined "PRIMARY" scenario: 0.10% + 0.10% = 0.20% round-trip drag.

A "GROSS" (no cost) scenario and a "FEE ONLY" (fee, no slippage) scenario
are always reported alongside PRIMARY. A fixed LOW/MID/HIGH sensitivity band
(bundled fee+slippage guesses predating this script's fee confirmation:
0.14% / 0.24% / 0.40% round trip) is retained for comparison, clearly
labeled as pre-confirmation.

For every scenario, reruns:
  - One-sided and two-sided exact binomial test on win rate
  - Fisher's exact test (win/loss x criterion-true) for each of the 5
    orthogonal OB quality criteria
  - Welch's t-test (pnl_pct x criterion-true) for each of the 5 criteria

Usage (run from repo root):
    python analysis/fee_slippage_analysis.py
    python analysis/fee_slippage_analysis.py --taker-fee-bps 5.0 --slippage-bps 5.0
    python analysis/fee_slippage_analysis.py --min-ob-quality 0 --no-sensitivity-band

Promoted from scratch/fee_slippage_audit.py (verified byte-for-byte
identical scenario numbers at default args before promotion).
"""
import argparse
import importlib.util

import pandas as pd
from scipy import stats as sstats

from _json_utils import write_json

CRITERIA = {
    "Displacement": "entry_ob_quality_displacement",
    "LargeBar": "entry_ob_quality_large_bar",
    "FVG": "entry_ob_quality_fvg",
    "LiqSweep": "entry_ob_quality_liquidity_sweep",
    "VolExpansion": "entry_ob_quality_volume_expansion",
}

# Fixed historical sensitivity band: bundled fee+slippage guesses from before
# this script's fee figure was confirmed against Binance's published rate.
# Kept only as a comparison point, not as the primary estimate.
LEGACY_SENSITIVITY_BAND = [
    ("[sensitivity band, pre-confirmation] LOW  (4bps taker + 3bps slip, round trip)", 0.14),
    ("[sensitivity band, pre-confirmation] MID  (7bps taker + 5bps slip, round trip)", 0.24),
    ("[sensitivity band, pre-confirmation] HIGH (10bps taker + 10bps slip, round trip)", 0.40),
]


def load_trades(min_ob_quality: int) -> pd.DataFrame:
    spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)

    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    df = bot.compute_indicators(df)

    sim = bot.simulate_trades(df.copy(), min_ob_quality=min_ob_quality)
    trades = sim.attrs.get("trades_df").copy()
    return trades


def run_scenario(trades: pd.DataFrame, label: str, drag_pct: float) -> dict:
    t = trades.copy()
    t["pnl_pct_adj"] = t["pnl_pct"] - drag_pct

    total_return = t["pnl_pct_adj"].sum()
    avg_return = t["pnl_pct_adj"].mean()
    sd_return = t["pnl_pct_adj"].std(ddof=1)
    wins = int((t["pnl_pct_adj"] > 0).sum())
    n = len(t)

    flipped = t[(trades["pnl_pct"] > 0) & (t["pnl_pct_adj"] <= 0)]

    bt = sstats.binomtest(wins, n, 0.5, alternative="greater")
    bt_two = sstats.binomtest(wins, n, 0.5, alternative="two-sided")

    print("=" * 100)
    print(f"  SCENARIO: {label}  (drag = {drag_pct:.2f}% round trip per trade)")
    print("=" * 100)
    print(f"  Total net return:      {total_return:+.4f}%  (gross was {trades['pnl_pct'].sum():+.4f}%)")
    print(f"  Avg return/trade:      {avg_return:+.4f}%")
    print(f"  SD (return/trade):     {sd_return:.4f}%")
    print(f"  Win rate:              {wins}/{n} = {wins / n * 100:.2f}%  (gross was {(trades['pnl_pct'] > 0).sum()}/{n})")
    print(f"  One-sided binomial p:  {bt.pvalue:.4f}")
    print(f"  Two-sided binomial p:  {bt_two.pvalue:.4f}")
    if not flipped.empty:
        print(f"  Trades flipped WIN->LOSS ({len(flipped)}):")
        for _, r in flipped.iterrows():
            print(f"    entry_idx={int(r['entry_idx']):<6} gross={r['pnl_pct']:+.4f}%  net={r['pnl_pct_adj']:+.4f}%")
    else:
        print("  Trades flipped WIN->LOSS: none")

    print(f"\n  Per-criterion Fisher's exact (win/loss) and Welch's t-test (pnl_pct), fee-adjusted:")
    print(f"  {'Criterion':<14} | {'True n(w)':<10} | {'False n(w)':<11} | {'Fisher p':<10} | {'Welch t':<10} | {'Welch p':<10}")
    criteria_results = {}
    for name, col in CRITERIA.items():
        mask = t[col].astype(bool)
        true_grp = t.loc[mask, "pnl_pct_adj"]
        false_grp = t.loc[~mask, "pnl_pct_adj"]
        true_wins = int((true_grp > 0).sum())
        false_wins = int((false_grp > 0).sum())
        true_losses = len(true_grp) - true_wins
        false_losses = len(false_grp) - false_wins
        _, fisher_p = sstats.fisher_exact([[true_wins, true_losses], [false_wins, false_losses]])
        t_stat, welch_p = sstats.ttest_ind(true_grp, false_grp, equal_var=False)
        print(f"  {name:<14} | {len(true_grp)} ({true_wins})".ljust(24) +
              f"| {len(false_grp)} ({false_wins})".ljust(15) +
              f"| {fisher_p:<10.4f} | {t_stat:<+10.4f} | {welch_p:<10.4f}")
        criteria_results[name] = {
            "true_n": len(true_grp), "true_wins": true_wins,
            "false_n": len(false_grp), "false_wins": false_wins,
            "fisher_p": fisher_p, "welch_t": t_stat, "welch_p": welch_p,
        }
    print()

    return {
        "label": label,
        "drag_pct": drag_pct,
        "total_return_pct": total_return,
        "avg_return_pct": avg_return,
        "sd_return_pct": sd_return,
        "wins": wins,
        "n": n,
        "win_rate_pct": wins / n * 100,
        "binomial_p_one_sided": bt.pvalue,
        "binomial_p_two_sided": bt_two.pvalue,
        "flipped_trades": [
            {"entry_idx": int(r["entry_idx"]), "gross_pnl_pct": r["pnl_pct"], "net_pnl_pct": r["pnl_pct_adj"]}
            for _, r in flipped.iterrows()
        ],
        "criteria": criteria_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-ob-quality", type=int, default=0,
                         help="OB quality threshold to simulate (default: 0, the locked baseline)")
    parser.add_argument("--taker-fee-bps", type=float, default=5.0,
                         help="Taker fee in bps per side (default: 5.0 = Binance USDT-M Futures standard tier, confirmed)")
    parser.add_argument("--slippage-bps", type=float, default=5.0,
                         help="Conservative slippage estimate in bps per side (default: 5.0)")
    parser.add_argument("--no-sensitivity-band", action="store_true",
                         help="Skip the legacy pre-confirmation LOW/MID/HIGH sensitivity band")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write results as JSON (does not change printed output)")
    args = parser.parse_args()

    trades = load_trades(args.min_ob_quality)
    expected_n = 27 if args.min_ob_quality == 0 else None
    if expected_n is not None:
        assert len(trades) == expected_n, f"expected {expected_n} baseline trades, got {len(trades)}"

    fee_round_trip = 2 * args.taker_fee_bps * 0.01
    slip_round_trip = 2 * args.slippage_bps * 0.01
    primary_round_trip = fee_round_trip + slip_round_trip

    scenarios = [
        ("GROSS (no fees, no slippage -- as currently reported)", 0.0),
        (f"FEE ONLY (confirmed {args.taker_fee_bps:.2f}bps/side taker, no slippage, round trip)", fee_round_trip),
        (f"PRIMARY: FEE (confirmed) + CONSERVATIVE SLIPPAGE "
         f"({args.taker_fee_bps:.2f}+{args.slippage_bps:.2f}bps/side, round trip)", primary_round_trip),
    ]
    if not args.no_sensitivity_band:
        scenarios += LEGACY_SENSITIVITY_BAND

    results = [run_scenario(trades, label, drag) for label, drag in scenarios]

    if args.json_out:
        write_json({"min_ob_quality": args.min_ob_quality, "scenarios": results}, args.json_out)


if __name__ == "__main__":
    main()
