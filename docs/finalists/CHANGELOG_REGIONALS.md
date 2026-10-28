# Changelog: bitcoin (5) → bitcoin (6), regional revision

Branch `dev/paper-3rq-2h`, 2026-10-28. Source: `docs/finalists/bitcoin (5).docx`
(unchanged). Output: `docs/finalists/bitcoin (6).docx` and `.pdf`, 76 pages
(bitcoin (5) has 74).

The structure (3 research questions, H₁ and H₂ in alternative form, RQ3 with
no hypothesis) is unchanged. No strategy parameter, rule or threshold
changed. The golden-master regression harness (`scratch/regression.py`)
passed before and after the code change: all 27 baseline trades match
exactly.

## Recomputed numbers and the functions that produced them

### Item 1: Sharpe ratio at one common frequency

Producing function: `run_benchmark_daily_sharpe()` in `research_analysis.py`
(Section 5B, new). Artifact: `artifacts/benchmark_daily_sharpe.json`. Every arm
is valued at the UTC daily close (the last 4h bar of each UTC day) and
annualized with m = 365. DCA daily returns are net of that day's
contribution. The function rebuilds each equity curve bar by bar and asserts
that its final value equals `run_benchmark_vs_passive()`'s published final
capital, so the curves it samples are the published curves.
`run_benchmark_vs_passive()` and `run_dca_blend_analysis()` are unchanged.

| Table | Arm | Old (native frequency) | New (daily, m = 365) |
|---|---|---|---|
| 9 (2022–26 gross) | Strategy | 1.1142 (4h bars, m = 2,191.5) | 1.1151 |
| 9 | Weekly DCA | 0.5559 (weekly, m = 52) | 0.5581 |
| 9 | Lump sum | 0.5642 (4h bars) | 0.5534 |
| 10 (2022–26 net) | Strategy | 0.9442 | 0.9446 |
| 10 | Weekly DCA | 0.5529 | 0.5552 |
| 10 | Lump sum | 0.5642 | 0.5534 |
| 11 (2018–22 gross) | Strategy | 0.681 | 0.681 (0.6808) |
| 11 | Weekly DCA | 0.824 | 0.802 |
| 11 | Lump sum | 0.789 | 0.796 |
| 12 (blend) | 100% / 0% | 0.556 (weekly) | 0.558 |
| 12 | 90% / 10% | 0.581 | 0.581 (0.5814) |
| 12 | 80% / 20% | 0.607 | 0.606 |
| 12 | 70% / 30% | 0.637 | 0.632 |

No comparison changed direction. The strategy has the highest Sharpe in
2022–2026 and the lowest in 2018–2022 under both methods, and the blend still
rises at every step, so H₂ is still supported. Table 12 was recomputed as well
(decision D1, approved) so that its 100% / 0% row still equals Table 9's DCA
row (0.558). Maximum drawdown was not re-sampled; every drawdown figure is
unchanged.

### Item 3: Funding rates

Data: a one-time pull by `experimental/pull_funding_rates.py` from Binance's
public monthly archives
(`data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT`, 2021-12 to
2026-01). Each zip was verified against its published `.CHECKSUM`, giving 4,569
settlements with no gaps. `fapi.binance.com` refused the connection from this
machine, so the mirror was used instead. Saved to
`experimental/data/btcusdt_funding.csv` (sha256 `ad21493a…`) plus a manifest.

Producing function: `main()` in `experimental/funding_cost.py`. Output:
`experimental/results_funding/funding.json`. Funding at settlement s is charged
when entry close < s ≤ exit close. Per settlement, the cost is
side × rate × close_s / entry × 100, as a percentage of 1x notional.

| Quantity | Value |
|---|---|
| Settlements crossed by the 27 trades | 114 (every trade crossed at least one) |
| Paid by longs | +0.17 pp (0.1749) |
| Received by shorts | 0.29 pp (−0.2872) |
| Net | credit of 0.11 pp (−0.1123) |
| Largest single-trade funding | 0.06% (0.0586) |
| Total after 0.20% cost and funding | +25.02% (was +24.91% with cost only) |
| Wins after cost and funding | 17 / 27, one-sided p = 0.1239 (unchanged) |
| Check: inclusive entry boundary | net −0.1154 pp |

### Item 2: Trade-off figure

Produced by `experimental/plot_tradeoff.py`, which reads committed results
only (`experimental/results/oos.json` rule_side_ablation 2022_2025, and
`experimental/results_1h/main.json`). Output:
`docs/finalists/src-images/fig11_tradeoff.png` at 300 dpi; the points are
listed in `experimental/results/fig11_points.json`. Trades per year is n / 4.
Net average is the gross average minus 0.20. No new number was computed beyond
that division and subtraction, and every point matches Tables 13 and 15.

### Item 4: Binomial p for 19 / 27

The value 0.026135 does not occur anywhere in bitcoin (5): not in the docx
text, the OMML equations, the PDF, or Figure 6's image (which shows 0.0261).
Every occurrence is already 0.0261, and Appendix D already shows
3,505,699 / 134,217,728 = 0.026119. `binomial_test(19, 27)` returns
0.026119492948 (`oos.json`). No change was needed.

### Item 16: Table 8

Table 8 already shows 0.2122. `binomial_test(15, 25)` returns 0.212178. No
change was needed.

## Notes for review

- **Number of shorts.** The brief said 11 of 27 trades are shorts. Table C1
  (formerly D1) and `oos.json` (`shorts: 12`) both show **12** shorts: indices
  335, 359, 902, 1050, 1913, 2624, 3196, 3947, 5800, 6109, 6537 and 8596. The
  manuscript says 12.
- **Possible second reporting issue, not fixed (CLAUDE.md: stop and report).**
  `_run_dca_dollar_arm()` measures DCA final capital and total return at the
  last *contribution* bar (2025-12-29), not the window's last bar (2026-01-01).
  The strategy and lump-sum arms are measured at the last bar. At the last bar
  the DCA value would be $22,395.86, not $22,312.94. No comparison changes. The
  issue is recorded as OPEN in `docs/SCRATCH_RESULTS_METHODS.md` and left as
  published until reviewed.
- **Other regulators.** BSP Circular No. 1108 (2021) is cited for the
  Responsible Use paragraph, as the brief asked. The Philippine SEC also
  regulates crypto-asset service providers under its own rules; the paper
  does not mention this.
- **Fonts.** The "mid-page typeface switch" was runs set to Gungsuh, a font
  not installed here, which Word rendered as Segoe Print. One table cell was
  Cardo, and page numbers fell back to the Cambria document default. All of
  these are now Times New Roman. The cover title and abstract-form header stay
  in Bookman Old Style (decision D2), and equations stay in Cambria Math.
  Checked in the rendered PDF: no Segoe Print, Cardo or Cambria text remains.

## Verification

- The regression harness passed before and after the code change (27/27
  trades exact).
- All 36 OMML equations are preserved (36 in bitcoin (5), 36 in bitcoin (6)).
- Number-token diff between (5) and (6): every token that appeared or
  disappeared traces to an entry below. None of the superseded values remain
  (1.1142, 0.5559, 0.5642, 0.9442, 0.5529, 0.824, 0.789, 0.556, 0.637, 0.607,
  "total net return", "Table E", "Refer to page", "No published study",
  "pending", "broad temporal"). The one remaining "spot-only" is the new
  Delimitation 4 sentence saying no spot-only version was tested.
- Word render (COM, PDF export): all 31 TOC lines match the real heading pages,
  and two render passes gave identical page numbers. The three SOP notes point
  to page 13, where the Statement of the Problem starts.

## Every edit, before and after

The entries are generated from the build script's edit log, in document
order within each item. Item numbers follow the brief.

### Item 1: Sharpe at one common frequency

**replace**

Before:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026, trading USDT-M perpetual futures at 1x, unlevered, both long and short. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. That +30.31% is the simple sum of the 27 trade returns; compounding the same returns in sequence gives +34.18%, which is what produces the final capital below. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

After:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026, trading USDT-M perpetual futures at 1x, unlevered, both long and short. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. That +30.31% is the simple sum of the 27 trade returns; compounding the same returns in sequence gives +34.18%, which is what produces the final capital below. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio, measured on daily closes, from 0.558 to 0.632 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

**replace**

Before:

> Head-to-head arms. Each starts from $10,000. The strategy arm holds the full amount in cash from the first bar and compounds only at each trade exit bar, by that trade's percentage return. Each trade commits the full amount; positions are unlevered and never partly sized. Trades are modelled as BTCUSDT USDT-M perpetual futures at 1x: the strategy goes short as well as long (12 of the 27 trades are shorts), which a spot account cannot do, and its cost model uses the Binance USDT-M Futures taker fee. Between trades the arm sits in cash and earns nothing. Returns are measured per 4-hour bar and annualized with m = 6 × 365.25 = 2,191.5.

After:

> Head-to-head arms. Each starts from $10,000. The strategy arm holds the full amount in cash from the first bar and compounds only at each trade exit bar, by that trade's percentage return. Each trade commits the full amount; positions are unlevered and never partly sized. Trades are modelled as BTCUSDT USDT-M perpetual futures at 1x: the strategy goes short as well as long (12 of the 27 trades are shorts), which a spot account cannot do, and its cost model uses the Binance USDT-M Futures taker fee. Between trades the arm sits in cash and earns nothing.

**replace**

Before:

> The weekly averaging arm contributes $10,000 ÷ 210 = $47.6190 per week, or $10,000 ÷ 209 = $47.8469 in the 2018 window. Each contribution buys at that bar's close. Value at any bar is units held times the current close. Period returns are measured only at contribution bars and are net of that week's own contribution, so new money is never counted as return:

After:

> The weekly averaging arm contributes $10,000 ÷ 210 = $47.6190 per week, or $10,000 ÷ 209 = $47.8469 in the 2018 window. Each contribution buys at that bar's close. Value at any bar is units held times the current close. Returns are measured net of any contribution made in the same period, so new money is never counted as return:

**replace**

Before:

> That arm is annualized with m = 52. The lump-sum arm buys the full $10,000 at the first bar's opening price, not the close the averaging arm uses, and holds to the last bar's close. Lump-sum returns are per 4-hour bar, annualized with m = 2,191.5.

After:

> Here V_k is the arm's value at the k-th daily close and C_k is the contribution made since the previous daily close, which is zero on six days in every seven. The lump-sum arm buys the full $10,000 at the first bar's opening price, not the close the averaging arm uses, and holds to the last bar's close.

**insert**

Before:

> (none)

After:

> One clock for the Sharpe ratio. Every arm in Tables 9 to 12 is valued at each daily close, taken as the last 4-hour candle of each UTC day, and its daily returns are annualized with m = 365, since Bitcoin trades every day of the year. Measuring every arm on the same clock matters here: on 4-hour candles most of the strategy's returns are exact zeros from idle cash, while the averaging arm only changes hands weekly, so ratios taken at each arm's own frequency cannot be compared directly. Maximum drawdown is taken on each arm's own value series: per 4-hour candle for the strategy and lump-sum arms, and at the weekly contribution candles for the averaging arm and the blends.

**replace**

Before:

> Blended-sleeve model. Contributions here are 1.0 relative unit per week across 210 weeks, not dollars. Table 12 therefore has no dollar column and should not be read against the $10,000 used elsewhere. In the 100% / 0% baseline the full unit buys Bitcoin at that bar's close. At a strategy share f of 0.10, 0.20, or 0.30, the remaining share buys Bitcoin and f goes into a strategy sleeve held as cash. The sleeve compounds by each trade's return at that trade's exit bar and is never moved back into Bitcoin. Portfolio value at any bar is Bitcoin units times the close, plus the sleeve's cash. Period returns are measured at the 210 contribution bars, net of that week's contribution, and annualized with m = 52. Maximum drawdown in Table 12 includes principal and is computed on the portfolio value series at contribution bars.

After:

> Blended-sleeve model. Contributions here are 1.0 relative unit per week across 210 weeks, not dollars. Table 12 therefore has no dollar column and should not be read against the $10,000 used elsewhere. In the 100% / 0% baseline the full unit buys Bitcoin at that bar's close. At a strategy share f of 0.10, 0.20, or 0.30, the remaining share buys Bitcoin and f goes into a strategy sleeve held as cash. The sleeve compounds by each trade's return at that trade's exit bar and is never moved back into Bitcoin. Portfolio value at any bar is Bitcoin units times the close, plus the sleeve's cash. Sharpe uses the portfolio's value at every daily close, net of any contribution that day, annualized with m = 365. Maximum drawdown in Table 12 includes principal and is computed on the portfolio value series at the 210 contribution bars.

**replace**

Before:

> Table 12's 100% / 0% row and Table 9's Weekly DCA row give the same Sharpe of 0.556 and the same maximum drawdown of −27.85%, because both use the same weekly rule. The two tables meeting at their shared point is a free consistency check.

After:

> Table 12's 100% / 0% row and Table 9's Weekly DCA row give the same Sharpe of 0.558 and the same maximum drawdown of −27.85%, because both use the same weekly rule. The two tables meeting at their shared point is a free consistency check.

**replace**

Before:

> Formula 3. Sharpe ratio. Let R₁, R₂, …, R_N be an arm's per-period returns, R̄ their mean, s_R their standard deviation, and m the number of periods in a year for that arm's own reporting frequency:

After:

> Formula 3. Sharpe ratio. Let R₁, R₂, …, R_N be an arm's per-period returns, R̄ their mean, s_R their standard deviation, and m the number of periods in a year; every arm in this paper uses daily returns, so m = 365:

**replace**

Before:

> Formula 3. Sharpe ratio. Assumes a risk-free rate of zero.

After:

> Formula 3. Sharpe ratio. Assumes a risk-free rate of zero. Applied to daily returns with m = 365.

**replace**

Before:

> Sharpe

After:

> Sharpe (daily)

**replace**

Before:

> 1.1142

After:

> 1.1151

**replace**

Before:

> 0.5559

After:

> 0.5581

**replace**

Before:

> 0.5642

After:

> 0.5534

**replace**

Before:

> Sharpe

After:

> Sharpe (daily)

**replace**

Before:

> 0.9442

After:

> 0.9446

**replace**

Before:

> 0.5529

After:

> 0.5552

**replace**

Before:

> 0.5642

After:

> 0.5534

**replace**

Before:

> Sharpe

After:

> Sharpe (daily)

**replace**

Before:

> 0.824

After:

> 0.802

**replace**

Before:

> 0.789

After:

> 0.796

**replace**

Before:

> Sharpe (annualized)

After:

> Sharpe (daily, annualized)

**replace**

Before:

> 0.556

After:

> 0.558

**replace**

Before:

> 0.607

After:

> 0.606

**replace**

Before:

> 0.637

After:

> 0.632

**replace**

Before:

> Note. Time in market for the strategy is 2.6349% of candles. The summed-versus-compounded reconciliation for the strategy arm is set out in Section E. The combined strategy is the MACD, KDJ, ATR, and Smart Money Concepts strategy tested in this study. aSimple sum of the 27 trade returns, the headline figure used throughout this paper. Compounding the same returns in sequence gives +34.18%, which produces the $13,417.77 final capital.

After:

> Note. Sharpe uses each arm's daily returns, annualized with m = 365 (Section E). Time in market for the strategy is 2.6349% of candles. The summed-versus-compounded reconciliation for the strategy arm is set out in Section E. The combined strategy is the MACD, KDJ, ATR, and Smart Money Concepts strategy tested in this study. aSimple sum of the 27 trade returns, the headline figure used throughout this paper. Compounding the same returns in sequence gives +34.18%, which produces the $13,417.77 final capital.

**replace**

Before:

> Weekly buying beat the strategy on final value, $22,312.94 against $13,417.77 gross and $22,290.65 against $12,719.01 after costs. The strategy's gross Sharpe of 1.1142 exceeds buy-and-hold Bitcoin's 0.5642 over the same window, but it holds a position only 2.63% of the time against 100% for both passive arms, so this is not a like-for-like comparison.

After:

> Weekly buying beat the strategy on final value, $22,312.94 against $13,417.77 gross and $22,290.65 against $12,719.01 after costs. Measured on the same daily clock, the strategy's gross Sharpe of 1.1151 exceeds buy-and-hold Bitcoin's 0.5534 and weekly buying's 0.5581 over the same window, but it holds a position only 2.63% of the time against 100% for both passive arms, so this is not a like-for-like comparison.

**replace**

Before:

> Sharpe rises from 0.556 to 0.637, and maximum drawdown shallows from −27.85% to −23.18%. The conclusion is bounded as stated with the hypothesis: it rests on one realized price path, it carries no p-value, and it shows what a blend would have done over this window, not what it will do over another.

After:

> Sharpe rises from 0.558 to 0.632, and maximum drawdown shallows from −27.85% to −23.18%. The conclusion is bounded as stated with the hypothesis: it rests on one realized price path, it carries no p-value, and it shows what a blend would have done over this window, not what it will do over another.

**replace**

Before:

> On the comparison against passive investing, the two results point opposite ways and both must be reported. Head-to-head from equal capital, weekly buying produced roughly 1.66 times the strategy's final capital before costs and roughly 1.75 times after, and no framing changes that. On risk-adjusted shape the strategy was stronger, but it did that while invested 2.63% of the time against 100%. The blended framing is the defensible one: Sharpe and drawdown both improve steadily as the strategy's share rises from 0% to 30% inside a weekly buying plan.

After:

> On the comparison against passive investing, the two results point opposite ways and both must be reported. Head-to-head from equal capital, weekly buying produced roughly 1.66 times the strategy's final capital before costs and roughly 1.75 times after, and no framing changes that. On risk-adjusted shape, with every arm's Sharpe measured on daily returns, the strategy was stronger, but it did that while invested 2.63% of the time against 100%. The blended framing is the defensible one: Sharpe and drawdown both improve steadily as the strategy's share rises from 0% to 30% inside a weekly buying plan.

**replace**

Before:

> sharpe_ratio() and max_drawdown_pct()

After:

> run_benchmark_daily_sharpe() for Sharpe; run_dca_blend_analysis() for drawdown

**replace**

Before:

> Blended equity curve, 210 weekly contributions, 2022 to 2026

After:

> Blended portfolio value at every daily close (Sharpe, m = 365) and at the 210 weekly contribution bars (drawdown), 2022 to 2026

**replace**

Before:

> Each arm's own equity curve, $10,000 start, annualization matched per arm

After:

> Each arm's own equity curve, $10,000 start; Sharpe from daily closes with m = 365 for every arm, via run_benchmark_daily_sharpe(); results in artifacts/benchmark_daily_sharpe.json

**replace**

Before:

> Candle count. 1,461 days × 6 candles per day = 8,766 intervals, plus the final stored row = 8,767 rows. Weekly contribution. $10,000 ÷ 210 weeks = $47.6190; for the 2018 window, $10,000 ÷ 209 = $47.8469. Annualization factor for 4-hour bars. 6 × 365.25 = 2,191.5; for weekly figures it is 52. Combined window in Table 8. 25 + 27 + 4 = 56 trades; 15 + 19 + 1 = 35 wins, and 35 ÷ 56 = 62.50%; returns +21.82 + 30.31 − 3.45 = +48.68%.

After:

> Candle count. 1,461 days × 6 candles per day = 8,766 intervals, plus the final stored row = 8,767 rows. Weekly contribution. $10,000 ÷ 210 weeks = $47.6190; for the 2018 window, $10,000 ÷ 209 = $47.8469. Annualization factor for the Sharpe ratio. Every arm uses daily returns, so m = 365. Combined window in Table 8. 25 + 27 + 4 = 56 trades; 15 + 19 + 1 = 35 wins, and 35 ÷ 56 = 62.50%; returns +21.82 + 30.31 − 3.45 = +48.68%.

**replace**

Before:

> • The Sharpe ratio and maximum drawdown in Tables 9 through 12. These are computed from full equity curves, one value per bar or per contribution week, not from trade returns. The construction is fully specified in Section E, but the underlying price series is needed to rebuild them.

After:

> • The Sharpe ratio and maximum drawdown in Tables 9 through 12. Sharpe uses each arm's value at every daily close, and maximum drawdown its value per 4-hour candle or per contribution week; neither comes from trade returns alone. The construction is fully specified in Section E, but the underlying price series is needed to rebuild them.

### Item 2: Trade-off figure

**insert**

Before:

> (none)

After:

> Figure 11 places every 2022 to 2026 gate setting from Table 13 and both 1-hour versions from Table 15 on one chart: trades per year against average return per trade after the 0.20% cost. The only 4-hour setting that trades less often than the baseline, the Order Block quality filter, earns about the same per trade. Every 4-hour setting that trades more often earns less per trade, and five of them average below +0.15% per trade after costs. The 1-hour literal version trades slightly more often than the baseline and loses money per trade; the time-scaled version trades less often and also loses money. The chart is descriptive: none of the gate differences survived the Holm correction (Table 13), and the 1-hour points come from a different candle interval.

**rewrite**

Before:

> Trade Frequency and Net Return per Trade on 4-Hour and 1-Hour Candles

After:

> Trade Frequency Against Average Net Return per Trade, 2022 to 2026

**figure inserted**

Before:

> (none)

After:

> Figure 11 / Trade Frequency Against Average Net Return per Trade, 2022 to 2026 / fig11_tradeoff.png

**table row added**

Before:

> (none)

After:

> Trade-off chart | Figure 11 | main() in experimental/plot_tradeoff.py | Custom (plot only) | Points read from experimental/results/oos.json (Table 13) and experimental/results_1h/main.json (Table 15); listed in experimental/results/fig11_points.json

### Item 3: Funding rates

**insert**

Before:

> (none)

After:

> Funding. Perpetual futures also charge or pay a funding rate every eight hours, which the cost scenarios above do not include. Using Binance's published BTCUSDT funding-rate history, the 27 trades were open across 114 funding settlements. Long trades paid a combined 0.17 percentage points and short trades received 0.29, a net credit of 0.11 points. With the 0.20% round-trip cost and funding together, total return is +25.02% instead of +24.91%, the win count stays at 17 of 27, and p stays at 0.1239. No single trade's funding exceeded 0.06%, so funding does not change any result in this paper.

**table row added**

Before:

> (none)

After:

> Funding: 114 settlements, net credit 0.11 points, +25.02% after costs and funding | SOP 1 subsection | main() in experimental/funding_cost.py | Custom | Baseline 27; experimental/data/btcusdt_funding.csv (sha256 ad21493a…), Binance monthly funding archives; results in experimental/results_funding/funding.json

### Item 5: Spot vs futures

**replace**

Before:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. That +30.31% is the simple sum of the 27 trade returns; compounding the same returns in sequence gives +34.18%, which is what produces the final capital below. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

After:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026, trading USDT-M perpetual futures at 1x, unlevered, both long and short. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. That +30.31% is the simple sum of the 27 trade returns; compounding the same returns in sequence gives +34.18%, which is what produces the final capital below. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

**replace**

Before:

> Head-to-head arms. Each starts from $10,000. The strategy arm holds the full amount in cash from the first bar and compounds only at each trade exit bar, by that trade's percentage return. Each trade commits the full amount; positions are unlevered and never partly sized. Between trades the arm sits in cash and earns nothing. Returns are measured per 4-hour bar and annualized with m = 6 × 365.25 = 2,191.5.

After:

> Head-to-head arms. Each starts from $10,000. The strategy arm holds the full amount in cash from the first bar and compounds only at each trade exit bar, by that trade's percentage return. Each trade commits the full amount; positions are unlevered and never partly sized. Trades are modelled as BTCUSDT USDT-M perpetual futures at 1x: the strategy goes short as well as long (12 of the 27 trades are shorts), which a spot account cannot do, and its cost model uses the Binance USDT-M Futures taker fee. Between trades the arm sits in cash and earns nothing. Returns are measured per 4-hour bar and annualized with m = 6 × 365.25 = 2,191.5.

**replace**

Before:

> 1. The study does not model leverage or margin, and reports unlevered returns throughout. The engine checks every exit on candle closes rather than on price movement inside a candle, so a leverage model on top would inherit that limit and report liquidations it cannot actually establish.

After:

> 1. Trades are modelled as USDT-M perpetual futures at 1x, unlevered; the study does not model leverage or margin. Funding payments were estimated from Binance's published rate history (SOP 1), not taken from a live account. The engine checks every exit on candle closes rather than on price movement inside a candle, so a leverage model on top would inherit that limit and report liquidations it cannot actually establish.

**replace**

Before:

> 4. No leverage or margin is modeled anywhere in this study. All returns reported are unlevered, spot-only returns.

After:

> 4. All trades are modelled as USDT-M perpetual futures at 1x, unlevered. No leverage or margin is modelled, and no spot-only version was tested; a spot account could not take the 12 short trades.

### Item 6: Order Block citation

**replace**

Before:

> When a very large buyer or seller pushes price hard in one direction, it leaves a mark on the chart. There is usually a price area where the large position was built before the move began. Researchers call these areas Order Blocks (Bessembinder et al., 2009). Large traders split big orders into pieces and time them, which moves both resting orders and short-term price (Brolley & Cimon, 2020; Díaz & Escribano, 2020). Smart Money Concepts, the trading framework this study borrows from, is built on the same idea (Biais et al., 2005). The strategy here waits for price to return to one of these areas, checks whether the pullback is losing strength, then enters, sizes its risk to current volatility, and exits when momentum fades.

After:

> When a very large buyer or seller pushes price hard in one direction, it leaves a mark on the chart. There is usually a price area where the large position was built before the move began. Smart Money Concepts, the practitioner trading framework this study borrows from, calls these areas Order Blocks (LuxAlgo, 2022). The term comes from trading practice, not from academic research. Academic work does support the narrower idea underneath it: large traders split big orders into pieces and time them, and this moves both resting orders and short-term price (Bessembinder et al., 2009; Biais et al., 2005; Brolley & Cimon, 2020; Díaz & Escribano, 2020). The strategy here waits for price to return to one of these areas, checks whether the pullback is losing strength, then enters, sizes its risk to current volatility, and exits when momentum fades.

**replace**

Before:

> None of these three tools accounts for the influence of very large participants. Smart Money Concepts addresses this by reading raw price structure for institutional footprints instead of statistical averages, on the premise that large entities engineer price moves to reach pools of resting orders and fill large positions before reversing (Bessembinder et al., 2009). Order Blocks are detected here at two levels, one with a 50-candle lookback for larger swings and one with a 5-candle lookback for smaller structure, and each is judged against five quality criteria defined in Section D.

After:

> None of these three tools accounts for the influence of very large participants. Smart Money Concepts tries to address this by reading raw price structure for signs of large participants instead of statistical averages. Its premise, as practitioners state it, is that large traders need resting orders on the other side to fill big positions, so price tends to come back to the area where such a position was built (LuxAlgo, 2022). That premise is a trading heuristic rather than an established research finding; the studies cited above support only the narrower point that large orders are split and timed. Order Blocks are detected here at two levels, one with a 50-candle lookback for larger swings and one with a 5-candle lookback for smaller structure, and each is judged against five quality criteria defined in Section D.

### Item 7: Sum vs compounded

**replace**

Before:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

After:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. That +30.31% is the simple sum of the 27 trade returns; compounding the same returns in sequence gives +34.18%, which is what produces the final capital below. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

### Item 8: Gross vs net labels

**replace**

Before:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026. It made 27 trades at a 70.37% win rate and a total net return of +30.31%, with a one-sided exact binomial p of 0.0261. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

After:

> Region IIIABSTRACTThis study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026. It made 27 trades at a 70.37% win rate and a total return before costs of +30.31%, with a one-sided exact binomial p of 0.0261. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. Two pre-registered follow-up analyses were added. Switching off any one of the four indicator gates lowered average return per trade in both test windows, but no difference survived a Holm correction for multiple comparisons. On 1-hour candles the unchanged rules made 31 trades and lost 0.18% per trade after costs (one-sided p = 0.696), so a faster timeframe did not keep the edge. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

**replace**

Before:

> 1. How effectively does the combined MACD, KDJ, ATR, and Smart Money Concepts strategy predict short-term Bitcoin price movements, as measured by win rate, total net return, and average return per trade?

After:

> 1. How effectively does the combined MACD, KDJ, ATR, and Smart Money Concepts strategy predict short-term Bitcoin price movements, as measured by win rate, total return, and average return per trade?

**replace**

Before:

> Dependent variables. For the strategy's own trades: win rate, total net return, average return per trade, and return concentration. For the comparison against passive options: total return and final capital from a fixed start, annualized Sharpe ratio, maximum drawdown, and time in market.

After:

> Dependent variables. For the strategy's own trades: win rate, total return before and after costs, average return per trade, and return concentration. For the comparison against passive options: total return and final capital from a fixed start, annualized Sharpe ratio, maximum drawdown, and time in market.

**replace**

Before:

> Answer: yes before costs, no after them. The strategy won 70.37% of 27 trades for +30.31% total net return at p = 0.0261, and the bootstrap interval on total return excludes zero. Charging a realistic 0.20% round trip moves p to 0.1239, so H₁ is not supported once costs a real trader would pay are charged.

After:

> Answer: yes before costs, no after them. The strategy won 70.37% of 27 trades for a +30.31% total return before costs at p = 0.0261, and the bootstrap interval on total return excludes zero. Charging a realistic 0.20% round trip moves p to 0.1239, so H₁ is not supported once costs a real trader would pay are charged.

**replace**

Before:

> Total net return

After:

> Total return, before costs

**replace**

Before:

> Bootstrap interval. A bootstrap of 10,000 resamples, drawn at the original sample size of 27 with a fixed seed of 42, gives a point estimate of +30.3065% total net return, which differs from the observed sum of +30.3064% only in the fourth decimal. The 95% confidence interval is [+5.9866%, +54.9866%]. It is wide but excludes zero, and 99.25% of resampled totals were positive. The matching interval for average return per trade is [+0.2217%, +2.0365%]. The companion website recomputes the same bootstrap in the browser at 2,000 resamples and lands on [+7.48%, +54.46%]. That is separate TypeScript code with its own random number generator, and the gap between the two intervals was traced to the resample count alone. They are kept separate rather than merged, because the website's independence is what makes the cross-check worth anything.

After:

> Bootstrap interval. A bootstrap of 10,000 resamples, drawn at the original sample size of 27 with a fixed seed of 42, gives a point estimate of +30.3065% total return, which differs from the observed sum of +30.3064% only in the fourth decimal. The 95% confidence interval is [+5.9866%, +54.9866%]. It is wide but excludes zero, and 99.25% of resampled totals were positive. The matching interval for average return per trade is [+0.2217%, +2.0365%]. The companion website recomputes the same bootstrap in the browser at 2,000 resamples and lands on [+7.48%, +54.46%]. That is separate TypeScript code with its own random number generator, and the gap between the two intervals was traced to the resample count alone. They are kept separate rather than merged, because the website's independence is what makes the cross-check worth anything.

**replace**

Before:

> Over January 2022 to January 2026 the strategy made 27 trades at a 70.37% win rate for +30.31% total net return, and weekly dollar-cost averaging still beat it on final value from equal capital, $22,312.94 against $13,417.77. The defensible use for this rule set is as a small sleeve inside a weekly buying plan, not as a replacement for one.

After:

> Over January 2022 to January 2026 the strategy made 27 trades at a 70.37% win rate for a +30.31% total return before costs, and weekly dollar-cost averaging still beat it on final value from equal capital, $22,312.94 against $13,417.77. The defensible use for this rule set is as a small sleeve inside a weekly buying plan, not as a replacement for one.

**replace**

Before:

> Note. Return % is the trade's net percentage return. Dsp = displacement, Lrg = large origin candle, FVG = Fair Value Gap, Swp = liquidity sweep, Vol = volume expansion. Idx is the entry candle index. Bars is the holding period in 4-hour candles, so each exit time equals its entry time plus four hours times the Bars value. Exit reason is the first exit condition satisfied under the priority order in Figure 5. q is the sum of the five criterion flags.

After:

> Note. Return % is the trade's percentage return before costs. Dsp = displacement, Lrg = large origin candle, FVG = Fair Value Gap, Swp = liquidity sweep, Vol = volume expansion. Idx is the entry candle index. Bars is the holding period in 4-hour candles, so each exit time equals its entry time plus four hours times the Bars value. Exit reason is the first exit condition satisfied under the priority order in Figure 5. q is the sum of the five criterion flags.

**replace**

Before:

> Win rate. Count the positive values in the Return % column. There are 19, and 19 ÷ 27 = 0.703703, so 70.37%. Total net return. Add all 27 values: +30.3064%, reported as +30.31%. Average return per trade. 30.3064 ÷ 27 = 1.12246, so +1.1225%. Standard deviation. Subtract 1.1225 from each return, square each result, add them, divide by 26, and take the square root. This gives 2.4101, reported as 2.41%. The divisor is 26, not 27, because this is the sample standard deviation.

After:

> Win rate. Count the positive values in the Return % column. There are 19, and 19 ÷ 27 = 0.703703, so 70.37%. Total return before costs. Add all 27 values: +30.3064%, reported as +30.31%. Average return per trade. 30.3064 ÷ 27 = 1.12246, so +1.1225%. Standard deviation. Subtract 1.1225 from each return, square each result, add them, divide by 26, and take the square root. This gives 2.4101, reported as 2.41%. The divisor is 26, not 27, because this is the sample standard deviation.

### Item 9: Soften the novelty claim

**replace**

Before:

> Earlier research has tested MACD, KDJ, and other technical rules alone, or at most in pairs (Chong & Ng, 2008; Corbet et al., 2019; Lv et al., 2017). No published study tests MACD, an adaptive KDJ exit, a dual-ATR risk framework, and Order Block detection all together, in one backtest, on cryptocurrency. That is the real gap. It is not whether any one of these tools works; each has already been shown to work alone. The open question is what combining them does to the result, for better or worse, measured against the passive options an ordinary participant would otherwise use. This study fills that gap.

After:

> Earlier research has tested MACD, KDJ, and other technical rules alone, or at most in pairs (Chong & Ng, 2008; Corbet et al., 2019; Lv et al., 2017). We found no study that tests MACD, an adaptive KDJ exit, a dual-ATR risk framework, and Order Block detection all together, in one backtest, on cryptocurrency. That is the real gap. It is not whether any one of these tools works; each has already been shown to work alone. The open question is what combining them does to the result, for better or worse, measured against the passive options an ordinary participant would otherwise use. This study fills that gap.

**replace**

Before:

> Earlier research has tested MACD, KDJ, and other technical rules alone, or at most in pairs (Chong & Ng, 2008; Corbet et al., 2019; Lv et al., 2017). We found no study that tests MACD, an adaptive KDJ exit, a dual-ATR risk framework, and Order Block detection all together, in one backtest, on cryptocurrency. That is the real gap. It is not whether any one of these tools works; each has already been shown to work alone. The open question is what combining them does to the result, for better or worse, measured against the passive options an ordinary participant would otherwise use. This study fills that gap.

After:

> Earlier research has tested MACD, KDJ, and other technical rules alone, or at most in pairs (Chong & Ng, 2008; Corbet et al., 2019; Lv et al., 2017). We found no study that tests MACD, an adaptive KDJ exit, a dual-ATR risk framework, and Order Block detection all together, in one backtest, on cryptocurrency. That is the real gap. It is not whether any one of these tools works; each has already been shown to work alone. The open question is what combining them does to the result, for better or worse, measured against the passive options an ordinary participant would otherwise use. This study addresses that gap.

### Item 10: Remove the literature comparison

**delete**

Before:

> Placed next to the literature this study cites, the headline numbers hold up. Chong and Ng (2008) found MACD produced returns higher than buy-and-hold in most of the cases they tested on the London Stock Exchange. Navarro and Navarro (2023) found only about 35% to 51% of the Philippine stocks they tested were consistently profitable under MACD alone, depending on the setting used. This study's combined strategy, which uses MACD as one confirmation signal among several rather than as a strategy on its own, reached a 70.37% win rate and a +30.31% total net return over 27 trades. On the KDJ side, Wu and Diao (2015) and Dai et al. (2020) both reported statistically significant predictive value for KDJ-family indicators, without building those signals into a full entry-and-exit strategy with real risk management. This study did, and the result sits above the single-indicator figures those studies report. That comparison is not proof the combination itself drove the improvement; Limitation 2 below already flags how much of the return sits in three trades. It is offered as honest context for where these numbers sit next to the prior literature, not as a stronger claim than the data support.

After:

> (none)

### Item 11: Precise H₁

**replace**

Before:

> H₁: The combined strategy produces a statistically significant win rate above 50% on BTC/USDT 4-hour data across all market conditions over a broad temporal scope.

After:

> H₁: The combined strategy produces a statistically significant win rate above 50% on BTC/USDT 4-hour candles over the January 2022 to January 2026 test window.

### Item 12: Limitation 10

**rewrite**

Before:

> 10. This study's strategy design, code, and statistics were not reviewed by a licensed financial professional or a quantitative-trading practitioner before submission. Verification was internal only, through the regression harness described in Appendix A and the hand recomputation of every headline number in Appendix D. The codebase behind the reported figures will be independently verified by a subject-matter expert in the days after submission, and the results should be read as pending that verification.

After:

> 10. This study's strategy design, code, and statistics were not reviewed by a licensed financial professional or a quantitative-trading practitioner. Verification was internal only, through the regression harness described in Appendix A and the hand recomputation of every headline number in Appendix D.

### Item 13: Trade-off framing

**rewrite**

Before:

> The two follow-up analyses explain why the strategy trades so rarely and suggest that this is not easy to fix. Each indicator gate removes trades, and every removal tested lowered average return per trade in both windows, although none of those differences is large enough, at this sample size, to be separated from chance after nine tests. Loosening the rule buys trades by giving up return per trade, and the one loosened setting that raised total return, K-acceleration alone, did so with nearly six times the drawdown and reversed on the formulation window.

After:

> The two follow-up analyses bear on why the strategy trades so rarely. Every gate removal lowered average return per trade in both windows, but with nine comparisons none of those differences survived the Holm correction. The pre-registered 1-hour test produced only four more trades than the 4-hour rules and a negative average return per trade after costs (one-sided p = 0.696). These results are consistent with a trade-off between how often the strategy trades and how much it earns per trade (Figure 11), but they do not establish one. The one loosened setting that raised total return, K-acceleration alone, did so with nearly six times the drawdown and reversed on the formulation window. The low trade count of 27 is the main reason the win-rate significance is fragile: two marginal trades are enough to move p from 0.0261 to 0.1239.

**replace**

Before:

> 6. Trade frequency is low, at roughly 0.56 trades per month, which limits how fast genuinely forward-looking evidence can build up. The two attempts in SOP 3 to raise it both lowered return per trade.

After:

> 6. Trade frequency is low, at roughly 0.56 trades per month, which limits how fast genuinely forward-looking evidence can build up. Neither attempt in SOP 3 to raise it kept the return per trade: every gate removal lowered the average, though no difference survived the Holm correction, and the 1-hour version lost money per trade after costs.

**replace**

Before:

> The third research question asked, through two pre-registered follow-up analyses, whether the strategy could trade more often. Switching off any one indicator gate lowered average return per trade in both windows, with no difference surviving the Holm correction. Running the unchanged rules on 1-hour candles gave 31 trades with an average loss of 0.179% per trade after costs at a one-sided p of 0.696, so the pre-registered test found no positive return, and on that timeframe the gates picked trades no better than chance.

After:

> The third research question asked, through two pre-registered follow-up analyses, whether the strategy could trade more often. Switching off any one indicator gate lowered average return per trade in both windows, with no difference surviving the Holm correction. Running the unchanged rules on 1-hour candles gave 31 trades with an average loss of 0.179% per trade after costs at a one-sided p of 0.696, so the pre-registered test found no positive return, and on that timeframe the gates picked trades no better than chance. Taken together, these results are consistent with a trade-off between trade frequency and return per trade, without establishing one, and the small sample of 27 trades is the main reason the win-rate result is fragile.

### Item 14: Page notes

**replace**

Before:

> Note. Refer to page  for the question being answered.

After:

> Note. The research questions are stated on page 13, under Statement of the Problem.

**replace**

Before:

> Note. Refer to page  for the question being answered.

After:

> Note. The research questions are stated on page 13, under Statement of the Problem.

**replace**

Before:

> Note. Refer to page  for the question being answered.

After:

> Note. The research questions are stated on page 13, under Statement of the Problem.

### Item 15: Appendix labels

**replace**

Before:

> Appendix D

After:

> Appendix C

**replace**

Before:

> Table D1

After:

> Table C1

**replace**

Before:

> This appendix exists so a reader with nothing but a calculator and Table D1 can check the paper. Every number below is derived only from those 27 rows. At the end is a short list of the numbers that cannot be checked this way, and what data would be needed to check them.

After:

> This appendix exists so a reader with nothing but a calculator and Table C1 can check the paper. Every number below is derived only from those 27 rows. At the end is a short list of the numbers that cannot be checked this way, and what data would be needed to check them.

**replace**

Before:

> The Total return column of Table 9 adds the 27 returns. The Final capital column compounds them. To compound, divide each return by 100, add 1, and multiply all 27 results together. That product is 1.341777, so the compounded return is +34.18% and $10,000 × 1.341777 = $13,417.77. For the net-of-cost row in Table 10, subtract 0.20 from each return first, then compound the same way. The product is 1.271900, giving +27.19% and $12,719.00. The paper reports $12,719.01; the one-cent gap comes from Table D1 rounding each return to four decimals while the engine carries more.

After:

> The Total return column of Table 9 adds the 27 returns. The Final capital column compounds them. To compound, divide each return by 100, add 1, and multiply all 27 results together. That product is 1.341777, so the compounded return is +34.18% and $10,000 × 1.341777 = $13,417.77. For the net-of-cost row in Table 10, subtract 0.20 from each return first, then compound the same way. The product is 1.271900, giving +27.19% and $12,719.00. The paper reports $12,719.01; the one-cent gap comes from Table C1 rounding each return to four decimals while the engine carries more.

**replace**

Before:

> Add the Bars column of Table D1. The total is 231 candles held. The window has 8,767 candles, and 231 ÷ 8,767 = 0.026349, which is the 2.6349% in the note to Table 9, reported as 2.63%.

After:

> Add the Bars column of Table C1. The total is 231 candles held. The window has 8,767 candles, and 231 ÷ 8,767 = 0.026349, which is the 2.6349% in the note to Table 9, reported as 2.63%.

**replace**

Before:

> Table 5 splits the same 27 trades by the year of the entry time in Table D1. Nothing else is needed.

After:

> Table 5 splits the same 27 trades by the year of the entry time in Table C1. Nothing else is needed.

**replace**

Before:

> Rebuilding Table 5 from Table D1

After:

> Rebuilding Table 5 from Table C1

**replace**

Before:

> Rebuilding Table 4 from Table D1

After:

> Rebuilding Table 4 from Table C1

**replace**

Before:

> Note. The smallest positive return in Table D1 is +0.1196 at index 7938, then +0.1264 at 8188, +0.2507 at 2859, and +0.3779 at 5825. That ordering decides which trades flip at each cost level. The p-value for each row comes from E2.

After:

> Note. The smallest positive return in Table C1 is +0.1196 at index 7938, then +0.1264 at 8188, +0.2507 at 2859, and +0.3779 at 5825. That ordering decides which trades flip at each cost level. The p-value for each row comes from E2.

**replace**

Before:

> Pearson's r uses the Bars column and the Return % column of Table D1. The mean of Bars is 231 ÷ 27 = 8.5556 candles and the mean of Return % is 1.1225. For each trade, multiply the two differences from their means and add the 27 products. Divide that by the square root of the sum of squared Bars differences times the sum of squared return differences. The result is r = 0.490698, reported as +0.4907. The t-value follows from r alone:

After:

> Pearson's r uses the Bars column and the Return % column of Table C1. The mean of Bars is 231 ÷ 27 = 8.5556 candles and the mean of Return % is 1.1225. For each trade, multiply the two differences from their means and add the 27 products. Divide that by the square root of the sum of squared Bars differences times the sum of squared return differences. The result is r = 0.490698, reported as +0.4907. The t-value follows from r alone:

**replace**

Before:

> The following numbers need data or computation that Table D1 does not contain. They are listed so no reader assumes an omission.

After:

> The following numbers need data or computation that Table C1 does not contain. They are listed so no reader assumes an omission.

**replace**

Before:

> E1. Win rate, total return, average, and standard deviation

After:

> D1. Win rate, total return, average, and standard deviation

**replace**

Before:

> E2. The binomial p-value

After:

> D2. The binomial p-value

**replace**

Before:

> E3. Final capital from $10,000

After:

> D3. Final capital from $10,000

**replace**

Before:

> E4. Time in market

After:

> D4. Time in market

**replace**

Before:

> E5. The calendar regime table

After:

> D5. The calendar regime table

**replace**

Before:

> E6. The three-trade concentration

After:

> D6. The three-trade concentration

**replace**

Before:

> E7. The six cost scenarios

After:

> D7. The six cost scenarios

**replace**

Before:

> E8. The correlation and its t-value

After:

> D8. The correlation and its t-value

**replace**

Before:

> E9. Dataset and schedule arithmetic

After:

> D9. Dataset and schedule arithmetic

**replace**

Before:

> E10. What cannot be checked by hand, and why

After:

> D10. What cannot be checked by hand, and why

**replace**

Before:

> Table E1

After:

> Table D1

**replace**

Before:

> Table E2

After:

> Table D2

**replace**

Before:

> Table E3

After:

> Table D3

**replace**

Before:

> with df = n − 2 = 25. Spearman's ρ uses the same two columns after replacing each value with its rank, giving ρ = 0.479728, reported as +0.4797. The p-values attached to both, 0.0094 and 0.0113, come from SciPy and are not hand-computable; see E10.

After:

> with df = n − 2 = 25. Spearman's ρ uses the same two columns after replacing each value with its rank, giving ρ = 0.479728, reported as +0.4797. The p-values attached to both, 0.0094 and 0.0113, come from SciPy and are not hand-computable; see D10.

**replace**

Before:

> Note. The smallest positive return in Table C1 is +0.1196 at index 7938, then +0.1264 at 8188, +0.2507 at 2859, and +0.3779 at 5825. That ordering decides which trades flip at each cost level. The p-value for each row comes from E2.

After:

> Note. The smallest positive return in Table C1 is +0.1196 at index 7938, then +0.1264 at 8188, +0.2507 at 2859, and +0.3779 at 5825. That ordering decides which trades flip at each cost level. The p-value for each row comes from D2.

### Item 17: Fonts

**fonts**

Before:

> Gungsuh/Cardo runs (rendered as Segoe Print), Cambria document default

After:

> Times New Roman everywhere except the cover title and abstract-form header (Bookman Old Style) and equations (Cambria Math)

### Item 18: Table of Contents

**toc**

Before:

> Introduction………………………………………………………………………………………..6
> Significance of the Study………………………………………………………………………...13
> Statement of the Problem………………………………………………………………….13
> Framework……………………………………………………………………………………….16
> A. Research Design………………………………………………………………………..16
> B. Materials and Sources…………………………………………………………………..17
> C. Variables………………………………………………………………………………..19
> D. Strategy Formulas……………………………………………………………………...20
> E. Portfolio Construction and Contribution Schedule…………………………………….27
> F. Data Analysis…………………………………………………………………………...28
> Findings………………………………………………………………………………………….33
> Answers to SOP 1 and Hypothesis H₁33
> Answers to SOP 2 and Hypothesis H₂39
> Answers to SOP 3…………………………………………………………………………43
> Conclusions……………………………………………………………………………………...47
> Limitations………………………………………………………………………………...49
> Delimitations………………………………………………………………………………52
> Summary and Conclusion…………………………………………………………………53
> References……………………………………………………………………………………….55
> Appendix A……………………………………………………………………………………...58
> Statistical Provenance of Every Reported Number……………………………………….58
> Appendix B………………………………………………………………………………………62
> Source Form of Every Formula Written for This Study…………………………………..62
> Appendix C………………………………………………………………………………………63
> Complete Trade Log for the Primary Window…………………………………………….63
> Appendix D……………………………………………………………………………………...66
> Recomputing Every Number by Hand…………………………………………………….66

After:

> Introduction6
> Significance of the Study12
> Statement of the Problem13
> Framework16
> A. Research Design16
> B. Materials and Sources17
> C. Variables19
> D. Strategy Formulas20
> E. Portfolio Construction and Contribution Schedule26
> F. Data Analysis28
> Findings33
> Answers to SOP 1 and Hypothesis H₁33
> Answers to SOP 2 and Hypothesis H₂39
> Answers to SOP 342
> Conclusions48
> Limitations50
> Delimitations53
> Summary and Conclusion54
> References56
> Appendix A60
> Statistical Provenance of Every Reported Number60
> Appendix B64
> Source Form of Every Formula Written for This Study64
> Appendix C66
> Complete Trade Log for the Primary Window66
> Appendix D69
> Recomputing Every Number by Hand69
> Appendix E75
> ISEF Forms75
> Appendix F76
> Curricula Vitae76

### Item 19: Responsible Use

**insert**

Before:

> (none)

After:

> Responsible use. This paper is a research report, not investment advice, and nothing in it recommends buying, selling, or holding Bitcoin or any other asset. Cryptocurrency carries a high risk of loss: over the window studied here, a single purchase of Bitcoin at one point stood 67.21% below its earlier peak (Table 9). In the Philippines, platforms that exchange or hold cryptocurrency for customers are regulated by the Bangko Sentral ng Pilipinas as virtual asset service providers (Bangko Sentral ng Pilipinas, 2021). Anyone who chooses to trade should use a registered platform and only money they can afford to lose.

**insert**

Before:

> (none)

After:

> Bangko Sentral ng Pilipinas. (2021). Guidelines for virtual asset service providers (Circular No. 1108, Series of 2021). https://www.bsp.gov.ph/Regulations/Issuances/2021/1108.pdf

### Item 20: Placeholder appendices

**insert**

Before:

> (none)

After:

> [INSERT SCANNED FORMS HERE]

**insert**

Before:

> (none)

After:

> Signed ISEF forms for this project.

**appendix added**

Before:

> (none)

After:

> Appendix E / ISEF Forms

**insert**

Before:

> (none)

After:

> [INSERT SCANNED FORMS HERE]

**insert**

Before:

> (none)

After:

> Curricula vitae of the researchers and the research adviser.

**appendix added**

Before:

> (none)

After:

> Appendix F / Curricula Vitae
