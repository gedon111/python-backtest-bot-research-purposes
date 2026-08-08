# Full Research Report — Paper Update Draft (Methodology / Results / Discussion / Conclusion)

> **Status: draft for paper integration, not yet inserted into the paper.**
> This document consolidates content that was previously scattered across
> `STUDY_REFERENCE.md`, `docs/results_section_addition_draft.md`,
> `docs/limitations_section_draft.md`, `artifacts/paper_sync_report.md`,
> `docs/backtest_methodology_defense_walkthrough.md`, and
> `docs/ablation_study_indicators_only.md` / `docs/ablation_unconfounding_analysis.md`
> into one document organized the way a paper is organized: Methodology,
> Results, Discussion, Conclusion. **No new figures were computed for this
> document** — every number below is reproduced verbatim from one of those
> already-verified sources, cross-checked against `CLAUDE.md`'s locked
> results block as final authority. Where a source document itself flags an
> unresolved wording tension or open question, that flag is carried forward
> here rather than silently resolved. Prepared 2026-08-08.

---

## 0. Study identity (for context, not for direct insertion)

**Working title:** *Harnessing Bitcoin Volatility: Backtesting an Integrated
Algorithmic Strategy Combining KDJ, MACD, and Smart Money Concepts.*

**Research question:** Does a rule-based entry/exit strategy that gates MACD
and KDJ momentum signals through Smart Money Concepts (SMC) Order Block (OB)
structural zones produce a historical win rate and return on BTC/USDT 4-hour
candles that departs from a zero-edge (50% win probability) null model, and
does OB "quality" (a 5-criterion structural score) modulate that departure?

**Framing:** This is a rule-based, parameter-fixed historical backtest, not a
live or production trading system. No parameter in the simulated strategy was
fit, swept, or optimized against the outcome being measured. `simulate_trades()`
runs bar-by-bar over a static historical DataFrame; there is no
order-execution or live-data code path.

---

## 1. Methodology

### 1.1 Data acquisition and preprocessing

**Source.** Binance `get_klines` REST endpoint, `BTCUSDT` symbol, 4-hour
interval (`Client.KLINE_INTERVAL_4HOUR`), paginated in batches of 1,000
candles.

**Timestamp convention.** Binance's raw millisecond `open_time` is converted
to a `datetime` and shifted by a fixed **+8 hour** offset. `open_time` in the
stored dataset is therefore UTC+8, not raw UTC — this must be stated
explicitly anywhere the paper reproduces a specific bar's timestamp.

**Window and bar count.** 2022-01-01 08:00:00 through 2026-01-01 08:00:00,
**8,767 bars**, verified live against `artifacts/candles.csv`. Arithmetic:
2022-01-01 to 2026-01-01 spans exactly 1,461 calendar days (365 + 365 + 366 +
365, the 366 accounting for the 2024 leap day). At 6 four-hour bars per day,
that is 1,461 × 6 = 8,766 bar-intervals; because the final bar is itself
included as a row rather than used only as an exclusive upper bound, the row
count is 8,766 + 1 = **8,767**. *(The paper's original figure of 8,760 was a
plain arithmetic slip — corrected in code and here. See §5 checklist item 1.)*
No gaps: the set of unique inter-bar timestamp deltas across all 8,767 rows is
the single value 4 hours.

**Storage.** `artifacts/candles.csv` / `artifacts/candles.json` (flat files)
and `backtest_results.db` (SQLite, table `Candle`).

### 1.2 Indicator computation

All indicators are computed once over the complete 8,767-bar series before
trade simulation (no per-trade recomputation, no lookahead in the indicator
layer itself — see §1.7).

**MACD(12, 26, 9).** Standard EMA-based MACD, causal (`adjust=False`, no
lookahead):

$$EMA_{12}(t) = C_t \cdot \tfrac{2}{13} + EMA_{12}(t-1)\cdot\left(1-\tfrac{2}{13}\right), \qquad EMA_{26}(t) = C_t \cdot \tfrac{2}{27} + EMA_{26}(t-1)\cdot\left(1-\tfrac{2}{27}\right)$$
$$\text{MACD}_t = EMA_{12}(t) - EMA_{26}(t), \qquad \text{Signal}_t = \text{MACD}_t\cdot\tfrac{2}{10} + \text{Signal}_{t-1}\cdot\left(1-\tfrac{2}{10}\right), \qquad \text{Hist}_t = \text{MACD}_t - \text{Signal}_t$$

**ATR(14) and ATR(200).** True range, then a **simple rolling mean** (not
Wilder's RMA — a code comment near this line says "Wilder's RMA" but the
executed line is `tr.rolling(n, min_periods=1).mean()`; the paper should
describe SMA smoothing, matching what actually runs):

$$TR_t = \max\!\big(H_t-L_t,\ |H_t-C_{t-1}|,\ |L_t-C_{t-1}|\big), \qquad ATR_{14}(t) = \frac{1}{14}\sum_{i=0}^{13}TR_{t-i}, \qquad ATR_{200}(t) = \frac{1}{200}\sum_{i=0}^{199}TR_{t-i}$$

$ATR_{14}$ drives stop-loss distance, the minimum-stop-ratio filter, the
trailing exit, and the ATR-move exit. $ATR_{200}$ is the volatility baseline
used by the ATR-regime entry filter and by two of the five OB quality
criteria (Displacement, LargeBar).

**KDJ(9, 3, 3) — static, full-history, entry-gating.** Computed once over the
whole dataset:

$$RSV_t = \frac{C_t - \min_{i\in[0,8]}L_{t-i}}{\max_{i\in[0,8]}H_{t-i} - \min_{i\in[0,8]}L_{t-i}}\times 100, \qquad K_t = \tfrac{2}{3}K_{t-1}+\tfrac{1}{3}RSV_t, \qquad D_t = \tfrac{2}{3}D_{t-1}+\tfrac{1}{3}K_t, \qquad J_t = 3K_t - 2D_t$$

This is a single, fixed-period (9) series computed once. Every K/D/J
reference inside the entry-condition checks reads this static column at the
current bar — it does **not** vary per trade. This must be kept distinct from
the second KDJ system described in §1.4.

### 1.3 SMC Order Block detection

`compute_smc()` runs two independent structural passes over the same price
series — **internal structure** (pivot lookback 5 bars) and **swing
structure** (pivot lookback 50 bars). In each pass, a bar $pb = i - \text{size}$
is confirmed as a pivot high only by strict right-side comparison,
$H_{pb} > \max(H_{pb+1..i})$ (mirror condition for pivot low) — no future bar
is ever read. A Break of Structure / Change of Character is flagged when
`close` crosses a tracked pivot level, and an Order Block is created from the
`parsedHigh`/`parsedLow` segment between the pivot bar and the crossover bar
$i$. Two bar indices matter and are easy to conflate: `ob_idx` (`ob_bar`) is
the bar where the OB's own extreme candle occurred; `created_at` is the bar
where the breakout candle *closes* — the OB is not eligible for entry until
strictly after `created_at`. Order Blocks expire after `MAX_OB_AGE = 500`
bars or once price closes through their boundary (`mitigated_at`).

### 1.4 OB quality: five orthogonal criteria (post-correction definitions)

Each detected OB is scored on five **independently evaluated** boolean
criteria, summed into a 0–5 `quality` field used only as a cumulative entry
threshold (`quality >= min_ob_quality`) — never as an ordinal "higher is
better" claim in the analysis (see Bug #1, §1.6).

1. **Displacement** — within bars $ob\_idx{+}1$ to $\min(i, ob\_idx{+}3)$
   (bounded at the OB's own confirmation bar $i$), a candle body move
   $|C-O|\ge 1.5\times ATR_{200}(ob\_idx)$ occurs in the OB's direction.
2. **LargeBar** — the OB's own bar has $H-L \ge ATR_{200}(ob\_idx)$.
3. **FVG (Fair Value Gap)** — a 3-candle imbalance exists for some $j$ in
   $[ob\_idx,\ \min(i-1, ob\_idx{+}2)]$: $L_{j+2}>H_j$ (DEMAND) or
   $H_{j+2}<L_j$ (SUPPLY), with $j+2\le i$ enforced.
4. **LiquiditySweep** — the OB bar's low $\le$ the minimum low of the prior
   10 bars (DEMAND), or its high $\ge$ the maximum high of the prior 10 bars
   (SUPPLY).
5. **VolumeExpansion** — the OB bar's volume $\ge 1.25\times$ the prior
   20-bar average, OR its body is $>60\%$ of its own high–low range.

### 1.5 Fixed entry/exit rule set (pre-registered, never swept)

| Parameter | Value |
|---|---|
| `sl_ratio_min` | 0.015 (min. stop distance, 1.5% of entry) |
| `kdj_j_long_cap` | 60.0 |
| `kdj_k_long_cap` | 50.0 |
| `kdj_k_short_floor` | 70.0 |
| `kdj_j_short_cap` | 100.0 |
| `atr_mult_exit` | 1.8 (ATR-move take-profit exit) |
| `atr_mult_be` | 2.0 (breakeven-stop trigger, in ATR) |
| `rr_min` | 1.5 (minimum reward:risk to accept a trade) |

**LONG entry** requires all of: price interacting with an active,
unmitigated DEMAND OB of sufficient quality; $\text{Hist}<0$ and rising for
$\ge2$ bars; static $K<50$ and rising, $J<60$; a bounded 2-bar
K-acceleration window $1\le k_{accel}\le 6$; ATR regime filter rejecting
$0.8\le ATR_{14}/ATR_{200}\le1.0$; stop distance $\ge1.5\%$ of entry;
reward:risk $\ge1.5$. **SHORT entry** is the mirror condition against a
SUPPLY OB with $K>50$, $J>K>D$, $K\ge70$, $J\le100$.

**Exit priority**, checked every bar while a position is open, first match
wins: (1) trailing exit — 50% retrace of peak favorable PnL once peak
$\ge1.5\%$; (2) KDJ-reset exit (gated to bar 3+ after entry, §1.6); (3)
ATR-move exit at $\sim1.8\times ATR$ favorable move; (4) breakeven-stop
adjustment at $2.0\times ATR$ favorable move (risk management, not itself an
exit); (5) hard stop-loss; (6) hard take-profit.

### 1.6 The two KDJ systems — kept explicitly separate

This is the single most easily miscommunicated part of the strategy and
should be stated as its own paragraph in the paper, not folded into §1.2.

**(a) Static entry-gating KDJ** — §1.2's fixed-period-9 series, identical
regardless of which OB triggers entry, never varies per trade.

**(b) Post-entry, adaptive exit-window KDJ state machine** — a *separate*
recursion (`kdj_reset_init` / `kdj_reset_update` / `kdj_reset_exit`), used
**only** to time the KDJ-reset exit signal after a trade is already open. At
entry, the state is seeded from the **static** K/D values already present at
`entry_idx` (not reseeded to 50, not backfilled), with a lookback window

$$\text{period} = w = \max(1,\ \text{entry\_idx} - ob\_bar)$$

held fixed for that trade's life. Each subsequent bar recomputes a custom RSV
over a rolling window of length $w$ and recurses K/D with the same
$\alpha=1/3$ smoothing:

$$RSV_{custom} = \frac{C_{cur} - \min_{j\in[cur-w+1,\,cur]}L_j}{\max_{j\in[cur-w+1,\,cur]}H_j - \min_{j\in[cur-w+1,\,cur]}L_j}\times100, \qquad K_{cur}=\tfrac{2}{3}K_{prev}+\tfrac{1}{3}RSV_{custom}, \qquad D_{cur}=\tfrac{2}{3}D_{prev}+\tfrac{1}{3}K_{cur}$$

The exit fires on a cross-back once "armed," gated so it cannot fire before
bar 3 of the trade. **What varies trade-to-trade is only $w$ — never the
entry-gating KDJ.** Live-verified $w$ across the 27 baseline trades: **range
14–439, median 74** — never a "two-bar window"; any prior paper language
suggesting a two-bar illustrative example describes an edge case, not the
observed distribution, and should be corrected or clearly marked as
illustrative only.

### 1.7 Statistical methods (formulas)

- **One-sided exact binomial test** of win rate against the zero-edge null,
  `scipy.stats.binomtest(wins, n, 0.5, alternative='greater')`:
  $$p = \sum_{k=\text{wins}}^{n}\binom{n}{k}(0.5)^n$$
  One-sided because the pre-registered hypothesis is directional (edge
  exceeds 50%, not merely differs from it). Two-sided values are reported
  alongside for reference.
- **Fisher's exact test**, on the 2×2 win/loss-by-criterion-truth
  contingency table, independently per criterion, over the 27-trade
  baseline.
- **Welch's (unequal-variance) t-test**, `scipy.stats.ttest_ind(equal_var=False)`,
  comparing per-trade `pnl_pct` between a criterion's True and False
  subgroups:
  $$t = \frac{\bar X_T - \bar X_F}{\sqrt{\dfrac{s_T^2}{n_T}+\dfrac{s_F^2}{n_F}}}, \qquad \bar X=\frac1n\sum X_i,\qquad s^2=\frac{1}{n-1}\sum(X_i-\bar X)^2$$
  Welch's (not Student's) form is used because subgroup sizes/variances are
  unequal and small (subgroup $n$ ranges 4–23).
- **Minimum Detectable Effect (MDE)** at $\alpha=0.05$, power $=0.80$, per
  criterion, from each subgroup's observed $n$ and SD — the smallest true
  mean-return gap the sample size could reliably detect.
- **Percentile bootstrap**, $B=10{,}000$ resamples with replacement of the
  27-trade return distribution, 95% CI from the 2.5th/97.5th percentiles.
- **Pearson $r$ / Spearman $\rho$** between hold duration (bars) and
  `pnl_pct` across the 27 baseline trades.

### 1.8 Methodological rigor: self-audit as method

Three bugs were found, corrected, and are disclosed rather than silently
absorbed — this history should appear in the paper's methods section as
evidence of process, not hidden as an embarrassment:

1. **Non-orthogonal composite score.** The original 0–5 quality score was
   built so higher-scored OB sets were nested subsets of lower-scored sets,
   confounding any "quality independently predicts outcome" claim. Fixed by
   evaluating and reporting the 5 criteria independently; the `quality`
   field is still computed and still used as the cumulative entry-filter
   threshold — only the *analysis* method changed.
2. **FVG two-candle vs. three-candle definition.** Originally tested
   adjacent candles ($L_{j+1}>H_j$) instead of the correct 3-candle
   imbalance ($L_{j+2}>H_j$). Corrected.
3. **Lookahead across the OB confirmation boundary.** The FVG and
   displacement forward-search loops were originally bounded by dataset
   length rather than by the OB's own confirmation bar $i$, so they could
   read 1–2 bars that would not have been available when the OB became
   usable for entry. Found via a dedicated no-lookahead audit; fixed by
   bounding both loops at $i$, with runtime assertions left in place at the
   read sites. This is a genuine data-leakage fix (distinct in kind from
   bugs #1–#2, which were definitional), and it **flips a significance
   conclusion**: the q≥1 one-sided binomial p moves from 0.038 (n=26,
   pre-fix) to 0.054 (n=25, post-fix) — marginally significant to not
   significant, driven by one trade (`entry_idx=3100`) losing its only
   quality point (FVG) under the corrected computation. This should be
   stated plainly in the paper, not smoothed over.

**Reporting-layer corrections from a final numerical audit (distinct from
the three code-level bugs above).** A closing cross-surface audit — checking
every headline number against this paper draft, the interactive website,
and the underlying committed scripts — found two further errors, neither in
the backtest engine itself, but in how results were *reported*: (a) the
website's interactive bootstrap confidence interval used a lighter
$B=2{,}000$ resamples than this paper's canonical $B=10{,}000$ figure,
producing two visibly different but individually correct intervals with no
stated reason they differed (§2.5); and (b) the Pearson/Spearman correlation
$p$-values in this document and a supporting walkthrough document were
reported as "$p<0.001$" when the correct values are $p\approx0.0094$
(Pearson) and $p\approx0.0113$ (Spearman) — still significant at
conventional thresholds, but overstated by roughly an order of magnitude
(§2.6). Both are corrected in this document. Consistent with the treatment
of the three code-level bugs above, these are disclosed rather than quietly
fixed: a project whose own final audit catches its own reporting errors is
demonstrating the same rigor the code-level corrections already
demonstrate, not undermining it.

**No-lookahead proof, independent of the bug-fix narrative above.**
Truncation-equality testing on ATR(14)/ATR_200/static KDJ(9,3,3): **180/180
checks pass** (36 sampled bars × 5 columns). A scope audit on the corrected
`compute_smc()` output: **0/253 FVG-true OBs and 0/107 displacement-true OBs**
read past their own confirmation bar.

**Reproducibility infrastructure.** `scratch/regression.py` is a golden-master
harness that recomputes indicators and the OB-gated simulation from raw
candle data and asserts exact equality (indicators to 1e-6, all 27 baseline
trade fields exactly) against committed fixtures — run after every code
change. A second, **independently implemented** JavaScript dashboard
recomputes the entry-condition/indicator layer (MACD/KDJ/ATR checklist and
its own from-scratch reimplementation of the post-entry adaptive-KDJ
recursion) client-side from trade data, as a cross-check against a second
codebase. Its documented scope limit should be stated alongside any claim of
independence: it does **not** independently detect Order Blocks, FVG, or
displacement — those fields are read as trusted data from the Python
pipeline. The JS cross-check therefore could not have caught bug #3 above; it
verifies a different, narrower layer of the pipeline.

---

## 2. Results

### 2.1 Baseline (q ≥ 0)

| Metric | Value |
|---|---|
| Trades | 27 |
| Wins / Losses | 19 / 8 |
| Win rate | 70.37% |
| Total net return | +30.31% |
| Avg return/trade | +1.1225% |
| SD (return/trade) | 2.41% |
| One-sided binomial $p$ | 0.0261 |
| Two-sided binomial $p$ | 0.0522 |

Computation: with $n=27$, wins $=19$, the one-sided exact binomial test sums
$P(K\ge19\mid n=27,p=0.5)=\sum_{k=19}^{27}\binom{27}{k}(0.5)^{27}=0.0261$ —
below the conventional $\alpha=0.05$ threshold, supporting rejection of the
zero-edge null in the hypothesized direction. (§2.7 shows this significance
claim is **not** robust to realistic transaction costs.)

### 2.2 Full threshold sweep (q0–q5)

| Threshold | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (1-sided) | p (2-sided) |
|---|---|---|---|---|---|---|---|---|---|
| q≥0 | 27 | 19 | 8 | 70.37% | +30.31% | +1.1225% | 2.41% | 0.0261 | 0.0522 |
| q≥1 | 25 | 17 | 8 | 68.00% | +28.31% | +1.1323% | 2.51% | 0.0539 | 0.1078 |
| q≥2 | 23 | 15 | 8 | 65.22% | +23.28% | +1.0120% | 2.56% | 0.1050 | 0.2100 |
| q≥3 | 14 | 8 | 6 | 57.14% | +6.59% | +0.4709% | 2.76% | 0.3953 | 0.7905 |
| q≥4 | 6 | 3 | 3 | 50.00% | +6.71% | +1.1177% | 3.85% | 0.6562 | 1.0000 |
| q≥5 | 1 | 0 | 1 | 0.00% | −0.38% | −0.3809% | n/a (n=1) | 1.0000 | 1.0000 |

**Caveat to state inline, not as a footnote:** because the cumulative filter
`quality >= min_ob_quality` draws every row from the same 27-trade pool
(q≥1 ⊂ q≥0, q≥2 ⊂ q≥1, …), these rows are **not independent samples of each
other**. Any cross-threshold comparison in the paper must say so explicitly
rather than treating the six rows as six separate experiments.

### 2.3 Per-criterion orthogonal tests (Fisher's exact + Welch's t-test)

| Criterion | True n (wins) | False n (wins) | Fisher $p$ | Welch $t$ | Welch $p$ |
|---|---|---|---|---|---|
| Displacement | 4 (2) | 23 (17) | 0.5583 | −0.9277 | 0.3775 |
| LargeBar | 20 (14) | 7 (5) | 1.0000 | +0.2895 | 0.7751 |
| FVG | 11 (8) | 16 (11) | 1.0000 | +0.5360 | 0.5996 |
| LiqSweep | 15 (10) | 12 (9) | 0.6957 | −0.8195 | 0.4204 |
| VolExpansion | 15 (9) | 12 (10) | 0.2357 | −0.8835 | 0.3864 |

No criterion crosses $p=0.05$ in either test.

**Wording tension to resolve before finalizing the paper (flagged, not
resolved here):** the Welch $p$-value range across all 5 criteria is
**0.3775–0.7751** ("0.38–0.78," Displacement sets the floor). The range
across only the four criteria the paper's own prose says were formally
tested (Displacement excluded for its thin $n=4$) is **0.3864–0.7751**
("0.39–0.78," VolExpansion sets the floor instead). `CLAUDE.md`'s pending
correction note uses the first framing; the paper's own methodology text
implies the second. **Pick one framing and make the stated range and the
stated inclusion/exclusion of Displacement agree** — this is an internal
consistency fix, not a new number to derive.

### 2.4 Power / Minimum Detectable Effect

| Criterion | Observed subgroup gap | MDE (80% power, α=0.05) |
|---|---|---|
| Displacement | 0.74 pp | 2.23 pp |
| LargeBar | 0.23 pp | 2.25 pp |
| FVG | 0.56 pp | 2.91 pp |
| LiqSweep | 0.74 pp | 2.53 pp |
| VolExpansion | 0.78 pp | 2.47 pp |

Every observed gap is roughly 3× (VolExpansion, FVG) to 10× (LargeBar)
smaller than the corresponding MDE. See §3 for the interpretation this
licenses (and the interpretation it does not).

### 2.5 Bootstrap CI on the core return finding

Nonparametric percentile bootstrap, $B=10{,}000$ resamples of the 27-trade
return distribution: point estimate **+30.31%** total net return, 95% CI
**[+5.99%, +54.99%]** — wide, but excludes zero (99.25% of resampled totals
positive). Avg return/trade 95% CI: roughly **[+0.22%, +2.04%]**. **This
$B=10{,}000$ figure is the paper's canonical bootstrap result**, computed
offline in Python (`analysis/bootstrap_power_analysis.py`) for maximum
precision. In plain terms: the interactive website (Stats/Solutions tabs)
recomputes the same bootstrap live, in the browser, but with a lighter
$B=2{,}000$ resamples for responsiveness, which lands on a very similar but
not identical interval, [+7.48%, +54.46%] — the gap between the two is a
direct consequence of the smaller resample count, not a different
methodology, a different seed, or a different underlying trade set (both
use seed 42 on the same 27 trades).

### 2.6 Regime breakdown, correlation, and benchmark reframing

**Calendar-split regime breakdown** (2022 = bear, 2023 = chop, 2024–25 =
bull):

| Regime | Trades | Win rate | Return contribution | Share of total return |
|---|---|---|---|---|
| BEAR (2022) | 7 | 57.14% | +10.45% | +34.5% |
| CHOP (2023) | 6 | 50.00% | −5.39% | −17.8% |
| BULL (2024–25) | 14 | 85.71% | +25.25% | +83.3% |

**Drawdown-based cross-check** (from BTC's pre-window ATH of $69,000,
2021-11-10; BEAR ≤ −40% dd, CHOP −40% to −12%, BULL > −12%):

| Regime | Trades | Win rate | Return contribution | Share of total return |
|---|---|---|---|---|
| BEAR (≤−40% dd) | 12 | 50.00% | −1.63% | −5.4% |
| CHOP (−40%..−12% dd) | 8 | 87.50% | +18.89% | +62.3% |
| BULL (>−12% dd) | 7 | 85.71% | +13.05% | +43.1% |

The two methods agree on only 13/27 trade assignments (they measure
different things — most of calendar-2023 was still 57–64% below the ATH),
but they agree on the conclusion that matters: **the BULL regime is
consistently strongest (85.71% win rate under both methods)**, and neither
method's weakest regime loses much of the total return. The three most
concentrated winning trades (entry_idx 359, 6366, 8280 — together 51.7% of
total net return) are **not** clustered in a single regime under either
method (BEAR/BULL/BULL calendar; CHOP/BULL/BULL drawdown).

**Correlation.** Pearson $r=+0.4907$ ($t=2.82$, $p\approx0.0094$) and Spearman
$\rho=+0.4797$ ($p\approx0.0113$) between hold duration and `pnl_pct` across
the 27 baseline trades. In plain terms: trades that stay open longer tend to
realize larger gains, a moderate positive association that is statistically
significant at the conventional $\alpha=0.05$ threshold (and at
$\alpha=0.01$). *(These $p$-values were corrected during a 2026-08-08
numerical audit — both were previously misreported as "$p<0.001$" here and
in a supporting walkthrough document; see §1.8.)*

**Benchmark, reframed as a complementary sleeve, not a replacement.** A
weekly-DCA blend model (210 weekly contributions over the study window,
splitting each week's contribution between BTC-DCA and a strategy sleeve
that redeploys its full balance into realized trades) shows Sharpe, Sortino,
and max-drawdown improving **monotonically** as strategy allocation rises
from 0% to 30%:

| Split (BTC-DCA / Strategy) | Sharpe (ann.) | Sortino (ann.) | Max drawdown |
|---|---|---|---|
| 100% / 0% | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |

Standalone strategy Sharpe (1.114) / Sortino (2.727) exceed BTC buy-and-hold
over the same window (Sharpe 0.564, Sortino 0.803) — but the strategy holds a
position only **2.63%** of the time, so this is not a like-for-like
comparison and must not be reported as "beats BTC's risk-adjusted profile."
The correct framing: risk-adjusted *shape* improves with a small strategy
allocation; absolute final value is lower at every split tested versus
100%-BTC-DCA, because the strategy sleeve is invested only a small fraction
of the time.

**Head-to-head benchmark arms: strategy vs. weekly DCA vs. lump-sum
buy-and-hold.** To make the exposure-time caveat above concrete rather than
only qualitative, the same \$10,000 in notional starting capital was run
through three independently-computed arms over the identical 2022–2026
window (`analysis/benchmark_vs_passive.py`): the OB-gated strategy
(compounding only at each of its 27 trades' exits, capital otherwise idle),
a weekly dollar-cost-average purchase of BTC (210 equal weekly buys, each at
that ISO week's first-bar close), and a lump-sum BTC purchase at the
window's very first bar's open, held unchanged to the window's last bar's
close. In plain terms: if an investor had actually put \$10,000 into each of
these three approaches on day one, this is what each would be worth by the
end.

| Arm | Total Return | Final Capital (from \$10,000) | Sharpe | Sortino | Max Drawdown | % Time In-Market |
|---|---|---|---|---|---|---|
| OB-gated strategy | +30.31% | \$13,417.77 | 1.114 | 2.727 | −6.46% | 2.63% |
| Weekly DCA into BTC | +123.13% | \$22,312.94 | 0.556 | 0.886 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +90.07% | \$19,007.32 | 0.564 | 0.803 | −67.21% | 100.00% |

**Stated plainly, not buried: dollar-cost-averaging into BTC outperformed
the strategy in raw terminal value over this window** — by a wide margin
(\$22,312.94 vs. \$13,417.77). This is not a favorable comparison to soften.
What the strategy offers instead is a materially better *risk-adjusted*
profile (Sharpe 1.114 vs. 0.564 for lump-sum buy-and-hold, 0.556 for DCA),
achieved while holding a position only 2.63% of the time against 100%
continuous exposure for both passive arms. These are not directly comparable
claims — a strategy exposed to the market 2.63% of the time will
mechanically show a different risk profile than one exposed 100% of the
time, and neither figure alone tells an investor which allocation to prefer.
The complementary-sleeve model above (Sharpe/Sortino/drawdown improving
monotonically from 0.556/0.886/−27.85% at 100% DCA to 0.637/1.032/−23.18% at
a 70/30 DCA/strategy blend) remains the more decision-relevant framing: a
small strategy allocation blended into an existing DCA plan improves the
portfolio's risk-adjusted shape — this is not a claim that the strategy
should replace DCA, or that it beats DCA outright.

**Formulation-period arm (2018–2022, not out-of-sample — see §2.8).** The
same three-arm comparison, repeated over the 2018–2022 window the strategy's
rule *structure* was originally formulated against, shows an even larger
gap in the same direction:

| Arm | Total Return | Final Capital (from \$10,000) | Sharpe | Sortino | Max Drawdown | % Time In-Market |
|---|---|---|---|---|---|---|
| OB-gated strategy | +21.82% | \$12,282.53 | 0.681 | 1.303 | −6.00% | 1.87% |
| Weekly DCA into BTC | +439.88% | \$53,987.55 | 0.824 | 1.234 | −46.16% | 100.00% |
| Lump-sum buy-and-hold | +236.96% | \$33,696.49 | 0.789 | 1.119 | −81.42% | 100.00% |

BTC's 2018–2022 window contained a much larger drawdown-then-recovery cycle
than 2022–2026, which mechanically favors dollar-cost-averaging's lower
average cost basis — this is a property of the passive benchmarks' own
mechanics under that specific price path, not a statement about the
strategy's edge in either direction, and per §2.8 this window is not
out-of-sample evidence for the strategy regardless of which arm "wins."

### 2.7 Fee/slippage sensitivity

Confirmed Binance USDT-M Futures standard-tier taker rate: **0.05%/side
(0.10% round-trip)**. Slippage modeled separately as a conservative
**0.05%/side (0.10% round-trip)** estimate.

| Scenario | Total net return | Win rate | Binomial $p$ (1-sided) |
|---|---|---|---|
| Gross (as reported) | +30.31% | 70.37% (19/27) | 0.0261 |
| + fee only (0.10% RT) | +27.61% | 70.37% | 0.0261 |
| + fee + slippage (0.20% RT, primary scenario) | +24.91% | 62.96% (17/27) | **0.1239** |

**This is a significance-conclusion flip and should be reported as such, not
softened:** a realistic 0.20% round-trip drag moves the win-rate significance
test from $p=0.0261$ (significant) to $p=0.1239$ (not significant). Two
trades (+0.12% and +0.13% gross) flip from winner to loser under this drag.
By contrast, **the Welch t-tests are mathematically unaffected** — a flat
per-trade percentage drag shifts every subgroup's mean by the same constant
without changing the difference between means or either subgroup's variance;
verified directly (identical to 4 decimals gross vs. fee-adjusted). One
sensitivity-band caution: across a wider drag range (0.14%–0.40% RT),
VolExpansion's Fisher's exact test crosses $p<0.05$ ($p=0.0185$) only at the
most pessimistic end (0.40% RT); at the primary 0.20% scenario it is
$p=0.1071$, not significant. Flagged as a multiple-comparisons artifact (5
criteria × several drag levels), not a finding.

### 2.8 Out-of-sample and extended-history validation

**Forward OOS test** — BTCUSDT 4H from 2026-01-01 through 2026-07-31,
genuinely postdating every commit to the strategy's source file, run through
the frozen pipeline (locked 27-trade baseline reproduced byte-identically
first):

| Metric | Value |
|---|---|
| New (OOS) trades | 4 |
| Wins / Losses | 1 / 3 |
| Win rate | 25.00% |
| Total return | −3.45% |
| Avg return/trade | −0.86% |

Reported as-is: a small, directionally unfavorable result. Four trades cannot
confirm or refute the strategy's edge on their own (by the same MDE logic as
§2.4), but this is the only genuinely prospective (not merely
held-out-historical) evidence available for this exact rule set, and it does
not add reassurance.

**8-year backfill integrity check.** The frozen pipeline was run against data
extended back to 2018-01-01, to test whether ~4 additional years of
indicator warm-up (MACD's EMAs and the static KDJ are recursive, with
theoretically unbounded memory) would change the locked 2022–2026 baseline.
Result: **PASS** — all 27 locked trades matched by entry timestamp, maximum
PnL difference **0.0000000000%** (exact) between the original and extended
runs.

**Formulation-period comparison** (2018–2022 is the period the strategy's
rule *structure* was originally formulated against — explicitly **not**
out-of-sample):

| Window | N | Win rate | Total return | Avg/trade | Binomial $p$ (1-sided) |
|---|---|---|---|---|---|
| 2018-01 → 2022-01 (formulation, not OOS) | 25 | 60.00% | +21.82% | +0.87% | 0.2122 |
| 2022-01 → 2026-01 (locked baseline) | 27 | 70.37% | +30.31% | +1.12% | 0.0261 |
| Combined 2018–2026 (mixed provenance) | 56 | 62.50% | +48.68% | — | 0.0407 |

The combined-window row must never be cited alone: roughly half of it is
drawn from the formulation period, so its $p=0.0407$ partly reflects
performance on data the rules could see during development. Notably, the
strategy performs *worse* on its own formulation-period data than on the
reported window — the opposite of what naive overfitting to that period
would predict, and consistent with the disclosed account (§3) that only the
minimum-stop-distance filter was adjusted after formulation, not the rule
structure.

### 2.9 Ablation studies

**Three-arm comparison** (`docs/ablation_study_indicators_only.md`,
`docs/ablation_unconfounding_analysis.md` — cited as committed disclosure;
see reproducibility caveat below):

| Arm | Entry | Risk placement | N | Win rate | Total return |
|---|---|---|---|---|---|
| OB-gated baseline | OB touch + MACD/KDJ/ATR | OB boundary | 27 | 70.37% | +30.31% |
| Indicators-only (flat-ATR stop) | MACD/KDJ/ATR only | Close − 1.5×ATR | 140 | 60.00% | −14.63% |
| Indicators-only (swing-pivot stop) | MACD/KDJ/ATR only | 5-bar swing pivot ± 0.5×ATR | 138 | 55.07% | −25.50% |

**Un-confounding entry selection from risk placement:** equipping the
indicators-only arm with a *structural* swing-anchored stop (arm 3) rather
than a flat-ATR offset (arm 2) changed candidate count negligibly (138 vs.
140, −1.4%) and did **not** rescue performance (55.07% vs. 60.00% win rate;
−25.50% vs. −14.63% return) — evidence that the un-gated arms' underperformance
is driven by **entry selection**, not stop-placement mechanics. A bootstrap
resample of $n=27$ from the 138-trade indicators-only pool ($B=2000$) gives
median avg-return −0.17% with 95% range [−1.17%, +0.70%]; the OB-gated
baseline's +1.12% sits at empirical $p=0.0020$ against that null — i.e., the
OB-gated average return is not explainable as a lucky 27-trade draw from the
un-gated pool, even though the corresponding win-rate bootstrap is weaker
(empirical $p\approx0.07$–$0.17$ depending on which un-gated arm is used as
the resampling pool).

**Reproducibility gap (disclose, do not paper over):** no committed script in
this repository currently reproduces the 140/138-trade figures from scratch
— the originating script was never committed. A best-effort reconstruction
attempted in this repository reproduces the trade **counts** exactly (140,
138) but its win rate diverges by roughly 11–13 percentage points from the
published 60.00%/55.07% figures, meaning the underlying per-trade outcomes in
the reconstruction are **not** the same trades the paper reports. Cite the
ablation figures as a committed, disclosed result — not as something this
repository can currently re-derive independently.

---

## 3. Discussion

**What the evidence supports.** The full-sample return effect is
directionally robust: the percentile bootstrap 95% CI on total return,
[+5.99%, +54.99%], excludes zero even though it is wide, and 99.25% of
10,000 resamples were positive. The win-rate significance claim, by
contrast, is **fragile** — it survives the exchange's published taker fee
alone (still $p=0.0261$) but flips to non-significant ($p=0.1239$) under a
realistic combined fee-and-slippage assumption. Both facts should be reported
together: the *return-magnitude* story is comparatively robust to
transaction costs (mathematically invariant for the Welch tests, since a flat
per-trade drag doesn't change between-group differences), while the
*win-rate* story is not. A paper that reports only the gross $p=0.026$
figure without this sensitivity result overstates what the data supports.

**What the evidence does not support.** None of the five orthogonal OB
quality criteria reach significance in either Fisher's or Welch's test — but
the MDE analysis (§2.4) shows every observed subgroup gap is 3–10× smaller
than what this sample size could reliably detect at 80% power. The correct
paper language is "insufficient power to distinguish quality-criterion
effects at this sample size," not "no significant difference" or "quality
criteria carry no signal" — the latter overclaims what a non-significant
result at $n=27$, split into subgroups as small as $n=4$, can support. This
power limitation is specific to the criterion-level subgroup comparisons; it
does not extend to the full-sample return finding, which has its own,
better-powered bootstrap evidence.

Two other claims in the current draft should not be treated as settled: the
**"190 total qualifying indicator signals"** denominator (behind the
25/27 = 92.6% OB/indicator-signal coincidence claim) was derived under the
indicators-only ablation's own 1.5×ATR entry-anchored stop, not the OB-gated
strategy's actual risk rules — the two populations are filtered differently,
and this should be marked unresolved rather than cited as a settled
denominator. And the **ablation A/B figures**, while consistent with every
other disclosed number in this repository, cannot currently be independently
reproduced from a committed script (§2.9) — a limitation to state plainly if
the paper leans on those figures for its central "the OB gate matters" claim.
The un-confounding follow-up (arm 3, swing-anchored stop) is the stronger,
independently-reproducible piece of evidence for that same claim, since it
isolates entry selection from stop-placement mechanics and still shows the
un-gated arm losing money.

**Self-correction as a feature of the methodology, not a defect in the
result.** Three bugs were found and fixed over the course of this project,
and one of them (the lookahead fix, §1.8 bug #3) changed a
significance conclusion at the q≥1 threshold. For a paper defense, this
history is worth presenting explicitly as evidence of a working audit
process — dedicated no-lookahead proofs, a golden-master regression harness,
and an independently implemented cross-check dashboard — rather than omitted
as though the numbers were always exactly as currently reported. A panel is
more likely to trust a result that shows its own correction history than one
presented as having been correct from the start. A later, separate audit
pass caught two further reporting-layer errors — a bootstrap-CI resample-count
mismatch between this paper and the interactive website, and an overstated
correlation $p$-value (§1.8) — the same self-auditing discipline applied to
the paper's own numbers, not only to the code.

**Regime dependence.** The strategy's edge is concentrated in bull-trending
conditions (85.71% win rate under both the calendar and drawdown regime
methods) and weaker or negative in choppy/bear conditions under at least one
of the two classification methods. This should temper any claim of
regime-general reliability: the reported 2022–2026 window happens to include
a substantial bull phase (2024–25), and the strategy's aggregate performance
depends on that phase's contribution (83.3% of total return share under the
calendar method). The three most-concentrated winning trades are not all
drawn from that one regime, which is a modest robustness point in the
strategy's favor, but it does not fully offset the broader regime-concentration
finding.

**Positioning against the benchmark.** The complementary-sleeve framing
(§2.6) is the defensible way to present the BTC comparison: monotonic
Sharpe/Sortino/drawdown improvement as strategy allocation rises, achieved
while the strategy sleeve is invested only 2.63% of the time. This should
not be presented as the strategy "beating" BTC buy-and-hold outright, since
the exposure profiles are not comparable.

---

## 4. Conclusion

Over BTC/USDT 4-hour candles, January 2022–January 2026, a rule-based
strategy gating MACD/KDJ momentum signals through SMC Order Block structural
zones produced 27 trades, a 70.37% win rate, and +30.31% total net return,
departing from a 50% zero-edge null at $p=0.026$ (one-sided exact binomial).
This headline result is **directionally robust** under a nonparametric
bootstrap of its own trade distribution (95% CI excludes zero) but **not
robust** to realistic transaction-cost assumptions for the win-rate
significance claim specifically ($p=0.026\to0.124$ under a 0.20% round-trip
drag), while the associated return-magnitude (Welch) tests are mathematically
unaffected by that same drag. An ablation comparison shows the OB structural
gate materially improves outcomes over ungated indicator signals (and this
improvement survives disentangling entry selection from stop-placement
mechanics), though the exact published ablation trade-level figures cannot
currently be reproduced from a committed script in this repository. None of
five hypothesized OB quality criteria show a statistically detectable
relationship to trade outcome at this sample size — but the study is
underpowered to detect effects of the size actually observed, not evidence
that no such effect exists. A genuinely prospective, out-of-sample test on
data postdating every code commit (4 trades, 2026-01 to 2026-07) was
directionally unfavorable and is reported as such; an 8-year backfill
confirmed the reported window's results are not an artifact of insufficient
indicator warm-up.

**What this study establishes:** a historically observed, directionally
robust return edge for this specific rule set on this specific window, with
its win-rate significance shown to be cost-sensitive and its regime
concentration made explicit, obtained through a process with a disclosed,
audited self-correction history.

**What this study does not establish:** that any individual OB quality
criterion predicts outcome (underpowered, not disproven); that the strategy
generalizes across market regimes evenly; that the 190-signal denominator or
the exact ablation trade-level figures are independently reproducible from
this repository as currently committed; or that the strategy's edge persists
prospectively (the only prospective evidence available, though too small to
be conclusive, was unfavorable).

**Future work:** (1) resolve the two disclosed open items (the 190-signal
denominator's population mismatch; the ablation-script reproducibility gap)
by committing a script that reproduces the ablation trade log from current
code, or by explicitly re-deriving the 190 figure under the OB-gated
strategy's own risk rules; (2) continue accumulating genuinely prospective
out-of-sample trades as time passes, since the trade frequency (~0.56/month)
means statistical power there will only build slowly; (3) consider a
lower-timeframe or multi-asset extension purely to increase $n$ for the
criterion-level power analysis, without altering this window's locked
results.

---

## 5. Appendix: specific paper-text corrections pending (checklist)

Reproduced from `artifacts/paper_sync_report.md`'s live cross-check — check
each by eye against the current draft, since the draft itself lives outside
this repository:

1. **Dataset size.** Draft should say **8,767 bars**, not 8,760 (§1.1).
2. **FVG correction narrative.** If the draft's account of the FVG fix stops
   at "FVG registered true for 47.6%," that describes the three-candle
   definition fix only (Bug #2). The subsequent no-lookahead fix (Bug #3)
   further corrected this to **33.2% (253/761)**. Disclose both steps if
   either is mentioned.
3. **Welch's t-test p-value range.** Should read **"0.38–0.78,"** not
   "0.38–0.90" (only FVG's value moved under the Bug #3 fix, 0.8956→0.5996;
   LargeBar's 0.7751 is now the max). Resolve the Displacement-inclusion
   wording tension noted in §2.3 before finalizing this sentence.
4. **"190 total qualifying indicator signals."** Open, unresolved — do not
   cite as a settled denominator for the 92.6% coincidence claim (§3).
5. **Ablation A/B reproducibility.** These figures match every other
   disclosed source in this repository but are not reproducible from a
   currently-committed script. Disclose this gap if the paper cites a
   reconstruction or reproduction claim for these numbers.
6. **Fisher's exact test citation.** Both Fisher's and Welch's tests are now
   independently reproducible two ways (a CLI script and the dashboard's
   Stats tab, client-side). If the Results section currently cites only
   Welch's t-test p-values, consider citing the Fisher's exact p-values
   alongside them (§2.3) — none cross $p=0.05$, consistent with Welch.
7. **MDE/power figures.** Available now (§2.4) as a concrete replacement for
   any qualitative "n=27 is small" caveat in the Limitations section.
8. **Own-trades bootstrap CI.** Available now (§2.5) for the Results
   section's return-concentration discussion.
