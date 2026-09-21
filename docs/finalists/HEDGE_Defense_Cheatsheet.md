@H1 HEDGE — ISEF Defense Cheat Sheet
@SUBTITLE Quick reference: reported numbers, how each was built, how each was solved, and why that tool over another. Not the paper — see HEDGE_Paper.docx for full text, citations, and Appendices A-E for per-number traceability and hand-computation.

@H2 Study at a Glance

Rule-based BTC/USDT strategy (MACD momentum gate + KDJ entry/exit + dual-ATR risk sizing + Smart Money Concepts Order Blocks) backtested candle-by-candle on 8,767 four-hour candles, 2022-01-01 to 2026-01-01. Every rule and parameter was set by eye from 2018-01 to 2022-01 charts and frozen before the reported window was measured (Fig. 1).

@LIST SOP 1 — Does the strategy itself win, before and after realistic costs? Answer: yes before costs (p=0.0261), no after them (p=0.1239).
@LIST SOP 2 — How does it compare to weekly DCA and lump-sum buy-and-hold from equal capital? Answer: DCA wins on final value ($22,312.94 vs $13,417.77); the strategy wins on risk-adjusted shape at only 2.63% time in market.
@LIST SOP 3 — Does blending a strategy share into a DCA plan improve its risk-adjusted profile? Answer: yes, all three measures (Sharpe, Sortino, MaxDD) improve monotonically from 0% to 30% strategy share.

@FIG Figure 9 | Headline Numbers at a Glance | fig09_headline_summary.png

@PAGEBREAK
@H2 SOP 1 — Strategy Performance

@TABLE cheat-1 | Baseline Performance, 2022-2026, Gross of Costs
| Metric | Value |
| Trades | 27 |
| Wins / Losses | 19 / 8 |
| Win rate | 70.37% |
| Total net return | +30.31% |
| Avg return/trade | +1.1225% |
| SD of return/trade | 2.41% |
| One-sided binomial p | 0.0261 |
| Bootstrap 95% CI (total return) | [+5.9866%, +54.9866%] |
| Pearson r (hold time vs return) | +0.4907, p ≈ 0.0094 |
| Spearman ρ (hold time vs return) | +0.4797, p ≈ 0.0113 |
@ENDTABLE

How built. Candle-by-candle `simulate_trades()`, no-lookahead enforced with runtime assertions at every forward-search site. Entry needs all six MACD+KDJ+ATR+SMC-OB conditions at one candle close (Fig. 4); exits checked in a fixed priority order each candle (Fig. 5).

@FIGROW
Figure 4 | Long Entry Decision Sequence | fig04.png
Figure 5 | Exit Priority Order | fig05.png
@ENDFIGROW

How solved.
@LIST Win rate / return / SD — descriptive statistics, no test.
@LIST One-sided binomial p — `binomial_test()`, a direct call to `scipy.stats.binomtest(19, 27, 0.5, alternative="greater")`.
@LIST Bootstrap CI — `bootstrap_resample()`, a hand-written percentile bootstrap (Formula 1): resample the 27 returns with replacement B=10,000 times (seed 42), take the 2.5th/97.5th percentiles of the resampled totals.
@LIST Pearson / Spearman — `pearson_correlation()` / `spearman_correlation()`, direct calls to `scipy.stats.pearsonr` / `spearmanr` on (hold_bars, pnl_pct).

Why this tool, not another.
@LIST Exact binomial, not a normal-approximation z-test — n=27 is small enough that the normal approximation to the binomial can misstate the tail; the exact test has no approximation error to disclose.
@LIST Plain percentile bootstrap, not `scipy.stats.bootstrap`'s BCa option — matches the textbook form Efron & Tibshirani (1993) describe, and matches what the independent JS dashboard cross-check also implements, which is what makes the two intervals comparable at all (see Q&A page).
@LIST Both Pearson AND Spearman, not just one — Pearson checks a straight-line relationship, Spearman checks only a consistent direction; running both is a robustness check, not redundancy.

Cost sensitivity (condensed from the paper's Table 4):

@TABLE cheat-2 | Win Rate and Significance Across Cost Scenarios
| Round-trip cost | Win rate | Total return | Binomial p (1-sided) |
| Gross (0%) | 70.37% | +30.31% | 0.0261 |
| 0.10% (fees only) | 70.37% | +27.61% | 0.0261 |
| 0.20% (primary, fee+slippage) | 62.96% | +24.91% | 0.1239 |
| 0.40% (high band) | 55.56% | +19.51% | 0.3506 |
@ENDTABLE
@NOTE Note. The flip at 0.14%-0.24% is exactly two trades (indices 7938, 8188), each worth +0.12%/+0.13% before costs.

@FIG Figure 6 | Win Rate and Significance Across Six Transaction-Cost Scenarios | fig07.png

@PAGEBREAK
@H2 SOP 2 — Strategy vs. Dollar-Cost Averaging vs. Buy-and-Hold

@TABLE cheat-3 | Three-Arm Head-to-Head, 2022-2026, Gross of Costs, $10,000 Start
| Arm | Total return | Final capital | Sharpe | Sortino | MaxDD | Time in market |
| OB-gated strategy | +30.31% | $13,417.77 | 1.114 | 2.727 | −6.46% | 2.63% |
| Weekly DCA into BTC | +123.13% | $22,312.94 | 0.556 | 0.886 | −27.85% | 100.00% |
| Lump-sum buy-and-hold | +90.07% | $19,007.32 | 0.564 | 0.803 | −67.21% | 100.00% |
@ENDTABLE
@NOTE Note. Strategy Total return is the arithmetic sum of the 27 trade returns (the +30.31% headline); Final capital compounds the same returns in sequence, giving +34.18% compounded, hence $13,417.77. Net of a 0.20%/0.10% cost model, the strategy row becomes +24.91% / $12,719.01; both passive arms barely move.

@FIG Figure 7 | Three Arms Grown From an Equal $10,000 Start, 2022-2026 | fig06.png

How built. `run_benchmark_vs_passive()` (Section 5B). All three arms share the same window and the same ISO-week contribution-timing rule (a contribution lands on the first bar of every ISO week, buys at that bar's close). Strategy arm sits in cash between trades and compounds only at trade-exit bars; DCA buys $47.6190/week across 210 weeks; lump-sum buys the full $10,000 at the first bar's open and holds.

How solved. `sharpe_sortino_ratios()` and `max_drawdown_pct()` — both custom (Formulas 3 and 2), computed once per arm's own equity curve, annualized with each arm's own frequency (m = 2,191.5 for the strategy and lump-sum's 4-hour bars, m = 52 for DCA's weekly bars).

Why custom, not a library call.
@LIST No single SciPy/package function turns an arbitrary-frequency equity curve into an annualized Sharpe/Sortino/MaxDD in one call — these were assembled from Sharpe (1966) and Sortino & van der Meer (1991) directly.
@LIST Sortino's downside deviation here divides by N (all periods), not just the count of losing periods — the textbook-correct convention, and a deliberate departure from a popular public tutorial that uses the losing-periods-only shortcut (checked line-by-line; see PROVENANCE_VERDICT.md #10).
@LIST Max drawdown is the standard three-line running-peak/percent-decline formula — too short and too standard to warrant a library dependency.

@PAGEBREAK
@H2 SOP 3 — Blended DCA + Strategy Sleeve

@TABLE cheat-4 | Risk-Adjusted Profile at Increasing Strategy Allocation
| Split (DCA / Strategy) | Sharpe | Sortino | MaxDD |
| 100% / 0% | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |
@ENDTABLE

@FIG Figure 8 | Risk-Adjusted Profile Across Increasing Strategy Allocations | fig08.png

How built/solved. Same `sharpe_sortino_ratios()` / `max_drawdown_pct()` as SOP 2, applied to the blended equity curve (Bitcoin units plus a strategy-sleeve cash balance that compounds at each trade exit, never moved back into Bitcoin) at each of four allocation levels.

Why no p-value here. Sharpe, Sortino, and MaxDD are each one number computed from one realized price path — there is no sampling distribution behind them, so H₀₂/H₁₂ are judged descriptively: do all three move the same direction at every step, with no reversal. They do.

@PAGEBREAK
@H2 Statistical Tool Chooser

@TABLE cheat-5 | Every Reported Statistic, Source, and Why
| Quantity | Source | Why this, not the alternative |
| Exact binomial test | SciPy `binomtest` | Exact for small n; no normal-approximation error to disclose |
| Pearson's r + p | SciPy `pearsonr` | Straight-line relationship check |
| Spearman's ρ + p | SciPy `spearmanr` | Monotonic-only check; run alongside Pearson as a robustness pair |
| Bootstrap 95% CI | Custom, Formula 1 | Plain percentile form (not BCa) matches the independent JS cross-check's method, keeping the comparison meaningful |
| Maximum drawdown | Custom, Formula 2 | 3-line running-peak formula; too standard/short to need a library |
| Sharpe & Sortino | Custom, Formula 3 | No single library call spans arbitrary-frequency annualization; Sortino uses the full-N (not losing-only) downside-deviation convention |
@ENDTABLE
@NOTE Note. Fisher's exact test, Welch's t-test, and an MDE power-analysis formula were used in an earlier per-OB-criterion draft and have since been fully removed from research_analysis.py (not merely unused) — that criterion-by-criterion comparison was cut from the final paper. If asked "what happened to Fisher/Welch," this is the answer.

@PAGEBREAK
@H2 Known Corrections and Panel Q&A Rapid-Fire

@LIST Backtest-engine bug (disclosed). The FVG and Displacement quality-criteria search loops could read 1-2 bars past an Order Block's own confirmation bar, because the loop was bounded by dataset length instead of the confirmation bar. Found via the no-lookahead audit; fixed by freezing the window at the confirmation bar. Does not change the 27-trade baseline, which applies no quality-score filter.
@LIST p-value overclaim (corrected). Two correlation p-values were once written as "p < 0.001"; independently recomputed at p ≈ 0.0094 (Pearson) and p ≈ 0.0113 (Spearman) — still significant at α=0.05, wrong significance bucket at α=0.001. Both source documents corrected.
@LIST Bootstrap B mismatch (both correct, kept separate). Python (`bootstrap_resample`, B=10,000, seed 42) gives [+5.99%, +54.99%]. The independent JS dashboard (`computeOwnBootstrapCI`, B=2,000, seed 42, its own mulberry32 PRNG) gives [+7.48%, +54.46%]. Root cause confirmed to be the B difference alone — porting mulberry32 to Python reproduced the JS figure exactly. The two are disclosed together, never merged into one number.
@LIST Dual KDJ architecture (by design, not a bug). Entry gating reads one fixed, full-history KDJ(9,3,3) computed once over the whole dataset — it never changes trade to trade. A separate state machine (`kdj_reset_init/update/exit`), seeded from the fixed KDJ at the entry bar, times one exit signal only, with a window `w` set once per trade (observed range 14-439, median 74). Confirmed by read-only audit that the exit-side window has no effect on entry.
@LIST 190-signal figure (open, not settled). The paper's "190 qualifying indicator signals" denominator was derived from the indicators-only ablation's entry-anchored stop rule, not the OB-gated strategy's own risk rules — two differently-filtered populations. Disclosed as unresolved; do not cite as a settled figure.
@LIST AI-assistance disclosure. Every commit that introduced or materially edited the statistics functions carries a `Co-Authored-By: Claude Sonnet 5` trailer. All hypothesis tests are direct, unmodified `scipy.stats` calls; the four custom-math functions (bootstrap, MDE formula since removed, Sharpe/Sortino, max drawdown) implement long-standing textbook formulas (Efron 1979; Sharpe 1966; Sortino & van der Meer 1991) independently assembled from public documentation, not copied from any single paper or repository — verified against `scratch/regression.py`'s golden-master fixtures.
@LIST Forward test (unfavorable, reported as-is). 4 out-of-sample trades, 2026-01 to 2026-07, 25.00% win rate, −3.45% total return. This is the only result out-of-sample in both the rule-building sense and the code-checking sense; every prior window either built the rules or was examined while finding the disclosed bug.
@LIST Return concentration. The three largest trades (+6.6888%, +4.6233%, +4.3634%) sum to +15.6755%, which is 51.7% of the +30.3064% total — profit rests on a few large outcomes, not a steady per-trade edge.

@PAGEBREAK
@H2 Figure Index

@FIGGRID
Fig. 1 — Formulation / primary-window / forward-test timeline | fig01.png | Framework A
Fig. 2 — Data collection and verification sequence | fig02.png | Framework B
Fig. 3 — Order Block detection, quality scoring, eligibility | fig03.png | Framework D
Fig. 4 — Long entry decision sequence | fig04.png | Framework D, SOP 1
Fig. 5 — Exit priority order | fig05.png | Framework D, SOP 1
Fig. 6 — Win rate/significance across cost scenarios | fig07.png | SOP 1, Table 4
Fig. 7 — Three arms grown from $10,000 | fig06.png | SOP 2, Table 9
Fig. 8 — Risk-adjusted profile across allocations | fig08.png | SOP 3, Table 12
Fig. 9 — Headline numbers at a glance | fig09_headline_summary.png | This cheat sheet only
@ENDFIGGRID
