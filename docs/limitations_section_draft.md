# Limitations — Draft for Paper Integration

> **Status: draft for review, not yet inserted into the paper.** Every
> quantitative claim below is translated from a specific scratch script's
> output in this session. Translation points are marked
> **[TRANSLATION NOTE]** wherever a script number is being converted into
> paper prose, so they can be spot-checked independently. Nothing in
> `src/`, `export_gui_data.py`, `db_manager.py`, any committed artifact, or
> any locked result was modified to produce this content — all four
> subsections are analysis run against a copy of the existing 27-trade
> `min_ob_quality=0` baseline log, offline, against `artifacts/candles.csv`.

---

## a. Out-of-sample validation

**[TRANSLATION NOTE]** Lightly edited for paper voice from the disclosure
paragraph drafted in the prior investigation session; no facts changed, only
framing (removed session/script meta-references, tightened for third-person
academic prose). The second paragraph below is updated from the original
draft: the "unaudited and unauditable" framing has been replaced with a
concrete, author-confirmed account (see commit history / session notes for
provenance of this disclosure), and a third and fourth paragraph have been
added reporting two new validation scripts' results in full, including an
unfavorable one, per the project's own "report null and unfavorable results
as they come" rule.

> Git history was audited for every parameter governing entry and exit
> logic. The eight entry/exit threshold parameters (minimum stop distance,
> the four KDJ entry caps/floors, the ATR-multiple exit and breakeven
> triggers, and the minimum reward:risk ratio) held their current values
> throughout this repository's history — including through a period when a
> full-window randomized parameter search (fifty trials, maximizing net
> return over the entire dataset) coexisted with the strategy. That search's
> output was only ever used to train a since-removed classifier layer and
> never overwrote these defaults. The KDJ(9,3,3) and MACD(12,26,9) periods
> and the market-structure lookback windows (5 and 50 bars) were never
> exposed as tunable parameters at all: they are hardcoded constants, with
> the structure lookback values explicitly inherited from a published
> reference implementation rather than fitted. No evidence was found that
> any of these values were selected via feedback from full-window
> performance.
>
> The strategy's entry/exit rule *structure* (as opposed to its parameter
> values) was confirmed by the developer to have been originally formulated
> against 2018–2022 BTC/USDT data, predating this repository's own history.
> The developer's account is that only the minimum stop-distance filter
> (the "v9" 1.5%-of-entry threshold) was adjusted after that formulation
> period, with the remaining rule structure held fixed. This filter has a
> bounded, checkable role in trade *exits* — only 2 of the 27 baseline
> trades resolve via a direct stop-loss hit, with the remaining 25 exiting
> through ATR-move, trailing, or KDJ-reset logic instead — but a less bounded
> role in trade *entry selection*, since it also screens which candidate
> setups qualify as trades at all, and that channel cannot be independently
> audited from available records. Consistent with this account: performance
> on the 2018–2022 formulation-period data (25 trades, 60.00% win rate,
> +21.82% total return; §[Out-of-sample and extended-history validation] in
> the Results section) is measurably weaker than the reported 2022–2026
> window (27 trades, 70.37%, +30.31%) — a gap of the size a
> feedback-adjusted stop filter would plausibly produce, though this is not
> proof of the mechanism, only a consistent and disclosable one.
>
> Given the trade frequency observed (27 trades over 48 months, ≈0.56
> trades/month), a calendar holdout reserving even six months of data would
> be expected to contain only three to four trades — too few to support any
> meaningful statistical test on its own. We therefore do not attempt a
> holdout split on the reported window. Instead, two supplementary checks
> were run and are reported in full regardless of outcome. First, a forward
> out-of-sample test: BTCUSDT 4H data through 2026-07-31 (genuinely postdating
> every commit to the strategy's source file) produced 4 new trades — 1
> win, 3 losses, 25.00% win rate, −3.45% total return. This is a small,
> directionally unfavorable result reported as-is, not as a rescue: 4 trades
> cannot confirm or refute anything about the strategy's edge on their own,
> but they are the only genuinely uncontaminated prospective evidence that
> exists for this rule set, and the honest reading is that they do not add
> reassurance. Second, an 8-year backfill audit confirmed the locked
> 2022–2026 baseline reproduces byte-identically even with four additional
> years of indicator warm-up prepended (a real methodological risk, given
> MACD's and the static KDJ's recursive, theoretically unbounded-memory
> smoothing — not guaranteed a priori, and empirically confirmed clean).
>
> The regime breakdown in the Results section (decomposing the same 27
> trades across three structurally distinct market conditions spanning the
> full reported window) remains the most informative robustness check
> available specifically for the reported window's internal consistency;
> the forward-pull and backfill results above are offered as separate,
> complementary evidence about the strategy's behavior outside that window
> entirely.

---

## b. Transaction costs

**[TRANSLATION NOTE]** Fee figure corrected this session. The prior
session's "4-10bps" range was an unverified placeholder; it has been
replaced with Binance's published USDT-M Futures standard-tier (VIP 0, no
BNB fee discount) taker rate, confirmed via Binance's fee-schedule FAQ and
cross-checked against independent fee-tracking sources: **0.05% (5bps) per
side**, i.e. **0.10% round-trip**. We use the taker rate because entries and
exits in this backtest are triggered at a bar-close price crossing a
threshold — a market-order-like fill, not a resting limit order.

Slippage is reported as a **separate** line item, since it is not a
published exchange number but a conservative modeling estimate: **0.05% per
side (0.10% round-trip)**, appropriate for a deep, liquid pair like
BTC/USDT at 4-hour bar resolution.

> The paper's headline return figures (+30.31% total net return, 70.37% win
> rate) are reported gross of trading costs. Applying the confirmed Binance
> USDT-M Futures standard-tier taker fee alone (0.10% round-trip, no
> slippage) reduces total net return to +27.61%; the win rate and every
> significance test are unaffected (no trade's return is small enough in
> magnitude to change classification from this fee alone). Applying the fee
> together with a conservative slippage estimate (0.10% + 0.10% = 0.20%
> round-trip drag per trade — our primary fee-adjusted scenario) reduces
> total net return to +24.91% and win rate to 62.96% (17 of 27 trades, down
> from 19). Two trades flip from winner to loser under this drag: one that
> gained +0.12% gross and one that gained +0.13% gross, both close enough to
> breakeven that a 0.20% round-trip cost is sufficient to reverse their
> sign.
>
> This drag is enough to move the one-sided exact binomial test on win rate
> from p = 0.0261 (significant at α = 0.05) to **p = 0.1239 (not
> significant)**. We report this plainly rather than treating fee-adjustment
> as a robustness check the result passes: **the win-rate significance
> claim is fragile to a realistic, conservative transaction-cost
> assumption.**
>
> By contrast, the return-magnitude tests (Welch's t-test comparing mean
> return between each orthogonal quality criterion's True/False subgroups)
> are **mathematically unaffected** by this adjustment. Because the
> round-trip drag is a flat percentage applied identically to every trade,
> it shifts every subgroup's mean return by the same constant without
> changing the *difference* between subgroup means or either subgroup's
> variance — the quantities a two-sample t-test depends on. We verified this
> directly: the Welch t-statistic and p-value for all five criteria are
> identical to four decimal places whether computed on gross or
> fee-adjusted returns. Readers should not expect fee adjustment to move
> any return-based (as opposed to win/loss-based) test in this paper.
>
> **A multiple-comparisons caution, not a finding:** under a wider
> sensitivity band explored around the primary scenario (round-trip drag
> from 0.14% to 0.40%, spanning both more optimistic and more pessimistic
> fee/slippage assumptions than the confirmed primary figure), one
> criterion's Fisher's exact test — VolExpansion, testing win/loss
> independence from the volume-expansion quality flag — crosses p < 0.05
> (p = 0.0185) only at the most pessimistic end of that band (0.40%
> round-trip drag), driven by all newly-flipped trades at that drag level
> sharing the VolExpansion=True flag. At the primary, defensible scenario
> (0.20% round-trip), VolExpansion's Fisher's exact p is 0.1071 — not
> significant. Testing five criteria across several drag assumptions is
> exactly the kind of repeated testing where an occasional p < 0.05 is
> expected by chance alone; we flag this as a sensitivity-band artifact to
> watch for, not as evidence that volume expansion predicts outcome.

---

## c. Statistical power at n = 27

**[TRANSLATION NOTE]** This subsection is intended to **replace** any
existing paper language stating that quality-criterion subgroup comparisons
"show no significant difference" — that phrasing implies a tested and
rejected effect, which overstates what a non-significant result at this
sample size can support. See the minimum-detectable-effect (MDE)
calculation below for the specific, defensible replacement claim.

> For each of the five orthogonal Order Block quality criteria, a two-sample
> comparison (Welch's t-test) was run between trades where the criterion was
> present versus absent, on this study's 27-trade baseline. All five
> comparisons fail to reach significance at α = 0.05. We characterize what
> this null result can and cannot support using a post-hoc
> minimum-detectable-effect (MDE) calculation: given each criterion's actual
> observed subgroup sizes (ranging n = 4 to n = 23) and observed
> within-group standard deviations, we compute the smallest true mean-return
> gap between subgroups that a test at this sample size could detect 80% of
> the time at α = 0.05.
>
> | Criterion | Observed subgroup gap | Minimum detectable effect (80% power) |
> |---|---|---|
> | Displacement | 0.74 percentage points | 2.23 pp |
> | LargeBar | 0.23 pp | 2.25 pp |
> | FVG | 0.56 pp | 2.91 pp |
> | LiqSweep | 0.74 pp | 2.53 pp |
> | VolExpansion | 0.78 pp | 2.47 pp |
>
> Every observed gap is smaller than its corresponding MDE — by a factor of
> roughly 3x (VolExpansion, FVG) to 10x (LargeBar). **The correct
> interpretation of these null results is that the study is underpowered to
> reliably detect criterion-level effects of the size actually observed, not
> that no true effect exists.** A true underlying gap as large as
> 2.2-2.9 percentage points between a criterion's True and False subgroups
> could exist in the population and this sample would still have a
> meaningful chance of failing to detect it. We revise the paper's framing
> accordingly: report the non-significant test results as evidence of
> *insufficient power to distinguish quality criteria at this sample size*,
> not as evidence that quality criteria carry no signal.
>
> This power limitation is specific to the *subgroup* (criterion-level)
> comparisons, which necessarily split an already-small n=27 sample into
> smaller pieces (as few as 4 trades in one subgroup). It does not extend to
> the study's core, full-sample return finding: a nonparametric bootstrap
> (10,000 resamples with replacement) of the 27-trade baseline's own return
> distribution gives a point estimate of +30.31% total net return with a 95%
> confidence interval of **[+5.99%, +54.99%]** — wide, but not crossing
> zero (99.25% of resampled totals were positive). The core return result is
> directionally robust at this sample size even though the finer-grained
> quality-criterion breakdown is not adequately powered to resolve.

---

## d. Leverage

> This study does not model leveraged or margined positions, and reports
> unlevered, notional (spot-equivalent) returns throughout. This is a
> deliberate scope decision rather than an oversight: the backtest engine
> evaluates every exit condition — hard stop-loss, take-profit, the trailing
> exit, the ATR-move exit, and the breakeven-stop adjustment — at bar-close
> resolution only. Intrabar high/low prices are available in the underlying
> candle data and are used elsewhere in the pipeline (order-block touch
> detection and several structural quality criteria), but no exit or
> position-sizing decision reads them, and the engine has no concept of a
> margin or liquidation price at any leverage level.
>
> A defensible leveraged backtest requires intrabar liquidation tracking: a
> position can be liquidated by a price excursion that fully reverses within
> a single bar, which a close-resolution simulation cannot see. Applying a
> leverage multiplier after the fact to this study's existing close-basis
> trade log would not model that risk — it would silently assume every
> trade's realized path was free of any intrabar excursion large enough to
> trigger liquidation, which the data cannot confirm one way or the other.
> We therefore report unlevered results only, consistent with common
> practice in the technical-trading-rule literature, which typically reports
> notional returns adjusted for transaction costs rather than
> leverage-and-liquidation-aware returns (e.g., Svogun & Bazán-Palomino,
> 2022, who evaluate moving-average and support/resistance rule profitability
> on cryptocurrency data net of transaction costs on a notional basis).

**[TRANSLATION NOTE]** The Svogun & Bazán-Palomino (2022) citation was
web-verified this session to be a real paper — "Technical analysis in
cryptocurrency markets: Do transaction costs and bubbles matter?", *Journal
of International Financial Markets, Institutions and Money*, Vol. 79 (2022)
— testing moving-average and support/resistance rules on crypto data net of
transaction costs. I was **not** able to independently verify from this
session's search results that it explicitly frames its results as
"unlevered notional returns" in those exact terms (some secondary sources
list the author order as "Bazán-Palomino & Svogun" rather than "Svogun &
Bazán-Palomino" — likely just inconsistent secondary-source formatting, but
worth a quick check against your own reference manager entry before this
citation goes in the paper). Please verify this specific characterization
against your own copy of the paper (and the "and similar" citations you
already have in the bibliography) before finalizing this subsection.
