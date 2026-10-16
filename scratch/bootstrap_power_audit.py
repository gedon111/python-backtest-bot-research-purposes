"""
Item 3 (investigation session): two standalone, non-pipeline-integrated checks
on the existing 27-trade min_ob_quality=0 baseline. Read-only against
artifacts/candles.csv via the unmodified strategy; does not touch
simulate_trades(), any committed artifact, or the ablation-arm bootstrap
methodology already documented in docs/ablation_*.md (which resamples FROM
the indicators-only ablation pool -- a different, between-arms design). This
script instead bootstraps the strategy's OWN 27 trade returns.

(a) Nonparametric bootstrap (resample 27 pnl_pct values with replacement,
    B=10000) -> 95% CI on total return and average return/trade.

(b) Minimum-detectable-effect (MDE) framing for the 5 orthogonal-criterion
    True/False subgroup comparisons: given each criterion's actual observed
    subgroup sizes and standard deviations, what mean-return difference would
    be needed for an 80%-power, alpha=0.05 two-sided Welch's t-test to reliably
    detect it? Uses the standard two-sample MDE approximation
    MDE = (z_{alpha/2} + z_{beta}) * sqrt(SD1^2/n1 + SD2^2/n2), z_{0.025}=1.9600,
    z_{0.80 power}=0.8416 -- a normal approximation to the Welch t reference
    distribution, standard for a post-hoc power/MDE sanity check at this scale
    and adequate given the subgroup sizes involved (n=4..23) are themselves
    too small for the approximation error to be the limiting factor.
"""
import importlib.util
import numpy as np
import pandas as pd
from scipy import stats as sstats

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)

sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
trades = sim.attrs.get("trades_df").copy()
assert len(trades) == 27

pnl = trades["pnl_pct"].values
n = len(pnl)

# ─── (a) Bootstrap CI on the strategy's own total / average return ──────────
print("=" * 90)
print("  (a) BOOTSTRAP CI ON OWN 27-TRADE RETURN (B=10,000, resample with replacement)")
print("=" * 90)

rng = np.random.default_rng(42)
B = 10000
boot_totals = np.empty(B)
boot_means = np.empty(B)
for b in range(B):
    sample = rng.choice(pnl, size=n, replace=True)
    boot_totals[b] = sample.sum()
    boot_means[b] = sample.mean()

total_point = pnl.sum()
mean_point = pnl.mean()
total_ci = np.percentile(boot_totals, [2.5, 97.5])
mean_ci = np.percentile(boot_means, [2.5, 97.5])

print(f"  Point estimate total return:      {total_point:+.4f}%")
print(f"  Bootstrap 95% CI on total return:  [{total_ci[0]:+.4f}%, {total_ci[1]:+.4f}%]")
print(f"  Point estimate avg return/trade:  {mean_point:+.4f}%")
print(f"  Bootstrap 95% CI on avg return:    [{mean_ci[0]:+.4f}%, {mean_ci[1]:+.4f}%]")
print(f"  Fraction of bootstrap resamples with total return <= 0: {(boot_totals <= 0).mean()*100:.2f}%")
print(f"  Fraction of bootstrap resamples with avg return <= 0:   {(boot_means <= 0).mean()*100:.2f}%")
print()
print("  NOTE: this is a percentile bootstrap on the strategy's own empirical")
print("  return distribution (resampling entry selection is NOT re-simulated --")
print("  it treats the 27 realized trade outcomes as the population to resample")
print("  from, which is the standard nonparametric approach for a fixed trade")
print("  log, but does NOT capture uncertainty in which trades would have fired")
print("  under a different history).")
print()

# ─── (b) MDE / power framing per orthogonal criterion ───────────────────────
CRITERIA = {
    "Displacement":  "entry_ob_quality_displacement",
    "LargeBar":      "entry_ob_quality_large_bar",
    "FVG":           "entry_ob_quality_fvg",
    "LiqSweep":      "entry_ob_quality_liquidity_sweep",
    "VolExpansion":  "entry_ob_quality_volume_expansion",
}

Z_ALPHA_2 = 1.9600   # alpha=0.05 two-sided
Z_BETA_80 = 0.8416   # 80% power

print("=" * 100)
print("  (b) MINIMUM DETECTABLE EFFECT (MDE) PER ORTHOGONAL CRITERION, alpha=0.05, power=0.80")
print("=" * 100)
print(f"  {'Criterion':<14} | {'n(True)':<8} | {'SD(True)':<9} | {'n(False)':<9} | {'SD(False)':<10} | "
      f"{'Observed diff':<14} | {'MDE (80% pwr)':<14} | {'Diff detectable?':<17}")

for name, col in CRITERIA.items():
    mask = trades[col].astype(bool)
    true_grp = trades.loc[mask, "pnl_pct"]
    false_grp = trades.loc[~mask, "pnl_pct"]
    n1, n2 = len(true_grp), len(false_grp)
    sd1, sd2 = true_grp.std(ddof=1), false_grp.std(ddof=1)
    observed_diff = true_grp.mean() - false_grp.mean()

    se = np.sqrt(sd1**2 / n1 + sd2**2 / n2)
    mde = (Z_ALPHA_2 + Z_BETA_80) * se
    detectable = "yes" if abs(observed_diff) >= mde else "NO (underpowered)"

    print(f"  {name:<14} | {n1:<8} | {sd1:<9.4f} | {n2:<9} | {sd2:<10.4f} | "
          f"{observed_diff:<+14.4f} | {mde:<14.4f} | {detectable:<17}")

print()
print("  Interpretation: 'MDE' is the smallest TRUE mean-return gap between a")
print("  criterion's True/False subgroups that this sample size could detect")
print("  80% of the time at alpha=0.05, given the OBSERVED subgroup SDs. Where")
print("  the observed difference is smaller than the MDE, the correct reading")
print("  of a non-significant Welch's t-test is 'underpowered to rule out a gap")
print("  up to roughly +/-MDE', not 'no gap exists' -- these are not the same")
print("  claim, and only the former is what this data can actually support.")
