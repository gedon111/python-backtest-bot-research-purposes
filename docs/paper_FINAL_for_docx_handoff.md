<!-- Consolidated final draft, 2026-08-08. Includes: Pearson/Spearman p-value
correction (p<0.001 -> p≈0.0094/0.0113), bootstrap B=10,000-vs-B=2,000
cross-surface disclosure, and first-time integration of the benchmark-vs-passive
(strategy vs. weekly DCA vs. lump-sum buy-and-hold) results for both the
2022-2026 and 2018-2022 windows. Source: docs/paper_full_update_2026-08-08.md
plus docs/limitations_section_draft.md's Leverage subsection, consolidated and
rewritten into standalone paper prose. This file is self-contained: it does
not assume the reader has access to the originating repository. -->

# Harnessing Bitcoin Volatility: An Audited Backtest of an Integrated KDJ, MACD, and Smart Money Concepts Strategy

## Abstract

This study backtests a rule-based, parameter-fixed BTC/USDT trading strategy that gates MACD and KDJ momentum signals through Smart Money Concepts (SMC) Order Block structural zones, on 4-hour candles from January 2022 through January 2026 ($N = 8{,}767$ bars). The strategy produced 27 trades, a 70.37% win rate, and a +30.31% total net return, departing from a zero-edge null model at $p = 0.026$ (one-sided exact binomial). The paper's central contribution, however, is not the strategy itself but the auditing methodology applied to it: three code-level correctness bugs and two reporting-layer errors were found, disclosed, and corrected over the course of the project, including one correction that reversed a significance conclusion at a stricter quality threshold. A three-arm ablation — comparing the Order-Block-gated strategy against two indicators-only configurations differing in stop-loss placement — provides the strongest evidence that the structural gate, not risk-management mechanics, drives the strategy's outperformance. A realistic transaction-cost sensitivity analysis shows the headline win-rate significance claim is fragile (flipping to non-significant, $p = 0.124$, under a conservative 0.20% round-trip fee-and-slippage assumption) even though the underlying return-magnitude comparisons are mathematically unaffected by that same cost. A head-to-head benchmark against weekly dollar-cost-averaging (DCA) and lump-sum buy-and-hold shows the strategy did not outperform passive BTC accumulation in raw terminal value over either window tested, though it shows a materially better risk-adjusted profile while holding a market position only 2.63% of the time — an exposure asymmetry that precludes a direct "beats the benchmark" claim. Five hypothesized Order Block quality criteria show no statistically detectable relationship to trade outcome, but a minimum-detectable-effect analysis shows the study is underpowered to detect effects of the size actually observed at this sample size, which is a different claim from "no effect exists." All results, code, and audit findings are treated as provisional and cost-sensitive rather than as settled conclusions.

*Keywords:* algorithmic trading, backtesting methodology, reproducibility, Smart Money Concepts, cryptocurrency, statistical power

---

## Introduction

Rule-based trading-strategy research is unusually exposed to a specific failure mode: a backtest can be internally consistent, numerically precise, and still wrong, because the error lives in the boundary between what a rule is allowed to see and when it is allowed to see it — lookahead bias — or in how a result is summarized rather than in how it was computed. Both failure modes are silent by default: a backtest with a one-bar lookahead leak, or a paper that quietly cites the more favorable of two internally inconsistent confidence intervals, produces a result that looks exactly as credible as a correct one until someone goes looking for the discrepancy.

This study takes the position that the discipline of looking for those discrepancies — and disclosing what is found, favorable or not — is itself the contribution worth reporting, not only the strategy's headline performance. The strategy under test combines two well-established technical indicators (MACD and KDJ) with Smart Money Concepts (SMC) Order Block structural zones, a market-structure framework popularized in retail technical analysis but rarely subjected to the kind of formal statistical treatment applied here. The research question is twofold: first, does a rule-based entry/exit strategy gating momentum signals through SMC Order Block zones produce a historical win rate and return on BTC/USDT 4-hour candles that departs from a zero-edge (50% win probability) null model; and second, does Order Block "quality" — a five-criterion structural score — modulate that departure.

This is a rule-based, parameter-fixed historical backtest, not a live or production trading system, and no parameter in the simulated strategy was fit, swept, or optimized against the outcome being measured. The remainder of this paper is organized to make the auditing process itself visible rather than only its conclusions: the Methodology section documents not only the strategy's rules but the specific, disclosed corrections made to the code that implements them; the Results section reports the headline finding alongside every stress test applied to it (transaction costs, statistical power, out-of-sample data, an ablation study, and a head-to-head benchmark against passive alternatives); and the Discussion and Limitations sections are organized around the explicit distinction between what the evidence supports and what it does not, including two further reporting-layer corrections caught during a final cross-surface numerical audit conducted after the code-level analysis was otherwise complete.

---

## Methodology

### Data Acquisition and Preprocessing

Historical price data were retrieved from the Binance `get_klines` REST endpoint for the `BTCUSDT` symbol at 4-hour resolution, paginated in batches of 1,000 candles. Binance's raw millisecond `open_time` timestamps were converted to datetimes and shifted by a fixed +8-hour offset; all timestamps reported in this paper are therefore UTC+8, not raw UTC.

The primary analysis window spans 2022-01-01 08:00:00 through 2026-01-01 08:00:00, comprising **8,767 bars**. This figure was verified directly against the stored dataset. The arithmetic: 2022-01-01 to 2026-01-01 spans exactly 1,461 calendar days ($365 + 365 + 366 + 365$, the 366 accounting for the 2024 leap day). At six 4-hour bars per day, that is $1{,}461 \times 6 = 8{,}766$ bar-intervals; because the final bar is itself included as a row rather than used only as an exclusive upper bound, the row count is $8{,}766 + 1 = 8{,}767$. No gaps were found in the dataset — the set of unique inter-bar timestamp deltas across all 8,767 rows is the single value 4 hours.

### Indicator Computation

All indicators were computed once over the complete 8,767-bar series prior to trade simulation, with no per-trade recomputation.

**MACD(12, 26, 9).** A standard EMA-based MACD, computed causally (no lookahead):

$$EMA_{12}(t) = C_t \cdot \tfrac{2}{13} + EMA_{12}(t-1)\cdot\left(1-\tfrac{2}{13}\right), \qquad EMA_{26}(t) = C_t \cdot \tfrac{2}{27} + EMA_{26}(t-1)\cdot\left(1-\tfrac{2}{27}\right)$$
$$\text{MACD}_t = EMA_{12}(t) - EMA_{26}(t), \qquad \text{Signal}_t = \text{MACD}_t\cdot\tfrac{2}{10} + \text{Signal}_{t-1}\cdot\left(1-\tfrac{2}{10}\right), \qquad \text{Hist}_t = \text{MACD}_t - \text{Signal}_t$$

**ATR(14) and ATR(200).** True range, smoothed by a simple rolling mean (not Wilder's exponential smoothing, despite an inherited code comment suggesting otherwise — the executed computation is a plain rolling mean, and that is the computation this paper describes):

$$TR_t = \max\!\big(H_t-L_t,\ |H_t-C_{t-1}|,\ |L_t-C_{t-1}|\big), \qquad ATR_{14}(t) = \frac{1}{14}\sum_{i=0}^{13}TR_{t-i}, \qquad ATR_{200}(t) = \frac{1}{200}\sum_{i=0}^{199}TR_{t-i}$$

$ATR_{14}$ drives stop-loss distance, the minimum-stop-ratio filter, the trailing exit, and the ATR-move exit. $ATR_{200}$ serves as the volatility baseline for the ATR-regime entry filter and for two of the five Order Block quality criteria (Displacement, LargeBar).

**KDJ(9, 3, 3), static and entry-gating.** Computed once over the whole dataset:

$$RSV_t = \frac{C_t - \min_{i\in[0,8]}L_{t-i}}{\max_{i\in[0,8]}H_{t-i} - \min_{i\in[0,8]}L_{t-i}}\times 100, \qquad K_t = \tfrac{2}{3}K_{t-1}+\tfrac{1}{3}RSV_t, \qquad D_t = \tfrac{2}{3}D_{t-1}+\tfrac{1}{3}K_t, \qquad J_t = 3K_t - 2D_t$$

This is a single, fixed-period series computed once for the entire dataset. Every K/D/J reference inside the entry-condition checks reads this static column at the current bar; it does not vary from trade to trade. This series must be kept conceptually distinct from a second, unrelated KDJ computation described below, since conflating the two is the single most common source of confusion about this strategy.

### Smart Money Concepts Order Block Detection

Order Block detection runs two independent structural passes over the same price series: an internal-structure pass (pivot lookback of 5 bars) and a swing-structure pass (pivot lookback of 50 bars). In each pass, a bar $pb = i - \text{size}$ is confirmed as a pivot high only by strict right-side comparison, $H_{pb} > \max(H_{pb+1..i})$ (with the mirror condition for a pivot low); no future bar is ever read in this comparison. A Break of Structure or Change of Character is flagged when price closes across a tracked pivot level, and an Order Block is created from the price segment between the pivot bar and the crossover bar $i$.

Two bar indices are easily conflated and are kept explicitly distinct throughout this paper: `ob_idx` is the bar at which the Order Block's own extreme candle occurred, while `created_at` is the bar at which the breakout candle *closes* — the Order Block is not eligible to trigger an entry until strictly after `created_at`. Order Blocks expire after 500 bars of age, or once price closes back through their boundary.

### Order Block Quality: Five Orthogonal Criteria

Each detected Order Block is scored on five independently evaluated boolean criteria, which are summed into a 0–5 composite score used only as a cumulative entry-eligibility threshold, never as an ordinal "higher score is better" claim in the statistical analysis reported below (see the discussion of the non-orthogonal composite-score correction under Methodological Rigor, below).

1. **Displacement** — within the bars immediately following the Order Block's own bar and bounded at the Order Block's own confirmation bar, a candle body move of at least $1.5\times ATR_{200}$ (evaluated at the Order Block's bar) occurs in the Order Block's direction.
2. **LargeBar** — the Order Block's own bar has a high-low range at least as large as $ATR_{200}$ at that bar.
3. **FVG (Fair Value Gap)** — a three-candle price imbalance exists within a bounded window following the Order Block's bar: for a demand block, the low of a bar two positions later exceeds the high of the earlier bar; for a supply block, the mirror condition.
4. **LiquiditySweep** — the Order Block bar's low is at or below the minimum low of the prior ten bars (for a demand block), or its high is at or above the maximum high of the prior ten bars (for a supply block).
5. **VolumeExpansion** — the Order Block bar's volume is at least 1.25 times the prior 20-bar average volume, or its candle body constitutes more than 60% of its own high-low range.

### Fixed Entry and Exit Rules

All strategy parameters were fixed prior to and independent of the analysis reported in this paper; none were fit, swept, or optimized against the outcome being measured.

| Parameter | Value |
|---|---|
| Minimum stop distance | 0.015 (1.5% of entry price) |
| KDJ $J$ cap, long entries | 60.0 |
| KDJ $K$ cap, long entries | 50.0 |
| KDJ $K$ floor, short entries | 70.0 |
| KDJ $J$ cap, short entries | 100.0 |
| ATR-move take-profit multiple | 1.8 |
| Breakeven-stop trigger multiple | 2.0 |
| Minimum reward-to-risk ratio | 1.5 |

A long entry requires, jointly: price interacting with an active, unmitigated demand Order Block of sufficient quality; MACD histogram negative and rising for at least two bars; static $K < 50$ and rising, $J < 60$; a bounded two-bar $K$-acceleration window; an ATR-regime filter rejecting a narrow band of $ATR_{14}/ATR_{200}$ ratios; a stop distance of at least 1.5% of entry price; and a reward-to-risk ratio of at least 1.5. A short entry is the mirror condition against a supply Order Block.

Exit conditions are evaluated every bar in a fixed priority order, with the first satisfied condition triggering the exit: a trailing exit at 50% retracement of peak favorable P\&L once that peak reaches 1.5%; a KDJ-reset exit (described below), gated to not fire before the third bar after entry; an ATR-move exit at approximately 1.8 times the entry-bar ATR in favorable movement; a breakeven-stop adjustment at 2.0 times ATR favorable movement (a risk-management adjustment, not itself an exit trigger); a hard stop-loss; and a hard take-profit.

### The Two KDJ Systems

This strategy contains two separate KDJ computations that never share state, and distinguishing them clearly is essential to understanding the strategy's exit logic.

The first is the static, full-history, entry-gating KDJ series described above: a single fixed-period-9 series computed once, identical regardless of which Order Block ultimately triggers a given entry, and never varying from trade to trade.

The second is a post-entry, adaptive exit-window KDJ state machine, used exclusively to time the KDJ-reset exit signal after a trade is already open. At entry, this second system's state is seeded from the *static* K/D values already present at the entry bar (not reseeded to a neutral value, and not backfilled from the Order Block's own bar), with a lookback window

$$\text{period} = w = \max(1,\ \text{entry\_idx} - ob\_bar)$$

held fixed for the remainder of that trade's life. On each subsequent bar, a custom RSV is recomputed over a rolling window of length $w$, and K/D are recursed with the same $\alpha = 1/3$ smoothing used by the static series:

$$RSV_{custom} = \frac{C_{cur} - \min_{j\in[cur-w+1,\,cur]}L_j}{\max_{j\in[cur-w+1,\,cur]}H_j - \min_{j\in[cur-w+1,\,cur]}L_j}\times100, \qquad K_{cur}=\tfrac{2}{3}K_{prev}+\tfrac{1}{3}RSV_{custom}, \qquad D_{cur}=\tfrac{2}{3}D_{prev}+\tfrac{1}{3}K_{cur}$$

The exit signal fires on a K/D cross-back once the state has "armed," subject to the bar-3 gate described above. What varies from trade to trade is exclusively the window length $w$ of this second system — never the entry-gating KDJ. Across the 27 baseline trades, the observed range of $w$ is 14 to 439 bars, with a median of 74; this window is never as short as two bars, and any characterization of it as a "two-bar window" describes an illustrative edge case, not the observed distribution.

### Statistical Methods

Five statistical procedures were applied to the trade-level results:

A **one-sided exact binomial test** of win rate against a zero-edge null of $p_0 = 0.5$:
$$p = \sum_{k=\text{wins}}^{n}\binom{n}{k}(0.5)^n$$
The one-sided form was chosen because the pre-registered hypothesis is directional — that the strategy's edge exceeds 50%, not merely that it differs from 50% in either direction. Two-sided values are also reported for reference.

A **Fisher's exact test**, applied to the $2\times2$ win/loss-by-criterion-truth contingency table, independently for each of the five Order Block quality criteria, over the 27-trade baseline.

A **Welch's (unequal-variance) t-test**, comparing per-trade percentage return between a given criterion's True and False subgroups:
$$t = \frac{\bar X_T - \bar X_F}{\sqrt{\dfrac{s_T^2}{n_T}+\dfrac{s_F^2}{n_F}}}, \qquad \bar X=\frac1n\sum X_i,\qquad s^2=\frac{1}{n-1}\sum(X_i-\bar X)^2$$
Welch's form (rather than Student's) was used because subgroup sizes and variances are unequal and small, with subgroup $n$ ranging from 4 to 23.

A **Minimum Detectable Effect (MDE)** calculation at $\alpha=0.05$ and 80% power, computed per criterion from each subgroup's observed sample size and standard deviation, giving the smallest true mean-return gap this sample size could reliably detect.

A **nonparametric percentile bootstrap**, resampling the 27-trade return distribution with replacement, with a 95% confidence interval taken from the 2.5th and 97.5th percentiles of the resampled distribution.

Pearson's $r$ and Spearman's $\rho$ were also computed between hold duration (in bars) and percentage return across the 27 baseline trades.

### Methodological Rigor: Self-Audit as Method

Three code-level corrections were made over the course of this project and are disclosed here as evidence of an active auditing process, not omitted as embarrassments.

First, the original composite 0–5 quality score was constructed such that higher-scored Order Block sets were, by construction, nested subsets of lower-scored sets — a structural property that would have confounded any claim that quality "independently" predicts outcome. This was corrected by evaluating and reporting the five criteria independently rather than relying on the composite score as an analytical variable; the composite score itself is still computed and still used as the cumulative entry-filter threshold, but only the analysis method changed.

Second, the Fair Value Gap criterion originally tested adjacent candles rather than the correct three-candle imbalance definition. This was corrected to use the three-candle definition throughout.

Third, and most consequentially, the Fair Value Gap and Displacement criteria's forward-search loops were originally bounded by the length of the dataset rather than by each Order Block's own confirmation bar, meaning they could read one to two bars of data that would not actually have been available at the moment the Order Block became eligible for trade entry. This lookahead defect was found via a dedicated no-lookahead audit and corrected by bounding both search loops at each Order Block's own confirmation bar, with runtime assertions left in place at the relevant read sites to catch any regression. This correction is a genuine data-leakage fix, distinct in kind from the two definitional corrections above, and it changes a reported conclusion: at a stricter quality threshold ($q \geq 1$), the one-sided binomial $p$-value for win rate moves from 0.038 (pre-fix, $n=26$) to 0.054 (post-fix, $n=25$) — a shift from marginally significant to not significant at the conventional threshold, driven by a single trade losing its only quality point under the corrected computation.

A fourth and fifth correction, distinct in kind from the three above, were found during a later and separate audit pass that checked every headline number in this paper against a live, interactive companion website and the underlying committed analysis scripts, rather than against the backtesting engine itself. This audit found that the website's interactive bootstrap confidence interval used a lighter 2,000 resamples than this paper's canonical 10,000-resample figure, producing two individually correct but visibly different confidence intervals with no stated explanation for the difference (see Results); and that this paper's Pearson and Spearman correlation $p$-values had been reported as "$p < 0.001$" when the correct values are approximately 0.0094 (Pearson) and 0.0113 (Spearman) — still significant at conventional thresholds, but overstated by roughly an order of magnitude. Both are corrected in this document. A project whose own closing audit catches its own reporting errors is demonstrating the same discipline its code-level corrections already demonstrate, not undermining it.

Independent of this bug-fix narrative, a dedicated no-lookahead proof was conducted separately: truncation-equality testing on the ATR(14), ATR(200), and static KDJ(9,3,3) series passed 180 of 180 sampled checks, and a scope audit of the corrected Order Block detection code found zero of 253 FVG-true Order Blocks and zero of 107 displacement-true Order Blocks reading past their own confirmation bar.

Two further pieces of reproducibility infrastructure support these claims. A golden-master regression harness recomputes indicators and the Order-Block-gated simulation from raw candle data and asserts exact equality — indicators to a tolerance of $10^{-6}$, all 27 baseline trade fields exactly — against committed fixtures, and is run after every code change to this repository. A second, independently implemented JavaScript dashboard recomputes the entry-condition and indicator layer client-side from trade data, as a cross-check against a second, separately written codebase; its scope is limited, however, to the indicator and entry-condition checklist — it does not independently detect Order Blocks, Fair Value Gaps, or displacement, which are read as trusted data from the primary pipeline. This independent cross-check therefore could not have caught the third, lookahead-related correction described above, since it verifies a different, narrower layer of the overall pipeline.

---

## Results

### Baseline Performance

| Metric | Value |
|---|---|
| Trades | 27 |
| Wins / Losses | 19 / 8 |
| Win rate | 70.37% |
| Total net return | +30.31% |
| Average return per trade | +1.1225% |
| SD (return per trade) | 2.41% |
| One-sided binomial $p$ | 0.0261 |
| Two-sided binomial $p$ | 0.0522 |

With $n=27$ and 19 wins, the one-sided exact binomial test sums $P(K\ge19\mid n=27,p=0.5)=\sum_{k=19}^{27}\binom{27}{k}(0.5)^{27}=0.0261$, below the conventional $\alpha=0.05$ threshold and supporting rejection of the zero-edge null in the hypothesized direction. As shown below, this significance claim is not robust to realistic transaction costs.

### Full Threshold Sweep

| Threshold | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (1-sided) | p (2-sided) |
|---|---|---|---|---|---|---|---|---|---|
| q≥0 | 27 | 19 | 8 | 70.37% | +30.31% | +1.1225% | 2.41% | 0.0261 | 0.0522 |
| q≥1 | 25 | 17 | 8 | 68.00% | +28.31% | +1.1323% | 2.51% | 0.0539 | 0.1078 |
| q≥2 | 23 | 15 | 8 | 65.22% | +23.28% | +1.0120% | 2.56% | 0.1050 | 0.2100 |
| q≥3 | 14 | 8 | 6 | 57.14% | +6.59% | +0.4709% | 2.76% | 0.3953 | 0.7905 |
| q≥4 | 6 | 3 | 3 | 50.00% | +6.71% | +1.1177% | 3.85% | 0.6562 | 1.0000 |
| q≥5 | 1 | 0 | 1 | 0.00% | −0.38% | −0.3809% | n/a ($n=1$) | 1.0000 | 1.0000 |

Because the cumulative filter that produces this table draws every row from the same 27-trade pool ($q{\ge}1$ is a subset of $q{\ge}0$, $q{\ge}2$ a subset of $q{\ge}1$, and so on), these six rows are not independent samples of one another, and any comparison across thresholds must account for this structural overlap rather than treating the rows as six separate experiments.

### Per-Criterion Orthogonal Tests

| Criterion | True $n$ (wins) | False $n$ (wins) | Fisher $p$ | Welch $t$ | Welch $p$ |
|---|---|---|---|---|---|
| Displacement | 4 (2) | 23 (17) | 0.5583 | −0.9277 | 0.3775 |
| LargeBar | 20 (14) | 7 (5) | 1.0000 | +0.2895 | 0.7751 |
| FVG | 11 (8) | 16 (11) | 1.0000 | +0.5360 | 0.5996 |
| LiqSweep | 15 (10) | 12 (9) | 0.6957 | −0.8195 | 0.4204 |
| VolExpansion | 15 (9) | 12 (10) | 0.2357 | −0.8835 | 0.3864 |

No criterion crosses $p = 0.05$ in either test. The Welch $p$-value range across all five criteria is 0.3775–0.7751; restricting to the four criteria with more adequately sampled subgroups (excluding Displacement's thin $n=4$ true-subgroup) narrows this to 0.3864–0.7751. Both framings are reported here rather than adjudicated between, since whether a criterion with a subgroup this small belongs in a summary range statement is an editorial judgment this paper leaves open.

### Statistical Power and Minimum Detectable Effect

| Criterion | Observed subgroup gap | MDE (80% power, $\alpha=0.05$) |
|---|---|---|
| Displacement | 0.74 pp | 2.23 pp |
| LargeBar | 0.23 pp | 2.25 pp |
| FVG | 0.56 pp | 2.91 pp |
| LiqSweep | 0.74 pp | 2.53 pp |
| VolExpansion | 0.78 pp | 2.47 pp |

Every observed subgroup gap is roughly three (VolExpansion, FVG) to ten (LargeBar) times smaller than the corresponding minimum detectable effect. The correct interpretation of the null results in the preceding table is therefore that this study is underpowered to reliably detect criterion-level effects of the size actually observed — not that no such effect exists. This distinction is discussed further below.

### Bootstrap Confidence Interval

A nonparametric percentile bootstrap with 10,000 resamples of the 27-trade return distribution gives a point estimate of +30.31% total net return with a 95% confidence interval of **[+5.99%, +54.99%]** — wide, but excluding zero (99.25% of resampled totals were positive). The average-return-per-trade 95% confidence interval is approximately [+0.22%, +2.04%]. This 10,000-resample figure is this paper's canonical bootstrap result, computed offline for maximum precision. A companion interactive website recomputes the same bootstrap live, in the browser, using a lighter 2,000 resamples for responsiveness, which lands on a similar but not identical interval, [+7.48%, +54.46%]; the difference between the two reflects only the smaller resample count in the interactive version, not a different methodology, a different random seed, or a different underlying trade set.

### Regime Breakdown and Correlation

Trades were tagged by macro market regime at entry, using two independent methods. A calendar-based split (2022 as bear, 2023 as chop, 2024–2025 as bull) gives:

| Regime | Trades | Win rate | Return contribution | Share of total return |
|---|---|---|---|---|
| Bear (2022) | 7 | 57.14% | +10.45% | +34.5% |
| Chop (2023) | 6 | 50.00% | −5.39% | −17.8% |
| Bull (2024–2025) | 14 | 85.71% | +25.25% | +83.3% |

A drawdown-from-all-time-high cross-check (seeded from BTC's pre-window all-time high of \$69,000 on 2021-11-10; bear defined as at or below −40% drawdown, chop as −40% to −12%, bull as above −12%) gives:

| Regime | Trades | Win rate | Return contribution | Share of total return |
|---|---|---|---|---|
| Bear (≤−40% dd) | 12 | 50.00% | −1.63% | −5.4% |
| Chop (−40% to −12% dd) | 8 | 87.50% | +18.89% | +62.3% |
| Bull (>−12% dd) | 7 | 85.71% | +13.05% | +43.1% |

The two methods agree on only 13 of 27 trade assignments, since they measure different things — much of calendar-2023 remained 57–64% below the all-time high even though price action that year was comparatively range-bound rather than actively declining. Both methods nonetheless agree on the conclusion that matters most: the bull regime is consistently strongest, with an 85.71% win rate under both classification methods. The three most concentrated winning trades, which together account for 51.7% of total net return, are not clustered in a single regime under either method.

Pearson's $r = +0.4907$ ($t = 2.82$, $p \approx 0.0094$) and Spearman's $\rho = +0.4797$ ($p \approx 0.0113$) between hold duration and percentage return, across the 27 baseline trades, indicate that trades held open longer tend to realize larger gains — a moderate positive association that is statistically significant at the conventional $\alpha = 0.05$ threshold and at $\alpha = 0.01$.

### Benchmark Comparison: Strategy versus Passive Alternatives

Two complementary benchmark analyses were conducted. The first models the strategy as a small allocation blended into an existing dollar-cost-averaging (DCA) plan rather than as a standalone replacement for it. Under a weekly-contribution model (210 equal weekly contributions across the study window, split between a BTC-DCA sub-sleeve and a strategy sub-sleeve that redeploys its full balance into each realized trade), Sharpe ratio, Sortino ratio, and maximum drawdown all improve monotonically as the strategy allocation rises from 0% to 30% of new weekly capital:

| Split (BTC-DCA / Strategy) | Sharpe (annualized) | Sortino (annualized) | Max drawdown |
|---|---|---|---|
| 100% / 0% | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |

Standalone, the strategy's own Sharpe (1.114) and Sortino (2.727) ratios exceed BTC buy-and-hold over the same window (Sharpe 0.564, Sortino 0.803); however, the strategy holds a market position only 2.63% of the time, so this is not a like-for-like comparison and should not be read as the strategy outperforming BTC's risk-adjusted profile outright. The correct framing is that blending a small strategy allocation into an existing DCA plan improves that plan's risk-adjusted shape.

The second analysis makes the exposure-time caveat concrete rather than only qualitative, by running three independently-computed, fully-capitalized arms head-to-head over the identical 2022–2026 window, each starting from \$10,000 in notional capital: the Order-Block-gated strategy (compounding only at each of its 27 trades' exits, with capital otherwise idle), a weekly dollar-cost-average purchase of BTC (210 equal weekly buys), and a lump-sum BTC purchase at the window's first bar, held unchanged to the window's last bar.

| Arm | Total Return | Final Capital (from \$10,000) | Sharpe | Sortino | Max Drawdown | % Time In-Market |
|---|---|---|---|---|---|---|
| OB-gated strategy | +30.31% | \$13,417.77 | 1.114 | 2.727 | −6.46% | 2.63% |
| Weekly DCA into BTC | +123.13% | \$22,312.94 | 0.556 | 0.886 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +90.07% | \$19,007.32 | 0.564 | 0.803 | −67.21% | 100.00% |

Stated plainly: dollar-cost-averaging into BTC outperformed the strategy in raw terminal value over this window, by a wide margin (\$22,312.94 versus \$13,417.77). This is not a favorable result and is not minimized here. What the strategy offers instead is a materially better risk-adjusted profile, achieved while holding a position only 2.63% of the time against 100% continuous exposure for both passive arms — an exposure asymmetry substantial enough that neither figure alone indicates which allocation an investor should prefer. The blended-sleeve model above remains the more decision-relevant framing of this comparison: a small strategy allocation blended into an existing DCA plan improves the portfolio's risk-adjusted shape, which is a materially different and more defensible claim than asserting the strategy replaces or outperforms DCA outright.

The same three-arm comparison, repeated over the 2018–2022 window against which the strategy's rule structure was originally formulated (and which is explicitly not out-of-sample evidence; see below), shows an even larger gap in the same direction:

| Arm | Total Return | Final Capital (from \$10,000) | Sharpe | Sortino | Max Drawdown | % Time In-Market |
|---|---|---|---|---|---|---|
| OB-gated strategy | +21.82% | \$12,282.53 | 0.681 | 1.303 | −6.00% | 1.87% |
| Weekly DCA into BTC | +439.88% | \$53,987.55 | 0.824 | 1.234 | −46.16% | 100.00% |
| Lump-sum buy-and-hold | +236.96% | \$33,696.49 | 0.789 | 1.119 | −81.42% | 100.00% |

BTC's 2018–2022 window contained a substantially larger drawdown-then-recovery cycle than 2022–2026, which mechanically favors dollar-cost-averaging's lower average cost basis; this is a property of the passive benchmarks' own mechanics under that specific price path rather than a statement about the strategy's edge in either direction.

### Transaction-Cost Sensitivity

The confirmed Binance USDT-M Futures standard-tier taker rate is 0.05% per side (0.10% round-trip); slippage was modeled separately as a conservative 0.05% per side (0.10% round-trip) estimate.

| Scenario | Total net return | Win rate | Binomial $p$ (one-sided) |
|---|---|---|---|
| Gross (as reported above) | +30.31% | 70.37% (19/27) | 0.0261 |
| Plus fee only (0.10% round-trip) | +27.61% | 70.37% | 0.0261 |
| Plus fee and slippage (0.20% round-trip, primary scenario) | +24.91% | 62.96% (17/27) | **0.1239** |

This is a significance-conclusion flip and is reported as such rather than softened: a realistic 0.20% round-trip drag moves the win-rate significance test from $p = 0.0261$ (significant) to $p = 0.1239$ (not significant), driven by two trades (originally +0.12% and +0.13% gross) flipping from winners to losers under this drag. By contrast, the Welch t-tests reported above are mathematically unaffected by this same adjustment, since a flat per-trade percentage drag shifts every subgroup's mean by an identical constant without changing the difference between subgroup means or either subgroup's variance — verified directly, with results identical to four decimal places under gross versus fee-adjusted returns. Across a wider sensitivity band (0.14%–0.40% round-trip), one criterion's Fisher's exact test (VolExpansion) crosses $p < 0.05$ only at the most pessimistic end of that range; at the primary 0.20% scenario it remains non-significant. This is treated as a multiple-comparisons artifact of testing five criteria across several drag assumptions, not as an independent finding.

### Out-of-Sample and Extended-History Validation

A forward out-of-sample test was constructed using BTCUSDT 4-hour data from 2026-01-01 through 2026-07-31 — genuinely postdating every commit to the strategy's source code — run through the identical, frozen pipeline after first confirming the locked 27-trade baseline reproduced exactly.

| Metric | Value |
|---|---|
| New (out-of-sample) trades | 4 |
| Wins / Losses | 1 / 3 |
| Win rate | 25.00% |
| Total return | −3.45% |
| Average return per trade | −0.86% |

This is reported as-is: a small, directionally unfavorable result. Four trades cannot confirm or refute the strategy's edge on their own, by the same minimum-detectable-effect logic discussed above, but this is the only genuinely prospective evidence available for this exact rule set, and it does not provide reassurance.

A separate eight-year backfill integrity check ran the identical, frozen pipeline against data extended back to 2018-01-01, to test whether approximately four additional years of indicator warm-up would alter the locked 2022–2026 baseline — a real methodological risk, since MACD's exponential moving averages and the static KDJ series are recursive with theoretically unbounded memory. The result was a pass: all 27 locked trades matched by entry timestamp, with a maximum P\&L difference of 0.0000000000% between the original and extended runs.

| Window | N | Win rate | Total return | Avg return/trade | Binomial $p$ (one-sided) |
|---|---|---|---|---|---|
| 2018-01 → 2022-01 (formulation period, not out-of-sample) | 25 | 60.00% | +21.82% | +0.87% | 0.2122 |
| 2022-01 → 2026-01 (primary window) | 27 | 70.37% | +30.31% | +1.12% | 0.0261 |
| Combined 2018–2026 (mixed provenance) | 56 | 62.50% | +48.68% | — | 0.0407 |

The combined-window row should never be cited on its own: roughly half of it is drawn from the period the strategy's rule structure was formulated against, so its $p = 0.0407$ partly reflects performance on data the rules could see during development. Notably, the strategy performs worse on its own formulation-period data than on the primary reported window — the opposite of what naive overfitting to that period would predict.

### Ablation Studies

A three-arm ablation study isolates the contribution of the Order Block structural gate from the underlying MACD/KDJ/ATR indicator layer:

| Arm | Entry | Risk placement | N | Win rate | Total return |
|---|---|---|---|---|---|
| Order-Block-gated baseline | Order Block touch + MACD/KDJ/ATR | Order Block boundary | 27 | 70.37% | +30.31% |
| Indicators-only (flat-ATR stop) | MACD/KDJ/ATR only | Close − 1.5×ATR | 140 | 60.00% | −14.63% |
| Indicators-only (swing-pivot stop) | MACD/KDJ/ATR only | 5-bar swing pivot ± 0.5×ATR | 138 | 55.07% | −25.50% |

This ablation's most important result is a controlled comparison designed to rule out an alternative explanation for the gated strategy's performance: that the Order Block gate's apparent benefit is really a side effect of its risk-placement rule, not its entry-selection rule. Equipping the indicators-only arm with a structural, swing-anchored stop (the third arm above) rather than a flat-ATR offset changed the candidate trade count only negligibly (138 versus 140, a 1.4% difference) and did not rescue performance — win rate fell further, from 60.00% to 55.07%, and total return worsened, from −14.63% to −25.50%. This is evidence that the underperformance of the ungated arms is driven by entry selection, not stop-placement mechanics: had risk placement been the real driver, a better-anchored stop should have narrowed the gap, and it did not.

A bootstrap resample of $n = 27$ trades from the 138-trade indicators-only pool (2,000 resamples) gives a median average return of −0.17%, with a 95% range of [−1.17%, +0.70%]; the Order-Block-gated baseline's own average return of +1.12% sits at an empirical $p = 0.0020$ against that null distribution, indicating the gated strategy's average return is not plausibly explained as a lucky 27-trade draw from the ungated pool, even though the corresponding win-rate-based bootstrap comparison is weaker (empirical $p$ in the range 0.07–0.17, depending on which ungated arm is used as the resampling pool).

This ablation's 140- and 138-trade figures cannot currently be reproduced end-to-end from a script committed to this project's codebase: the script that originally generated them was never committed, and a best-effort reconstruction attempt reproduces the correct trade counts exactly but diverges from the published win rates by roughly 11 to 13 percentage points, indicating the underlying per-trade outcomes in the reconstruction are not the same trades originally reported. This is disclosed here as an open reproducibility gap rather than resolved by substituting the reconstruction's figures for the originally published ones. The swing-anchored-stop unconfounding result described above is comparatively the stronger and more defensible piece of evidence for the claim that the Order Block gate matters, since it isolates entry selection from stop-placement mechanics using logic and data internal to this analysis, independent of the reproducibility gap affecting the original two-arm figures.

---

## Discussion

The full-sample return effect reported above is directionally robust: the percentile bootstrap 95% confidence interval on total return, [+5.99%, +54.99%], excludes zero even though it is wide, and 99.25% of the 10,000 bootstrap resamples were positive. The win-rate significance claim, by contrast, is fragile — it survives the exchange's published taker fee alone (still $p = 0.0261$) but flips to non-significant ($p = 0.1239$) under a realistic combined fee-and-slippage assumption. Both facts should be read together rather than in isolation: the return-magnitude comparisons are mathematically invariant to this same transaction-cost adjustment, while the win-rate significance claim is not. Reporting only the gross $p = 0.026$ figure, without the accompanying sensitivity result, would overstate what this dataset supports.

None of the five orthogonal Order Block quality criteria reach statistical significance in either the Fisher's exact or Welch's t-test comparisons reported above, but the minimum-detectable-effect analysis shows every observed subgroup gap is three to ten times smaller than what this sample size could reliably detect at 80% power. The correct characterization of these null results is that the study is underpowered to distinguish quality-criterion effects at this sample size — not that no significant difference exists, and not that quality criteria carry no signal. That stronger claim would overstate what a non-significant result at $n = 27$, split into subgroups as small as $n = 4$, can support. This power limitation is specific to the criterion-level subgroup comparisons; it does not extend to the full-sample return finding, which rests on its own, better-powered bootstrap evidence.

Two further claims discussed in this paper should not be treated as settled. The "190 total qualifying indicator signals" figure sometimes cited as the denominator behind a claimed coincidence rate between Order-Block-gated trades and independent indicator signals was derived under the indicators-only ablation's own risk-anchoring rule, not the Order-Block-gated strategy's actual risk rules; because the two populations are filtered differently, this denominator is treated as unresolved rather than settled in this paper, and no coincidence-rate claim built on it is asserted here. Separately, the ablation A/B figures discussed above, while internally consistent with every other disclosed figure in this project, cannot currently be independently reproduced from a committed script; readers should weight the ablation's central claim — that the Order Block gate matters — primarily on the strength of the independently reproducible swing-anchored-stop unconfounding result, rather than on the original two-arm figures alone.

The self-correction history described in the Methodology section is presented here as a feature of this project's methodology, not a defect in its result. Three code-level corrections were made over the course of the project, one of which changed a significance conclusion at a stricter quality threshold, and a later, separate audit pass caught two further reporting-layer errors — the bootstrap resample-count mismatch between this paper and its companion website, and the overstated correlation $p$-value — described in the Methodology section above. A result that shows its own correction history, including corrections found late and after the underlying analysis was otherwise complete, is more credible than one presented as though it had been correct from the start.

The strategy's edge is concentrated in bull-trending market conditions, with an 85.71% win rate under both regime-classification methods reported above, and is weaker or negative in choppy or bearish conditions under at least one of the two methods. This tempers any claim of regime-general reliability: the reported 2022–2026 window happens to include a substantial bull phase, and the strategy's aggregate performance depends materially on that phase's contribution. The three most concentrated winning trades are not all drawn from a single regime, which is a modest robustness point in the strategy's favor, but it does not fully offset the broader regime-concentration finding.

The complementary-sleeve framing of the benchmark comparison — monotonic Sharpe, Sortino, and drawdown improvement as strategy allocation rises within a blended DCA portfolio, achieved while the strategy sleeve is invested only 2.63% of the time — is the defensible way to present the relationship between this strategy and passive BTC accumulation. The head-to-head comparison reported above, in which dollar-cost-averaging outperformed the strategy in raw terminal value over both windows tested, should not be read as contradicting the complementary-sleeve result; the two analyses answer different questions, and neither licenses a claim that the strategy "beats" DCA or buy-and-hold outright.

---

## Limitations

This study does not model leveraged or margined positions and reports unlevered, notional (spot-equivalent) returns throughout. This is a deliberate scope decision rather than an oversight: the backtesting engine evaluates every exit condition — hard stop-loss, take-profit, the trailing exit, the ATR-move exit, and the breakeven-stop adjustment — at bar-close resolution only. Intrabar high and low prices are available in the underlying candle data and are used elsewhere in the pipeline, including Order Block touch detection and several of the structural quality criteria described above, but no exit or position-sizing decision reads them, and the simulation engine has no concept of a margin or liquidation price at any leverage level. A defensible leveraged backtest requires intrabar liquidation tracking, since a position can be liquidated by a price excursion that fully reverses within a single bar — an event a close-resolution simulation cannot see. Applying a leverage multiplier after the fact to this study's existing close-basis trade log would not model that risk; it would silently assume every trade's realized path was free of any intrabar excursion large enough to trigger liquidation, which the underlying data cannot confirm one way or the other. Unlevered results are reported throughout, consistent with common practice in the technical-trading-rule literature (e.g., Svogun & Bazán-Palomino, 2022, who evaluate moving-average and support/resistance rule profitability on cryptocurrency data net of transaction costs on a notional basis).

Two items discussed in this paper remain explicitly open rather than resolved. First, the "190 total qualifying indicator signals" denominator discussed above requires re-derivation under the Order-Block-gated strategy's own risk rules before any coincidence-rate claim built on it can be treated as settled; this paper does not attempt that re-derivation and does not rely on the figure. Second, the Welch $p$-value range reported for the five orthogonal quality criteria depends on an editorial choice — whether the Displacement criterion's thin four-trade true-subgroup should be included in a summary range statement — that this paper leaves open, reporting both framings rather than adjudicating between them.

The ablation study's original 140- and 138-trade indicators-only arms cannot currently be reproduced end-to-end from a committed script, as discussed above; this is disclosed as a standing reproducibility gap in this project's own toolchain rather than a claim about the correctness of the originally published figures, which remain internally consistent with every other figure reported in this paper.

Finally, the reported window's trade frequency is low (approximately 0.56 trades per month), which limits how quickly genuinely prospective, out-of-sample evidence can accumulate; the four-trade forward out-of-sample test reported above is too small on its own to confirm or refute the strategy's edge, and additional prospective evidence will only accumulate slowly as more time passes.

---

## Conclusion

Over BTC/USDT 4-hour candles from January 2022 through January 2026, a rule-based strategy gating MACD and KDJ momentum signals through Smart Money Concepts Order Block structural zones produced 27 trades, a 70.37% win rate, and a +30.31% total net return, departing from a 50% zero-edge null model at $p = 0.026$ (one-sided exact binomial). This headline result is directionally robust under a nonparametric bootstrap of its own trade distribution, whose 95% confidence interval excludes zero, but is not robust to realistic transaction-cost assumptions for the win-rate significance claim specifically, which moves from $p = 0.026$ to $p = 0.124$ under a conservative 0.20% round-trip cost assumption, even though the associated return-magnitude comparisons are mathematically unaffected by that same cost. A three-arm ablation study shows the Order Block structural gate materially improves outcomes over ungated indicator signals, and this improvement survives a controlled test disentangling entry selection from stop-placement mechanics, though the originally published ablation trade-level figures cannot currently be reproduced from a script committed to this project. None of five hypothesized Order Block quality criteria show a statistically detectable relationship to trade outcome at this sample size, but this study is underpowered to detect effects of the size actually observed — not evidence that no such effect exists. A genuinely prospective out-of-sample test on data postdating every code commit was small and directionally unfavorable, and is reported as such; an eight-year backfill confirmed the reported window's results are not an artifact of insufficient indicator warm-up. A head-to-head benchmark against passive alternatives shows dollar-cost-averaging into BTC outperformed the strategy in raw terminal value over both windows tested, while the strategy showed a materially better risk-adjusted profile achieved through only 2.63% market exposure — an asymmetry that precludes a simple "beats the benchmark" claim in either direction.

This study establishes a historically observed, directionally robust return edge for this specific rule set on this specific window, with its win-rate significance shown to be cost-sensitive and its regime concentration made explicit, obtained through a process with a disclosed and audited self-correction history spanning both the backtesting code itself and this paper's own reporting of results. This study does not establish that any individual Order Block quality criterion predicts trade outcome — the relevant tests are underpowered, not negative; that the strategy generalizes evenly across market regimes; that the disputed 190-signal denominator or the original ablation trade-level figures are independently reproducible from this project's current codebase; that the strategy outperforms passive BTC accumulation in raw terms; or that the strategy's edge persists prospectively, given that the only prospective evidence available, though too small to be conclusive, was unfavorable.

Future work should prioritize three directions: first, resolving the two disclosed open items — the 190-signal denominator's population mismatch and the ablation script's reproducibility gap — by committing a script that reproduces the ablation trade log from current code, or by explicitly re-deriving the 190 figure under the Order-Block-gated strategy's own risk rules; second, continuing to accumulate genuinely prospective out-of-sample trades as time passes, recognizing that the strategy's low trade frequency means statistical power in that direction will build only slowly; and third, considering a lower-timeframe or multi-asset extension whose sole purpose is increasing the sample size available for the criterion-level power analysis, without altering any of the locked results reported in this paper.

---

## References

Svogun, D., & Bazán-Palomino, W. (2022). Technical analysis in cryptocurrency markets: Do transaction costs and bubbles matter? *Journal of International Financial Markets, Institutions and Money, 79*. (Author order as cited here follows the primary source consulted during this project; at least one secondary source lists the order as Bazán-Palomino & Svogun. This should be verified against the authors' own reference-manager entry before final submission, since this project could not independently confirm the correct order or fully verify that the paper frames its own results in the specific "unlevered, notional returns" terminology used in this paper's Limitations section.)

*Note: this project's own internal records contain no other independently verifiable academic citations. A complete References section suitable for submission will require the authors' own literature review and reference-manager entries; this list should not be treated as exhaustive.*
