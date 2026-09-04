@TITLEPAGE
@TITLE HEDGE: A Rule-Based Bitcoin Trading Strategy Tested Against Dollar-Cost Averaging, 2022 to 2026

@H1 Abstract

This study tests a rule-based Bitcoin trading strategy against the two things an ordinary investor would otherwise do: buy a fixed amount every week, or buy once and hold. Every rule and parameter was set by eye from BTC/USDT 4-hour charts covering January 2018 to January 2022, then frozen before the reported window was measured. The strategy was run candle by candle over 8,767 four-hour candles from January 2022 to January 2026. It made 27 trades at a 70.37% win rate and a total net return of +30.31%, with a one-sided exact binomial p of 0.0261. A bootstrap of 10,000 resamples placed the 95% confidence interval on total return at [+5.9866%, +54.9866%], which excludes zero. Charging a realistic 0.20% round-trip cost cut the win rate to 62.96% and raised p to 0.1239, so the significance did not survive. From an equal $10,000 start, weekly buying reached $22,312.94 against the strategy's $13,417.77, a clear loss on final value, although the strategy held a position only 2.63% of the time. Directing 10%, 20%, and 30% of weekly contributions into the strategy raised the Sharpe ratio from 0.556 to 0.637 and the Sortino ratio from 0.886 to 1.032, and made maximum drawdown shallower, from −27.85% to −23.18%. A forward test from January to July 2026 returned −3.45% over four trades. One data-leakage bug was found during verification and fixed. Costs decide the verdict.

@KEYWORDS Keywords: Bitcoin, algorithmic trading, backtesting, dollar-cost averaging, Smart Money Concepts, technical analysis

@TOC

@H1 Introduction

Money has moved online over the past thirty years. Faster internet, cheaper phones, and digital payments have closed much of the distance between ordinary people and financial services. The World Bank surveyed 123 economies and found that 76 percent of adults held a formal financial account by 2021, up from 51 percent in 2011, with most of that growth coming from mobile money and e-wallets in developing countries (Demirgüç-Kunt et al., 2022). For many people these tools are not an addition to banking. They are the only banking they have.

Cryptocurrency is one of the largest products of this shift. A cryptocurrency is a digital asset whose ownership is recorded on a blockchain, a shared public ledger kept by many computers instead of one bank. Decentralized exchanges let people trade these assets directly, with no bank or broker in between, so all a person needs is a phone and an internet connection (Schär, 2021). In places like Magalang, Pampanga, where bank branches are few, crypto platforms are often a person's first door into global markets.

Bitcoin launched in 2009 as the first fully decentralized cryptocurrency and is still the most traded by value and volume (Nakamoto, 2008). It trades every hour of every day, has no circuit breakers to pause it, and has neither a central bank nor company earnings behind it, so its swings are larger than those of traditional assets. That volatility is both the main risk and the main opportunity.

When a very large buyer or seller pushes price hard in one direction, it leaves a mark on the chart. There is usually a price area where the large position was built before the move began. Market microstructure research, the study of how orders reach a market and move its price, calls these areas Order Blocks (Bessembinder et al., 2009). Studies of order flow show that large participants split big orders into pieces and time them, which affects both resting orders and short-term direction (Brolley & Cimon, 2020; Díaz & Escribano, 2020). Smart Money Concepts, the trading framework this study borrows from, rests on the same ideas (Biais et al., 2005). The strategy here waits for price to return to one of these areas, checks whether the pullback is losing strength, then enters, sizes its risk to current volatility, and exits when momentum fades.

Because Bitcoin trades non-stop and reacts fast to sentiment, company fundamentals are of little use for short-term decisions. Traders use technical analysis instead, forecasting price from past price and volume (Svogun & Bazán-Palomino, 2022). It rests on two ideas: price already reflects what the market knows, and people repeat their behaviour, so chart patterns recur (Fang et al., 2014). Technical rules have been shown to carry real predictive value in liquid crypto markets over short horizons (Corbet et al., 2019).

This study combines three families of tools. Each answers a different question about the same price series: which way price is likely to move, how hard it is moving, and where the large participants have already acted.

The first is MACD, short for Moving Average Convergence Divergence. It compares a fast moving average against a slow one and plots the gap between them as a histogram, showing whether the force behind a move is building or fading (Chong & Ng, 2008). MACD does not predict a reversal; it reports current momentum. A twelve-year study of the Philippine stock market found a MACD strategy produced measurable results there (Navarro & Navarro, 2023). Here the slope of the histogram is the momentum check: below zero but rising favours a long entry, and above zero but falling favours a short entry.

The second is the KDJ oscillator, which moves within a fixed range, so readings near the top or bottom flag unusual conditions. KDJ is a stochastic oscillator with a third line, J, added to make disagreements between price and momentum easier to see. It starts from the Raw Stochastic Value, which measures where the current close sits inside the high-to-low range of recent candles. K and D smooth that value, and J is three times K minus two times D, which makes it react faster than either (Wu & Diao, 2015). KDJ indicators carry significant predictive power for returns (Dai et al., 2020) and are widely used as an early warning of a reversal (Lv et al., 2017).

This study uses two separate KDJ calculations, and telling them apart matters. The first is one fixed nine-period series computed across the whole dataset. It decides whether to enter a trade and never changes from trade to trade. The second runs only after a trade is open, to time one kind of exit. Only this second one has a window length that adapts, and it adapts to the number of candles between the Order Block that triggered the trade and the entry candle. Across the 27 trades that window ranged from 14 to 439 candles, with a middle value of 74. This ties exit timing to the structure that caused the trade while keeping the entry decision on a fixed footing.

The third tool measures how hard price is moving rather than which way. The Average True Range, introduced by Wilder (1978), fills that gap. True range is the largest of three quantities: the current high minus the current low, the gap from the current high to the previous close, or the gap from the current low to the previous close. ATR averages that over a window and has no bullish or bearish opinion. Here a 14-period ATR sets the stop-loss distance, the trailing exit, and one profit-taking exit, while a 200-period ATR gives a long-run volatility baseline used to filter market conditions and judge Order Blocks. Two windows mean risk settings scale with current conditions instead of sitting at fixed levels.

None of these three tools accounts for the influence of very large participants. Smart Money Concepts addresses this by reading raw price structure for institutional footprints instead of statistical averages, on the premise that large entities engineer price moves to reach pools of resting orders and fill large positions before reversing (Bessembinder et al., 2009). Order Blocks are detected here at two levels, one with a 50-candle lookback for larger swings and one with a 5-candle lookback for smaller structure, and each is judged against five quality criteria defined in Section D.

Earlier research has tested MACD, KDJ, and other technical rules alone or in partial combinations (Chong & Ng, 2008; Corbet et al., 2019; Lv et al., 2017). No published study combines MACD momentum confirmation, an adaptive KDJ exit, a dual-ATR risk framework, and Order Block detection in one backtest on cryptocurrency, and then measures the result against the passive options an ordinary participant would otherwise use. This study fills that gap.

A strategy is only interesting next to what a person would otherwise do. For most retail participants the realistic alternative is not another algorithm. It is dollar-cost averaging, buying a fixed amount on a fixed schedule regardless of price, or one lump-sum purchase held without further action. Dollar-cost averaging is the default in the recurring-buy feature of most exchanges and savings apps. Constantinides (1979) showed it is suboptimal under standard expected-utility assumptions, because delaying investment gives up expected return. Statman (1995) argued it survives anyway because it answers behavioural needs, such as regret aversion and a desire for self-control, that an optimal policy does not. Theoretically weak but behaviourally dominant is exactly what makes it the right benchmark for a study aimed at ordinary participants. This paper therefore runs the strategy against weekly dollar-cost averaging and lump-sum buy-and-hold over the same window from the same starting capital, then asks the question closer to real use: not whether the strategy replaces a weekly buying plan, but whether putting part of that plan into the strategy improves it.

The design separates the period used to build the rules from the period used to test them. Every rule, parameter, and threshold was set by eye from BTC/USDT charts over January 2018 to January 2022, drawing on prior trading experience. That period was examined visually. It was never fed into a search, a sweep, or an optimizer, and no parameter was adjusted to improve a measured outcome. The primary findings come from January 2022 to January 2026, which the rules were not built against.

@H2 Significance of the Study

Access to financial services in the Philippines has grown far faster than participation in financial markets. Account ownership among Filipino adults rose from 29 percent in 2019 to 56 percent in 2021, driven mostly by e-money accounts, which rose from 8 percent to 36 percent (Bangko Sentral ng Pilipinas, 2022). Over the same two years, investment uptake excluding contributions to pension schemes fell from 15 percent to 10 percent. More Filipinos can reach a market than ever before, and fewer of them are actually invested in one.

That gap is what this study speaks to. Reproducible, openly documented research on rule-based trading gives a first-time participant something better than a screenshot of somebody's returns: a full set of rules, the data they were tested on, and an honest account of where they failed. The work supports United Nations Sustainable Development Goal 8, on inclusive economic growth, by turning market participation into transparent, repeatable rules, and Goal 11, on inclusive and resilient communities, by contributing to the digital financial infrastructure residents use (United Nations, 2015). Everything here is built from publicly available data and open-source tools, so it can be replicated anywhere.

@H2 Statement of the Problem

Bitcoin is hard to forecast over short horizons. It trades 24 hours a day, moves sharply, and reacts to large institutional order flow, so ordinary analysis often misses directional signals before they appear. MACD and KDJ have shown predictive value on their own (Chong & Ng, 2008; Dai et al., 2020; Wu & Diao, 2015). What has not been tested systematically is what happens when those momentum tools are combined with volatility-based risk management and Order Block detection, and how the result holds up against the passive options an ordinary participant would otherwise use.

This study seeks to answer:

@BOOKMARK sop1
@LIST 1. How effectively does the combined MACD, KDJ, ATR, and Smart Money Concepts strategy predict short-term Bitcoin price movements, as measured by win rate, total net return, and average return per trade?

@BOOKMARK sop2
@LIST 2. How does the strategy compare against the two passive alternatives an ordinary participant would realistically use, namely weekly dollar-cost averaging into Bitcoin and a single lump-sum purchase held to the end of the window, when all three are started from identical capital and measured on total return, Sharpe ratio, Sortino ratio, maximum drawdown, and time in market?

@BOOKMARK sop3
@LIST 3. Does directing a share of new weekly contributions into the strategy improve the risk-adjusted profile of an otherwise ordinary Bitcoin dollar-cost-averaging plan, and if so, how does that improvement behave as the allocated share rises?

@H3 Hypotheses

H₀₁: The combined strategy does not produce a statistically significant win rate above 50% on BTC/USDT 4-hour data across all market conditions over a broad temporal scope.

H₁₁: The combined strategy produces a statistically significant win rate above 50% on BTC/USDT 4-hour data across all market conditions over a broad temporal scope.

In plain terms, this pair asks whether the strategy wins more often than a coin flip by a margin too large to be luck. It is tested with a one-sided exact binomial test, specified in Section F.

H₀₂: Blending a strategy allocation into a Bitcoin dollar-cost-averaging plan does not improve that plan's risk-adjusted profile, as measured by the Sharpe ratio, the Sortino ratio, and maximum drawdown, relative to a plan held entirely in dollar-cost-averaged Bitcoin.

H₁₂: Blending a strategy allocation into a Bitcoin dollar-cost-averaging plan improves that plan's risk-adjusted profile on all three of those measures relative to a plan held entirely in dollar-cost-averaged Bitcoin.

This pair is stated formally so the direction of the claim is fixed before the numbers are seen. How it is judged is fixed here too. Sharpe, Sortino, and maximum drawdown are each computed from one realized price path, so each is a single observation, not a sample. There is no sampling distribution behind them, so no p-value can honestly be formed. The pair is therefore settled descriptively, by whether all three measures move in the predicted direction consistently as the allocated share rises. That is a weaker standard than a significance test and is treated as one throughout.

@H1 Framework

@H2 A. Research Design

This is a retrospective quantitative backtest. The strategy is applied candle by candle to historical BTC/USDT 4-hour data, simulating how it would have traded in real time. The simulation reads candles in order and is never allowed to see a candle that had not yet closed when a decision was made. No parameter was fitted, swept, or optimized against the outcome being measured.

The rules, parameters, and thresholds were set by eye from charts covering January 2018 to January 2022. The primary findings come from January 2022 to January 2026. A third and stricter test uses January 2026 to July 2026, which came after every change to the code. Figure 1 shows how the three periods relate.

This separation has two limits. The build period was inspected by eye, not fitted numerically, so the rules carry whatever bias visual pattern recognition introduces, and the strength of the separation cannot be measured the way a held-out split in a machine-learning study can. The 2022 to 2026 window is also out-of-sample for rule building but not for code checking, because the bug described in the Limitations was found while examining that same window. Only the January to July 2026 test is out-of-sample in both senses.

@FIG 1 | Relationship Between the Formulation Period, the Primary Reported Window, and the Forward Test | fig01.png

@H2 B. Materials and Sources

BTC/USDT 4-hour candlestick data (Binance, via API). Open, high, low, close, and volume were pulled from the Binance public price endpoint for BTCUSDT at 4-hour resolution, in batches of 1,000 candles. Millisecond timestamps were converted to datetimes and shifted forward eight hours, so all stored timestamps are UTC+8. Every timestamp in this paper follows that convention. Figure 2 shows the collection and verification sequence.

@FIG 2 | Data Collection, Timestamp Conversion, and Dataset Verification | fig02.png

The dataset runs from 2022-01-01 08:00:00 to 2026-01-01 08:00:00. That is exactly 1,461 days: 365 + 365 + 366 + 365, with the 366 covering the 2024 leap day. At six 4-hour candles a day, 1,461 × 6 = 8,766 intervals. The final candle is stored as a row rather than used only as an upper boundary, so the file holds 8,766 + 1 = 8,767 rows. A gap check found only one unique time difference between consecutive candles, four hours, with no duplicate timestamps. No candle is missing.

The 2018 to 2022 build window holds 8,750 rows against the 8,767 expected under the same counting. That is seventeen candles missing across eight exchange outages, the largest a seven-candle gap. It is disclosed for completeness and does not affect any figure from the primary window.

Python 3 environment. Backtesting logic was implemented using pandas, numpy, python-binance, and gspread with oauth2client.

SciPy. A free, open-source scientific computing library for Python, widely used in published research (Virtanen et al., 2020). Every standard textbook test in this paper is an unmodified call into scipy.stats.

Google Sheets and SQL database. Simulation results were exported to Google Sheets and to a local SQL database, including per-trade records.

LuxAlgo Smart Money Concepts indicator (LuxAlgo, 2022). Order Block detection is a Python translation of the LuxAlgo indicator for TradingView, using a 50-candle swing pivot lookback and a 5-candle internal pivot lookback.

Average True Range (Wilder, 1978). True range follows Wilder's definition. Both ATR windows use a plain rolling mean, not Wilder's original exponential smoothing. That is what the code does and what this paper reports.

Web-based verification dashboard. A separately written JavaScript dashboard recomputes the indicator and entry-condition layer in the browser, as a cross-check from a second codebase. Its scope is limited on purpose: it does not detect Order Blocks, Fair Value Gaps, or liquidity sweeps on its own, and it never imports any value from the Python analysis. That independence is why the two bootstrap intervals in the Findings are kept separate instead of merged.

@H2 C. Variables

Independent variable. How capital is allocated over one identical stretch of price history. Six levels: the Order-Block-gated strategy alone; weekly dollar-cost averaging into Bitcoin; one lump-sum purchase held to the end; and three blends putting 10%, 20%, and 30% of new weekly contributions into the strategy with the rest dollar-cost averaged. The 0% blend is the same arm as pure weekly averaging and appears as the blended model's baseline row.

Dependent variables. For the strategy's own trades: win rate, total net return, average return per trade, and return concentration. For the comparison against passive options: total return and final capital from a fixed start, annualized Sharpe, annualized Sortino, maximum drawdown, and time in market.

Controlled variables. Trading pair, candle interval, and backtest window are the same for every arm. The MACD, KDJ, and ATR settings, the exit rules, and the minimum reward-to-risk requirement are the same wherever the strategy appears. Starting capital is $10,000 for every head-to-head arm. The schedule is 210 equal weekly contributions for the averaging arm and every blend. The cost assumption is applied at the same rate to every arm in a given comparison.

@H2 D. Strategy Formulas

Throughout this section, C, H, L, and V with subscript t denote the closing price, high, low, and traded volume of candle t.

MACD (12, 26, 9). Momentum confirmation comes from the gap between a fast and a slow exponential moving average. Every value uses only past and present candles.

@EQ EMA₁₂(t) = C_t × (2/13) + EMA₁₂(t−1) × (1 − 2/13)
@EQ EMA₂₆(t) = C_t × (2/27) + EMA₂₆(t−1) × (1 − 2/27)
@EQ MACD_t = EMA₁₂(t) − EMA₂₆(t)
@EQ Signal_t = MACD_t × (2/10) + Signal_{t−1} × (1 − 2/10)
@EQ Hist_t = MACD_t − Signal_t

ATR (14) and ATR (200). True range measures how far price travelled on a candle. ATR averages it.

@EQ TR_t = max( H_t − L_t , |H_t − C_{t−1}| , |L_t − C_{t−1}| )
@EQ ATR₁₄(t) = (1/14) × Σ TR_{t−i} for i = 0 to 13
@EQ ATR₂₀₀(t) = (1/200) × Σ TR_{t−i} for i = 0 to 199

ATR₁₄ sets stop-loss distance, the minimum-stop filter, the trailing exit, and the ATR-move exit. ATR₂₀₀ is the volatility baseline for the market-condition filter and for two Order Block criteria, Displacement and Large Origin Candle.

KDJ (9, 3, 3), the fixed entry gate. Computed once over the whole dataset. It does not vary from trade to trade, and every K, D, and J reference inside the entry conditions reads this series at the current candle.

@EQ RSV_t = [ (C_t − min L over the last 9 candles) / (max H over the last 9 candles − min L over the last 9 candles) ] × 100
@EQ K_t = (2/3) K_{t−1} + (1/3) RSV_t
@EQ D_t = (2/3) D_{t−1} + (1/3) K_t
@EQ J_t = 3K_t − 2D_t

KDJ, the adaptive exit series. A second system that exists only to time one exit signal after a trade is open. It never shares state with the series above. At entry it is seeded from the fixed series' K and D at the entry candle, and its window length is set once and held for the life of that trade:

@EQ w = max( 1 , number of candles between the Order Block and the entry candle )

On each later candle a Raw Stochastic Value is recomputed over a rolling window of length w, and K and D are updated with the same one-third smoothing:

@EQ RSV_custom = [ (C_cur − min L over the window) / (max H over the window − min L over the window) ] × 100
@EQ K_cur = (2/3) K_prev + (1/3) RSV_custom     D_cur = (2/3) D_prev + (1/3) K_cur

Across the 27 trades, w ranged from 14 to 439 candles, with a median of 74. Only w varies between trades; the entry gate never does. These are two separate systems by design.

Order Block detection. Two independent structural passes run over the same price series, one with a 5-candle pivot lookback for internal structure and one with a 50-candle lookback for swing structure. Figure 3 sets out the detection and scoring sequence.

@FIG 3 | Order Block Detection, Quality Scoring, and Eligibility | fig03.png

In each pass a candle is confirmed as a pivot high only by right-side comparison: its high must exceed every high that follows it up to the breakout candle. A pivot low is the mirror. No future candle is read. A break of structure is flagged when price closes across a tracked pivot level, and an Order Block is created from the price segment between the pivot candle and the candle whose close confirms the break. Two candles are kept separate on purpose: the one holding the Order Block's own extreme, and the one where the breakout closes. An Order Block cannot trigger an entry until strictly after its confirmation candle. Order Blocks expire after 500 candles, or once price closes back through their boundary.

Order Block quality criteria. Each Order Block is scored on five separate true-or-false criteria. Their sum, 0 to 5, is used only as an entry-eligibility threshold. The baseline reported here uses a threshold of 0, so no Order Block is excluded by score.

@LIST 1. Displacement: within the candles immediately following the Order Block's own candle, and bounded at that Order Block's own confirmation candle, a candle body move of at least 1.5 times ATR₂₀₀ occurs in the Order Block's direction.
@LIST 2. Large Origin Candle: the high minus the low of the Order Block's candle is at least ATR₂₀₀ at that candle, meaning the block's own candle is at least as tall as the long-run average candle.
@LIST 3. Fair Value Gap: a three-candle price imbalance exists within a bounded window following the Order Block's candle. For a demand block the low of the third candle exceeds the high of the first; for a supply block the mirror condition holds.
@LIST 4. Liquidity Sweep: the low of the Order Block's candle is at or below the minimum low over the prior ten candles for a demand block, or its high is at or above the maximum high over the prior ten candles for a supply block.
@LIST 5. Volume Expansion: the volume of the Order Block's candle is at least 1.25 times the mean volume over the prior twenty candles, or the candle body exceeds 60% of the candle's own high-to-low range.

Both the Displacement and the Fair Value Gap search windows are bounded at the Order Block's own confirmation candle.

Fixed parameters. Every value below was set before, and independently of, the analysis reported here.

@TABLE 1 | Fixed Strategy Parameters
| Parameter | Value |
| Minimum stop distance | 0.015, meaning 1.5% of entry price |
| KDJ J cap, long entries | 60.0 |
| KDJ K cap, long entries | 50.0 |
| KDJ K floor, short entries | 70.0 |
| KDJ J cap, short entries | 100.0 |
| ATR-move take-profit multiple | 1.8 |
| Breakeven-stop trigger multiple | 2.0 |
| Minimum reward-to-risk ratio | 1.5 |
| Order Block expiry | 500 candles |
| Internal pivot lookback | 5 candles |
| Swing pivot lookback | 50 candles |
@ENDTABLE
@NOTE Note. Every value was set during the 2018 to 2022 formulation period and was never adjusted afterwards.

Entry conditions. A long entry needs all six conditions in Figure 4 to hold at the same candle close. A short entry is the mirror against a supply Order Block, with K above 70 and J at or below 100.

@FIG 4 | Long Entry Decision Sequence | fig04.png

Exit conditions. Exits are checked on every candle in the fixed order shown in Figure 5. The first condition met triggers the exit and the rest are not checked for that candle.

@FIG 5 | Exit Priority Order | fig05.png

@H2 E. Portfolio Construction and Contribution Schedule

This section gives the full construction of every comparison arm, so a reader can rebuild Tables 6 through 9 by hand.

Shared timing rule. A contribution lands on the first bar of every ISO calendar week and buys at that bar's close. The blended model and the head-to-head averaging arm both use this rule, so the two cannot drift apart. The primary window holds 210 such weeks. The 2018 to 2022 window holds 209.

Head-to-head arms. Each starts from $10,000. The strategy arm holds the full amount in cash from the first bar and compounds only at each trade exit bar, by that trade's percentage return. Each trade commits the full amount; positions are unlevered and never partly sized. Between trades the arm sits in cash and earns nothing. Returns are measured per 4-hour bar and annualized with m = 6 × 365.25 = 2,191.5.

The weekly averaging arm contributes $10,000 ÷ 210 = $47.6190 per week, or $10,000 ÷ 209 = $47.8469 in the 2018 window, buying at each contribution bar's close. Value at any bar is units held times the current close. Period returns are measured only at contribution bars, net of that week's own contribution, so new money is never counted as return:

@EQ r_k = ( V_k − C_k ) / V_{k−1} − 1

That arm is annualized with m = 52. The lump-sum arm buys the full $10,000 at the first bar's opening price, which differs from the averaging arm's use of the close, and holds to the last bar's close. Its returns are per 4-hour bar, annualized with m = 2,191.5.

One reconciliation applies wherever the strategy arm appears. Its Total return column is the arithmetic sum of the individual trade returns, which is the convention behind the +30.31% headline throughout this paper, while its Final capital column compounds those same returns in sequence from the $10,000 start. Compounded, the strategy returns +34.18% over the primary window, which is what produces $13,417.77. The two passive arms hold one position throughout, so no such gap arises for them.

In the net-of-cost version in Table 8, the strategy arm pays a 0.20% round-trip drag taken off each trade's return. The two passive arms pay a 0.10% one-sided markup on the buy price, since they buy and hold instead of round-tripping.

Blended-sleeve model. Contributions here are 1.0 relative unit per week across 210 weeks, not dollars, so Table 6 has no dollar column and should not be read against the $10,000 used elsewhere. In the 100% / 0% baseline the full unit buys Bitcoin at that bar's close. At a strategy share f of 0.10, 0.20, or 0.30, the remaining share buys Bitcoin and f goes into a strategy sleeve held as cash. That sleeve compounds by each trade's return at the trade's exit bar and is never moved back into Bitcoin. Portfolio value at any bar is Bitcoin units times the close, plus the sleeve's cash. Period returns are measured at the 210 contribution bars, net of that week's contribution, and annualized with m = 52. Maximum drawdown in Table 6 includes principal and is computed on the portfolio value series at contribution bars.

Table 6's 100% / 0% row and Table 7's Weekly DCA row give the same Sharpe of 0.556, the same Sortino of 0.886, and the same maximum drawdown of −27.85%, because both use the same weekly rule. The two tables meeting at their shared point is a free consistency check.

@H2 F. Data Analysis

The main approach is exploratory data analysis: descriptive statistics, distribution summaries, and table comparison, used to find patterns before drawing conclusions (Tukey, 1977). It suits this case because the backtest output is a finite, fully observed set of trade records with no missing values. Descriptive statistics reported are trade count, win rate, net return, average return, and standard deviation.

@H3 Statistical Software and the Division Between Library and Custom Code

All statistics were computed in Python 3 using SciPy, a free open-source library whose routines are the same ones used across published quantitative research (Virtanen et al., 2020). Using it means the standard tests here are not this study's own code, which removes a whole class of possible arithmetic error.

This paper reports exactly six quantities. Three are unmodified SciPy calls. Three are formulas written for this study, either because no single library function computes them or because they follow this study's own resampling design. Sharpe, Sortino, and maximum drawdown are descriptive measures, not hypothesis tests, and no p-value is attached to any of them anywhere in this paper.

@TABLE 2 | Division Between SciPy Library Calls and Formulas Written for This Study
| Quantity | Source | Routine |
| Exact binomial test on win rate | SciPy | scipy.stats.binomtest |
| Pearson's correlation and its p-value | SciPy | scipy.stats.pearsonr |
| Spearman's correlation and its p-value | SciPy | scipy.stats.spearmanr |
| Bootstrap confidence interval on total return | Custom | Percentile bootstrap, Formula 1 |
| Maximum drawdown | Custom | Running-peak decline, Formula 2 |
| Sharpe and Sortino ratios | Custom | Annualized risk-adjusted return, Formula 3 |
@ENDTABLE
@NOTE Note. Formula numbering runs 1, 2, and 3. Appendix B gives each custom formula in source form.

@H3 Tests Computed by SciPy

One-sided exact binomial test. With n closed trades and w winners, and a null win probability of 0.5, the one-sided p-value is the sum, for k from w to n, of n-choose-k times 0.5 to the power n:

@EQ p_one-sided = Σ_{k=w}^{n} C(n, k) (0.5)^k (0.5)^{n−k} = Σ_{k=w}^{n} C(n, k) (0.5)^n

A p-value is the chance of a result at least this strong if the strategy had no edge at all. The one-sided form was chosen because the hypothesis is directional. Two-sided values are given for reference.

Correlation. Pearson's r and Spearman's ρ were computed between how long a trade was held, in candles, and its percentage return. Pearson assumes a straight-line relationship; Spearman assumes only a consistent direction.

@H3 Formulas Written for This Study

Formula 1. Percentile bootstrap confidence interval. Let r₁, r₂, …, r_n be the percentage returns of the n trades. For each of B repetitions, draw n returns from that set at random with replacement and record the resample's total and mean:

@EQ T^(b) = Σ r_i^(b)     T̄^(b) = (1/n) Σ r_i^(b)     for b = 1, 2, …, B

The 95% confidence interval is the 2.5th and 97.5th percentiles of the B recorded values:

@EQ CI₉₅% = [ Q₂.₅( T^(1), …, T^(B) ) , Q₉₇.₅( T^(1), …, T^(B) ) ]

Twenty-seven trades is too few, and too skewed by a few large winners, for a normal-theory interval to be safe. The bootstrap assumes nothing about the shape of the distribution and uses the data's own shape instead (Efron & Tibshirani, 1993). Drawing exactly n values with replacement follows Efron, so the spread between resamples reflects real sampling uncertainty rather than a changed sample size. Parameters are B = 10,000, n = 27, and a fixed seed of 42, so the figure is exactly reproducible. This is the plain percentile bootstrap, not the bias-corrected and accelerated version. That is a choice, not the only option.

Formula 2. Maximum drawdown. Let E_t be the value of an equity curve at time t. Define the running peak, the percentage decline from that peak, and the worst such decline:

@EQ P_t = max_{u ≤ t} E_u     DD_t = [ (E_t − P_t) / P_t ] × 100     MDD = min_t DD_t

Drawdown is a percentage, not dollars, so the three arms can be compared directly despite very different equity-curve shapes. Tracking the running peak, instead of comparing only the final value to the all-time high, is what catches a fall partway through that later recovers.

Formula 3. Sharpe and Sortino ratios. Let R₁, R₂, …, R_N be an arm's per-period returns, R̄ their mean, s_R their standard deviation, and m the number of periods in a year for that arm's own reporting frequency:

@EQ SR = ( R̄ / s_R ) × √m
@EQ σ_d = √[ (1/N) Σ ( min(R_t, 0) )² ]     SoR = ( R̄ / σ_d ) × √m

Sharpe measures return per unit of overall variability, so a higher value means a smoother ride for the same return (Sharpe, 1994). Sortino counts only downward movement as risk (Sortino & van der Meer, 1991). The downside deviation divides by N, the count of all periods, not just losing ones, which follows the original 1991 definition. A widely copied online tutorial divides by the number of losing periods instead, which inflates the ratio; this study does not use that shortcut.

Both ratios assume a risk-free rate of zero, and Sortino assumes a minimum acceptable return of zero. In full, the general Sharpe formula is

@EQ SR_general = ( E[ R_a − R_f ] / σ_a ) × √m

and this study sets R_f = 0. That is defensible for a crypto strategy with no funding-rate component modelled, and every arm is treated the same way, so the ranking between arms does not change. It is still a deviation from the general formula, so it is stated here.

Additional analyses. The headline result was recomputed under six cost scenarios, compared against the two passive alternatives both gross and net of fees, and re-run on data that came after the code was finished. The binomial test is re-run in full on each fee-adjusted trade set rather than adjusted from the gross p-value.

Reproducibility. A golden-master regression harness recomputes the indicators and the full simulation from raw candle data and requires exact agreement with committed reference files: indicators to a tolerance of 10⁻⁶, and all 27 trade records exactly. It runs after every code change. Truncation-equality testing on the ATR(14), ATR(200), and fixed KDJ(9,3,3) series passed 180 of 180 sampled checks, meaning each indicator recomputed on a shortened dataset gave exactly the same values, which is what must happen if no future data is used. The separate JavaScript dashboard gives a second cross-check on the indicator and entry-condition layer. All results appear as observed, including non-significant and unfavourable ones.

@H1 Findings

This section is organized around the three research questions. Each subsection opens with a direct answer, then gives the evidence behind it. Interpretation is held back to the Conclusions. Appendix A traces every number here to the function that produced it, and Appendix E shows how to recompute by hand each number that can be recomputed by hand.

@H2 Answers to SOP 1 and Hypotheses H₀₁ and H₁₁

@NOTE Note. Refer to page {PAGEREF sop1} for the question being answered.

Answer: yes before costs, no after them. The strategy won 70.37% of 27 trades for +30.31% total net return at p = 0.0261, and the bootstrap interval on total return excludes zero. Charging a realistic 0.20% round trip moves p to 0.1239, so H₀₁ is not rejected once costs a real trader would pay are charged.

@TABLE 3 | Baseline Strategy Performance, 2022 to 2026 Window, Gross of Costs
| Metric | Value |
| Trades | 27 |
| Wins / Losses | 19 / 8 |
| Win rate | 70.37% |
| Total net return | +30.31% |
| Average return per trade | +1.1225% |
| Standard deviation of return per trade | 2.41% |
| One-sided binomial p | 0.0261 |
| Two-sided binomial p | 0.0522 |
@ENDTABLE
@NOTE Note. Exact binomial test on 27 trades with 19 wins against a null win probability of 0.5.

With 27 trades and 19 wins, the one-sided exact binomial test gives

@EQ P( K ≥ 19 | n = 27, p = 0.5 ) = Σ_{k=19}^{27} C(27, k) (0.5)^{27} = 0.0261

If the strategy had no edge, a run this good would happen about 26 times in every 1,000 attempts. Each trade is named throughout this paper by the candle index where it was entered: 335, 359, 673, 902, 1050, 1158, 1913, 2624, 2859, 3100, 3196, 3859, 3947, 4455, 5800, 5825, 6040, 6109, 6366, 6537, 6991, 7109, 7938, 7964, 8188, 8280, and 8596. The full per-trade record is Appendix D.

Bootstrap interval. A bootstrap of 10,000 resamples, drawn at the original sample size of 27 with a fixed seed of 42, gives a point estimate of +30.3065% total net return, which differs from the observed sum of +30.3064% only in the fourth decimal. The 95% confidence interval is [+5.9866%, +54.9866%]. It is wide but excludes zero, and 99.25% of resampled totals were positive. The matching interval for average return per trade is [+0.2217%, +2.0365%]. The companion website recomputes the same bootstrap in the browser at 2,000 resamples and lands on [+7.48%, +54.46%]. That is separate TypeScript code with its own random number generator, and the gap between the two intervals was traced to the resample count alone. They are kept separate rather than merged, because the website's independence is what makes the cross-check worth anything.

Cost sensitivity. Six scenarios were run: gross, fee-only, and four spanning 0.14% to 0.40% round trip. The confirmed Binance USDT-M Futures standard taker rate is 0.05% per side, giving 0.10% for a round trip, and slippage was modelled separately at a conservative 0.05% per side.

@TABLE 4 | Win Rate and Significance Across Six Transaction-Cost Scenarios
| Scenario | N | Win rate | Total net return | Binomial p (1-sided) | Trades flipped to losses |
| Gross, no fees or slippage | 27 | 70.37% | +30.31% | 0.0261 | none |
| Fee only, 5.00 bps per side round trip | 27 | 70.37% | +27.61% | 0.0261 | none |
| Low band, 0.14% round trip | 27 | 62.96% | +26.53% | 0.1239 | 7938, 8188 |
| Primary, 0.20% round trip | 27 | 62.96% | +24.91% | 0.1239 | 7938, 8188 |
| Mid band, 0.24% round trip | 27 | 62.96% | +23.83% | 0.1239 | 7938, 8188 |
| High band, 0.40% round trip | 27 | 55.56% | +19.51% | 0.3506 | 2859, 5825, 7938, 8188 |
@ENDTABLE
@NOTE Note. Each row re-runs the binomial test in full on that scenario's fee-adjusted trade set. Flipped trades are named by entry candle index. One basis point (bps) is one hundredth of one percent.

@FIG 6 | Win Rate and Significance Across Six Transaction-Cost Scenarios | fig07.png

The flip comes from exactly two trades, those at candle indices 7938 and 8188, worth +0.12% and +0.13% before costs, crossing from winners into losers.

Regime dependence. Trades were tagged by market condition at entry using two independent methods. The first is a calendar split. The second measures how far price sat below its previous all-time high, starting from Bitcoin's pre-window high of $69,000 on 2021-11-10, with bear at 40% or more below that high, sideways between 40% and 12% below, and bull less than 12% below.

@TABLE 5 | Performance by Calendar Regime
| Regime | Trades | Win rate | Return contribution | Share of total return |
| Bear (2022) | 7 | 57.14% | +10.45% | +34.5% |
| Chop (2023) | 6 | 50.00% | −5.39% | −17.8% |
| Bull (2024 to 2025) | 14 | 85.71% | +25.25% | +83.3% |
@ENDTABLE
@NOTE Note. The three rows partition the same 27 trades, so counts sum to 27 and contributions sum to +30.31%.

@TABLE 6 | Performance by Drawdown-From-High Regime
| Regime | Trades | Win rate | Return contribution | Share of total return |
| Bear (at or below −40% from high) | 12 | 50.00% | −1.63% | −5.4% |
| Chop (−40% to −12% from high) | 8 | 87.50% | +18.89% | +62.3% |
| Bull (above −12% from high) | 7 | 85.71% | +13.05% | +43.1% |
@ENDTABLE
@NOTE Note. The same 27 trades, re-partitioned by a different definition of market regime.

The two methods agree on only 13 of the 27 assignments, because they measure different things. Much of 2023 sat 57% to 64% below the all-time high even though price that year was range-bound rather than falling. Both methods agree that bull is the strongest regime, at an 85.71% win rate under each.

Holding time and return. Across the same 27 trades, Pearson's r = +0.4907 with t = 2.82, df = 25, and p ≈ 0.0094. Spearman's ρ = +0.4797 with p ≈ 0.0113. Trades held longer tended to end up larger, and the pattern holds at both the 5% and 1% thresholds.

Forward test. A forward out-of-sample test used 4-hour data from 2026-01-01 to 2026-07-31, a period that came after every change to the code, run through the identical frozen pipeline after first confirming the locked 27-trade baseline reproduced exactly.

@TABLE 7 | Forward Out-of-Sample Result, January to July 2026
| Metric | Value |
| New out-of-sample trades | 4 |
| Wins / Losses | 1 / 3 |
| Win rate | 25.00% |
| Total return | −3.45% |
| Average return per trade | −0.86% |
@ENDTABLE
@NOTE Note. Same frozen pipeline as Table 3, applied to candles after 2026-01-01 08:00:00.

This is reported as it came out: small and unfavourable. A separate eight-year backfill check ran the same pipeline on data extended back to 2018-01-01, to test whether four extra years of indicator warm-up would change the locked results. All 27 locked trades matched by entry timestamp, with a maximum profit-and-loss difference of 0.0000000000%.

@TABLE 8 | Comparison of the Formulation Window, the Primary Window, and Their Combination
| Window | N | Win rate | Total return | Avg return/trade | Binomial p (1-sided) |
| 2018-01 to 2022-01, formulation period, not out-of-sample | 25 | 60.00% | +21.82% | +0.87% | 0.2122 |
| 2022-01 to 2026-01, primary reported window | 27 | 70.37% | +30.31% | +1.12% | 0.0261 |
| Combined 2018 to 2026, mixed provenance | 56 | 62.50% | +48.68% | n/a | 0.0407 |
@ENDTABLE
@NOTE Note. Each row is a separate binomial test. The combined row is the 25 formulation trades, the 27 primary trades, and the 4 forward-test trades: 25 + 27 + 4 = 56, and 15 + 19 + 1 = 35 wins.

The combined row should never be cited on its own, because about half of it comes from the period the rules were built on. The strategy does worse on its own build data, at 60.00% and p = 0.2122, than on the primary window.

@H2 Answers to SOP 2

@NOTE Note. Refer to page {PAGEREF sop2} for the question being answered.

Answer: weekly buying won on final value by a wide margin, and the strategy won on risk-adjusted shape while holding a position only 2.63% of the time. Both are true and neither settles the comparison alone.

@TABLE 9 | Three-Arm Head-to-Head Comparison, 2022 to 2026, Gross of Costs
| Arm | Total return | Final capital from $10,000 | Sharpe | Sortino | Max drawdown | Time in market |
| OB-gated strategy | +30.31% | $13,417.77 | 1.1142 | 2.7273 | −6.46% | 2.63% |
| Weekly DCA into BTC | +123.13% | $22,312.94 | 0.5559 | 0.8857 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +90.07% | $19,007.32 | 0.5642 | 0.8034 | −67.21% | 100.00% |
@ENDTABLE
@NOTE Note. Time in market for the strategy is 2.6349% of candles. The summed-versus-compounded reconciliation for the strategy arm is set out in Section E.

@FIG 7 | Three Arms Grown From an Equal $10,000 Start, 2022 to 2026 | fig06.png

@TABLE 10 | Three-Arm Head-to-Head Comparison, 2022 to 2026, Net of Costs
| Arm | Total return | Final capital from $10,000 | Sharpe | Sortino | Max drawdown | Time in market |
| OB-gated strategy | +24.91% | $12,719.01 | 0.9442 | 2.0830 | −7.78% | 2.63% |
| Weekly DCA into BTC | +122.91% | $22,290.65 | 0.5529 | 0.8806 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +89.88% | $18,988.34 | 0.5642 | 0.8034 | −67.21% | 100.00% |
@ENDTABLE
@NOTE Note. Same construction and window as Table 9, with costs applied as set out in Section E. Both passive arms are almost unaffected, because a single purchase markup is charged once rather than 27 times.

Weekly buying beat the strategy on final value, $22,312.94 against $13,417.77 gross and $22,290.65 against $12,719.01 after costs. The strategy's gross Sharpe of 1.1142 and Sortino of 2.7273 exceed buy-and-hold Bitcoin's 0.5642 and 0.8034 over the same window, but it holds a position only 2.63% of the time against 100% for both passive arms, so this is not a like-for-like comparison.

@TABLE 11 | Three-Arm Head-to-Head Comparison, 2018 to 2022 Formulation Window, Gross of Costs
| Arm | Total return | Final capital from $10,000 | Sharpe | Sortino | Max drawdown | Time in market |
| OB-gated strategy | +21.82% | $12,282.53 | 0.681 | 1.303 | −6.00% | 1.87% |
| Weekly DCA into BTC | +439.88% | $53,987.55 | 0.824 | 1.234 | −46.16% | 100.00% |
| Lump-sum buy-and-hold | +236.96% | $33,696.49 | 0.789 | 1.119 | −81.42% | 100.00% |
@ENDTABLE
@NOTE Note. Same construction as Table 9, applied to 2018-01-01 to 2022-01-01, where the weekly schedule holds 209 contributions of $47.8469.

That window is where the rules were built, so it is shown for comparison only. Bitcoin's 2018 to 2022 window held a much bigger fall-and-recovery cycle than 2022 to 2026, which mechanically favours weekly buying by lowering its average purchase price.

@H2 Answers to SOP 3 and Hypotheses H₀₂ and H₁₂

@NOTE Note. Refer to page {PAGEREF sop3} for the question being answered.

Answer: yes. All three risk-adjusted measures improve at every step as the strategy share rises from 0% to 30%, with no reversal, which is the pattern that rejects H₀₂ in favour of H₁₂ under the descriptive standard set with the hypothesis.

@TABLE 12 | Risk-Adjusted Profile of a Blended DCA Portfolio at Increasing Strategy Allocations
| Split (BTC-DCA / Strategy) | Sharpe (annualized) | Sortino (annualized) | Max drawdown |
| 100% / 0% | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |
@ENDTABLE
@NOTE Note. Computed on the blended equity curve of 210 weekly contributions over 2022 to 2026, under the construction in Section E. Both ratios assume a risk-free rate of zero.

@FIG 8 | Risk-Adjusted Profile Across Increasing Strategy Allocations | fig08.png

Sharpe rises from 0.556 to 0.637, Sortino from 0.886 to 1.032, and maximum drawdown shallows from −27.85% to −23.18%. The conclusion is bounded as stated with the hypothesis: it rests on one realized price path, it carries no p-value, and it shows what a blend would have done over this window, not what it will do over another.

@H1 Conclusions

Over January 2022 to January 2026 the strategy made 27 trades at a 70.37% win rate for +30.31% total net return, and weekly dollar-cost averaging still beat it on final value from equal capital, $22,312.94 against $13,417.77. The defensible use for this rule set is as a small sleeve inside a weekly buying plan, not as a replacement for one.

The return finding holds up directionally. The bootstrap 95% interval on total return excludes zero even though it is wide, and 99.25% of the 10,000 resamples were positive. The win-rate significance is fragile by comparison. It survives the exchange fee alone at p = 0.0261 but not the addition of conservative slippage at p = 0.1239. Both belong to the same answer, and reporting only the first would misrepresent the second.

Return is concentrated. Three trades make up 51.7% of the total, so at this sample size profit rests on a few large outcomes rather than a steady edge in every trade. The positive correlation between holding time and return fits that picture: the large outcomes are the ones the exit rules let run. The edge is also concentrated in bull-trending conditions, at an 85.71% win rate under both regime methods, and is weaker or negative in sideways or bearish conditions under at least one of them.

On the comparison against passive investing, the two results point opposite ways and both must be reported. Head-to-head from equal capital, weekly buying produced roughly 1.66 times the strategy's final capital before costs and roughly 1.75 times after, and no framing changes that. On risk-adjusted shape the strategy was stronger, but it did that while invested 2.63% of the time against 100%. The blended framing is the defensible one: Sharpe, Sortino, and drawdown all improve steadily as the strategy's share rises from 0% to 30% inside a weekly buying plan.

Table 8 is the most direct evidence that the separation between formulation and reported windows is real rather than claimed, because the strategy does worse on the window its rules came from. That should not be overstated. Inspecting charts by eye is weaker separation than a formal held-out split, and the reported window is out-of-sample only for rule building. The four-trade forward test is the only result out-of-sample in both senses, and it is unfavourable.

@H2 Limitations

@LIST 1. The study does not model leverage or margin, and reports unlevered returns throughout. The engine checks every exit on candle closes rather than on price movement inside a candle, so a leverage model on top would inherit that limit and report liquidations it cannot actually establish.
@LIST 2. The sample is small at 27 trades, and return is concentrated in three of them, which together make up 51.7% of the total. Conclusions in either direction are provisional.
@LIST 3. The separation between the build period and the reported window is real but weaker than a formal held-out split, and no record exists of what rule variants were tried and dropped.
@LIST 4. The comparison against passive options is descriptive, not inferential. Sharpe, Sortino, and maximum drawdown are each computed once on one realized price path, so no confidence interval or p-value attaches to the difference between arms. A different four-year window could reverse the ordering, as Table 11 already shows in one direction.
@LIST 5. Two choices are disclosed as assumptions rather than defended as the only correct option: Sharpe and Sortino assume a risk-free rate and minimum acceptable return of zero, and the bootstrap is the plain percentile form, not the bias-corrected and accelerated version.
@LIST 6. Trade frequency is low, at roughly 0.56 trades per month, which limits how fast genuinely forward-looking evidence can build up.
@LIST 7. Structural criteria can read forward without anyone noticing. Two Order Block criteria in this study originally bounded their search loops by the length of the whole dataset instead of by each block's own confirmation candle, so they could read one or two candles that would not have been available yet. That is a real data-leakage bug. A no-lookahead audit found it, and the fix bounds both loops at the confirmation candle with runtime assertions left at those read sites. The fix does not change the 27-trade baseline, because that baseline applies no quality-score filter. Any future study that scans forward from a signal candle can repeat this if the window is not bounded.
@LIST 8. A reported number can drift from the code that produced it. Two correlation p-values in this study were once reported as below 0.001 when the correct values are about 0.0094 and 0.0113, an overstatement of roughly ten times. Both are corrected here. A figure restated by hand can drift from its source unless every number is traced back to the function that produced it, which is what Appendix A now does.
@LIST 9. Two correct implementations can disagree. The Python bootstrap here uses 10,000 resamples and the companion dashboard uses 2,000, giving different but individually correct intervals. The gap was traced to the resample count alone, by rewriting the dashboard's random number generator in Python and reproducing its interval exactly. Independent reimplementations must be reconciled explicitly, not silently averaged or quietly dropped.

@H2 Summary and Conclusion

A percentile bootstrap of 10,000 resamples put the 95% interval on total return at [+5.99%, +54.99%], which excludes zero, so the return finding holds up directionally in this window. The win-rate significance does not. A realistic 0.20% round-trip cost moves p from 0.0261 to 0.1239, and every stricter scenario moves it further, driven by exactly two marginal trades. Since that is the realistic assumption, the answer this paper carries forward is that H₀₁ is not rejected once costs a real trader would pay are charged.

On the second research question, weekly buying beat the strategy on final value from equal capital while the strategy had the stronger risk-adjusted shape at 2.63% time in market against 100%. On the third, all three risk-adjusted measures improved steadily as the strategy share rose from 0% to 30% inside a weekly buying plan, settled descriptively with no p-value attached. The forward test that came after every code change returned −3.45% across four trades. It is too small to settle anything, and it is also the only evidence out-of-sample in both senses.

This study therefore shows a historically observed, directionally robust return edge for this rule set on this window, with its win-rate significance shown to be cost-sensitive and its regime concentration stated openly. It does not show that the strategy will stay profitable in future conditions, and the only evidence so far on that question is unfavourable. Future work should keep collecting genuinely forward-looking trades at the strategy's natural frequency, since only forward evidence can settle whether the edge lasts, and should test the same rules on other instruments and timeframes.

@H1 References

@REF Bangko Sentral ng Pilipinas. (2022). 2021 financial inclusion survey: Topline report. https://www.bsp.gov.ph/Inclusive%20Finance/Financial%20Inclusion%20Reports%20and%20Publications/2021/2021FISToplineReport.pdf
@REF Bessembinder, H., Panayides, M., & Venkataraman, K. (2009). Hidden liquidity: An analysis of order exposure strategies in electronic stock markets. Journal of Financial Economics, 94(3), 361–383. https://doi.org/10.1016/j.jfineco.2009.02.001
@REF Biais, B., Glosten, L., & Spatt, C. (2005). Market microstructure: A survey of microfoundations, empirical results, and policy implications. Journal of Financial Markets, 8(2), 217–264. https://doi.org/10.1016/j.finmar.2004.11.001
@REF Brolley, M., & Cimon, D. A. (2020). Order-flow segmentation, liquidity, and price discovery: The role of latency delays. Journal of Financial and Quantitative Analysis, 55(8), 2555–2587. https://doi.org/10.1017/S002210901900067X
@REF Chong, T. T.-L., & Ng, W.-K. (2008). Technical analysis and the London stock exchange: Testing the MACD and RSI rules using the FT30. Applied Economics Letters, 15(14), 1111–1114. https://doi.org/10.1080/13504850600993598
@REF Constantinides, G. M. (1979). A note on the suboptimality of dollar-cost averaging as an investment policy. Journal of Financial and Quantitative Analysis, 14(2), 443–450. https://doi.org/10.2307/2330513
@REF Corbet, S., Eraslan, V., Lucey, B., & Şensoy, A. (2019). The effectiveness of technical trading rules in cryptocurrency markets. Finance Research Letters, 31, 32–37. https://doi.org/10.1016/j.frl.2019.04.027
@REF Dai, Z., Dong, X., Kang, J., & Hong, L. (2020). Forecasting stock market returns: New technical indicators and two-step economic constraint method. The North American Journal of Economics and Finance, 53, Article 101216. https://doi.org/10.1016/j.najef.2020.101216
@REF Demirgüç-Kunt, A., Klapper, L., Singer, D., & Ansar, S. (2022). The Global Findex Database 2021: Financial inclusion, digital payments, and resilience in the age of COVID-19. World Bank. https://doi.org/10.1596/978-1-4648-1897-4
@REF Díaz, A., & Escribano, A. (2020). Measuring the multi-faceted dimension of liquidity in financial markets: A literature review. Research in International Business and Finance, 51, Article 101079. https://doi.org/10.1016/j.ribaf.2019.101079
@REF Efron, B., & Tibshirani, R. J. (1993). An introduction to the bootstrap. Chapman & Hall.
@REF Fang, J., Jacobsen, B., & Qin, Y. (2014). Predictability of the simple technical trading rules: An out-of-sample test. Review of Financial Economics, 23(1), 30–45. https://doi.org/10.1016/j.rfe.2013.05.004
@REF LuxAlgo. (2022, October 11). Smart money concepts (SMC) [LuxAlgo] [Pine Script indicator]. TradingView. https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-SMC-LuxAlgo/
@REF Lv, T., Hao, Y., Hao, Y., & Shen, C. (2017). K-line patterns' predictive power analysis using the methods of similarity match and clustering. Mathematical Problems in Engineering, 2017, Article 3096917. https://doi.org/10.1155/2017/3096917
@REF Nakamoto, S. (2008). Bitcoin: A peer-to-peer electronic cash system. https://bitcoin.org/bitcoin.pdf
@REF Navarro, M. M., & Navarro, B. B. (2023). Assessing the long-term performance of MACD strategy in the Philippine stock market: A 12-year review. In Proceedings of the 6th European Conference on Industrial Engineering and Operations Management (pp. 1280–1286). IEOM Society International. https://ieomsociety.org/proceedings/2023lisbon/327.pdf
@REF Schär, F. (2021). Decentralized finance: On blockchain- and smart contract-based financial markets. Federal Reserve Bank of St. Louis Review, 103(2), 153–174. https://doi.org/10.20955/r.103.153-74
@REF Sharpe, W. F. (1994). The Sharpe ratio. The Journal of Portfolio Management, 21(1), 49–58. https://doi.org/10.3905/jpm.1994.409501
@REF Sortino, F. A., & van der Meer, R. (1991). Downside risk. The Journal of Portfolio Management, 17(4), 27–31. https://doi.org/10.3905/jpm.1991.409343
@REF Statman, M. (1995). A behavioral framework for dollar-cost averaging. The Journal of Portfolio Management, 22(1), 70–78. https://doi.org/10.3905/jpm.1995.409537
@REF Svogun, D., & Bazán-Palomino, W. (2022). Technical analysis in cryptocurrency markets: Do transaction costs and bubbles matter? Journal of International Financial Markets, Institutions and Money, 79, Article 101601. https://doi.org/10.1016/j.intfin.2022.101601
@REF Tukey, J. W. (1977). Exploratory data analysis. Addison-Wesley.
@REF United Nations. (2015). Transforming our world: The 2030 agenda for sustainable development (A/RES/70/1). https://sdgs.un.org/2030agenda
@REF Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., Burovski, E., Peterson, P., Weckesser, W., Bright, J., van der Walt, S. J., Brett, M., Wilson, J., Millman, K. J., Mayorov, N., Nelson, A. R. J., Jones, E., Kern, R., Larson, E., … van Mulbregt, P. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. Nature Methods, 17(3), 261–272. https://doi.org/10.1038/s41592-019-0686-2
@REF Wilder, J. W., Jr. (1978). New concepts in technical trading systems. Trend Research.
@REF Wu, M., & Diao, X. (2015). Technical analysis of three stock oscillators testing MACD, RSI and KDJ rules in SH & SZ stock markets. In 2015 4th International Conference on Computer Science and Network Technology (pp. 320–323). IEEE. https://doi.org/10.1109/ICCSNT.2015.7490760

@PAGEBREAK
@H1 Appendix A

@H2 Statistical Provenance of Every Reported Number

Every statistic reported in a numbered table or stated as a headline figure in the Findings can be traced here to the function that produced it and the data that function was given. Function names refer to research_analysis.py unless another file is named. "Baseline 27" means the 27 trades whose entry candle indices are listed in the Findings.

@TABLE A1 | Provenance of Every Reported Statistic
| Reported value | Where it appears | Producing function | Library or custom | Exact input |
| 8,767 candles; 4-hour uniform spacing | Section B, Figure 2 | Data loader and gap check | Custom | BTCUSDT 4h, 2022-01-01 08:00 to 2026-01-01 08:00, stamps shifted +8h; 8,766 intervals all equal to four hours, no duplicates |
| Per-trade log for the baseline 27 | Appendix D | Backtest engine export | Custom | Full trade records including the five criterion flags |
| 27 trades, 19 wins, 70.37% | Table 3 | Backtest engine | Custom | Full 8,767-candle series, parameters as in Table 1 |
| p = 0.0261 one-sided; 0.0522 two-sided | Table 3 | binomial_test(), wrapping scipy.stats.binomtest | SciPy | n = 27, k = 19, null p = 0.5 |
| Bootstrap point +30.3065%, CI [+5.9866%, +54.9866%] | SOP 1 subsection | bootstrap_resample(), driven by run_bootstrap_ci() | Custom (Formula 1) | Returns of the baseline 27; B = 10,000; n = 27; seed = 42 |
| Average-return CI [+0.2217%, +2.0365%] | SOP 1 subsection | Same as above | Custom (Formula 1) | Same input |
| 99.25% of resamples positive | SOP 1 subsection | Same as above | Custom (Formula 1) | Same input |
| Cross-check CI [+7.48%, +54.46%] | SOP 1 subsection | computeOwnBootstrapCI() in the dashboard, using mulberry32() | Custom, independent TypeScript | Same baseline 27; B = 2,000; seed = 42 |
| Regime tables, both methods | Tables 5 and 6 | Regime tagging routine | Custom | Baseline 27, tagged by calendar year and by drawdown from the $69,000 high of 2021-11-10 |
| Pearson r = +0.4907, t = 2.82, p ≈ 0.0094 | SOP 1 subsection | pearson_correlation(), wrapping scipy.stats.pearsonr | SciPy | Hold time in candles versus percentage return; recomputed r = 0.490698, p = 0.009356 |
| Spearman ρ = +0.4797, p ≈ 0.0113 | SOP 1 subsection | spearman_correlation(), wrapping scipy.stats.spearmanr | SciPy | Same input; recomputed ρ = 0.479728, p = 0.011335 |
| Blended-sleeve Sharpe, Sortino, drawdown | Table 12 | sharpe_sortino_ratios() and max_drawdown_pct() | Custom (Formulas 3 and 2) | Blended equity curve, 210 weekly contributions, 2022 to 2026 |
| Three-arm gross figures | Table 9 | run_benchmark_vs_passive() | Custom (Formulas 3 and 2) | Each arm's own equity curve, $10,000 start, annualization matched per arm |
| Three-arm fee-adjusted figures | Table 10 | Same, fee-adjusted branch | Custom (Formulas 3 and 2) | Round-trip drag per trade for the strategy, one-sided buy markup for the passive arms |
| Three-arm formulation-window figures | Table 11 | Same, formulation-period branch | Custom (Formulas 3 and 2) | 2018-01-01 to 2022-01-01 window |
| Six cost scenarios | Table 4 | Fee and slippage sweep, re-calling binomial_test() per scenario | SciPy for each p-value; custom for the cost model | Baseline 27 with each scenario's cost subtracted per trade |
| Forward test: 4 trades, 25.00%, −3.45% | Table 7 | Frozen backtest pipeline | Custom | BTCUSDT 4h, 2026-01-01 to 2026-07-31 |
| Window comparison, p = 0.2122 / 0.0261 / 0.0407 | Table 8 | binomial_test() per row | SciPy | Each window's own trade set: n = 25, n = 27, n = 56 |
| Backfill check: 27/27 matched, max difference 0.0000000000% | SOP 1 subsection | Regression comparison routine | Custom | 2018-extended run versus locked 2022 to 2026 run |
| No-lookahead: 180/180 truncation checks | Section F | Truncation-equality audit | Custom | ATR(14), ATR(200), fixed KDJ(9,3,3) recomputed on truncated series |
@ENDTABLE
@NOTE Note. Every row was recomputed from the exported trade log during final preparation and agreed with the reported figure to the precision printed here.

@PAGEBREAK
@H1 Appendix B

@H2 Source Form of Every Formula Written for This Study

The three formulas below are reproduced in LaTeX source form so a reader can reproduce the exact expression rather than re-key it from a rendered image. Formula numbering runs 1, 2, and 3.

Formula 1. Percentile bootstrap confidence interval. Parameters as used: B = 10,000, n = 27, fixed random seed 42, sampling with replacement.

@MONO T^{(b)} = \sum_{i=1}^{n} r_i^{(b)}, \qquad \bar{T}^{(b)} = \frac{1}{n}\sum_{i=1}^{n} r_i^{(b)}, \qquad b = 1,2,\ldots,B
@MONO CI_{95\%} = \left[\, Q_{2.5}\left(T^{(1)},\ldots,T^{(B)}\right),\; Q_{97.5}\left(T^{(1)},\ldots,T^{(B)}\right) \,\right]

Formula 2. Maximum drawdown.

@MONO P_t = \max_{u \leq t} E_u, \qquad DD_t = \frac{E_t - P_t}{P_t}\times 100, \qquad MDD = \min_t DD_t

Formula 3. Sharpe and Sortino ratios. Both assume a risk-free rate of zero and, for Sortino, a minimum acceptable return of zero.

@MONO SR = \frac{\bar{R}}{s_R}\sqrt{m}
@MONO \sigma_d = \sqrt{\frac{1}{N}\sum_{t=1}^{N}\left[\min(R_t, 0)\right]^2}, \qquad SoR = \frac{\bar{R}}{\sigma_d}\sqrt{m}
@MONO SR_{general} = \frac{E[R_a - R_f]}{\sigma_a}\sqrt{m}, \quad \text{with } R_f = 0 \text{ in this study}

@PAGEBREAK
@H1 Appendix C

@H2 Statement on Software Authorship

The statistical routines described in Section F fall into two groups. Three of the six reported quantities are direct calls into SciPy, a public open-source library, and implement no arithmetic of this project's own. The remaining three implement standard published formulas, each written independently from public documentation of that formula rather than copied from any particular paper's or repository's implementation.

@PAGEBREAK
@H1 Appendix D

@H2 Complete Trade Log for the Primary Window

@TABLE D1 | All 27 Trades, 2022 to 2026 Window
| Idx | Side | Entry time | Exit time | Return % | Bars | Exit reason | Dsp | Lrg | FVG | Swp | Vol | q |
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
@ENDTABLE
@NOTE Note. Return % is the trade's net percentage return. Dsp = displacement, Lrg = large origin candle, FVG = Fair Value Gap, Swp = liquidity sweep, Vol = volume expansion. Idx is the entry candle index. Bars is the holding period in 4-hour candles, so each exit time equals its entry time plus four hours times the Bars value. Exit reason is the first exit condition satisfied under the priority order in Figure 5. q is the sum of the five criterion flags.

Checks a reader can run on this table. The Return column holds 19 positive values out of 27, giving the 70.37% win rate. Those 27 values sum to +30.3064%, with a mean of +1.1225% and a standard deviation of 2.41%. Of the 27 trades, 9 closed on the ATR-move exit, 8 on the trailing exit, 8 on the KDJ-reset exit, and 2 on the hard stop-loss. No trade in this window closed on the hard take-profit.

@PAGEBREAK
@H1 Appendix E

@H2 Recomputing Every Number by Hand

This appendix exists so a reader with nothing but a calculator and Table D1 can check the paper. Every number below is derived only from those 27 rows. At the end is a short list of the numbers that cannot be checked this way, and what data would be needed to check them.

@H3 E1. Win rate, total return, average, and standard deviation

Win rate. Count the positive values in the Return % column. There are 19, and 19 ÷ 27 = 0.703703, so 70.37%. Total net return. Add all 27 values: +30.3064%, reported as +30.31%. Average return per trade. 30.3064 ÷ 27 = 1.12246, so +1.1225%. Standard deviation. Subtract 1.1225 from each return, square each result, add them, divide by 26, and take the square root. This gives 2.4101, reported as 2.41%. The divisor is 26, not 27, because this is the sample standard deviation.

@H3 E2. The binomial p-value

The one-sided exact p-value is the sum of nine terms divided by 2 to the power 27. The denominator is 2²⁷ = 134,217,728. The nine numerators are the binomial coefficients for k from 19 to 27.

@TABLE E1 | Binomial Coefficients Needed for the Table 3 p-Value
| k (wins) | 27 choose k | k (wins) | 27 choose k |
| 19 | 2,220,075 | 24 | 2,925 |
| 20 | 888,030 | 25 | 351 |
| 21 | 296,010 | 26 | 27 |
| 22 | 80,730 | 27 | 1 |
| 23 | 17,550 | Total | 3,505,699 |
@ENDTABLE
@NOTE Note. 3,505,699 ÷ 134,217,728 = 0.026119, which is the p = 0.0261 in Table 3. The two-sided value is twice this, 0.0522.

The same method gives the other two p-values in Table 4. For 17 wins, add the coefficients for k = 17 and k = 18, which are 8,436,285 and 4,686,825, to the 3,505,699 above, giving 16,628,809, and 16,628,809 ÷ 134,217,728 = 0.12389, which is p = 0.1239. For 15 wins, add the coefficients for k = 15 and k = 16, which are 17,383,860 and 13,037,895, giving 47,050,564, and 47,050,564 ÷ 134,217,728 = 0.35055, which is p = 0.3506.

@H3 E3. Final capital from $10,000

The Total return column of Table 9 adds the 27 returns. The Final capital column compounds them. To compound, divide each return by 100, add 1, and multiply all 27 results together. That product is 1.341777, so the compounded return is +34.18% and $10,000 × 1.341777 = $13,417.77. For the net-of-cost row in Table 10, subtract 0.20 from each return first, then compound the same way. The product is 1.271900, giving +27.19% and $12,719.00. The paper reports $12,719.01; the one-cent gap comes from Table D1 rounding each return to four decimals while the engine carries more.

@H3 E4. Time in market

Add the Bars column of Table D1. The total is 231 candles held. The window has 8,767 candles, and 231 ÷ 8,767 = 0.026349, which is the 2.6349% in the note to Table 9, reported as 2.63%.

@H3 E5. The calendar regime table

Table 5 splits the same 27 trades by the year of the entry time in Table D1. Nothing else is needed.

@TABLE E2 | Rebuilding Table 5 from Table D1
| Year | Trades | Wins | Win rate | Sum of returns | Share of +30.3064 |
| 2022 (indices 335 to 1913) | 7 | 4 | 4 ÷ 7 = 57.14% | +10.4525 | 10.4525 ÷ 30.3064 = 34.5% |
| 2023 (indices 2624 to 3947) | 6 | 3 | 3 ÷ 6 = 50.00% | −5.3947 | −5.3947 ÷ 30.3064 = −17.8% |
| 2024–2025 (indices 4455 to 8596) | 14 | 12 | 12 ÷ 14 = 85.71% | +25.2486 | 25.2486 ÷ 30.3064 = 83.3% |
@ENDTABLE
@NOTE Note. The three rows use all 27 trades: 7 + 6 + 14 = 27, and 10.4525 − 5.3947 + 25.2486 = +30.3064.

@H3 E6. The three-trade concentration

Take the three largest values in the Return % column: +6.6888, +4.6233, and +4.3634. They add to +15.6755, and 15.6755 ÷ 30.3064 = 0.51723, which is the 51.7% quoted in the Conclusions and the Limitations.

@H3 E7. The six cost scenarios

Each row of Table 4 subtracts one fixed cost from all 27 returns, then recounts. Because the cost is the same for every trade, the new total is simply the old total minus 27 times the cost. A trade flips from winner to loser when its return is smaller than the cost.

@TABLE E3 | Rebuilding Table 4 from Table D1
| Round-trip cost | New total = 30.3064 − (27 × cost) | Trades below the cost | New wins | Win rate |
| 0.00% | 30.3064 − 0 = +30.3064 | none | 19 | 70.37% |
| 0.10% | 30.3064 − 2.70 = +27.6064 | none | 19 | 70.37% |
| 0.14% | 30.3064 − 3.78 = +26.5264 | 7938, 8188 | 17 | 62.96% |
| 0.20% | 30.3064 − 5.40 = +24.9064 | 7938, 8188 | 17 | 62.96% |
| 0.24% | 30.3064 − 6.48 = +23.8264 | 7938, 8188 | 17 | 62.96% |
| 0.40% | 30.3064 − 10.80 = +19.5064 | 2859, 5825, 7938, 8188 | 15 | 55.56% |
@ENDTABLE
@NOTE Note. The smallest positive return in Table D1 is +0.1196 at index 7938, then +0.1264 at 8188, +0.2507 at 2859, and +0.3779 at 5825. That ordering decides which trades flip at each cost level. The p-value for each row comes from E2.

@H3 E8. The correlation and its t-value

Pearson's r uses the Bars column and the Return % column of Table D1. The mean of Bars is 231 ÷ 27 = 8.5556 candles and the mean of Return % is 1.1225. For each trade, multiply the two differences from their means and add the 27 products. Divide that by the square root of the sum of squared Bars differences times the sum of squared return differences. The result is r = 0.490698, reported as +0.4907. The t-value follows from r alone:

@EQ t = r × √(n − 2) ÷ √(1 − r²) = 0.4907 × √25 ÷ √(1 − 0.2408)
@EQ  = 2.4535 ÷ 0.8713 = 2.82

with df = n − 2 = 25. Spearman's ρ uses the same two columns after replacing each value with its rank, giving ρ = 0.479728, reported as +0.4797. The p-values attached to both, 0.0094 and 0.0113, come from SciPy and are not hand-computable; see E10.

@H3 E9. Dataset and schedule arithmetic

Candle count. 1,461 days × 6 candles per day = 8,766 intervals, plus the final stored row = 8,767 rows. Weekly contribution. $10,000 ÷ 210 weeks = $47.6190; for the 2018 window, $10,000 ÷ 209 = $47.8469. Annualization factor for 4-hour bars. 6 × 365.25 = 2,191.5; for weekly figures it is 52. Combined window in Table 8. 25 + 27 + 4 = 56 trades; 15 + 19 + 1 = 35 wins, and 35 ÷ 56 = 62.50%; returns +21.82 + 30.31 − 3.45 = +48.68%.

@H3 E10. What cannot be checked by hand, and why

The following numbers need data or computation that Table D1 does not contain. They are listed so no reader assumes an omission.

@LIST • The bootstrap interval [+5.9866%, +54.9866%], the point estimate +30.3065%, the average-return interval, and the 99.25% figure. These need 10,000 random resamples. The inputs, the 27 returns and the seed 42, are both given, but the arithmetic is not hand-scale.
@LIST • The Sharpe ratio, the Sortino ratio, and maximum drawdown in Tables 9 through 12. These are computed from full equity curves, one value per bar or per contribution week, not from trade returns. The construction is fully specified in Section E, but the underlying price series is needed to rebuild them.
@LIST • The exact p-values on the two correlations, 0.0094 and 0.0113. The r and ρ values themselves are hand-computable, as is the t-value; converting t to a p-value requires the t-distribution.
@LIST • Table 6, the drawdown-from-high regime split. Assigning each trade needs Bitcoin's price history relative to the $69,000 high of 2021-11-10. The counts and sums can still be checked: 12 + 8 + 7 = 27, and −1.63 + 18.89 + 13.05 = +30.31.
@LIST • Table 11, the 2018 to 2022 window, and Table 7, the 2026 forward test. These use trade sets that are not printed in this paper.

For everything on that list, Appendix A names the exact function and the exact input, so the computation can be repeated by anyone who runs the code.
