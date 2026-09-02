# Math Correctness + Comprehension Audit

Scope: the 5 CUSTOM_IMPLEMENTATION / HYBRID functions in `research_analysis.py`
(the 5 direct `scipy.stats` wrappers — `binomtest`, `fisher_exact`, `ttest_ind`,
`pearsonr`, `spearmanr` — are out of scope; they're library calls, not custom math,
and were already provenance-checked in `PROVENANCE_VERDICT.md`):

1. `bootstrap_resample()` / `run_bootstrap_ci()` — `research_analysis.py:2866`, `3155`
2. `bootstrap_ablation_arm_vs_baseline()` — `research_analysis.py:2621`
3. `mde_power_analysis()` — `research_analysis.py:2978`
4. `max_drawdown_pct()` — `research_analysis.py:3033`
5. `sharpe_sortino_ratios()` — `research_analysis.py:3057`

Every numeric example below was actually run against the live functions (not
hand-simulated) by importing `research_analysis.py` and calling them directly,
then cross-checked against an independently written recomputation. Verification
script results are reproduced inline; nothing here is asserted without a
matching computed number.

**Verdict up front: no incorrect math was found.** All 5 functions correctly
implement their respective standard formulas. What follows below is not "these
are wrong" — it's "here is exactly what each one assumes, so you can defend
every assumption by name if asked."

---

## FLAGGED — REVIEW BEFORE DEFENSE

None of these are bugs. All are silent, undisclosed **simplifying assumptions**
or **edge-case behaviors** that a panelist could reasonably probe. Know these
by name before the defense.

### F1. Sharpe/Sortino implicitly assume risk-free rate (and MAR) = 0 — undisclosed in the docstring

`sharpe_sortino_ratios()` (`research_analysis.py:3057`) computes
`sharpe = mean_return / return_std * sqrt(periods_per_year)` — i.e. it uses the
raw per-bar return directly, with **no subtraction of a risk-free rate**.

The textbook formula (Sharpe 1994, "The Sharpe Ratio," *Journal of Portfolio
Management* 21(1): 49–58) is:

> SR = E[R_a − R_f] / σ, where σ = std(R_a − R_f)

i.e. the numerator and the thing you take the standard deviation of are both
**excess** return over a risk-free/benchmark rate `R_f`, not the raw return.
The code is mathematically equivalent to setting `R_f = 0` for every bar.

Same story for Sortino: `downside_returns = np.minimum(bar_returns, 0.0)` uses
a **Minimum Acceptable Return (MAR) of 0**. Sortino & van der Meer's original
1991 formula (*Journal of Portfolio Management* 17: 27–31) is defined against
a general target `T` (MAR), not hardwired to 0:

> σ_d = sqrt( (1/N) · Σᵢ₌₁ᴺ [min(0, Rᵢ − T)]² )

**Why this is defensible, not wrong:** for a strategy with no explicit funding-
rate or benchmark to subtract (crypto, no formal cash leg modeled), assuming
`R_f = MAR = 0` is a common and reasonable simplification — but it is a real,
nameable deviation from the textbook formula's general form, and the docstring
doesn't say so. If a panelist asks "where's the risk-free rate in this Sharpe
ratio," the honest answer is "assumed zero, not subtracted — not stated in the
code comments, but mathematically implied by the direct use of raw returns."

### F2. `mde_power_analysis()`'s `detectable` flag reads `False`, not "undefined," when a subgroup's SD is NaN

If a subgroup has fewer than 2 trades, `np.std(..., ddof=1)` divides by
`n - 1 = 0`, producing `NaN` (with a `RuntimeWarning`, not an exception — see
numeric check below). `mde` then becomes `NaN`, and
`detectable = abs(observed_diff) >= mde` evaluates to `False` in Python
because **any comparison against NaN is False** — never raises, never flags
itself as unusable. Read naively, `"detectable": False` looks identical to a
real "this sample is underpowered" result, when the real state is "this MDE
could not be computed at all."

**Does this occur in the actual study?** No — the module docstring for
`mde_power_analysis()` states subgroup sizes range n=4..23 across the 5 OB
quality criteria actually used (`run_mde_power_report()`,
`research_analysis.py:3196`), so this path is never hit on real data. Still
worth naming if asked "what happens with a 1-trade subgroup" — the honest
answer is "the code would silently report `detectable: False`, which is
misleading; it should really say 'undefined.'"

### F3. Plain percentile bootstrap, not bias-corrected (BCa)

`bootstrap_resample()` / `run_bootstrap_ci()` use the plain **percentile**
method (Efron 1981/1982): take the raw 2.5th/97.5th percentiles of the
resample distribution as the CI bounds. This is the simplest bootstrap CI
variant. It does not apply the bias-correction-and-acceleration (BCa) that
Efron later proposed, which corrects for skew in the resample distribution.
For a 27-trade sample with a right-skewed return distribution (a few large
winners), the plain percentile CI can be mildly liberal/conservative relative
to BCa. This is a standard, disclosed-as-standard simplification (the
docstring already says "standard practice for a fixed trade log"), not a
hidden defect — named here so you have the specific term ("BCa") ready if a
panelist asks "why not a corrected bootstrap."

---

## 1. `bootstrap_resample()` / `run_bootstrap_ci()`

**Location:** `research_analysis.py:2866` (mechanism), `:3155` (applies it to
the baseline's own 27 trades for the paper's headline 95% CI).

### Step 1 — Canonical source

Bradley Efron, "Bootstrap Methods: Another Look at the Jackknife," *Annals of
Statistics* 7(1): 1–26 (1979) — introduces resampling-with-replacement to
estimate a statistic's sampling distribution without assuming a parametric
form. The specific **percentile confidence interval** construction used here
(take the α/2 and 1−α/2 percentiles of the resample distribution directly as
the CI) is Efron (1981, 1982); it's the simplest of the bootstrap CI family,
predating the bias-corrected (BC) and bias-corrected-and-accelerated (BCa)
refinements. In one line: draw B resamples of size n with replacement from the
data, compute your statistic on each, and read the CI off the resulting
histogram's percentiles.

### Step 2 — Line-by-line correctness check

```python
values = np.asarray(values)
n = resample_size if resample_size is not None else len(values)   # resample at original n by default
rng = np.random.default_rng(seed)                                  # modern Generator API, not legacy RandomState
resample_totals = np.empty(bootstrap_resamples)
resample_means = np.empty(bootstrap_resamples)
for k in range(bootstrap_resamples):
    sample = rng.choice(values, size=n, replace=True)               # <-- the "bootstrap" step: WITH replacement
    resample_totals[k] = sample.sum()
    resample_means[k] = sample.mean()
```

- `replace=True` is the entire definition of a bootstrap resample (vs. a
  permutation test, which resamples *without* replacement) — correctly set.
- Default `n = len(values)` matches Efron's prescription: each resample must
  be the **same size** as the original sample, not larger or smaller, so that
  resample-to-resample variability reflects genuine sampling variability, not
  an artifact of a mismatched sample size.
- `run_bootstrap_ci()` (`:3155`) then does
  `np.percentile(resample_totals, [2.5, 97.5])` — the textbook percentile-CI
  read-off, no interpolation subtleties beyond numpy's default linear
  interpolation between order statistics, which is standard.
- `np.random.default_rng(seed)` is numpy's modern PCG64-based Generator, seeded
  once per call — correct for exact reproducibility; every call with the same
  `(values, B, seed)` produces bit-identical output.
- Edge cases: an empty `values` array would make `rng.choice` raise (numpy
  requires a nonempty array to choose from) — not silently wrong, fails loud.
  A single-element `values` array works fine (every resample is just that one
  value repeated `n` times; percentile CI collapses to a point).

**No deviation found.** This is a correct, standard percentile bootstrap.

### Step 3 — Comprehension bridge

**The problem in one sentence:** you have 27 trades and one number (total
return = +30.31%) — how do you put honest error bars on that number without
assuming the returns follow a bell curve?

**The idea:** treat your 27 actual trades as a stand-in for "the underlying
population of trades this strategy could produce." Repeatedly build a fake
27-trade dataset by drawing (with replacement — so the same real trade can get
picked more than once) from your real 27, compute the total/mean return of
each fake dataset, and do this thousands of times. You now have a whole
distribution of "what totals are plausible" — and the middle 95% of that
distribution is your confidence interval.

**The formula, in plain English:**
- Draw a resample of size 27 from the 27 real trade returns, with replacement.
- Compute its sum and its mean. Do this B (e.g. 10,000) times.
- Sort the B totals. The value 2.5% of the way up is your CI's lower bound;
  97.5% of the way up is your upper bound.

**Worked example (actually run, values = [1.0, 2.0, 3.0, 4.0, 5.0], seed=42):**

```
resample 0: draw=[1. 4. 4. 3. 3.], sum=15.0, mean=3.0
resample 1: draw=[5. 1. 4. 2. 1.], sum=13.0, mean=2.6
resample 2: draw=[3. 5. 4. 4. 4.], sum=20.0, mean=4.0
```

Notice resample 0 drew `3` and `4` twice each and never drew `2` — that's
expected and is the entire mechanism; every resample is a different, valid
re-weighting of the same 5 numbers. With B=2000 resamples of this same 5-value
array, the 95% CI on the total came out to `[9.0, 21.0]` around the true
total of `15.0` — verified by direct import and execution, matching an
independent line-by-line replication of the resampling loop exactly.

**Gotcha questions:**

1. *"Why resample WITH replacement instead of just re-splitting the data?"*
   Without replacement, you'd only ever get permutations of the same 27
   numbers — same sum, same mean, every time (not useful for measuring
   uncertainty). With replacement, some trades get counted 0, 1, 2, or more
   times per resample, which is exactly what lets the resample's total vary —
   that variation IS your estimate of sampling uncertainty.
2. *"Why not just use a normal-distribution confidence interval (mean ± 1.96
   SE) instead?"* That assumes the 27 returns are (approximately) normally
   distributed. Trade returns are typically skewed (a few big winners), so a
   normal-theory CI can be a poor approximation. The bootstrap makes no
   distributional assumption — it uses the data's own actual shape.
3. *"What would change if you used B=100 instead of B=10,000?"* The same
   underlying uncertainty exists either way, but with fewer resamples the
   2.5th/97.5th percentile estimates themselves become noisier — rerunning
   with a different seed at B=100 would give visibly different CI bounds,
   whereas at B=10,000 they've converged to stable values. B is a precision
   knob on the *estimate of the CI*, not a parameter of the underlying math.

---

## 2. `bootstrap_ablation_arm_vs_baseline()`

**Location:** `research_analysis.py:2621`.

### Step 1 — Canonical source

Same family as above (Efron 1979/1981 percentile bootstrap), applied here as
an empirical (bootstrap-based) hypothesis test rather than a CI on one
population — see Efron & Tibshirani, *An Introduction to the Bootstrap*
(1993), ch. 16, on using bootstrap resampling to build empirical p-values for
between-group comparisons.

### Step 2 — Line-by-line correctness check

```python
rng = np.random.default_rng(seed)
for k in range(bootstrap_resamples):
    resample = rng.choice(arm_pnl_values, size=baseline_n, replace=True)  # <-- size=baseline_n (27), NOT len(arm_pnl_values) (140/138)
    win_rate_samples[k] = (resample > 0).mean() * 100
    avg_return_samples[k] = resample.mean()
...
"empirical_p_win_rate_ge_baseline": float((win_rate_samples >= baseline_win_rate).mean()),
```

- The deliberate choice to resample **at `baseline_n` (27), not at the arm
  pool's own size (140 or 138)** is correct for the question being asked:
  "if I drew a sample the *same size as the real baseline* from this arm's
  distribution, how often would it look this good?" Resampling at the pool's
  own size would answer a different question (uncertainty in the arm's own
  mean), not a comparison to the baseline.
- The "empirical p-value" `(win_rate_samples >= baseline_win_rate).mean()` is
  exactly what it says: the fraction of B resamples whose win rate met or
  exceeded the baseline's actual win rate. This is a legitimate nonparametric
  p-value construction (not read off a t/normal table) — correct mechanism
  for "how surprising is the baseline's result if trades were really just
  draws from this arm's pool."
- `>=` (not `>`) is used, so ties count toward "beating" the baseline — a
  defensible, standard convention for this kind of test (matches "at least as
  extreme," the usual empirical-p-value definition).

**No deviation found.**

### Step 3 — Comprehension bridge

**The problem in one sentence:** the OB-gated strategy has 27 trades at
70.37% win rate. Could that just be luck, if the *real* underlying edge is
only the indicators-only ablation arm's (weaker) win rate?

**The idea:** pretend, for the sake of argument, that the ablation arm's 140
trades represent the true population your strategy actually draws from.
Repeatedly draw a sample of size 27 (matching the real baseline's size) from
that pool, with replacement, and see how often a same-sized draw from the
*weaker* population would produce a win rate as good as or better than the
real baseline's 70.37%. If that happens rarely, the baseline's result is hard
to explain away as "the ablation arm just got a lucky 27-trade draw."

**Worked example (actually run, arm_pnl = [1, -1, 2, -2, 3, -3, 4], baseline_n=4, seed=7):**

```
resample 0: draw=[4. 3. 3. 4.], win_rate=100.0, avg=3.5
resample 1: draw=[ 3. -3. -3. -1.], win_rate=25.0, avg=-1.0
resample 2: draw=[ 1.  2. -1.  4.], win_rate=75.0, avg=1.5
```

Over B=2000 resamples of this toy 7-value pool at size 4, with a hypothetical
baseline of 70% win rate / 1.5% avg return: `empirical_p_win_rate_ge_baseline
= 0.422`, `empirical_p_avg_return_ge_baseline = 0.2605` — both independently
recomputed by a separate script and matched to the function's own output
exactly.

**Gotcha questions:**

1. *"Why resample at 27, not at 140?"* Because you're asking "would a
   baseline-sized sample from the weaker population look this good," not
   "how uncertain is the ablation arm's own mean." Resampling at 140 answers
   a different question entirely.
2. *"Is 'empirical p-value' really a p-value?"* Yes, in the nonparametric
   sense — it's the proportion of a resampling distribution that meets or
   exceeds an observed value, which is the standard bootstrap-hypothesis-test
   construction. It's not read from a table because there is no closed-form
   distribution assumed; the resample distribution IS the reference
   distribution.
3. *"Doesn't resampling at a small n (27, or 4 in the toy example) make the
   result unstable?"* Yes, and that's expected, not a flaw — small-n resamples
   have wide percentile bands (a real run at n=4 in the toy example gave a
   95% win-rate band of literally 0%–100%). That width is honest: it reflects
   genuine uncertainty at that sample size, which is exactly what this method
   is supposed to surface, not hide.

---

## 3. `mde_power_analysis()`

**Location:** `research_analysis.py:2978`.

### Step 1 — Canonical source

The standard two-sample normal-approximation Minimum Detectable Effect (MDE)
formula, ubiquitous across A/B-testing and clinical-trial sample-size
literature (e.g. Kohavi et al., *Trustworthy Online Controlled Experiments*,
2020; standard treatments of two-sample power analysis going back to Cohen,
*Statistical Power Analysis for the Behavioral Sciences*). In general form:

> MDE = (z₁₋α/₂ + z_β) · √Var(τ̂)

where for two independent samples, `Var(τ̂) = σ_true²/n_true + σ_false²/n_false`
(variances of independent quantities add).

### Step 2 — Line-by-line correctness check

```python
z_alpha_2 = scipy_stats.norm.ppf(1 - alpha / 2)     # two-sided critical value
z_beta = scipy_stats.norm.ppf(power)                # one-sided power quantile

n_true, n_false = len(group_true_returns), len(group_false_returns)
sd_true = np.std(group_true_returns, ddof=1)        # ddof=1 = Bessel's correction (N-1 denominator)
sd_false = np.std(group_false_returns, ddof=1)
observed_diff = np.mean(group_true_returns) - np.mean(group_false_returns)

standard_error = np.sqrt(sd_true ** 2 / n_true + sd_false ** 2 / n_false)  # SE of the DIFFERENCE of two means
mde = (z_alpha_2 + z_beta) * standard_error
detectable = abs(observed_diff) >= mde
```

- `ddof=1` correctly uses N−1 (Bessel's correction) for the sample standard
  deviation — the unbiased estimator, matching the standard formula's implicit
  use of *sample* SD, not population SD. Confirmed against a hand computation
  below.
- `sd_true**2/n_true + sd_false**2/n_false` is exactly `σ_true²/n_true +
  σ_false²/n_false` — the variance of a difference of two independent sample
  means. Correct term-by-term match.
- `z_alpha_2 = norm.ppf(1 - alpha/2)` is the correct two-sided critical value
  (verified: at alpha=0.05, this returns 1.959964, matching the well-known
  1.96 table value). `z_beta = norm.ppf(power)` is the correct one-sided power
  quantile (at power=0.80, returns 0.841621, matching the standard 0.84 table
  value).
- `detectable = abs(observed_diff) >= mde` correctly asks "does the actually
  observed gap clear the smallest gap this sample size could reliably
  detect" — matches the documented reframing purpose exactly.
- Normal approximation (not Welch's t) is a disclosed simplification in the
  docstring itself, justified there as adequate since subgroup size (n=4..23),
  not approximation error, is the binding constraint on power — this is a
  standard, named practice, not hidden.
- **Edge case (see Flag F2 above):** `n_true` or `n_false` = 1 produces
  `NaN` (verified below), and `detectable` silently reads `False` rather than
  "undefined." Does not occur on real data (n≥4 per the actual criteria).

**No deviation found in the core formula.** F2 above is the only caveat.

### Step 3 — Comprehension bridge

**The problem in one sentence:** if a hypothesis test comes back
"not significant," is that because there's truly no effect, or because the
sample is just too small to see an effect that's actually there? MDE answers:
"given this sample size, how big would a real effect have to be for this test
to have a good chance of catching it?"

**The formula, plain English:**
- `z_alpha_2` and `z_beta`: two numbers pulled off the standard normal
  distribution that encode "how many standard errors away from zero do I need
  to be to call a difference significant at my chosen alpha" and "...to have
  an 80% chance of detecting a real difference of this size," respectively.
- `standard_error`: how much a difference-of-two-sample-means naturally
  wobbles from sample to sample, combining both groups' own spread (SD) and
  size (n). Bigger groups or tighter spreads → smaller SE → the test can
  detect smaller real effects.
- `MDE = (z_alpha_2 + z_beta) * standard_error`: the smallest true gap between
  the two groups' means that this sample size has a good (80%) chance of
  correctly flagging as significant.
- `detectable`: is the gap you *actually* observed at least as big as that
  threshold?

**Worked example (actually run):** `group_true = [1, 2, 3, 4, 5]` (n=5),
`group_false = [0.5, 1.5, 2.5]` (n=3), alpha=0.05, power=0.80.

```
mean_true = 3.0,  mean_false = 1.5   -> observed_diff = 1.5
sd_true (ddof=1) = 1.58114, sd_false (ddof=1) = 1.0
standard_error = sqrt(1.58114^2/5 + 1.0^2/3) = sqrt(0.5 + 0.3333) = 0.91287
z_alpha_2 = norm.ppf(0.975) = 1.959964
z_beta    = norm.ppf(0.80)  = 0.841621
mde = (1.959964 + 0.841621) * 0.91287 = 2.55749
detectable = (|1.5| >= 2.55749) = False
```

Function's own output matched this hand computation to 1e-9. In plain words:
the observed gap of 1.5 is real, but with only 5 and 3 data points this test
is only reliably sensitive to gaps of 2.56 or larger — so "not significant"
here correctly reads as "underpowered to confirm a gap this size," not "no
gap exists."

**Gotcha questions:**

1. *"Why does the standard error formula ADD the two groups' variance-over-n
   terms instead of, say, averaging them?"* Because variances of two
   *independent* random quantities add when you combine them (this is a basic
   probability fact — Var(A−B) = Var(A) + Var(B) when A and B are
   independent). Since a "difference of two independent sample means" is
   exactly A−B, its variance is the sum of each mean's own variance
   (`σ²/n` is the variance of a sample mean itself, from the standard error of
   the mean formula).
2. *"Why divide by N−1 instead of N in the standard deviation?"* Using the
   *sample* mean (rather than the true population mean, which is unknown) to
   compute spread systematically underestimates the true variance if you
   divide by N. Dividing by N−1 ("Bessel's correction") corrects that bias.
   It matters most at small N — with n=3 or n=5 like the worked example
   above, N vs. N−1 is a meaningfully different divisor (3 vs. 2, 5 vs. 4).
3. *"Why use a normal approximation here instead of the actual Welch's t
   distribution the rest of the codebase uses for the real hypothesis test?"*
   Welch's t distribution's exact critical value depends on the Satterthwaite
   degrees-of-freedom formula, which itself depends on the data — using it
   for a power/MDE calculation (which asks about *hypothetical* future data,
   not the data in hand) would require assuming a degrees-of-freedom value in
   advance. The normal approximation is the standard practice for this kind
   of post-hoc power sanity check, and is adequate here because the small
   subgroup sizes are the real limiting factor, not the choice of reference
   distribution.

---

## 4. `max_drawdown_pct()`

**Location:** `research_analysis.py:3033`.

### Step 1 — Canonical source

No single formal paper defines this exact simple formula (Magdon-Ismail &
Atiya's 2004 "Maximum Drawdown" gives a more elaborate probabilistic
treatment of drawdown *distributions*, not this empirical calculation). This
three-line running-peak / percent-decline / minimum construction is the
standard, near-universally taught quant-finance definition — found
identically in QuantStart's "Event-Driven Backtesting with Python" series and
DataCamp's "Historical drawdown" lesson, among many others. In words: at
every point in time, compare the current value to the highest value seen so
far; the maximum drawdown is the worst (most negative) such comparison across
the whole series.

### Step 2 — Line-by-line correctness check

```python
equity_curve = pd.Series(equity_curve)
running_max = equity_curve.cummax()                              # running peak-to-date at every index
drawdown_pct = (equity_curve - running_max) / running_max * 100  # % decline from that peak, at every index
return drawdown_pct.min()                                        # the single worst (most negative) decline
```

- `.cummax()` is exactly "running maximum up to and including this point" —
  correct definition of "peak so far."
- `(equity_curve - running_max) / running_max` is decline-from-peak as a
  fraction of the peak (always ≤ 0, since `running_max >= equity_curve` by
  construction) — correct percentage-drawdown formula.
- `.min()` correctly picks the *worst* (most negative) drawdown across the
  whole curve, not just the drawdown at the final point — this is the
  critical detail that makes it "maximum" drawdown rather than "current"
  drawdown; an earlier peak-to-trough dip that later recovered still counts.
- No division-by-zero risk in practice: `running_max` is 0 only if the
  equity curve itself starts at (or below) 0, which doesn't occur for a
  dollar-denominated equity curve starting from positive capital.

**No deviation found. Numeric verification (actually run):**

```
equity = [100, 110, 105, 120, 90, 95, 130]
running_max:  100, 110, 110, 120, 120, 120, 130
drawdown%:      0,   0, -4.545,  0, -25.0, -20.833, 0
max_drawdown_pct() -> -25.0   (matches hand calc: (90-120)/120*100 = -25.0)

Edge cases (all verified):
  monotonic increasing [100,101,102,103] -> 0.0
  single value [100]                     -> 0.0
  simple decline [100, 50]               -> -50.0
```

### Step 3 — Comprehension bridge

**The problem in one sentence:** if you'd put money into this strategy, what's
the worst percentage decline your account balance would have suffered at any
point, from its own prior high point, before recovering (or not)?

**The formula, plain English:**
- At every point in time, ask: "what's the highest my balance has *ever* been,
  up to right now?" That's the running peak.
- At every point, compute how far below that peak you currently are, as a
  percentage of the peak. (E.g., peak was $120, now at $90 → down 25%.)
- The single most negative one of those percentages, anywhere in the whole
  history, is the maximum drawdown.

**Worked example (traced by hand and confirmed against the function):**

| Bar | Equity | Running peak so far | Drawdown % |
|---|---|---|---|
| 1 | 100 | 100 | 0% |
| 2 | 110 | 110 | 0% |
| 3 | 105 | 110 | −4.55% |
| 4 | 120 | 120 | 0% |
| 5 | 90  | 120 | **−25.00%** ← worst |
| 6 | 95  | 120 | −20.83% |
| 7 | 130 | 130 | 0% |

Maximum drawdown = −25.00% (bar 5), even though the curve later recovers to a
new high of 130 by bar 7 — the recovery doesn't erase the fact that someone
holding through bar 5 would have seen a 25% decline from their peak.

**Gotcha questions:**

1. *"Why percentage and not dollars?"* Dollar drawdown isn't comparable across
   arms with different starting capital or different curve shapes (this
   codebase compares the strategy against DCA and lump-sum buy-and-hold, all
   starting from the same $10,000 but with very different equity paths) — a
   percentage normalizes for scale so the three arms' risk profiles are
   directly comparable.
2. *"Why track a running max instead of just comparing the final value to the
   all-time high?"* Because the worst drawdown might happen mid-history and
   fully recover by the end — comparing only the final point to the peak
   would completely miss it. Bar 5 in the worked example above is exactly
   this: the curve recovers by bar 7, but the −25% dip at bar 5 still
   happened and is still the risk that mattered to anyone holding through it.
3. *"What if the curve only ever goes up?"* Then the running peak always
   equals the current value, every drawdown is exactly 0%, and the function
   correctly returns 0.0 — verified directly, not just theoretically.

---

## 5. `sharpe_sortino_ratios()`

**Location:** `research_analysis.py:3057`.

### Step 1 — Canonical source

- **Sharpe ratio:** William F. Sharpe, "Mutual Fund Performance," *Journal of
  Business* 39(1): 119–138 (1966), the original "reward-to-variability ratio";
  restated in Sharpe, "The Sharpe Ratio," *Journal of Portfolio Management*
  21(1): 49–58 (1994) as `SR = E[R_a − R_f] / σ`, `σ = std(R_a − R_f)`.
- **Sortino ratio:** Frank A. Sortino & Robert van der Meer, "Downside Risk,"
  *Journal of Portfolio Management* 17(4): 27–31 (1991). Downside deviation:
  `σ_d = sqrt( (1/N) · Σᵢ₌₁ᴺ [min(0, Rᵢ − T)]² )`, `T` = target/Minimum
  Acceptable Return (MAR), `N` = **total** number of return observations (not
  just the count of losing periods).

### Step 2 — Line-by-line correctness check

```python
mean_return = np.mean(bar_returns)
return_std = np.std(bar_returns, ddof=1)                                   # sample SD, N-1 denominator
sharpe = (mean_return / return_std) * np.sqrt(periods_per_year) if return_std > 0 else float("nan")

downside_returns = np.minimum(bar_returns, 0.0)                            # min(Ri, 0) == min(Ri - T, 0) with T=0
downside_deviation = np.sqrt(np.mean(np.asarray(downside_returns) ** 2))   # (1/N) sum(...)^2 over ALL N periods
sortino = (mean_return / downside_deviation) * np.sqrt(periods_per_year) if downside_deviation > 0 else float("nan")
```

- `return_std` uses `ddof=1` (sample SD, N−1 denominator) — correct unbiased
  estimator, matches standard practice for a finite empirical return sample.
- `sharpe = mean_return/return_std * sqrt(periods_per_year)`: numerator/
  denominator terms are structurally correct (mean over spread), and
  `sqrt(periods_per_year)` is the standard "square root of time" annualization
  rule. **See Flag F1**: `mean_return` here is the *raw* return, not an
  excess-over-risk-free return — the formula is correct *given* an implicit
  `R_f = 0` assumption, but that assumption isn't in Sharpe's general formula
  and isn't stated in the docstring.
- `downside_deviation = sqrt(mean(min(Ri, 0)^2))`: this is **exactly**
  Sortino & van der Meer's own formula with `T (MAR) = 0` and dividing by the
  **full N** (via `np.mean`, which divides by `len(downside_returns)` — the
  total bar count, including all the zero-contribution winning/flat bars, not
  just the losers). This full-N convention is confirmed, by direct comparison
  to the original paper's formula, to be the textbook-correct one — not an
  approximation or simplification. (A popular public code tutorial checked
  during the earlier provenance audit instead divides by the count of losing
  periods only, `series[series<0].std()`; that tutorial's version is the
  non-standard one, not this codebase's.)
- Both ratios correctly guard against division by zero (`if return_std > 0`,
  `if downside_deviation > 0`) and return `float("nan")` rather than raising
  or returning `inf` — a clean, documented edge-case behavior.

**Numeric verification (actually run), `bar_returns = [0.02, -0.01, 0.03, -0.02, 0.01]`, `periods_per_year = 12`:**

```
mean_return = 0.006
return_std (ddof=1) = 0.0207364
sharpe = (0.006 / 0.0207364) * sqrt(12) = 1.002323     <- matches hand calc exactly

downside_returns = [0, -0.01, 0, -0.02, 0]
downside_deviation = sqrt((0^2 + 0.01^2 + 0^2 + 0.02^2 + 0^2) / 5) = sqrt(0.0005/5)... = 0.01
sortino = (0.006 / 0.01) * sqrt(12) = 2.078461         <- matches hand calc exactly
```

Both matched the live function's output to 1e-9.

**Edge cases verified:**
- All-positive returns → `downside_deviation = 0` → **Sortino = NaN**
  (Sharpe still computes normally: 6.928). Correct — no downside risk to
  measure, division-by-zero correctly avoided via NaN, not a crash.
- Constant returns (`[0.01, 0.01, 0.01]`) → `return_std = 0` → **both NaN**.
  Correct — zero variance means "risk-adjusted return" is undefined, not
  infinite.
- Single-element input → `ddof=1` divides by 0 → NaN with a `RuntimeWarning`,
  caught cleanly by the `> 0` guard → NaN, not a crash. (Same underlying
  mechanism as Flag F2 in `mde_power_analysis()`.)

**No formula deviation found beyond the disclosed-here Flag F1 (implicit
zero risk-free rate/MAR).**

### Step 3 — Comprehension bridge

**The problem in one sentence:** raw average return doesn't tell you whether
that return came with a lot of ups-and-downs (risky) or was steady (safe) —
Sharpe and Sortino both divide average return by a measure of "how bumpy was
the ride" so strategies with different risk levels can be compared fairly.

**The formulas, plain English:**
- **Sharpe** = (average return per period) ÷ (how much the return varies,
  period to period) × (a scaling factor to express this per-year instead of
  per-bar). Bigger number = more return per unit of *total* bumpiness
  (counting both good and bad surprises).
- **Sortino** = same idea, but the "bumpiness" in the denominator only counts
  the *bad* bumps (periods below 0, or below whatever target you set) — a
  strategy that has occasional huge upside spikes but is otherwise steady on
  the downside gets rewarded by Sortino in a way plain Sharpe wouldn't give it
  credit for, since Sharpe penalizes upside volatility too.
- The `sqrt(periods_per_year)` factor exists because volatility measured over
  short periods (like 4-hour bars) needs to be scaled up to be comparable to
  an "annual" volatility figure — volatility scales with the square root of
  time under the standard assumption that period-to-period returns don't
  influence each other.

**Worked example (traced by hand, matches the function's actual output):**

5 periods of returns: `+2%, −1%, +3%, −2%, +1%`, annualizing factor 12
(pretend monthly-equivalent):

```
mean = (0.02 - 0.01 + 0.03 - 0.02 + 0.01) / 5 = 0.006  (0.6%)

Sharpe's denominator (sample SD, N-1=4):
  squared deviations from mean: (0.014)^2, (0.016)^2, (0.024)^2, (0.026)^2, (0.004)^2
  sum = 0.000196+0.000256+0.000576+0.000676+0.000016 = 0.00172
  variance = 0.00172/4 = 0.00043 -> std = 0.020736
Sharpe = (0.006/0.020736) * sqrt(12) = 1.0023

Sortino's denominator (downside only, but divided by ALL 5 periods):
  min(each return, 0): 0, -0.01, 0, -0.02, 0
  squared: 0, 0.0001, 0, 0.0004, 0
  mean over all 5: 0.0005/5 = 0.0001 -> sqrt = 0.01
Sortino = (0.006/0.01) * sqrt(12) = 2.0785
```

Sortino (2.08) is noticeably higher than Sharpe (1.00) here because 3 of the 5
periods were gains that don't penalize Sortino's denominator at all, while
they do inflate Sharpe's — exactly the intended behavior: Sortino rewards
"upside without matching downside," which is the asymmetric payoff profile
this paper's strategy is argued to have.

**Gotcha questions:**

1. *"Why multiply by sqrt(periods_per_year) instead of just periods_per_year
   itself?"* Because return scales linearly with time (double the time,
   roughly double the expected return) but variance/standard-deviation scales
   with the *square root* of time (this falls out of variances adding under
   independence, then taking a square root to get back to a standard
   deviation) — so the ratio of return-to-risk needs the sqrt, not a linear
   factor, to correctly rescale from "per-bar" to "per-year."
2. *"Where's the risk-free rate in this Sharpe ratio?"* It's implicitly
   assumed to be zero — the code uses raw per-bar returns directly rather than
   subtracting a risk-free benchmark first. This is a simplification, not
   part of the textbook definition itself (see Flag F1). Be ready to say this
   plainly rather than let it sound like an omission you didn't know about.
3. *"Why does Sortino divide by the count of ALL periods, not just the
   losing ones?"* Because that's what the original Sortino & van der Meer
   (1991) formula actually specifies — winning and flat periods contribute a
   literal 0 to the sum (since `min(positive_or_zero, 0) = 0`), but they still
   count in the denominator N. Dividing only by the count of losers (a
   version seen in some public tutorials) is a *different*, non-standard
   convention, not the more "correct" one, even though it might sound more
   intuitive at first (this codebase's convention was checked directly
   against the original paper's formula for this audit).
4. *"What happens if the strategy has zero losing periods?"* Sortino's
   downside deviation becomes 0 (nothing to divide by), so the function
   returns NaN rather than an infinite or undefined ratio — verified directly
   against a synthetic all-positive-returns example.

---

## Summary table

| Function | Formula matches textbook? | Deviations found | Numerically verified? |
|---|---|---|---|
| `bootstrap_resample`/`run_bootstrap_ci` | Yes (Efron percentile bootstrap) | Plain percentile, not BCa (F3, disclosed as standard) | Yes — matched independent replication exactly |
| `bootstrap_ablation_arm_vs_baseline` | Yes (bootstrap empirical p-value) | None | Yes — matched independent replication exactly |
| `mde_power_analysis` | Yes (standard 2-sample MDE formula) | `detectable` reads False (not "undefined") on NaN input (F2, doesn't occur on real n=4..23 data) | Yes — matched hand calc to 1e-9 |
| `max_drawdown_pct` | Yes (standard running-peak formula) | None | Yes — matched hand calc + 3 edge cases |
| `sharpe_sortino_ratios` | Yes (Sharpe 1966/1994, Sortino & van der Meer 1991) | Implicit risk-free rate/MAR = 0, undisclosed in docstring (F1) | Yes — matched hand calc to 1e-9 + 3 edge cases |
