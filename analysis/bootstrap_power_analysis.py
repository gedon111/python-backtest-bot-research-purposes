"""
Bootstrap confidence intervals and minimum-detectable-effect (MDE) / power
analysis for the min_ob_quality=0 baseline trade log.

Read-only, additive analysis: loads artifacts/candles.csv, runs the
UNMODIFIED src/Binance backtest bot.py strategy, and only reads from the
resulting trades_df. Never touches simulate_trades(), never writes to
backtest_results.db or any artifacts/* file, never changes a
locked/reported headline number. Distinct from the ablation-arm bootstrap
methodology documented in docs/ablation_*.md (which resamples FROM the
indicators-only ablation pool, a between-arms design) -- this bootstraps
the strategy's OWN 27 trade returns.

(a) Nonparametric percentile bootstrap (resample n trades with replacement,
    B resamples, default 10,000) on the trade log's own total and average
    return -> 95% CI on each.

(b) MDE / power framing for the 5 orthogonal OB quality criteria: given each
    criterion's actual observed True/False subgroup sizes and standard
    deviations, computes the smallest true mean-return gap between
    subgroups that this sample size could detect 80% of the time at
    alpha=0.05, using the standard two-sample normal-approximation MDE
        MDE = (z_alpha/2 + z_beta) * sqrt(SD1^2/n1 + SD2^2/n2)
    A normal approximation to the Welch t reference distribution is
    standard practice for a post-hoc power/MDE sanity check at this scale,
    and is adequate here since the subgroup sizes (n=4..23) are themselves
    the binding constraint, not the approximation error.

Usage (run from repo root):
    python analysis/bootstrap_power_analysis.py
    python analysis/bootstrap_power_analysis.py --bootstrap-n 5000 --seed 7
    python analysis/bootstrap_power_analysis.py --power 0.8 --alpha 0.05

Promoted from scratch/bootstrap_power_audit.py (verified byte-for-byte
identical numbers at default args before promotion, aside from RNG-seed-
dependent bootstrap CI figures reproducing exactly at the same seed).
"""
import argparse
import importlib.util

import numpy as np
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


def load_trades(min_ob_quality: int) -> pd.DataFrame:
    spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)

    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    df = bot.compute_indicators(df)

    sim = bot.simulate_trades(df.copy(), min_ob_quality=min_ob_quality)
    return sim.attrs.get("trades_df").copy()


def bootstrap_ci(trades: pd.DataFrame, b: int, seed: int) -> dict:
    pnl = trades["pnl_pct"].values
    n = len(pnl)

    print("=" * 90)
    print(f"  (a) BOOTSTRAP CI ON OWN {n}-TRADE RETURN (B={b:,}, resample with replacement, seed={seed})")
    print("=" * 90)

    rng = np.random.default_rng(seed)
    boot_totals = np.empty(b)
    boot_means = np.empty(b)
    for i in range(b):
        sample = rng.choice(pnl, size=n, replace=True)
        boot_totals[i] = sample.sum()
        boot_means[i] = sample.mean()

    total_point = pnl.sum()
    mean_point = pnl.mean()
    total_ci = np.percentile(boot_totals, [2.5, 97.5])
    mean_ci = np.percentile(boot_means, [2.5, 97.5])

    print(f"  Point estimate total return:      {total_point:+.4f}%")
    print(f"  Bootstrap 95% CI on total return:  [{total_ci[0]:+.4f}%, {total_ci[1]:+.4f}%]")
    print(f"  Point estimate avg return/trade:  {mean_point:+.4f}%")
    print(f"  Bootstrap 95% CI on avg return:    [{mean_ci[0]:+.4f}%, {mean_ci[1]:+.4f}%]")
    print(f"  Fraction of bootstrap resamples with total return <= 0: {(boot_totals <= 0).mean() * 100:.2f}%")
    print(f"  Fraction of bootstrap resamples with avg return <= 0:   {(boot_means <= 0).mean() * 100:.2f}%")
    print()
    print("  NOTE: percentile bootstrap on the strategy's own empirical return")
    print("  distribution -- treats the realized trade outcomes as the population")
    print("  to resample from (standard for a fixed trade log), but does NOT")
    print("  capture uncertainty in which trades would have fired under a")
    print("  different history.")
    print()

    return {
        "b": b, "seed": seed, "n": n,
        "total_return_point_pct": total_point, "total_return_ci_pct": total_ci.tolist(),
        "avg_return_point_pct": mean_point, "avg_return_ci_pct": mean_ci.tolist(),
        "pct_resamples_total_le_zero": (boot_totals <= 0).mean() * 100,
        "pct_resamples_avg_le_zero": (boot_means <= 0).mean() * 100,
    }


def mde_power(trades: pd.DataFrame, alpha: float, power: float) -> dict:
    z_alpha_2 = sstats.norm.ppf(1 - alpha / 2)
    z_beta = sstats.norm.ppf(power)

    print("=" * 100)
    print(f"  (b) MINIMUM DETECTABLE EFFECT (MDE) PER ORTHOGONAL CRITERION, alpha={alpha}, power={power}")
    print("=" * 100)
    print(f"  {'Criterion':<14} | {'n(True)':<8} | {'SD(True)':<9} | {'n(False)':<9} | {'SD(False)':<10} | "
          f"{'Observed diff':<14} | {'MDE':<14} | {'Diff detectable?':<17}")

    results = {}
    for name, col in CRITERIA.items():
        mask = trades[col].astype(bool)
        true_grp = trades.loc[mask, "pnl_pct"]
        false_grp = trades.loc[~mask, "pnl_pct"]
        n1, n2 = len(true_grp), len(false_grp)
        sd1, sd2 = true_grp.std(ddof=1), false_grp.std(ddof=1)
        observed_diff = true_grp.mean() - false_grp.mean()

        se = np.sqrt(sd1 ** 2 / n1 + sd2 ** 2 / n2)
        mde = (z_alpha_2 + z_beta) * se
        detectable = abs(observed_diff) >= mde

        print(f"  {name:<14} | {n1:<8} | {sd1:<9.4f} | {n2:<9} | {sd2:<10.4f} | "
              f"{observed_diff:<+14.4f} | {mde:<14.4f} | {'yes' if detectable else 'NO (underpowered)':<17}")

        results[name] = {
            "n_true": n1, "sd_true": sd1, "n_false": n2, "sd_false": sd2,
            "observed_diff_pct": observed_diff, "mde_pct": mde, "detectable": bool(detectable),
        }

    print()
    print("  Interpretation: 'MDE' is the smallest TRUE mean-return gap between a")
    print("  criterion's True/False subgroups that this sample size could detect")
    print(f"  at the given power {power:.0%} of the time at alpha={alpha}, given the")
    print("  OBSERVED subgroup SDs. Where the observed difference is smaller than")
    print("  the MDE, the correct reading of a non-significant test is 'underpowered")
    print("  to rule out a gap up to roughly +/-MDE', not 'no gap exists'.")

    return {"alpha": alpha, "power": power, "criteria": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-ob-quality", type=int, default=0,
                         help="OB quality threshold to simulate (default: 0, the locked baseline)")
    parser.add_argument("--bootstrap-n", type=int, default=10000, help="Number of bootstrap resamples (default: 10,000)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for the bootstrap (default: 42)")
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance level for the MDE calc (default: 0.05)")
    parser.add_argument("--power", type=float, default=0.80, help="Target power for the MDE calc (default: 0.80)")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write results as JSON (does not change printed output)")
    args = parser.parse_args()

    trades = load_trades(args.min_ob_quality)
    expected_n = 27 if args.min_ob_quality == 0 else None
    if expected_n is not None:
        assert len(trades) == expected_n, f"expected {expected_n} baseline trades, got {len(trades)}"

    bootstrap_result = bootstrap_ci(trades, args.bootstrap_n, args.seed)
    mde_result = mde_power(trades, args.alpha, args.power)

    if args.json_out:
        write_json({"min_ob_quality": args.min_ob_quality, "bootstrap": bootstrap_result, "mde_power": mde_result},
                    args.json_out)


if __name__ == "__main__":
    main()
