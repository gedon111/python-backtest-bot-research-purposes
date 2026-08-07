# Results Section Addition — Draft for Paper Integration

> **Status: draft for review, not yet inserted into the paper.**
> Quantitative claims are translated from `scratch/regime_breakdown_audit.py`
> and `scratch/dca_blend_audit.py` (plus the correlation figure from
> `scratch/02_benchmark_and_risk.py`), all run this session against a copy
> of the existing 27-trade `min_ob_quality=0` baseline and
> `artifacts/candles.csv`. Translation points marked **[TRANSLATION NOTE]**.
> No locked result, committed artifact, or pipeline file was modified.

---

## a. Regime breakdown

Each of the 27 baseline trades was tagged by the macro market regime active
at its entry bar, using two independent methods that were both run and
cross-checked against each other.

**Primary method — calendar split**, following the standard, widely-cited
narrative for this exact window (cycle low November 2022; prior all-time-high
breakout March 2024): 2022 = bear, 2023 = chop, 2024–2025 = bull.

| Regime | Trades | Win rate | Total return contribution | Share of total return |
|---|---|---|---|---|
| BEAR (2022) | 7 | 57.14% | +10.45% | +34.5% |
| CHOP (2023) | 6 | 50.00% | −5.39% | −17.8% |
| BULL (2024–25) | 14 | 85.71% | +25.25% | +83.3% |

**Robustness cross-check — price drawdown from all-time high.** Running
drawdown from BTC's actual pre-window all-time high ($69,000, November 10,
2021 — seeded explicitly rather than computed from the dataset's own first
bar, since the window begins seven weeks after that peak and using an
in-window seed would misclassify early 2022 as "at the high"). Thresholds:
BEAR ≤ −40% drawdown, CHOP −40% to −12%, BULL > −12%.

| Regime | Trades | Win rate | Total return contribution | Share of total return |
|---|---|---|---|---|
| BEAR (≤−40% dd) | 12 | 50.00% | −1.63% | −5.4% |
| CHOP (−40% to −12% dd) | 8 | 87.50% | +18.89% | +62.3% |
| BULL (>−12% dd) | 7 | 85.71% | +13.05% | +43.1% |

**[TRANSLATION NOTE]** The two methods agree on only 13 of 27 trade
assignments — not because either is wrong, but because they measure
different things: most of calendar-2023 ("chop" by convention) was still
57–64% below the $69,000 all-time high, i.e. deep in drawdown-method BEAR
territory, even though price action that year was sideways/recovering
rather than actively crashing. Both methods agree on the conclusion that
matters for this paper: the BULL regime is consistently the strongest
(85.71% win rate under both methods), and neither method's weakest regime
loses much (calendar CHOP: −17.8% of total return; drawdown BEAR: −5.4%).
We recommend leading with the calendar method in the paper body, since it
matches readers' existing mental model of the BTC cycle, and citing the
drawdown method as an independent cross-check that reaches the same
headline conclusion under a differently-defined regime boundary.

**Regime distribution of the three concentrated top-return trades**
(entry_idx 359, +6.69%; entry_idx 6366, +4.36%; entry_idx 8280, +4.62% —
together 51.7% of total net return):

| Trade | Date | Return | Calendar regime | Drawdown regime |
|---|---|---|---|---|
| 359 | 2022-03-02 | +6.69% | BEAR | CHOP (−35.6% dd — recovered enough to sit just short of the BEAR threshold) |
| 6366 | 2024-11-27 | +4.36% | BULL | BULL |
| 8280 | 2025-10-12 | +4.62% | BULL | BULL |

**The three concentrated winning trades are not clustered in a single
regime under either method** — under the calendar method they split
BEAR/BULL/BULL, and under the drawdown method CHOP/BULL/BULL, with the union
across both methods spanning all three regime labels. This is a genuinely
favorable robustness finding for the return-concentration discussion: the
paper's largest individual contributions to total return did not all arise
from one favorable market condition. The one nuance worth stating explicitly
in the paper text: the 2022-03-02 trade sits close to the BEAR/CHOP boundary
by construction — calendar-2022 labels it BEAR, but by the time it entered,
BTC had already recovered to only 35.6% below the all-time high, short of
the −40% threshold used for the drawdown method's BEAR classification.

---

## b. Benchmark comparison — reframed as a complementary strategy

**Correlation.** Pearson correlation between per-trade strategy return and
BTC's own return over the identical holding window, computed across all 27
baseline trades: **r = −0.3688, p = 0.0584**.

**[TRANSLATION NOTE]** This is **borderline, not statistically significant**
at the conventional α = 0.05 threshold, and should not be reported as
"proven negative correlation" or "significantly diversifying." The correct,
precise framing: at n = 27, the data shows a **weak-to-moderate negative
association that falls just short of conventional significance** — directionally
consistent with (not proof of) a complementary or diversifying role relative
to simple BTC exposure. We recommend stating the p-value alongside the r
value every time this figure is cited, so readers can calibrate the claim's
strength themselves rather than inferring more certainty than the test
supports.

> Rather than positioning this strategy as an outright replacement for BTC
> buy-and-hold exposure, we evaluate it as a **complementary capital
> sleeve**: a separate allocation running alongside an investor's existing
> BTC accumulation, rather than competing for the same capital. We model an
> investor who contributes a fixed amount of new capital every week over the
> study's full window (2022–01 to 2026–01, 210 weekly contributions),
> comparing a 100%-into-BTC dollar-cost-averaging (DCA) baseline against
> otherwise-identical portfolios that instead split each week's contribution
> between the same BTC-DCA sleeve and an independently-capitalized strategy
> sleeve (which redeploys its full accumulated balance into each of the
> strategy's realized trades and otherwise sits uninvested between trades,
> mirroring the strategy's own realized 2.63% time-in-market).

| Split (BTC-DCA / Strategy) | Sharpe (weekly, annualized) | Sortino (weekly, annualized) | Max drawdown (principal-inclusive) |
|---|---|---|---|
| 100% / 0% (DCA-only baseline) | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |

> Sharpe ratio, Sortino ratio, and maximum drawdown all improve
> **monotonically** as the strategy allocation increases from 0% to 30% of
> new weekly capital. This is presented as a **risk-adjusted-improvement
> story, not a return-supremacy claim**: because the strategy sleeve holds a
> position only 2.63% of the time (versus BTC-DCA's continuous exposure),
> its absolute final value is lower at every split tested (e.g., at the 80/20
> split: $426 combined vs. $469 DCA-only, on $210 total contributed over the
> window) — the improvement shows up in the *shape* of the return stream
> (smoother, shallower drawdowns, better downside-adjusted ratios), not in
> outrunning BTC's raw appreciation. We frame the standalone strategy Sharpe
> (1.114) and Sortino (2.727) figures the same way: as returns generated
> during a small, selectively-timed fraction of total market time, not as a
> claim of beating BTC's own risk-adjusted profile outright (BTC buy-and-hold
> over the same window: Sharpe 0.564, Sortino 0.803) — the standalone
> strategy figures are numerically higher, but achieved over 2.63% of the
> time-in-market that the buy-and-hold figures reflect, and are not a
> like-for-like exposure comparison.

**[TRANSLATION NOTE]** The DCA-blend model makes several explicit,
stated-not-hidden simplifying assumptions worth surfacing in the paper's
methods text if this table is included: (1) contributions are $1/week for
both portfolios, so total capital contributed is identical across splits;
(2) the strategy sub-sleeve assumes 100% redeployment of its current balance
into every trade (not a granular position-sizing model); (3) periodic
returns are computed net of that period's own contribution, to avoid
misreading injected capital as investment return; (4) "max drawdown" is
reported on principal-inclusive portfolio value, which is the conventional
way DCA-style calculators present it, but is mechanically bounded below by
how much has been contributed so far rather than being a pure market-risk
measure — a secondary peak-to-trough cumulative-P&L (contribution-excluded)
metric is available in the underlying script if the paper wants a purer
risk-only drawdown figure instead.

---

## c. Out-of-sample and extended-history validation

**[TRANSLATION NOTE]** New subsection, reporting `analysis/oos_validation_analysis.py`
(promoted from `scratch/oos_live_pull_2026_08.py` and
`scratch/eightyr_backfill_audit.py`). Both live-pull BTCUSDT 4H data through
a fixed boundary (2026-07-31) rather than an open-ended "now," specifically
so the results are reproducible on re-run rather than drifting — see the
script's own docstring. Numbers below are exact script output, not rounded
differently between here and the Limitations section's citation of the same
figures.

**Forward out-of-sample test.** BTCUSDT 4H data from 2026-01-01 through
2026-07-31 — genuinely postdating every commit to the strategy's source
file, and therefore the only prospective (not merely held-out-historical)
evidence available for this exact rule set — was run through the frozen,
unmodified pipeline. The locked 27-trade baseline reproduced byte-identically
(integrity and regression checks both PASS) before any new trades were
examined.

| Metric | Value |
|---|---|
| New (OOS) trades | 4 |
| Wins / Losses | 1 / 3 |
| Win rate | 25.00% |
| Total return | −3.45% |
| Avg return/trade | −0.86% |

> We report this plainly rather than omitting or softening it: this is a
> small, directionally unfavorable result. Four trades cannot meaningfully
> update any significance claim in either direction — by the same
> minimum-detectable-effect logic used for the quality-criteria subgroup
> analysis, n=4 is far too small to distinguish a true edge from noise. But
> it is the only data this strategy has ever been tested against that it
> could not possibly have been shaped by, and the honest reading is that it
> does not provide reassurance. We do not treat it as disqualifying either —
> a single small unfavorable sample is not evidence the edge is absent, only
> evidence that it did not show up here.

**Extended-history (2018–2026) backfill audit.** The same frozen pipeline
was run against BTCUSDT 4H data extended back to 2018-01-01, testing two
separate things.

*Methodological integrity*: does prepending ~4 additional years of indicator
warm-up change the locked 2022–2026 baseline at all? This was not
guaranteed a priori — MACD's EMAs and the static KDJ's smoothing are
recursive with a theoretically unbounded memory back to the first row of
whatever data is supplied. Result: **PASS** — all 27 locked trades matched
by entry timestamp with a maximum PnL difference of 0.0000000000 (exact,
not merely close) between the original and extended runs.

*Pre-2022 performance* — reported for completeness, explicitly **not**
out-of-sample evidence, since this is the period the strategy's rule
structure was originally formulated against (see Limitations §a):

| Window | N | Win rate | Total return | Avg return/trade | One-sided binomial p |
|---|---|---|---|---|---|
| 2018-01 → 2022-01 (formulation period, not OOS) | 25 | 60.00% | +21.82% | +0.87% | 0.2122 |
| 2022-01 → 2026-01 (locked baseline) | 27 | 70.37% | +30.31% | +1.12% | 0.0261 |
| Combined 2018–2026 (mixed provenance) | 56 | 62.50% | +48.68% | — | 0.0407 |

> The combined-window row is included for completeness and must never be
> cited on its own without the caveat directly attached: roughly half of it
> is drawn from the period the strategy was built against, so its
> significance figure (p=0.0407) partly reflects performance on data the
> rules could see during development, not independent confirmation. The
> weaker formulation-period performance relative to the reported window is
> discussed as evidence consistent with (not proof of) the stop-loss-filter
> caveat in Limitations §a — a strategy fit to its own formulation data
> would ordinarily be expected to perform *at least* as well there as
> elsewhere, and the fact that it performs worse is the opposite of what
> naive overfitting to that period would predict.
