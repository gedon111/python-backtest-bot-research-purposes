# Provenance Verdict: Statistical Tools in `research_analysis.py`

Prepared for research-panel defense. Scope: every hypothesis-test, confidence-interval,
and risk/performance-metric function in `research_analysis.py` (Sections 5 and 5B —
`binomial_test`, `fisher_exact_test`, `welch_t_test`, `bootstrap_resample`,
`pearson_correlation`, `spearman_correlation`, `mde_power_analysis`, `max_drawdown_pct`,
`sharpe_sortino_ratios`, and the `bootstrap_ablation_arm_vs_baseline` between-arms
bootstrap). **Out of scope:** `compute_indicators()` (MACD/KDJ/ATR), `compute_smc()`
(Smart Money Concepts order blocks), and the `kdj_reset_*` exit state machine. Those are
technical-analysis / trading-strategy logic, not statistical inference tools, and were not
audited here — say so explicitly if the panel asks about them, and this report can be
extended to cover them on request.

## Executive summary — direct answer to the panel's question

None of these functions were copied from a specific academic paper's Python
implementation, and no matching prior public implementation (predating this codebase)
was found for any of them. Every hypothesis test (binomial, Fisher's exact, Welch's t,
Pearson, Spearman) is a **direct, unmodified call to `scipy.stats`** — the "translation"
work for those is limited to argument marshaling and dict packaging, not the statistics
itself. The four functions with genuine custom math — the percentile bootstrap loop, the
MDE/power formula, Sharpe/Sortino, and max drawdown — implement long-standing, textbook-
standard formulas (Efron 1979/1981; the standard two-sample normal-approximation MDE
formula ubiquitous in A/B-testing literature; Sharpe 1966; Sortino & van der Meer 1991)
that appear near-identically across dozens of independent tutorials and packages, so they
cannot be attributed to any single source — they are best described as independently
assembled from the published formula definitions. **One thing the panel should hear
directly and unprompted: every commit that introduced this code carries a
`Co-Authored-By: Claude Sonnet 5` trailer — it was written in collaboration with an AI
coding assistant, not typed unassisted by the student from a blank editor.** That is a
distinct provenance category from both "personally translated" and "copied from a paper,"
and it is disclosed in detail in the "AI-assistance disclosure" section below because
rounding it off to "personally written" would not be accurate.

## NEEDS ATTENTION BEFORE DEFENSE

**Nothing here lands in `STRUCTURALLY_SIMILAR_TO_SOURCE` or `POSSIBLE_DERIVATION`.** The
one item that genuinely needs to be said out loud to the panel, unprompted, is the
AI-assistance point above — not because it resembles plagiarism (it doesn't; no
third-party source was found to have been copied), but because "did you personally
translate this" has a factually incomplete "yes" answer if AI assistance goes unmentioned.
See the disclosure section below for exactly what that means function-by-function.

---

## AI-assistance disclosure

Every commit in this repository's history that introduces or materially edits any of the
functions covered by this report carries a `Co-Authored-By: Claude Sonnet 5
<noreply@anthropic.com>` trailer (verified via `git show -s --format=%B` on all nine
commits listed in the per-function table below). This means:

- The student directed the work (which test to use, which trade populations to compare,
  which parameters — alpha, power, B, seed — to use, and reviewed/ran the resulting code
  against `scratch/regression.py`'s golden-master fixtures per this repo's own
  `CLAUDE.md` regression discipline).
- The line-by-line code — including the specific `scipy.stats` call signatures and the
  custom bootstrap/MDE/Sharpe/Sortino/drawdown formulas — was drafted with Claude's
  assistance, not copied from any specific external paper or repository (none was found
  predating these commits — see per-function verdicts), but also not typed from scratch
  by the student unassisted.
- Claude's knowledge of `scipy.stats.binomtest`/`fisher_exact`/`ttest_ind`/`pearsonr`/
  `spearmanr` and of the standard MDE/Sharpe/Sortino/drawdown formulas comes from its
  training on public documentation and widely published formula definitions — the same
  category of source a student would consult (SciPy docs, standard stats/finance
  references), not from any single identifiable paper's implementation.

If the panel's question is "did a human at this institution personally type this code
from a formula they looked up," the accurate answer is: the formulas were looked up
against public/scipy documentation and standard references, and the code was written in
an AI-assisted collaborative process, then verified by the student against known-good
fixtures. That is meaningfully different from either "wrote it alone" or "copied a
paper's code," and this report recommends stating it in exactly those terms rather than
letting the panel assume either extreme.

---

## Per-function verdicts

### 1. `binomial_test()` — `research_analysis.py:2773`

- **Classification:** DIRECT_LIBRARY_CALL (wrapped in a 2-line dict-packaging function).
- Calls `scipy.stats.binomtest(win_count, trade_count, null_win_probability,
  alternative=...)` twice (one-sided, two-sided). No custom math.
- **Earliest commit:** `909a25c` ("feat: promote fee/slippage sensitivity analysis to
  analysis/"), 2026-08-03, as part of `analysis/fee_slippage_analysis.py`. Consolidated
  into `research_analysis.py` at `8242b6c` (2026-08-13).
- **Closest external match:** `scipy.stats.binomtest` official documentation
  (docs.scipy.org). The exact binomial test itself dates to classical statistics; no
  single paper "owns" it, and no third-party Python file predating `909a25c` was found
  using this exact call pattern for a trading win-rate test.
- **Similarity assessment:** INDEPENDENT_TRANSLATION (trivially so — it's a library call).
- **One-sentence panel answer:** "This is a direct `scipy.stats.binomtest` call, run
  once one-sided and once two-sided — no translation of the binomial-test math occurred;
  the only authored logic is passing our win/loss counts into it."

### 2. `fisher_exact_test()` — `research_analysis.py:2805`

- **Classification:** DIRECT_LIBRARY_CALL.
- Builds a 2x2 contingency table, calls `scipy.stats.fisher_exact(contingency_table)`.
- **Earliest commit:** `909a25c`, 2026-08-03 (`analysis/fee_slippage_analysis.py`).
- **Closest external match:** `scipy.stats.fisher_exact` docs. The test itself
  originates with R.A. Fisher, "On the Interpretation of χ² from Contingency Tables, and
  the Calculation of P" (1922) — a 100+-year-old classical method, not a modern paper
  someone's code could be "copied from."
- **Similarity assessment:** INDEPENDENT_TRANSLATION.
- **One-sentence panel answer:** "This is a direct `scipy.stats.fisher_exact` call on a
  win/loss 2x2 table — Fisher's exact test is Fisher (1922); no modern paper's
  implementation was translated or copied."

### 3. `welch_t_test()` — `research_analysis.py:2835`

- **Classification:** DIRECT_LIBRARY_CALL.
- Calls `scipy.stats.ttest_ind(group_true_returns, group_false_returns,
  equal_var=False)`.
- **Earliest commit:** `909a25c`, 2026-08-03.
- **Closest external match:** `scipy.stats.ttest_ind` docs. Welch's t-test itself is
  B.L. Welch, "The generalization of 'Student's' problem when several different
  population variances are involved," Biometrika (1947).
- **Similarity assessment:** INDEPENDENT_TRANSLATION.
- **One-sentence panel answer:** "This is a direct `scipy.stats.ttest_ind(...,
  equal_var=False)` call — Welch's test itself is Welch (1947); scipy performs the
  computation, we only select `equal_var=False` and pass in the two subgroups."

### 4. `pearson_correlation()` — `research_analysis.py:2917`

- **Classification:** DIRECT_LIBRARY_CALL.
- Calls `scipy.stats.pearsonr(x_values, y_values)`.
- **Earliest commit:** `e3fee8c` ("feat: promote benchmark/DCA-blend analysis to
  analysis/"), 2026-08-03, in `analysis/benchmark_dca_analysis.py`.
- **Closest external match:** `scipy.stats.pearsonr` docs; Pearson (1895) for the
  underlying statistic.
- **Similarity assessment:** INDEPENDENT_TRANSLATION.
- **One-sentence panel answer:** "This is a direct `scipy.stats.pearsonr` call — no
  translation of Pearson's formula occurred."

### 5. `spearman_correlation()` — `research_analysis.py:2943`

- **Classification:** DIRECT_LIBRARY_CALL.
- Calls `scipy.stats.spearmanr(x_values, y_values)`.
- **Earliest commit:** `8242b6c`, 2026-08-13 — the single-file consolidation commit
  itself. Confirmed by `git log -S"spearmanr" --all`: this string appears in **no**
  earlier commit anywhere in the repository's history. The function's own docstring
  independently discloses this: "unlike every other function in this section, this is
  NOT ported from an existing script — no .py file in this repository previously
  computed Spearman's rho... added with explicit user approval to fill that gap." This
  self-disclosure is corroborated, not contradicted, by the git evidence.
- **Closest external match:** `scipy.stats.spearmanr` docs; Spearman (1904) for the
  underlying statistic.
- **Similarity assessment:** INDEPENDENT_TRANSLATION.
- **One-sentence panel answer:** "This is the newest of the seven test wrappers, added
  in the same commit as the single-file consolidation on 2026-08-13, and is a direct
  `scipy.stats.spearmanr` call added specifically to reproduce a rho/p-value figure that
  had previously only been computed ad hoc and recorded in a markdown doc."

### 6. `bootstrap_resample()` / `run_bootstrap_ci()` — `research_analysis.py:2866`, `3155`

- **Classification:** HYBRID (custom resampling loop driving `numpy.random.Generator`,
  not a library call to `scipy.stats.bootstrap`).
- Implements a nonparametric percentile bootstrap by hand: `rng.choice(values, size=n,
  replace=True)` repeated `bootstrap_resamples` times, collecting resample sums/means,
  then taking `np.percentile([2.5, 97.5])` of the resulting distribution.
- **Earliest commit:** `094ed4a` ("feat: promote bootstrap CI / power analysis to
  analysis/"), 2026-08-03, in `analysis/bootstrap_power_analysis.py`. Its own docstring
  states it was "Promoted from `scratch/bootstrap_power_audit.py`" — that scratch file
  is gitignored and not in git history, so its true first-written date cannot be
  independently verified from git; only the tracked `094ed4a` date is evidentiary.
- **Closest external match:** This is the "percentile bootstrap," the textbook method
  from Bradley Efron, "Bootstrap Methods: Another Look at the Jackknife," *Annals of
  Statistics* (1979), and formalized further in Efron & Tibshirani, *An Introduction to
  the Bootstrap* (1993). `scipy.stats.bootstrap()` (added in SciPy 1.7, 2021) implements
  the same family of methods as a library call and could have been used instead — the
  code here reimplements the simple percentile variant by hand rather than calling that
  newer library function. No third-party Python file predating 2026-08-03 was found with
  this exact resampling structure (`rng.choice(..., replace=True)` in a `for k in
  range(B)` loop collecting sums/means) applied to a trading-strategy trade log; this
  loop-and-percentile pattern is, however, extremely common in general
  data-science/quant-finance tutorial code (e.g., the "12.3 Percentile bootstrap
  confidence intervals" chapter of UChicago's public *Introduction to Data Science*
  course notes uses the identical `for` loop + `np.percentile` structure on generic
  data, not trading data).
- **Similarity assessment:** LIKELY_INDEPENDENT. The mechanism (loop + `rng.choice` +
  `np.percentile`) is a standard, widely-taught pattern for hand-rolling a percentile
  bootstrap rather than calling `scipy.stats.bootstrap()` — convergent implementation
  from a common textbook description is the more parsimonious explanation than copying,
  since no single closer external match was found across three separate searches
  (general percentile-bootstrap tutorials, quant-finance-specific bootstrap code, and
  trading-strategy-specific bootstrap code).
- **One-sentence panel answer:** "This hand-rolled percentile bootstrap — resample with
  replacement B times, take the 2.5th/97.5th percentiles — is Efron's 1979 bootstrap
  method in its most standard textbook form; it does not call SciPy's own
  `scipy.stats.bootstrap()` function, and no specific paper or repository's
  implementation was found to match it more closely than the general textbook pattern."

### 7. `bootstrap_ablation_arm_vs_baseline()` — `research_analysis.py:2621`

- **Classification:** HYBRID. Same underlying mechanism as #6 (loop + `rng.choice` +
  `np.percentile`), applied to a between-arms comparison instead of a within-arm CI —
  resample from one ablation arm's trade pool at the baseline's sample size and ask how
  often the resample's win rate/avg return meets or beats the baseline's actual result
  (an empirical p-value via `(samples >= baseline_value).mean()`).
- **Earliest commit:** `46c6e8e` ("feat: add ablation reconstruction script for
  indicators-only entry (no OB gate)"), consolidated into `research_analysis.py` at
  `8242b6c` (2026-08-13).
- **Closest external match:** Same as #6 — this is a permutation/bootstrap-style
  empirical-p-value construction, a standard nonparametric technique (see also Efron &
  Tibshirani 1993, ch. 16, on bootstrap hypothesis testing), not attributable to one
  specific paper.
- **Similarity assessment:** LIKELY_INDEPENDENT, same reasoning as #6.
- **One-sentence panel answer:** "This is a between-arms percentile-bootstrap empirical
  p-value, the same general Efron-style bootstrap technique as the baseline CI function,
  applied to a different comparison; no closer external match than the general method
  was found."

### 8. `mde_power_analysis()` — `research_analysis.py:2978`

- **Classification:** CUSTOM_IMPLEMENTATION (the only function in this report that is
  genuinely hand-derived arithmetic, not a library call or a loop around one).
- Implements `MDE = (z_(alpha/2) + z_beta) * sqrt(SD_true^2/n_true + SD_false^2/n_false)`
  using `scipy.stats.norm.ppf` only for the two z-quantiles; the combination formula
  itself is hand-written arithmetic.
- **Earliest commit:** `094ed4a`, 2026-08-03, in `analysis/bootstrap_power_analysis.py`
  (docstring there states the same formula explicitly, predating consolidation).
- **Closest external match:** This is the standard two-sample normal-approximation
  minimum-detectable-effect formula used ubiquitously in A/B-testing and clinical-trial
  sample-size literature (e.g., it is the two-sample analog of the formula in any
  standard power-analysis reference, and matches the general form given independently
  by contemporary MDE explainer sources such as frequentist.org's "Minimum Detectable
  Effect (MDE) Calculation" post and multiple CRO/growth-marketing MDE guides found in
  web search — see Sources). It is not attributable to one canonical paper; it is
  standard textbook content (comparable to Cohen, *Statistical Power Analysis for the
  Behavioral Sciences*, or Kohavi et al., *Trustworthy Online Controlled Experiments*,
  2020, for the online-experimentation formulation). No third-party Python
  implementation predating 2026-08-03 was found using this exact variable-naming
  convention (`z_alpha_2`, `z_beta`, `standard_error`, `mde`, `detectable`).
- **Similarity assessment:** LIKELY_INDEPENDENT / INDEPENDENT_TRANSLATION — closest
  candidate to a genuine "translated from a formula definition" case in this whole
  report, since it is the one place actual algebra (not a library call) was written by
  hand from a formula, but that formula itself is common enough across sources that no
  single one is "the" source.
- **One-sentence panel answer:** "This one is the closest thing to a hand-translated
  formula in the whole codebase — the standard two-sample MDE formula from
  power-analysis/A/B-testing methodology, using scipy only for the two z-quantiles; it
  is ubiquitous across statistics and experimentation references and is not attributable
  to a single paper."

### 9. `max_drawdown_pct()` — `research_analysis.py:3033`

- **Classification:** CUSTOM_IMPLEMENTATION (three lines: running max via `.cummax()`,
  percentage decline from it, take the min).
- **Earliest commit:** `8ef4076` ("docs: track the audit-evidence scripts behind
  CLAUDE.md's Known bugs #3"), 2026-08-01, in `scratch/02_benchmark_and_risk.py` as
  `max_drawdown()` — appears fully-formed in that single commit (no visible stub-then-
  refine history; see honesty note below). Renamed/relocated into
  `research_analysis.py`'s `max_drawdown_pct()` unchanged in logic at `8242b6c`
  (2026-08-13).
- **Closest external match:** This exact three-line pattern (`running_max =
  equity.cummax()`; `drawdown = (equity - running_max) / running_max`; `drawdown.min()`)
  is the standard formula taught in essentially every quant-finance Python tutorial —
  QuantStart's "Event-Driven Backtesting with Python - Part VII," DataCamp's "Historical
  drawdown" lesson, and multiple TradingView/Quantt explainers all describe the
  identical running-max/percent-decline/min construction (see Sources). No formal single
  paper defines max drawdown this way (Magdon-Ismail & Atiya's 2004 "Maximum Drawdown"
  is the most commonly cited formal treatment, but its treatment is probabilistic/
  analytic, not this simple empirical formula). The pattern is too generic and too
  widely convergent to be attributed to one source.
- **Similarity assessment:** LIKELY_INDEPENDENT. Flagging honestly per this report's own
  instructions: this function does appear complete and idiomatic in its very first
  commit, which is a signal worth naming — but the construction is so standard (3 lines,
  the only "natural" way to vectorize this calculation in pandas) that "arrived
  fully-formed" here is much better explained by its simplicity than by copying.
- **One-sentence panel answer:** "Max drawdown here is the standard three-line
  running-peak/percent-decline formula found in nearly every quant-finance Python
  tutorial — it appeared complete in its first commit, which is worth disclosing, but
  the formula is generic enough (and short enough) that this is the expected result of
  writing it from the definition, not a sign of copying from one specific source."

### 10. `sharpe_sortino_ratios()` — `research_analysis.py:3057`

- **Classification:** CUSTOM_IMPLEMENTATION.
- Sharpe: `(mean_return / return_std) * sqrt(periods_per_year)`, `return_std` via
  `np.std(..., ddof=1)`. Sortino: downside deviation computed as
  `sqrt(mean(minimum(returns, 0)^2))` — i.e., squared negative deviations averaged over
  **all** periods (not just the negative ones), then `(mean_return / downside_deviation)
  * sqrt(periods_per_year)`.
- **Earliest commit:** `8ef4076`, 2026-08-01, in `scratch/02_benchmark_and_risk.py` as
  `sharpe_sortino()` — also appears fully-formed in this first commit.
- **Closest external match:** Sharpe ratio: William F. Sharpe, "Mutual Fund
  Performance," *Journal of Business* (1966), later "The Sharpe Ratio," *Journal of
  Portfolio Management* (1994). Sortino ratio: Frank A. Sortino & Robert van der Meer,
  "Downside Risk," *Journal of Portfolio Management* (1991). A direct code comparison
  was run against a popular public tutorial with a matching title (codearmo.com,
  "Sharpe, Sortino and Calmar Ratios with Python") to check for structural copying: that
  source's Sortino downside-deviation step is `series[series<0].std() * sqrt(N)` — i.e.
  standard deviation of *only* the negative subset. `research_analysis.py`'s version
  instead uses `sqrt(mean(minimum(returns,0)**2))` over *all* periods, which is the
  more textbook-correct downside-deviation definition (dividing by total N, not just the
  count of losing periods — the distinction multiple independent sources flagged as the
  "correct" way to compute it, e.g. the semi-deviation convention described across
  several Sortino-ratio explainer articles found in search). This is a **meaningful
  formula-level difference** from that particular popular tutorial, which is evidence
  against copying from it specifically.
- **Similarity assessment:** LIKELY_INDEPENDENT. Same fully-formed-on-first-commit
  caveat as #9 applies and is disclosed for the same reason. The specific downside-
  deviation convention used (full-N denominator) rules out the one close public tutorial
  match that was checked line-by-line.
- **One-sentence panel answer:** "Sharpe and Sortino here follow the standard
  definitions from Sharpe (1966) and Sortino & van der Meer (1991); when checked against
  a popular public Python tutorial with a similar structure, this implementation uses
  the more textbook-correct full-sample downside-deviation denominator rather than that
  tutorial's simplified negative-subset-only version, which is evidence against having
  copied from it."

---

## Methodology notes / limitations of this audit

- Git history is authoritative only back to this repository's own commits; several
  functions were "promoted" from `scratch/*.py` prototype files that are gitignored and
  therefore have no independently verifiable first-written date — only the "promotion"
  commit date is used as the conservative (latest-possible) earliest-appearance date.
  Where this applies, it is called out per-function above.
- "No prior public match found" is evidence of absence up to the limits of a web-search-
  based literature/code scan (three search rounds per function, covering general
  tutorials, quant-finance-specific sources, and trading-strategy-specific sources per
  this report's instructions) — it is not a formal plagiarism-detection tool (no
  MOSS/Turnitin-style corpus diff was run). If the panel wants a stronger guarantee, a
  formal code-similarity tool run against a broader corpus is the appropriate next step,
  not a claim this report can make on its own.
- Two "dump"-labeled commits (`ff92210` "dump1", 2026-08-05, and `d316d89` "docs: pull
  ... from dumpsite", 2026-08-07) were checked because their names could suggest
  external content being merged in. Both are the *same author's own* work being
  re-integrated from a separate local working copy/session (`STUDY_REFERENCE.md`,
  `CLAUDE.md` corrections, a chart bug fix) — `d316d89`'s own commit message explicitly
  documents what was pulled in and why, and neither touches any function covered by this
  report. Checked and cleared, not a provenance concern.

## Sources consulted

- [scipy.stats.binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)
- [scipy.stats.fisher_exact](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html)
- [scipy.stats.ttest_ind](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)
- [scipy.stats.bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
- [12.3 The percentile bootstrap confidence intervals — UChicago Intro to Data Science](https://ds1.datascience.uchicago.edu/13/3/ConfidenceIntervals_3_PercentileBootstrap.html)
- [Minimum Detectable Effect (MDE) Calculation — frequentist.org](https://frequentist.org/posts/20250807-mde/)
- [Sharpe, Sortino and Calmar Ratios with Python — Codearmo](https://www.codearmo.com/blog/sharpe-sortino-and-calmar-ratios-python)
- [12 Risk metrics for investments with Python — Medium](https://medium.com/@phitzi/12-risk-metrics-for-investments-with-python-from-standard-deviation-to-r-squared-b24a97c1412e)
- [Event-Driven Backtesting with Python - Part VII — QuantStart](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-VII/)
- [Historical drawdown — DataCamp](https://campus.datacamp.com/courses/introduction-to-portfolio-risk-management-in-python/value-at-risk?ex=2)
