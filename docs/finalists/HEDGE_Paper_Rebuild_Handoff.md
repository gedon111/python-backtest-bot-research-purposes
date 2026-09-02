# HEDGE Research Paper — Build Specification

Build a complete ISEF research paper from this document. Everything needed is
here; no external files or repository access are required. Every figure in this
document has been recomputed and verified — reproduce them exactly as written,
to the decimal places shown.

---

## 1. Paper identity

**Title:** HEDGE: Hedging Erratic-market Dynamics: A Dynamic-KDJ, MACD, and SMC
Order Block Strategy Backtested Against DCA on Bitcoin

**Institution:** Rodolfo V. Feliciano Memorial High School, San Pedro II,
Magalang, Pampanga

**Authors:** Pasok, Charles Gideon T.; Esguerra, Eireen Joy U.; Valerio, Euan
Deign D.; Galang, Blessie M.

**Research II Teacher:** Aleah G. Sabado, MAEd – Physical Science, LPT

**Keywords:** Bitcoin, algorithmic trading, backtesting, dollar-cost averaging,
Smart Money Concepts, technical analysis

**Style:** APA 7th edition. Plain, precise academic prose. Define every
technical term at first use — the audience is a science-fair panel, not a
quantitative-finance audience. Prefer short declarative sentences.

---

## 2. Statistical scope

The paper reports exactly six quantities. No others.

| Quantity | Source | Routine |
| :---- | :---- | :---- |
| Exact binomial test on win rate | SciPy | `scipy.stats.binomtest` |
| Pearson's correlation and its p-value | SciPy | `scipy.stats.pearsonr` |
| Spearman's correlation and its p-value | SciPy | `scipy.stats.spearmanr` |
| Bootstrap confidence interval on total return | Custom | Percentile bootstrap, Formula 1 |
| Maximum drawdown | Custom | Running-peak decline, Formula 2 |
| Sharpe and Sortino ratios | Custom | Annualized risk-adjusted return, Formula 3 |

Three are unmodified SciPy calls; three are formulas written for this study.
Sharpe, Sortino, and maximum drawdown are **descriptive performance metrics,
not hypothesis tests** — the paper must never attach a p-value to them.

Formula numbering runs 1, 2, 3. There is no Formula 4.

---

## 3. Structure to produce

```
Abstract
Introduction
  Rationale
  Statement of the Problem
    Hypotheses
Framework
  A. Research Design
  B. Materials and Sources
  C. Variables
  D. Strategy Formulas
  E. Portfolio Construction and Contribution Schedule
  F. Data Analysis
  G. Verification and Corrections
Findings
  Overall Strategy Performance
  Bootstrap Confidence Interval
  Regime Breakdown and Correlation
  Strategy Versus Dollar-Cost Averaging and Lump-Sum Buy-and-Hold
    The Blended-Sleeve Model
    Head-to-Head at Equal Starting Capital
  Transaction-Cost Sensitivity
  Out-of-Sample and Extended-History Validation
Conclusions
  Discussion of Findings
  Limitations
  Summary and Conclusion
References
Appendix A — Statistical Provenance of Every Reported Number
Appendix B — Source Form of Every Formula Written for This Study
Appendix C — Statement on Software Authorship
Appendix D — Complete Trade Log for the Primary Window
```

---

## 4. Research questions and hypotheses

**RQ1.** How effectively does the combined MACD, KDJ, ATR, and Smart Money
Concepts strategy predict short-term Bitcoin price movements, as measured by
win rate, total net return, and average return per trade?

**RQ2.** How does the strategy compare against the two passive alternatives an
ordinary participant would realistically use — weekly dollar-cost averaging
into Bitcoin, and a single lump-sum purchase held to the end of the window —
when all three are started from identical capital and measured on total return,
Sharpe ratio, Sortino ratio, maximum drawdown, and time in market?

**RQ3.** Does directing a share of new weekly contributions into the strategy
improve the risk-adjusted profile of an otherwise ordinary Bitcoin
dollar-cost-averaging plan, and if so, how does that improvement behave as the
allocated share rises?

**H₀₁:** The combined strategy does not produce a statistically significant win
rate above 50% on BTC/USDT 4-hour data across all market conditions over a
broad temporal scope.

**H₁₁:** The combined strategy produces a statistically significant win rate
above 50% on BTC/USDT 4-hour data across all market conditions over a broad
temporal scope.

Tested with a one-sided exact binomial test.

**H₀₂:** Blending a strategy allocation into a Bitcoin dollar-cost-averaging
plan does not improve that plan's risk-adjusted profile, as measured by the
Sharpe ratio, the Sortino ratio, and maximum drawdown, relative to a plan held
entirely in dollar-cost-averaged Bitcoin.

**H₁₂:** Blending a strategy allocation into a Bitcoin dollar-cost-averaging
plan improves that plan's risk-adjusted profile on all three of those measures
relative to a plan held entirely in dollar-cost-averaged Bitcoin.

The second pair is resolved **descriptively**, by whether all three measures
move in the predicted direction consistently as the allocated share rises. The
paper must state why: the Sharpe ratio, the Sortino ratio, and maximum drawdown
are each computed from a single realized price path, so each is one observation
rather than a sample, and there is no sampling distribution behind it against
which a p-value could legitimately be formed. This is a weaker standard than a
significance test and must be treated as such throughout — it is evidence about
one historical window, not an inferential claim about future ones.

---

## 5. Research design

Retrospective quantitative backtesting design. A rule-based strategy
integrating MACD, KDJ, ATR, and Smart Money Concepts Order Block detection is
applied candle by candle to historical BTC/USDT 4-hour data, simulating how the
strategy would have traded in real time. The simulation processes each candle in
order and is never permitted to read a candle that had not yet closed at the
moment a decision was made.

The study proceeds in two stages. First, the full strategy is backtested.
Second, every surviving result is stress-tested against transaction costs,
against passive benchmarks, and against data that postdates the source code.

This is a historical backtest, not a live or production trading system. No
parameter was fitted, swept, or optimized against the outcome being measured.

**Separation of the formulation period from the reported window.** The rules,
parameters, and thresholds were settled by visual inspection of BTC/USDT charts
covering January 2018 through January 2022, drawing on prior trading
experience. That period was examined by eye only. No search procedure,
parameter sweep, or optimizer was ever run against it, and no value was
adjusted to improve a measured outcome. The primary findings come from January
2022 through January 2026. A third and stricter test uses January 2026 through
July 2026, a period that postdates every change to the source code.

Two limits on this separation must be stated explicitly rather than left to be
inferred. First, the formulation period was inspected visually, not fitted
numerically, so the rules carry whatever biases visual pattern recognition
introduces, and the strength of the separation cannot be quantified the way a
held-out split in a machine-learning study can. Second, the 2022 to 2026 window
is out-of-sample with respect to *rule formulation* but not with respect to
*code auditing*, because the implementation error reported in Section G was
found and corrected while examining that same window. Only the January 2026
through July 2026 test is out-of-sample in both senses.

---

## 6. Materials and sources

**BTC/USDT 4-hour candlestick data (Binance, via API).** Open, high, low,
close, and volume retrieved from the Binance `get_klines` endpoint for the
BTCUSDT symbol at 4-hour resolution, paginated in batches of 1,000 candles. Raw
millisecond timestamps were converted to datetimes and shifted by a fixed
positive eight hours, so the stored dataset's opening timestamp is expressed in
UTC+8 rather than raw UTC. Every timestamp quoted in the paper follows that
convention.

The dataset spans **2022-01-01 08:00:00 through 2026-01-01 08:00:00**. That
interval covers exactly **1,461 calendar days** (365 + 365 + 366 + 365, where
the 366 accounts for the 2024 leap day). At six four-hour candles per day,
1,461 × 6 = **8,766 candle intervals**. Because the final candle is stored as a
row rather than used only as an exclusive upper boundary, the stored row count
is 8,766 + 1 = **8,767 rows**. A gap check confirmed that the set of unique
time differences between consecutive candles across all 8,767 rows contains the
single value four hours, with no duplicate timestamps, so no candle is missing.

The 2018 to 2022 formulation window holds **8,750 rows** against the 8,767
expected under the same counting convention — a shortfall of seventeen candles
across eight separate outages on the exchange's side, the largest a gap of
seven consecutive candles. Disclose this. It does not affect any figure reported
from the primary window, which is verified complete.

**Python 3 environment.** pandas, numpy, python-binance, gspread with
oauth2client.

**SciPy.** A free, publicly available, open-source scientific computing library
for Python, widely used for statistical computation in published research
(Virtanen et al., 2020). Every hypothesis test in this paper whose formula is a
standard textbook test is a direct, unmodified call into `scipy.stats`.

**Google Sheets and SQL database.** Simulation results were exported to Google
Sheets and to a local SQL database, including per-trade records.

**LuxAlgo Smart Money Concepts indicator (LuxAlgo, 2022).** Order Block
detection is a Python translation of the LuxAlgo Smart Money Concepts indicator
for TradingView, using a 50-candle swing pivot lookback and a 5-candle internal
pivot lookback.

**Average True Range (Wilder, 1978).** True range follows Wilder's definition.
Both ATR windows are computed as a simple rolling mean rather than Wilder's
original exponential smoothing. The executed computation is a plain rolling
mean, and that is what the paper reports.

**Web-based verification dashboard.** A separately written JavaScript dashboard
recomputes the indicator and entry-condition layer in the browser from trade
data, as a cross-check against a second, independent codebase. Its scope is
deliberately limited: it does not independently detect Order Blocks, Fair Value
Gaps, or liquidity sweeps, and it never imports any value from the Python
analysis. That independence is what makes the cross-check meaningful, and it is
the reason the two bootstrap intervals in the Findings are reported separately
rather than reconciled into one number.

---

## 7. Variables

**Independent variable.** The capital-allocation approach applied to one
identical stretch of price history. Six levels: the Order-Block-gated strategy
traded on its own; weekly dollar-cost averaging into Bitcoin; a single lump-sum
purchase held to the end of the window; and three blended portfolios directing
10%, 20%, and 30% of new weekly contributions into the strategy with the
remainder dollar-cost averaged. The 0% blend is the same arm as pure weekly
dollar-cost averaging and is reported as the blended model's baseline row.

**Dependent variables.** For the strategy's own trade record: win rate (the
percentage of closed trades with a positive net return); total net return;
average return per trade; and return concentration (the share of total return
attributable to a small subgroup of trades). For the comparison against passive
alternatives: total return and final capital from a fixed starting amount, the
annualized Sharpe ratio, the annualized Sortino ratio, maximum drawdown, and
time in market (the share of candles on which the arm held an open position).

**Controlled variables.** Trading pair, candlestick interval, and backtest
window, identical for every arm; the MACD, KDJ, and ATR parameters, the exit
rules, and the minimum reward-to-risk requirement, identical wherever the
strategy appears; the starting capital of $10,000, identical for every arm in
the head-to-head comparison; the contribution schedule of 210 equal weekly
contributions, identical for the dollar-cost-averaging arm and for every
blended portfolio; and the transaction-cost assumption, applied at the same rate
to every arm within a given comparison. All strategy parameters were fixed
before backtesting and none was tuned against the reported dataset.

---

## 8. Strategy formulas

Throughout, $C_t$, $H_t$, $L_t$, and $V_t$ denote the closing price, high, low,
and traded volume of candle $t$.

**MACD (12, 26, 9).** Computed causally — each value uses only past and present
candles.

$$EMA_{12}(t) = C_t \cdot \tfrac{2}{13} + EMA_{12}(t-1)\cdot\left(1-\tfrac{2}{13}\right)$$
$$EMA_{26}(t) = C_t \cdot \tfrac{2}{27} + EMA_{26}(t-1)\cdot\left(1-\tfrac{2}{27}\right)$$
$$MACD_t = EMA_{12}(t) - EMA_{26}(t)$$
$$Signal_t = MACD_t \cdot \tfrac{2}{10} + Signal_{t-1}\cdot\left(1-\tfrac{2}{10}\right)$$
$$Hist_t = MACD_t - Signal_t$$

**ATR (14) and ATR (200).**

$$TR_t = \max\left(H_t - L_t,\ |H_t - C_{t-1}|,\ |L_t - C_{t-1}|\right)$$
$$ATR_{14}(t) = \tfrac{1}{14}\sum_{i=0}^{13} TR_{t-i}, \qquad ATR_{200}(t) = \tfrac{1}{200}\sum_{i=0}^{199} TR_{t-i}$$

$ATR_{14}$ drives stop-loss distance, the minimum-stop filter, the trailing
exit, and the ATR-move exit. $ATR_{200}$ serves as the volatility baseline for
the market-condition filter and for two of the five Order Block quality
criteria (Displacement and Large Origin Candle).

**KDJ (9, 3, 3), the fixed entry-gating series.** Computed once over the whole
dataset; does not vary from trade to trade.

$$RSV_t = \frac{C_t - \min_{i\in[0,8]} L_{t-i}}{\max_{i\in[0,8]} H_{t-i} - \min_{i\in[0,8]} L_{t-i}} \times 100$$
$$K_t = \tfrac{2}{3}K_{t-1} + \tfrac{1}{3}RSV_t, \qquad D_t = \tfrac{2}{3}D_{t-1} + \tfrac{1}{3}K_t, \qquad J_t = 3K_t - 2D_t$$

Every $K$, $D$, and $J$ reference inside the entry conditions reads this fixed
series at the current candle.

**KDJ, the adaptive post-entry exit series.** A second system that exists only
to time one exit signal after a trade is already open. It never shares state
with the series above. At entry its state is seeded from the fixed series' $K$
and $D$ values at the entry candle, and its window length is set once and held
for the life of that trade:

$$w = \max\left(1,\ \textit{entry\_idx} - \textit{ob\_bar}\right)$$

On each later candle a Raw Stochastic Value is recomputed over a rolling window
of length $w$, and $K$ and $D$ are updated with the same one-third smoothing:

$$RSV_{custom} = \frac{C_{cur} - \min_{j\in[cur-w+1,\,cur]} L_j}{\max_{j\in[cur-w+1,\,cur]} H_j - \min_{j\in[cur-w+1,\,cur]} L_j}\times 100$$
$$K_{cur} = \tfrac{2}{3}K_{prev} + \tfrac{1}{3}RSV_{custom}, \qquad D_{cur} = \tfrac{2}{3}D_{prev} + \tfrac{1}{3}K_{cur}$$

**Verified:** across the 27 trades, $w$ ranged from **14 to 439** candles, with
a median of **74**. It was never as short as two candles. Only $w$ varies
between trades; the entry-gating KDJ never does.

The paper must state clearly that these are two separate, intentional systems,
because confusing them is the most common misunderstanding about how the
strategy works.

**Order Block detection.** Two independent structural passes run over the same
price series, one with a 5-candle pivot lookback for internal structure and one
with a 50-candle lookback for swing structure. In each pass a candle
$pb = i - size$ is confirmed as a pivot high only by strict right-side
comparison, $H_{pb} > \max(H_{pb+1..i})$, with the mirror condition for a pivot
low. No future candle is read in that comparison. A break of structure is
flagged when price closes across a tracked pivot level, and an Order Block is
created from the price segment between the pivot candle and the crossover
candle $i$. Two candle indices are kept deliberately distinct: `ob_idx` is the
candle holding the Order Block's own extreme candle, while `created_at` is the
candle on which the breakout candle closes. An Order Block cannot trigger an
entry until strictly after `created_at`. Order Blocks expire after 500 candles
of age, or once price closes back through their boundary.

**Order Block quality criteria.** Each detected Order Block is scored on five
independently evaluated true-or-false criteria. Their sum, 0 to 5, is used only
as a cumulative entry-eligibility threshold. The reported baseline uses a
threshold of 0, so no Order Block is excluded by score.

1. **Displacement:** within the candles immediately following the Order Block's
   own candle, and bounded at that Order Block's own confirmation candle, a
   candle body move of at least $1.5 \times ATR_{200}$, measured at the Order
   Block's candle, occurs in the Order Block's direction.
2. **Large Origin Candle:** $H_i - L_i \geq ATR_{200}(i)$.
3. **Fair Value Gap:** a three-candle price imbalance exists within a bounded
   window following the Order Block's candle. For a demand block the condition
   is $L_{j+2} > H_j$; for a supply block the mirror condition holds.
4. **Liquidity Sweep:** $L_i \leq \min(L)$ over the prior ten candles for a
   demand block, or $H_i \geq \max(H)$ over the prior ten candles for a supply
   block.
5. **Volume Expansion:** $V_i \geq 1.25 \times \text{mean}(V)$ over the prior
   twenty candles, or the candle body exceeds 60% of the candle's own
   high-to-low range.

Both the Displacement and the Fair Value Gap search windows are bounded at the
Order Block's own confirmation candle.

**Table 1 — Fixed Strategy Parameters**

| Parameter | Value |
| :---- | :---- |
| Minimum stop distance | 0.015, meaning 1.5% of entry price |
| KDJ $J$ cap, long entries | 60.0 |
| KDJ $K$ cap, long entries | 50.0 |
| KDJ $K$ floor, short entries | 70.0 |
| KDJ $J$ cap, short entries | 100.0 |
| ATR-move take-profit multiple | 1.8 |
| Breakeven-stop trigger multiple | 2.0 |
| Minimum reward-to-risk ratio | 1.5 |
| Order Block expiry | 500 candles |
| Internal pivot lookback | 5 candles |
| Swing pivot lookback | 50 candles |

*Note.* Every value was set during the 2018 to 2022 formulation period and was
never adjusted afterwards.

**Entry conditions.** A long entry requires all six conditions in Figure 4 to
hold at the same candle close. A short entry is the mirror condition against a
supply Order Block, with $K > 70$ and $J \leq 100$.

**Exit conditions.** Exits are evaluated on every candle in the fixed priority
order shown in Figure 5. The first condition satisfied triggers the exit, and
the remaining conditions are not evaluated for that candle. The four exit types
are the hard stop-loss, the ATR-move take-profit, the trailing exit, and the
KDJ-reset exit.

---

## 9. Portfolio construction and contribution schedule

This section is **required** and must appear in the Framework. Its purpose is
to let a reader recompute Tables 6 through 9 by hand. State all of it.

**Shared timing convention.** A contribution lands on the **first bar of every
ISO calendar week**, and is transacted at that bar's **closing** price. The same
convention governs both the blended-sleeve model and the head-to-head
dollar-cost-averaging arm, so the two cannot drift apart. The primary window,
2022-01-01 08:00 through 2026-01-01 08:00 (UTC+8), contains **210** such weeks.
The 2018 to 2022 formulation window contains **209**.

**Head-to-head arms — each starts from $10,000 (Tables 7, 8, 9).**

- **Strategy arm.** The full $10,000 sits in cash from the window's first bar
  and compounds multiplicatively **only at each of the 27 trade exit bars**, by
  that trade's percentage return. Full notional is committed on each trade;
  positions are unlevered and never partially sized. Between trades the arm
  holds cash and earns nothing. Returns are measured per 4-hour bar and
  annualized with $m = 6 \times 365.25 = 2{,}191.5$.
- **Weekly dollar-cost-averaging arm.** $10{,}000 \div 210 = \mathbf{\$47.6190}$
  per week (formulation window: $10{,}000 \div 209 = \$47.8469$), buying at each
  contribution bar's close. Value at any bar is accumulated units × current
  close. Period returns are measured **only at contribution bars** and are net
  of that week's own contribution:
  $$r_k = \frac{V_k - C_k}{V_{k-1}} - 1$$
  so injected capital is never mistaken for investment return. Annualized with
  $m = 52$.
- **Lump-sum arm.** The full $10,000 is deployed at the window's **first bar's
  opening** price — note that this differs from the dollar-cost-averaging arm,
  which transacts at the close — and held unchanged to the last bar's close.
  Per-4-hour-bar returns, annualized with $m = 2{,}191.5$.
- **Net-of-cost variants (Table 8).** The strategy arm is charged a **0.20%
  round-trip** drag subtracted from each trade's percentage return. The two
  passive arms are charged a **0.10% one-sided** buy-price markup, since they
  buy and hold rather than round-tripping.

**Blended-sleeve model (Table 6).**

- Contributions are **1.0 relative unit per ISO week across 210 weeks**, not
  dollars. State this explicitly — Table 6 therefore carries no dollar column,
  and a reader will otherwise assume the $10,000 figure used elsewhere.
- The 100% / 0% baseline: the full 1.0 unit buys Bitcoin at that bar's close.
- At a strategy share $f \in \{0.10, 0.20, 0.30\}$: $(1-f)$ buys Bitcoin units,
  and $f$ is added to a strategy sleeve held **as cash**. That sleeve compounds
  by each trade's percentage return at the trade's exit bar. The sleeve is never
  rebalanced back into Bitcoin.
- Portfolio value at bar $i$ = (Bitcoin units × close at $i$) + strategy sleeve
  cash.
- Period returns are measured at the 210 contribution bars, net of that week's
  own contribution, using the same formula as the dollar-cost-averaging arm.
  Annualized with $m = 52$.
- Maximum drawdown in Table 6 is the **principal-inclusive** percentage
  drawdown computed on the portfolio value series at contribution bars.

**Reconciliation the paper must state.** Table 6's 100% / 0% row and Table 7's
Weekly DCA row report the same Sharpe (0.556), Sortino (0.886), and maximum
drawdown (−27.85%). They agree because both use this identical weekly
convention. Stating that the two tables meet at their shared point is a free
consistency check for the reader.

---

## 10. Data analysis

**Exploratory data analysis.** The primary approach: descriptive statistics,
distributional summaries, and tabular comparison used to uncover patterns
before drawing conclusions (Tukey, 1977). The approach suits this case because
the backtest output is a finite, fully observed set of trade records with no
missing values.

**Descriptive statistics.** Trade count, win rate, net return, average return,
and standard deviation.

### Statistical software

All statistical computation was performed in Python 3 using SciPy, a free and
publicly available open-source library (Virtanen et al., 2020). SciPy is
maintained by a large public community, its source code is open to inspection,
and its statistical routines are the same ones used in a great deal of
published quantitative research. Using it means the standard hypothesis tests
in this paper are not this study's own implementations, which removes a whole
category of possible arithmetic error.

Three of the six quantities reported are direct, unmodified calls into SciPy.
The remaining three are formulas written for this study, either because no
single library function computes the quantity or because the quantity is a
resampling procedure defined by this study's own design. Reproduce the Table in
§2 above as **Table 2**, captioned *Division Between SciPy Library Calls and
Formulas Written for This Study*.

### Tests computed by SciPy

**One-sided exact binomial test.** With $n$ closed trades and $w$ winners,
under a null win probability of 0.5:

$$p_{\text{one-sided}} = \sum_{k=w}^{n}\binom{n}{k}(0.5)^{k}(0.5)^{n-k} = \sum_{k=w}^{n}\binom{n}{k}(0.5)^{n}$$

A p-value is the probability of seeing a result at least this strong if the
strategy actually had no edge at all. The one-sided form was chosen because the
hypothesis is directional: it predicts a win rate above 50%, not merely one
different from 50% in either direction. Two-sided values are reported for
reference.

**Correlation.** Pearson's $r$ and Spearman's $\rho$ were computed between how
long a trade was held, measured in candles, and its percentage return. Both
measure whether two quantities move together, with Pearson assuming a
straight-line relationship and Spearman assuming only a consistent direction.

### Formulas written for this study

**Formula 1. Percentile bootstrap confidence interval.** Let
$r_1, r_2, \ldots, r_n$ be the observed percentage returns of the $n$ trades.
For each of $B$ repetitions, draw $n$ returns from that set at random *with
replacement* — the same trade may be drawn more than once — and record the
resample's total and mean:

$$T^{(b)} = \sum_{i=1}^{n} r_i^{*(b)}, \qquad \bar{T}^{(b)} = \frac{1}{n}\sum_{i=1}^{n} r_i^{*(b)}, \qquad b = 1,2,\ldots,B$$

The 95% confidence interval is the 2.5th and 97.5th percentiles of the $B$
recorded values:

$$CI_{95\%} = \left[\,Q_{2.5}\left(T^{(1)},\ldots,T^{(B)}\right),\; Q_{97.5}\left(T^{(1)},\ldots,T^{(B)}\right)\,\right]$$

*Why it is designed this way.* Twenty-seven trades is too few, and too skewed by
a handful of large winners, to safely assume that a textbook normal-theory
interval of the form mean plus or minus 1.96 standard errors is valid. The
bootstrap makes no assumption about the shape of the distribution; it uses the
data's own actual shape (Efron & Tibshirani, 1993). Drawing *with* replacement
rather than reshuffling is what allows a resample's total to differ from the
original at all. Drawing exactly $n$ values follows Efron's prescription, so
that the variation between resamples reflects genuine sampling uncertainty
rather than an artifact of a changed sample size. Parameters: $B = 10{,}000$,
$n = 27$, fixed random seed 42, so the figure is exactly reproducible.

*Disclosed simplification.* This is the plain percentile bootstrap, not the
bias-corrected and accelerated (BCa) variant, which adjusts the percentile
cutoffs for skewness in the resampling distribution. The plain form is the
standard textbook procedure and is disclosed here as a deliberate
simplification rather than presented as the only option.

**Formula 2. Maximum drawdown.** Let $E_t$ be the value of an equity curve at
time $t$. Define the running peak, the percentage decline from that peak, and
the worst such decline:

$$P_t = \max_{u \leq t} E_u, \qquad DD_t = \frac{E_t - P_t}{P_t}\times 100, \qquad MDD = \min_t DD_t$$

*Why it is designed this way.* Drawdown is expressed as a percentage rather than
in dollars so that the strategy, the dollar-cost-averaging arm, and the
buy-and-hold arm can be compared directly, even though their equity curves have
very different shapes from the same $10,000 starting point. Tracking the
*running* peak, rather than comparing only the final value to the all-time
high, is what catches a fall that happens partway through the window and later
recovers. The strategy's worst drawdown of −6.46% occurs mid-window and would
be invisible to a formula that only compared the end value to the highest value.

**Formula 3. Sharpe and Sortino ratios.** Let $R_1, R_2, \ldots, R_N$ be an
arm's per-period returns, $\bar{R}$ their mean, $s_R$ their standard deviation,
and $m$ the number of periods in a year for that arm's own reporting frequency:

$$SR = \frac{\bar{R}}{s_R}\sqrt{m}$$
$$\sigma_d = \sqrt{\frac{1}{N}\sum_{t=1}^{N}\left[\min(R_t, 0)\right]^2}, \qquad SoR = \frac{\bar{R}}{\sigma_d}\sqrt{m}$$

*Why it is designed this way.* The Sharpe ratio measures return earned per unit
of overall variability, so a higher value means a smoother ride for the same
return (Sharpe, 1994). The Sortino ratio counts only downward movement as risk,
on the reasoning that an investor does not object to upward surprises (Sortino
& van der Meer, 1991). The downside deviation $\sigma_d$ divides by $N$, the
count of *all* periods, not by the count of losing periods only. This follows
the original 1991 definition. A widely circulated online tutorial divides
instead by the number of losing periods, which inflates the resulting ratio;
this study deliberately does not follow that shortcut.

*Disclosed assumption.* Both ratios assume a risk-free rate of zero, and the
Sortino ratio assumes a minimum acceptable return of zero. The code uses raw
per-period returns directly rather than subtracting a benchmark rate first.
Written in full, the general Sharpe formula is

$$SR_{general} = \frac{E[R_a - R_f]}{\sigma_a}\sqrt{m}$$

and this study sets $R_f = 0$. This is defensible for a cryptocurrency strategy
with no explicit funding-rate component modelled, and every arm is treated
identically, so the ranking between arms is unaffected. It is nonetheless a
real and nameable deviation from the general formula and must be stated as a
disclosed assumption rather than left to be discovered.

**Additional analyses.** The headline result was recomputed under realistic
trading costs across six cost scenarios, compared against two passive
alternatives under both gross and fee-adjusted assumptions, and re-run on a
later stretch of data that postdates the source code. The binomial test is
re-run in full on each fee-adjusted trade set rather than adjusted analytically.

**Honest reporting (ISEF standard).** All results are reported as observed,
including non-significant findings, unfavourable findings, and the
implementation error identified during verification.

---

## 11. Verification and corrections

**The forward-search loops for two Order Block quality criteria could read data
from the future.** The Fair Value Gap and Displacement criteria's forward-search
loops were originally bounded by the length of the whole dataset rather than by
each Order Block's own confirmation candle. That meant they could read one to
two candles of data that would not actually have been available at the moment
the Order Block became eligible for entry. This is a genuine data-leakage
defect. It was found through a dedicated no-lookahead audit and corrected by
bounding both search loops at each Order Block's own confirmation candle, with
runtime assertions left in place at the relevant read sites to catch any future
regression. The correction does not change the 27-trade baseline reported in
this paper, since that baseline is unaffected by quality-score filtering.

**Two further corrections in the reporting rather than in the code.** A separate
audit pass checked every headline number against a live companion website and
against the committed analysis scripts, rather than against the backtesting
engine.

The first concerned the bootstrap confidence interval. The website's
interactive version uses 2,000 resamples while this paper's canonical figure
uses 10,000, producing two individually correct but visibly different intervals
with no stated explanation for the difference. Both are now reported side by
side in the Findings. The cause was traced conclusively rather than assumed:
the website's random number generator, an algorithm called mulberry32, was
reimplemented in Python and run at 2,000 resamples, which reproduced the
website's interval of [+7.48%, +54.46%] exactly. This proves the difference
comes from the resample count alone, and not from a different method, a
different random seed, or a different underlying set of trades. The two figures
are deliberately not merged into one, because the website's independence from
the Python analysis is what makes it a useful cross-check.

The second concerned the correlation p-values, which had been reported as
$p < 0.001$ when the correct values are approximately **0.0094** for Pearson and
**0.0113** for Spearman. Those values remain significant at conventional
thresholds, but the original claim overstated them by roughly a factor of ten.
Both are corrected.

**Independent no-lookahead verification.** A dedicated no-lookahead proof was
conducted. Truncation-equality testing on the ATR(14), ATR(200), and fixed
KDJ(9,3,3) series passed **180 of 180** sampled checks: recomputing each
indicator on a shortened dataset gave exactly the same values, which is what
must happen if no future data is being used. A scope audit of the corrected
Order Block code found no Fair-Value-Gap-true or displacement-true Order Blocks
reading past their own confirmation candle.

**Reproducibility infrastructure.** A golden-master regression harness
recomputes the indicators and the Order-Block-gated simulation from raw candle
data and asserts exact agreement against committed reference files, with
indicators matched to a tolerance of $10^{-6}$ and all 27 trade records matched
exactly. It runs after every code change. The independently written JavaScript
dashboard provides a second cross-check, limited to the indicator and
entry-condition layer.

---

## 12. Findings — all tables and figures

Organize this section against the three research questions. Five subsections —
overall performance, the bootstrap interval, the regime breakdown,
transaction-cost sensitivity, and the out-of-sample validation — address RQ1.
The subsection comparing the strategy against dollar-cost averaging and
lump-sum buy-and-hold addresses RQ2 and RQ3.

Every number carries, in Appendix A, a reference to the exact function that
produced it and the exact data that function was given.

### Overall strategy performance

**Table 3 — Baseline Strategy Performance, 2022 to 2026 Window, Gross of Costs**

| Metric | Value |
| :---- | :---- |
| Trades | 27 |
| Wins / Losses | 19 / 8 |
| Win rate | 70.37% |
| Total net return | +30.31% |
| Average return per trade | +1.1225% |
| Standard deviation of return per trade | 2.41% |
| One-sided binomial p | 0.0261 |
| Two-sided binomial p | 0.0522 |

*Note.* Computed by `binomial_test()`, which wraps `scipy.stats.binomtest`, on
27 trades with 19 wins against a null win probability of 0.5.

With 27 trades and 19 wins, the one-sided exact binomial test gives

$$P(K \geq 19 \mid n = 27,\ p = 0.5) = \sum_{k=19}^{27}\binom{27}{k}(0.5)^{27} = 0.0261$$

which falls below the conventional 5% threshold. Gross of costs, this supports
rejecting H₀₁ in favour of H₁₁. In plain terms, if the strategy truly had no
edge, a run this good would happen about 26 times in every 1,000 attempts. That
is unlikely enough to take seriously, but it is not overwhelming, and it rests
on only 27 trades. This significance claim does not survive realistic trading
costs — see the transaction-cost subsection.

The 27 trades are identified throughout the paper by the candle index at which
each was entered. In ascending order: **335, 359, 673, 902, 1050, 1158, 1913,
2624, 2859, 3100, 3196, 3859, 3947, 4455, 5800, 5825, 6040, 6109, 6366, 6537,
6991, 7109, 7938, 7964, 8188, 8280, and 8596.** Every statistic referring to
"the 27 baseline trades" refers to exactly this set. The complete per-trade
record is in Appendix D, Table D1.

### Bootstrap confidence interval

A bootstrap with 10,000 resamples of the 27-trade return distribution, drawn at
the original sample size of 27 with a fixed random seed of 42, gives a point
estimate of **+30.3065%** total net return — which differs from the observed sum
of the 27 trade returns, **+30.3064%**, only in the fourth decimal place — with
a 95% confidence interval of **[+5.9866%, +54.9866%]**. The interval is wide but
excludes zero, and **99.25%** of resampled totals were positive, meaning 0.75%
came out at or below zero. The corresponding confidence interval for average
return per trade is **[+0.2217%, +2.0365%]**.

In plain terms: when the recorded trades are reshuffled thousands of times,
almost every version of the result still makes money, though the amount varies
a great deal.

The companion interactive website recomputes the same bootstrap live in the
browser using a lighter 2,000 resamples for responsiveness, and lands on a
similar but not identical interval, **[+7.48%, +54.46%]**. That computation is a
separate TypeScript implementation which never imports any value from the
Python analysis, using its own random number generator, mulberry32. The
difference between the two intervals was traced conclusively to the resample
count alone. The two are deliberately reported separately rather than merged,
because the website's independence is what gives the cross-check its value.

### Regime breakdown and correlation

Trades were tagged by broad market condition at entry, using two independent
methods. The first is a simple calendar split, treating 2022 as a bear market,
2023 as sideways, and 2024 to 2025 as a bull market.

**Table 4 — Performance by Calendar Regime**

| Regime | Trades | Win rate | Return contribution | Share of total return |
| :---- | :---- | :---- | :---- | :---- |
| Bear (2022) | 7 | 57.14% | +10.45% | +34.5% |
| Chop (2023) | 6 | 50.00% | −5.39% | −17.8% |
| Bull (2024 to 2025) | 14 | 85.71% | +25.25% | +83.3% |

*Note.* The three regime rows partition the same 27 baseline trades, so the
trade counts sum to 27 and the return contributions sum to +30.31%.

The second method measures how far price sat below its previous all-time high,
seeded from Bitcoin's pre-window high of $69,000 on 2021-11-10, with bear
defined as 40% or more below that high, sideways as between 40% and 12% below,
and bull as less than 12% below.

**Table 5 — Performance by Drawdown-From-High Regime**

| Regime | Trades | Win rate | Return contribution | Share of total return |
| :---- | :---- | :---- | :---- | :---- |
| Bear (at or below −40% from high) | 12 | 50.00% | −1.63% | −5.4% |
| Chop (−40% to −12% from high) | 8 | 87.50% | +18.89% | +62.3% |
| Bull (above −12% from high) | 7 | 85.71% | +13.05% | +43.1% |

*Note.* The same 27 baseline trades, re-partitioned by a different definition of
market regime.

The two methods agree on only **13 of the 27** trade assignments, because they
measure different things. Much of calendar-2023 remained 57% to 64% below the
all-time high even though price that year was comparatively range-bound rather
than actively falling. Both methods nonetheless agree on the point that matters
most: the bull regime is consistently the strongest, at an 85.71% win rate under
both classifications. The three most concentrated winning trades, which together
account for **51.7%** of total net return, are not clustered in a single regime
under either method.

Across the same 27 trades, Pearson's $r = \mathbf{+0.4907}$ with $t = 2.82$,
$df = 25$, and $p \approx \mathbf{0.0094}$; Spearman's
$\rho = \mathbf{+0.4797}$ with $p \approx \mathbf{0.0113}$ — both computed
between holding time in candles and percentage return. In plain terms, trades
held open longer tended to end up larger, and the pattern is strong enough that
chance is an unlikely explanation, holding up at both the 5% and the 1%
threshold.

### Strategy versus dollar-cost averaging and lump-sum buy-and-hold

This subsection addresses RQ2 and RQ3, and provides the evidence on which the
second hypothesis pair is resolved. Present the blended-sleeve model **first**,
then the head-to-head comparison — the head-to-head figures are easy to misread
on their own, and the blended model is the framing they should be read against.

#### The blended-sleeve model

**Table 6 — Risk-Adjusted Profile of a Blended DCA Portfolio at Increasing
Strategy Allocations**

| Split (BTC-DCA / Strategy) | Sharpe (annualized) | Sortino (annualized) | Max drawdown |
| :---- | :---- | :---- | :---- |
| 100% / 0% | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |

*Note.* Computed on the blended equity curve of 210 weekly contributions across
the 2022 to 2026 window, under the construction set out in Section E. Both
ratios assume a risk-free rate of zero, as disclosed under Formula 3.

Every one of the three measures moves in the direction predicted by H₁₂, and
each moves consistently across all four allocation levels rather than reversing
at any point. Sharpe rises from 0.556 to 0.637, Sortino from 0.886 to 1.032, and
maximum drawdown shallows from −27.85% to −23.18%. Under the descriptive
standard set out with the hypothesis, this is the pattern that would lead to
rejecting H₀₂ in favour of H₁₂. That conclusion is bounded exactly as stated
there: it rests on one realized price path, it carries no p-value, and it
establishes what a blend would have done over this window rather than what it
will do over another.

#### Head-to-head at equal starting capital

Three fully capitalized arms were run over the identical 2022-01-01 to
2026-01-01 window, each starting from $10,000.

**Table 7 — Three-Arm Head-to-Head Comparison, 2022 to 2026, Gross of Costs**

| Arm | Total return | Final capital from $10,000 | Sharpe | Sortino | Max drawdown | Time in market |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| OB-gated strategy | +30.31% | $13,417.77 | 1.1142 | 2.7273 | −6.46% | 2.63% |
| Weekly DCA into BTC | +123.13% | $22,312.94 | 0.5559 | 0.8857 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +90.07% | $19,007.32 | 0.5642 | 0.8034 | −67.21% | 100.00% |

*Note.* Time in market for the strategy is 2.6349% of candles. One
reconciliation must be stated explicitly so that it is not mistaken for an
arithmetic error. For the strategy arm the Total return column is the arithmetic
sum of the 27 individual trade returns, which is the convention used for the
+30.31% headline figure throughout this paper, while the Final capital column
compounds those same 27 returns in sequence from the $10,000 start. Compounded,
the strategy's return over this window is **+34.18%**, which is what produces
$13,417.77. The two passive arms hold one position throughout, so for them the
two columns are the same quantity expressed two ways and no such gap arises.

**Table 8 — Three-Arm Head-to-Head Comparison, 2022 to 2026, Net of Costs**

| Arm | Total return | Final capital from $10,000 | Sharpe | Sortino | Max drawdown | Time in market |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| OB-gated strategy | +24.91% | $12,719.01 | 0.9442 | 2.0830 | −7.78% | 2.63% |
| Weekly DCA into BTC | +122.91% | $22,290.65 | 0.5529 | 0.8806 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +89.88% | $18,988.34 | 0.5642 | 0.8034 | −67.21% | 100.00% |

*Note.* Same construction and window as Table 7, with costs applied as set out
in Section E. The same summed-versus-compounded reconciliation applies: the
strategy's +24.91% is the sum of its 27 net trade returns, while $12,719.01 is
those returns compounded, equivalent to +27.19%. Charging costs reduces the
strategy's Sharpe from 1.1142 to 0.9442 and its Sortino from 2.7273 to 2.0830,
and deepens its maximum drawdown from −6.46% to −7.78%. Both passive arms are
almost unaffected, because a single purchase markup is charged once rather than
27 times.

On its own, the strategy's gross Sharpe of 1.114 and Sortino of 2.727 exceed
those of simply buying and holding Bitcoin over the same window, which give
0.564 and 0.803. However, the strategy holds a market position only 2.63% of the
time. This is therefore **not** a like-for-like comparison and must not be read
as the strategy outperforming Bitcoin's risk-adjusted profile outright.

State plainly: dollar-cost averaging into Bitcoin beat the strategy in raw final
value over this window, by a wide margin — $22,312.94 against $13,417.77 gross,
and $22,290.65 against $12,719.01 after costs. This is not a favourable result
and must not be minimized. What the strategy offers instead is a materially
better risk-adjusted profile, achieved while holding a position only 2.63% of
the time against 100% continuous exposure for both passive arms. That gap in
exposure is large enough that neither figure on its own tells an investor which
approach to prefer. The blended-sleeve model in Table 6 remains the more
decision-relevant framing.

**Table 9 — Three-Arm Head-to-Head Comparison, 2018 to 2022 Formulation Window,
Gross of Costs**

| Arm | Total return | Final capital from $10,000 | Sharpe | Sortino | Max drawdown | Time in market |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| OB-gated strategy | +21.82% | $12,282.53 | 0.681 | 1.303 | −6.00% | 1.87% |
| Weekly DCA into BTC | +439.88% | $53,987.55 | 0.824 | 1.234 | −46.16% | 100.00% |
| Lump-sum buy-and-hold | +236.96% | $33,696.49 | 0.789 | 1.119 | −81.42% | 100.00% |

*Note.* Same construction as Table 7, applied to the 2018-01-01 to 2022-01-01
window, where the weekly schedule contains 209 contributions of $47.8469 each.
The strategy's +21.82% is again the summed figure; $12,282.53 is the compounded
equivalent of +22.83%.

That window is where the strategy's rules were formed, so it is not
out-of-sample evidence and is reported for comparison only. Bitcoin's 2018 to
2022 window contained a much larger fall-and-recovery cycle than 2022 to 2026,
which mechanically favours dollar-cost averaging by lowering its average
purchase price. That is a property of how the passive benchmarks behave on that
particular price path, not a statement about the strategy's edge. Note that the
strategy's own performance is *worse* on its formulation window than on the
reported window, which is the opposite of what fitting the rules to that period
would have produced.

### Transaction-cost sensitivity

The confirmed Binance USDT-M Futures standard-tier taker rate is 0.05% per side,
or 5.00 basis points per side, giving 0.10% for a full round trip. Slippage —
the gap between the expected and the actual fill price — was modelled separately
as a conservative 0.05% per side, or 0.10% round trip. Six cost scenarios were
run: a gross case, a fee-only case, and four scenarios spanning a sensitivity
band from 0.14% to 0.40% round trip.

**Table 10 — Win Rate and Significance Across Six Transaction-Cost Scenarios**

| Scenario | N | Win rate | Total net return | Binomial p (1-sided) | Trades flipped to losses |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Gross, no fees or slippage | 27 | 70.37% | +30.31% | 0.0261 | none |
| Fee only, 5.00 bps per side round trip | 27 | 70.37% | +27.61% | 0.0261 | none |
| Low band, 4 bps fee + 3 bps slippage per side, 0.14% round trip | 27 | 62.96% | +26.53% | 0.1239 | 7938, 8188 |
| **Primary, 5 bps fee + 5 bps slippage per side, 0.20% round trip** | 27 | 62.96% | +24.91% | **0.1239** | 7938, 8188 |
| Mid band, 7 bps fee + 5 bps slippage per side, 0.24% round trip | 27 | 62.96% | +23.83% | 0.1239 | 7938, 8188 |
| High band, 10 bps fee + 10 bps slippage per side, 0.40% round trip | 27 | 55.56% | +19.51% | 0.3506 | 2859, 5825, 7938, 8188 |

*Note.* Each row re-runs the binomial test in full on that scenario's
fee-adjusted trade set rather than adjusting the gross p-value analytically. The
flipped-trade column gives the candle indices of the trades that cross from
winners into losers. "bps" means basis points, where one basis point is one
hundredth of one percent.

This is a reversal of a significance conclusion, and must be reported as such
rather than softened. The first hypothesis pair resolves differently depending
on the cost assumption, and both resolutions must be stated. Gross of costs, and
under the exchange fee alone, H₀₁ is rejected at p = 0.0261. Under the primary
cost assumption of a 0.20% round trip, and under every stricter scenario tested,
H₀₁ is **not** rejected. Since the primary cost assumption is the realistic one,
the honest overall answer is that **H₀₁ is not rejected once costs a real trader
would pay are charged.** In plain terms, once realistic fees and slippage are
charged, the strategy's above-50% win rate can no longer be distinguished from
luck. The flip is driven by exactly two trades — those entered at candle indices
7938 and 8188, originally worth +0.12% and +0.13% before costs — crossing from
winners into losers.

### Out-of-sample and extended-history validation

A forward out-of-sample test was built using BTCUSDT 4-hour data from
2026-01-01 through 2026-07-31, a period that genuinely postdates every change to
the strategy's source code. It was run through the identical frozen pipeline,
after first confirming that the locked 27-trade baseline reproduced exactly.

**Table 11 — Forward Out-of-Sample Result, January to July 2026**

| Metric | Value |
| :---- | :---- |
| New out-of-sample trades | 4 |
| Wins / Losses | 1 / 3 |
| Win rate | 25.00% |
| Total return | −3.45% |
| Average return per trade | −0.86% |

*Note.* Produced by the same frozen pipeline that generated Table 3, applied to
candles after 2026-01-01 08:00:00.

Report this as it came out: a small and directionally unfavourable result. Four
trades cannot confirm or refute the strategy's edge on their own. But this is
the only evidence available that is out-of-sample with respect to both rule
formulation and code auditing, and it does not provide reassurance.

A separate eight-year backfill check ran the identical frozen pipeline against
data extended back to 2018-01-01, to test whether roughly four extra years of
indicator warm-up would change the locked 2022 to 2026 results. This was a real
methodological risk, because MACD's exponential moving averages and the fixed
KDJ series are recursive and therefore carry memory with no theoretical
cut-off. The check passed: all 27 locked trades matched by entry timestamp,
with a maximum profit-and-loss difference of **0.0000000000%**.

**Table 12 — Comparison of the Formulation Window, the Primary Window, and
Their Combination**

| Window | N | Win rate | Total return | Avg return/trade | Binomial p (1-sided) |
| :---- | :---- | :---- | :---- | :---- | :---- |
| 2018-01 to 2022-01, formulation period, not out-of-sample | 25 | 60.00% | +21.82% | +0.87% | 0.2122 |
| 2022-01 to 2026-01, primary reported window | 27 | 70.37% | +30.31% | +1.12% | 0.0261 |
| Combined 2018 to 2026, mixed provenance | 56 | 62.50% | +48.68% | n/a | 0.0407 |

*Note.* Each row is a separate binomial test on that window's own trade set. The
combined row's 56 trades are the 25 formulation-period trades, the 27
primary-window trades, and the 4 forward-test trades of Table 11. The arithmetic
reconciles exactly: 25 + 27 + 4 = 56 trades; 15 + 19 + 1 = 35 wins, which is
62.50%; and +21.82% + 30.31% − 3.45% = +48.68%.

The combined row should never be cited on its own. Roughly half of it comes from
the period the rules were formulated against, so its p = 0.0407 partly reflects
performance on data the rules were formed by looking at. Notably, the strategy
performs worse on its own formulation-period data, at a 60.00% win rate and
p = 0.2122, than on the primary reported window, at 70.37% and p = 0.0261. This
is the opposite of what fitting the rules to the formulation period would
predict, and it is the clearest single piece of evidence in this paper that the
rules were not tuned to that window.

---

## 13. Conclusions

### Discussion of findings

**Predictive effectiveness.** The full-sample return finding is directionally
robust: the bootstrap 95% confidence interval on total return, [+5.99%,
+54.99%], excludes zero even though it is wide, and 99.25% of the 10,000
resamples were positive. The win-rate significance claim, by contrast, is
fragile — it survives the exchange fee alone at p = 0.0261, but not the addition
of conservative slippage at p = 0.1239. Both facts are part of the same answer
to RQ1, and reporting only the first would misrepresent the second.

Return is also concentrated. Three trades account for **51.7%** of the total.
Profitability at this sample size rests on a handful of large outcomes rather
than on a steady, repeatable edge in every trade, and a different four-year
window could plausibly produce a different result. The positive correlation
between holding time and return, at r = +0.4907 and ρ = +0.4797, is consistent
with that picture: the large outcomes are the ones the exit rules allowed to run.

**The separation between formulation and reported windows.** Table 12 gives the
most direct evidence that the separation is real rather than nominal — the
strategy performs *worse* on the window its rules were formed against. That
evidence should not be overstated: visual inspection is a weaker form of
separation than a formal held-out split, because it leaves no record of what was
tried and discarded. And the reported window is out-of-sample only with respect
to rule formulation, not code auditing. The four-trade January to July 2026 test
is the only result out-of-sample in both senses, and it is unfavourable.

**Regime dependence and the relationship to passive investing.** The strategy's
edge is concentrated in bull-trending conditions, at an 85.71% win rate under
both regime-classification methods, and is weaker or negative in sideways or
bearish conditions under at least one of the two. This tempers any claim of
reliability across market conditions.

On RQ2 and RQ3 the two results point in opposite directions and both must be
reported. Head-to-head from equal capital, dollar-cost averaging beat the
strategy decisively on final value, and no framing changes that. On
risk-adjusted shape, the strategy was the stronger of the two, but it achieved
that while invested 2.63% of the time against 100% — not a like-for-like
comparison. The blended-sleeve framing is the defensible one: Sharpe, Sortino,
and drawdown all improve steadily as the strategy's allocation rises from 0% to
30% inside a DCA portfolio. The head-to-head comparison shows dollar-cost
averaging producing roughly 1.66 times the final capital of the strategy gross
of costs, and roughly 1.75 times net of costs. Both results are true
simultaneously, and citing either without the other would misrepresent the
finding. The practical reading is that this rule set is a candidate **supplement**
to a dollar-cost-averaging plan over this window, not a replacement for one.

### Limitations

Include each of these:

1. The study does not model leveraged or margined positions, and reports
   unlevered, notional returns throughout. This is a deliberate scope decision.
   The engine evaluates every exit condition on candle closes rather than on
   intra-candle price paths, so a leverage model layered on top would inherit
   that resolution limit and report liquidation outcomes it cannot establish.
2. Findings are constrained by a small sample of 27 trades, and by the
   concentration of return in three of them (51.7% of total net return).
   Conclusions in either direction should be treated as provisional.
3. The separation between the formulation period and the reported window is real
   but weaker than a formal held-out split, and no record exists of what rule
   variants were considered and set aside.
4. The comparison against passive alternatives is descriptive rather than
   inferential. Sharpe, Sortino, and maximum drawdown are each computed once on
   a single realized price path, so no confidence interval or p-value attaches
   to the difference between arms, and none is claimed. A second four-year
   window with a different shape could plausibly reverse the ordering, as
   Table 9 already illustrates in one direction.
5. Two implementation choices are disclosed as assumptions rather than defended
   as the only correct option: Sharpe and Sortino assume a risk-free rate and a
   minimum acceptable return of zero; the bootstrap is the plain percentile form
   rather than the BCa variant.
6. The reported window's trade frequency is low, at roughly 0.56 trades per
   month, which limits how quickly genuinely forward-looking evidence can
   accumulate.

### Summary and conclusion

Cover, in order: the headline result and its binomial p; that the rules were
formed on a separate window and fixed before the reported window was measured;
that the bootstrap interval excludes zero; that the win-rate significance does
not survive realistic costs and that this is the answer to carry forward; the
data-leakage correction and the two reporting corrections; the unfavourable
four-trade forward test; the RQ2 answer (DCA won on final value, the strategy
won on risk-adjusted shape, the two are not like-for-like); and the RQ3 answer
(all three measures improved consistently from 0% to 30%, resolved descriptively
with no p-value).

Close with: this study establishes a historically observed, directionally robust
return edge for this specific rule set on this specific window, with its
win-rate significance shown to be cost-sensitive and its regime concentration
made explicit. It does **not** establish that the strategy will remain profitable
in future market conditions, and the only evidence available on that question so
far is unfavourable.

Future work: continue accumulating genuinely forward-looking trades at the
strategy's natural frequency, since only prospective evidence can settle whether
the edge persists; and test the same rule set on additional instruments and
timeframes.

---

## 14. Results that must be reported unsoftened

These four are non-negotiable. Do not hedge, bury, or reframe them.

1. **Dollar-cost averaging beat the strategy on final value**, $22,312.94
   against $13,417.77 gross. State it plainly in the Findings and again in the
   Summary.
2. **Win-rate significance does not survive realistic costs** — p moves from
   0.0261 to 0.1239 at a 0.20% round trip. The honest overall answer to H₀₁ is
   that it is *not* rejected.
3. **The forward out-of-sample test returned −3.45%** on 4 trades with 1 win.
4. **Return is concentrated in three trades** accounting for 51.7% of total net
   return.

---

## 15. Figures

Five figures. Insert a placeholder at each location in the form
`[Figure N placeholder — <caption>]`, followed by the figure number and caption
formatted per APA. Do not attempt to draw or generate the images.

| # | Caption | What it must show |
| :---- | :---- | :---- |
| 1 | *Relationship Between the Formulation Period, the Primary Reported Window, and the Forward Test* | A timeline: 2018-01→2022-01 formulation, 2022-01→2026-01 primary, 2026-01→2026-07 forward test. |
| 2 | *Data Collection, Timestamp Conversion, and Dataset Verification* | Flow from the Binance `get_klines` endpoint through pagination, the +8h timestamp shift, and the candle-count arithmetic to the gap check. |
| 3 | *Order Block Detection, Quality Scoring, and Eligibility* | The two pivot passes (5-candle internal, 50-candle swing), break of structure, Order Block creation, the five quality criteria, and the eligibility rule barring entry until after `created_at`. |
| 4 | *Long Entry Decision Sequence* | The six conditions that must hold at one candle close for a long entry. |
| 5 | *Exit Priority Order* | The fixed priority order in which exits are evaluated; the first satisfied condition triggers and the rest are skipped for that candle. |

---

## 16. Appendices

**Appendix A — Statistical Provenance of Every Reported Number.** A table with
columns: Reported value | Where it appears | Producing function | Library or
custom | Exact input. One row per statistic in Tables 3 through 12, plus the
dataset row and the per-trade log row. State that all function names refer to
`research_analysis.py`, and that "Baseline 27" means the 27 trades whose entry
candle indices are listed in the Findings.

**Appendix B — Source Form of Every Formula Written for This Study.** Formulas
1, 2, and 3 in LaTeX source form, so a reader can reproduce the exact
expression rather than re-key it from a rendered image. Include the parameters
as used: Formula 1 at $B = 10{,}000$, $n = 27$, seed 42, sampling with
replacement.

**Appendix C — Statement on Software Authorship.** State that of the six
reported quantities, three are direct calls into SciPy and implement no
arithmetic of this project's own, while three implement standard published
formulas written independently from public documentation. State that the commits
which introduced or materially edited those three functions were made with the
assistance of an AI coding assistant, and that each such commit carries a
co-authorship trailer recording that. The accurate description is that the
design decisions were directed by the researchers and the code was written with
AI assistance under that direction. Disclose this unprompted.

**Appendix D — Complete Trade Log for the Primary Window.** Reproduce Table D1
below in full.

**Table D1 — All 27 Trades, 2022 to 2026 Window**

| Idx | Side | Entry time | Exit time | Return % | Bars | Exit reason | Dsp | Lrg | FVG | Swp | Vol | q |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| 335 | Short | 2022-02-26 04:00 | 2022-02-27 16:00 | -0.6645 | 9 | Trailing | Y | - | - | - | Y | 2 |
| 359 | Short | 2022-03-02 04:00 | 2022-03-04 08:00 | +6.6888 | 13 | ATR move | - | Y | Y | Y | Y | 4 |
| 673 | Long | 2022-04-23 12:00 | 2022-04-25 04:00 | -0.3809 | 10 | KDJ reset | Y | Y | - | Y | Y | 4 |
| 902 | Short | 2022-05-31 16:00 | 2022-06-01 20:00 | +3.2248 | 7 | ATR move | - | Y | - | - | Y | 2 |
| 1050 | Short | 2022-06-25 08:00 | 2022-06-26 00:00 | +0.4433 | 4 | Trailing | - | Y | Y | Y | - | 3 |
| 1158 | Long | 2022-07-13 08:00 | 2022-07-13 20:00 | -0.0898 | 3 | Trailing | - | - | - | Y | - | 1 |
| 1913 | Short | 2022-11-16 04:00 | 2022-11-18 04:00 | +1.2308 | 12 | Trailing | - | - | - | - | - | 0 |
| 2624 | Short | 2023-03-14 16:00 | 2023-03-14 20:00 | -4.6544 | 1 | Stop loss | - | Y | Y | Y | Y | 4 |
| 2859 | Long | 2023-04-22 20:00 | 2023-04-23 08:00 | +0.2507 | 3 | KDJ reset | - | Y | - | Y | Y | 3 |
| 3100 | Long | 2023-06-02 00:00 | 2023-06-04 04:00 | +0.7689 | 13 | Trailing | - | - | - | - | - | 0 |
| 3196 | Short | 2023-06-18 00:00 | 2023-06-20 00:00 | -0.7818 | 12 | KDJ reset | - | Y | Y | - | - | 2 |
| 3859 | Long | 2023-10-06 12:00 | 2023-10-08 16:00 | +0.6263 | 13 | Trailing | - | Y | - | Y | - | 2 |
| 3947 | Short | 2023-10-21 04:00 | 2023-10-22 00:00 | -1.6044 | 5 | Stop loss | - | Y | - | Y | Y | 3 |
| 4455 | Long | 2024-01-13 20:00 | 2024-01-15 00:00 | -1.1458 | 7 | KDJ reset | - | Y | Y | - | Y | 3 |
| 5800 | Short | 2024-08-25 00:00 | 2024-08-27 16:00 | +2.7933 | 16 | ATR move | - | Y | Y | - | - | 2 |
| 5825 | Long | 2024-08-29 04:00 | 2024-08-30 00:00 | +0.3779 | 5 | Trailing | - | - | Y | Y | Y | 3 |
| 6040 | Long | 2024-10-04 00:00 | 2024-10-06 08:00 | +1.3806 | 14 | KDJ reset | Y | - | - | - | - | 1 |
| 6109 | Short | 2024-10-15 12:00 | 2024-10-16 00:00 | -2.0284 | 3 | KDJ reset | - | Y | - | Y | Y | 3 |
| 6366 | Long | 2024-11-27 08:00 | 2024-11-28 00:00 | +4.3634 | 4 | ATR move | - | Y | - | - | Y | 2 |
| 6537 | Short | 2024-12-25 20:00 | 2024-12-27 12:00 | +3.4665 | 10 | ATR move | - | Y | Y | - | Y | 3 |
| 6991 | Long | 2025-03-11 12:00 | 2025-03-12 20:00 | +1.6338 | 8 | Trailing | Y | Y | Y | Y | - | 4 |
| 7109 | Long | 2025-03-31 04:00 | 2025-04-01 20:00 | +3.5088 | 10 | ATR move | - | Y | Y | Y | Y | 4 |
| 7938 | Long | 2025-08-16 08:00 | 2025-08-18 00:00 | +0.1196 | 10 | KDJ reset | - | Y | - | - | Y | 2 |
| 7964 | Long | 2025-08-20 16:00 | 2025-08-22 20:00 | +2.3789 | 13 | ATR move | - | Y | - | Y | - | 2 |
| 8188 | Long | 2025-09-27 00:00 | 2025-09-27 16:00 | +0.1264 | 4 | KDJ reset | - | Y | - | Y | Y | 3 |
| 8280 | Long | 2025-10-12 08:00 | 2025-10-14 00:00 | +4.6233 | 10 | ATR move | - | Y | - | Y | - | 2 |
| 8596 | Short | 2025-12-04 00:00 | 2025-12-06 00:00 | +3.6503 | 12 | ATR move | - | - | Y | - | - | 1 |

*Note.* Return % is the trade's net percentage return. Dsp = displacement,
Lrg = large origin candle, FVG = Fair Value Gap, Swp = liquidity sweep,
Vol = volume expansion. Idx is the entry candle index. Bars is the holding
period in candles. q is the sum of the five criterion flags.

**Checks a reader can run on this table.** The Return column contains 19
positive values out of 27, giving the 70.37% win rate in Table 3. Those 27
values sum to **+30.3064%**, with a mean of **+1.1225%** and a standard
deviation of **2.41%**.

**Exit-reason distribution.** Of the 27 trades, **9** closed on the ATR-move
exit, **8** on the trailing exit, **8** on the KDJ-reset exit, and **2** on the
hard stop-loss. No trade in this window closed on the hard take-profit.

---

## 17. References

Use exactly this list, APA 7th edition, alphabetical.

Bangko Sentral ng Pilipinas. (2022). *2021 financial inclusion survey: Topline report*. https://www.bsp.gov.ph/Inclusive%20Finance/Financial%20Inclusion%20Reports%20and%20Publications/2021/2021FISToplineReport.pdf
Baur, D. G., Hong, K., & Lee, A. D. (2018). Bitcoin: Medium of exchange or speculative assets? *Journal of International Financial Markets, Institutions and Money, 54*, 177–189. https://doi.org/10.1016/j.intfin.2017.12.004
Bergsli, L. Ø., Lind, A. F., Molnár, P., & Polasik, M. (2022). Forecasting volatility of Bitcoin. *Research in International Business and Finance, 59*, Article 101540. https://doi.org/10.1016/j.ribaf.2021.101540
Bessembinder, H., Panayides, M., & Venkataraman, K. (2009). Hidden liquidity: An analysis of order exposure strategies in electronic stock markets. *Journal of Financial Economics, 94*(3), 361–383. https://doi.org/10.1016/j.jfineco.2009.02.001
Biais, B., Glosten, L., & Spatt, C. (2005). Market microstructure: A survey of microfoundations, empirical results, and policy implications. *Journal of Financial Markets, 8*(2), 217–264. https://doi.org/10.1016/j.finmar.2004.11.001
Bibi, S. (2023). Money in the time of crypto. *Research in International Business and Finance, 65*, Article 101964. https://doi.org/10.1016/j.ribaf.2023.101964
Brolley, M., & Cimon, D. A. (2020). Order-flow segmentation, liquidity, and price discovery: The role of latency delays. *Journal of Financial and Quantitative Analysis, 55*(8), 2555–2587. https://doi.org/10.1017/S002210901900067X
Chong, T. T.-L., & Ng, W.-K. (2008). Technical analysis and the London stock exchange: Testing the MACD and RSI rules using the FT30. *Applied Economics Letters, 15*(14), 1111–1114. https://doi.org/10.1080/13504850600993598
Constantinides, G. M. (1979). A note on the suboptimality of dollar-cost averaging as an investment policy. *Journal of Financial and Quantitative Analysis, 14*(2), 443–450. https://doi.org/10.2307/2330513
Corbet, S., Eraslan, V., Lucey, B., & Şensoy, A. (2019). The effectiveness of technical trading rules in cryptocurrency markets. *Finance Research Letters, 31*, 32–37. https://doi.org/10.1016/j.frl.2019.04.027
Dai, Z., Dong, X., Kang, J., & Hong, L. (2020). Forecasting stock market returns: New technical indicators and two-step economic constraint method. *The North American Journal of Economics and Finance, 53*, Article 101216. https://doi.org/10.1016/j.najef.2020.101216
Demirgüç-Kunt, A., Klapper, L., Singer, D., & Ansar, S. (2022). *The Global Findex Database 2021: Financial inclusion, digital payments, and resilience in the age of COVID-19*. World Bank. https://doi.org/10.1596/978-1-4648-1897-4
Díaz, A., & Escribano, A. (2020). Measuring the multi-faceted dimension of liquidity in financial markets: A literature review. *Research in International Business and Finance, 51*, Article 101079. https://doi.org/10.1016/j.ribaf.2019.101079
Efron, B., & Tibshirani, R. J. (1993). *An introduction to the bootstrap*. Chapman & Hall.
Eom, C., Kaizoji, T., Kang, S. H., & Pichl, L. (2019). Bitcoin and investor sentiment: Statistical characteristics and predictability. *Physica A: Statistical Mechanics and Its Applications, 514*, 511–521. https://doi.org/10.1016/j.physa.2018.09.063
Fang, J., Jacobsen, B., & Qin, Y. (2014). Predictability of the simple technical trading rules: An out-of-sample test. *Review of Financial Economics, 23*(1), 30–45. https://doi.org/10.1016/j.rfe.2013.05.004
Katsiampa, P. (2017). Volatility estimation for Bitcoin: A comparison of GARCH models. *Economics Letters, 158*, 3–6. https://doi.org/10.1016/j.econlet.2017.06.023
LuxAlgo. (2022, October 11). *Smart money concepts (SMC) [LuxAlgo]* [Pine Script indicator]. TradingView. https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-SMC-LuxAlgo/
Nakamoto, S. (2008). *Bitcoin: A peer-to-peer electronic cash system*. https://bitcoin.org/bitcoin.pdf
Navarro, M. M., & Navarro, B. B. (2023). Assessing the long-term performance of MACD strategy in the Philippine stock market: A 12-year review. In *Proceedings of the 6th European Conference on Industrial Engineering and Operations Management* (pp. 1280–1286). IEOM Society International. https://ieomsociety.org/proceedings/2023lisbon/327.pdf
Schär, F. (2021). Decentralized finance: On blockchain- and smart contract-based financial markets. *Federal Reserve Bank of St. Louis Review, 103*(2), 153–174. https://doi.org/10.20955/r.103.153-74
Sharpe, W. F. (1994). The Sharpe ratio. *The Journal of Portfolio Management, 21*(1), 49–58. https://doi.org/10.3905/jpm.1994.409501
Sortino, F. A., & van der Meer, R. (1991). Downside risk. *The Journal of Portfolio Management, 17*(4), 27–31. https://doi.org/10.3905/jpm.1991.409343
Statman, M. (1995). A behavioral framework for dollar-cost averaging. *The Journal of Portfolio Management, 22*(1), 70–78. https://doi.org/10.3905/jpm.1995.409537
Svogun, D., & Bazán-Palomino, W. (2022). Technical analysis in cryptocurrency markets: Do transaction costs and bubbles matter? *Journal of International Financial Markets, Institutions and Money, 79*, Article 101601. https://doi.org/10.1016/j.intfin.2022.101601
Tao, L., Hao, Y., Yijie, H., & Chunfeng, S. (2017). K-line patterns’ predictive power analysis using the methods of similarity match and clustering. *Mathematical Problems in Engineering, 2017*, Article 3096917. https://doi.org/10.1155/2017/3096917
Tukey, J. W. (1977). *Exploratory data analysis*. Addison-Wesley.
United Nations. (2015). *Transforming our world: The 2030 agenda for sustainable development* (A/RES/70/1). https://sdgs.un.org/2030agenda
Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., Burovski, E., Peterson, P., Weckesser, W., Bright, J., van der Walt, S. J., Brett, M., Wilson, J., Millman, K. J., Mayorov, N., Nelson, A. R. J., Jones, E., Kern, R., Larson, E., … van Mulbregt, P. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. *Nature Methods, 17*(3), 261–272. https://doi.org/10.1038/s41592-019-0686-2
Wen, F., Xu, L., Ouyang, G., & Kou, G. (2019). Retail investor attention and stock price crash risk: Evidence from China. *International Review of Financial Analysis, 65*, Article 101376. https://doi.org/10.1016/j.irfa.2019.101376
Wilder, J. W., Jr. (1978). *New concepts in technical trading systems*. Trend Research.
Wu, M., & Diao, X. (2015). Technical analysis of three stock oscillators testing MACD, RSI and KDJ rules in SH & SZ stock markets. In *2015 4th International Conference on Computer Science and Network Technology* (pp. 320–323). IEEE. https://doi.org/10.1109/ICCSNT.2015.7490760

---

## 18. Prohibitions

The following must not appear anywhere in the paper, in any form — not in the
body, not in a table, not in an appendix, not as a mention of something
considered.

- Welch's t-test
- Fisher's exact test
- Minimum detectable effect (MDE) and power analysis
- Any ablation, indicators-only arm, or component-isolation comparison, and any
  statistic computed from one
- Any figure describing a count of qualifying indicator signals

Further rules:

- Do not introduce any statistic beyond the six listed in §2.
- Do not attach a p-value to Sharpe, Sortino, or maximum drawdown.
- Do not change any strategy rule, threshold, parameter, or formula.
- Do not soften, omit, or reframe any null or unfavourable result.
- Do not alter any number given in this document. Reproduce each to the decimal
  places shown.
