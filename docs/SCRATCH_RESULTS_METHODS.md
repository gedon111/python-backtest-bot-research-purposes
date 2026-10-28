# Results & Methods Reference

Canonical record of locked results, corrected errors, and disclosed design
decisions for the BTC/USDT MACD+KDJ+ATR+SMC backtest study (Jan 2022 - Jan
2026, 4h candles). This is the reference to cite for any number, correction,
or methodological decision appearing in the paper or a panel Q&A. Update it
whenever a result, correction, or open question changes; do not let a number
here go stale relative to the codebase.

## Dataset

`artifacts/candles.csv`: 8,767 bars covering 1,461 days (365*4 + 1 leap day
in 2024, x 6 bars/day, plus one boundary-inclusive endpoint bar). The figure
is NOT 8,760 - an earlier draft used a plain arithmetic figure that omitted
the leap day and endpoint bar; corrected. Bars are not trimmed.

## Locked headline results

- Baseline (min_ob_quality=0): 27 trades, 70.37% win rate, +30.31% total net
  return, +1.12% avg return/trade, SD 2.41%.
- One-sided binomial p = 0.026 (two-sided 0.052) for the q>=0 baseline.
- Ablation A (indicators-only, entry-ATR stop): 140 trades, 60.00%, -14.63%.
- Ablation B (indicators-only, swing-pivot stop): 138 trades, 55.07%, -25.50%.

## Benchmark vs. passive strategies

`run_benchmark_vs_passive()` (research_analysis.py, Section 5B), $10,000
notional starting capital, gross unless stated:

**2022-2026 window:**
- OB-gated strategy: +30.31% -> $13,417.77 (Sharpe 1.114, Sortino 2.727,
  MaxDD -6.46%, 2.63% time-in-market).
- Weekly DCA into BTC: +123.13% -> $22,312.94 (Sharpe 0.556, MaxDD -27.85%,
  100% time-in-market).
- Lump-sum buy & hold: +90.07% -> $19,007.32 (Sharpe 0.564, MaxDD -67.21%,
  100% time-in-market).

DCA and lump-sum B&H both beat the strategy in raw terminal value over this
window. Any statement of the strategy "beating" DCA/BTC must carry the
exposure-time caveat (2.63% vs 100%) in the same sentence - the strategy's
edge is risk/exposure-adjusted, not a raw-return claim.

Fee-adjusted variant: strategy +24.91% -> $12,719.01.

**2018-2022 window (formulation period, NOT out-of-sample):** strategy
+21.82% -> $12,282.53; DCA +439.88% -> $53,987.55; lump-sum +236.96% ->
$33,696.49.

**Sharpe at one common frequency (2026-10-28, paper bitcoin (6)).** The
Sharpe figures above are each arm's NATIVE frequency (strategy and lump sum
per 4h bar, m = 2,191.5; DCA weekly, m = 52), so they are not comparable
across arms. From bitcoin (6) on, the paper reports every arm at the UTC daily
close, m = 365, from `run_benchmark_daily_sharpe()` (research_analysis.py,
Section 5B; artifact `artifacts/benchmark_daily_sharpe.json`). The native
figures above are unchanged in code and still produced by
`run_benchmark_vs_passive()`. Daily-close values:
- 2022-2026 gross: strategy 1.1151, DCA 0.5581, lump sum 0.5534.
- 2022-2026 net of costs: strategy 0.9446, DCA 0.5552, lump sum 0.5534.
- 2018-2022 gross: strategy 0.681, DCA 0.802, lump sum 0.796.
- Blend (Table 12): 100/0 0.558, 90/10 0.581, 80/20 0.606, 70/30 0.632.
No ordering changed: the strategy is highest in 2022-2026 and lowest in
2018-2022, and the blend still rises at every step.

**Funding (2026-10-28).** `experimental/funding_cost.py` on Binance's monthly
BTCUSDT funding archives (`experimental/data/btcusdt_funding.csv`): the 27
trades crossed 114 settlements; longs paid 0.17 pp, shorts received 0.29 pp,
net credit 0.11 pp. Total after 0.20% cost and funding +25.02% (vs +24.91%),
17/27 wins, p = 0.1239 unchanged.

**OPEN (found 2026-10-28, not fixed - needs review):** `_run_dca_dollar_arm()`
reports DCA final capital and total return at the LAST CONTRIBUTION bar (first
bar of the window's last ISO week, 2025-12-29), not the window's last bar
(2026-01-01), while the strategy and lump-sum arms are measured at the last
bar. At the last bar the 2022-2026 DCA value is $22,395.86, not $22,312.94.
The paper's ordering is unaffected; the figure is left as published until
reviewed.

**Mark-to-market and cash-sleeve control (2026-10-28, paper bitcoin (7)).**
`run_benchmark_mark_to_market()` (research_analysis.py, Section 5B; artifact
`artifacts/benchmark_mtm.json`) values every arm at the UTC daily close with
the strategy's open trades marked to market, and takes maximum drawdown on
the same daily values. Final capitals are unchanged (asserted). From bitcoin
(7) on, the paper's Sharpe and drawdown come from here:
- 2022-2026 gross: strategy 1.1440 / -6.64%, DCA 0.5581 / -36.02%, lump sum
  0.5534 / -66.93%.
- 2022-2026 net: strategy 0.9456 / -8.13%, DCA 0.5552 / -36.02%, lump sum
  0.5534 / -66.93%.
- 2018-2022 gross: strategy 0.607 / -8.24%, DCA 0.802 / -52.37%, lump sum
  0.796 / -81.18%.
The DCA daily drawdown (-36.02%, 2022-06-07 to 2022-06-19, 25 contributions in)
is deeper than the weekly-sampled -27.85%.
Blend, NET (0.20% per strategy trade, 0.10% per BTC buy), strategy sleeve vs
cash sleeve (same share held as cash at 0%): 100/0 0.555 / -36.02%; 90/10
0.576 / -31.03% vs 0.566 / -31.22%; 80/20 0.598 / -28.30% vs 0.576 / -28.87%;
70/30 0.621 / -26.43% vs 0.585 / -27.34%. H2 (decision rule set in bitcoin
(7): strategy sleeve beats cash sleeve on both measures at every share, net)
HOLDS, gross too; the drawdown margin over cash is small (0.18 / 0.57 / 0.90
points). Blend construction CHANGED in the same function: a contribution that
arrives while a trade is open now waits as cash until the exit (4 of 210
contributions; 70/30 gross final value 406.3435 -> 406.3271, via
`_blend_mid_trade_effect()`). `run_dca_blend_analysis()` and
`run_benchmark_daily_sharpe()` are unchanged and still produce the older figures.

**After-cost uncertainty and stop realism (2026-10-28, bitcoin (7)).**
`experimental/bootstrap_net_4h.py`: net 0.20% percentile CI on total
[+0.59%, +49.59%]; stationary block bootstrap (seed 42, L = 3) [-1.29%,
+49.96%], mean [-0.048, +1.850] -- includes zero. Binomial power at true 60/65/70%:
0.18 / 0.36 / 0.58; H1 significant only while cost < 0.1196%.
`experimental/stop_intrabar.py`: with the stop checked against candle high/low
(baseline is close-only), 6 trades change; gross 18/27 wins, +24.85%,
p = 0.0610; net 16/27, +19.45%, p = 0.2210. Funding at full precision: longs
paid 0.175 pp, shorts received 0.287 pp, net credit 0.112 pp.

## Corrected errors (disclosed)

### Backtest-engine bug

FVG and displacement quality criteria could read 1-2 bars past an Order
Block's own confirmation bar - the forward-search loop was bounded by
dataset length instead of the confirmation bar. Found via the no-lookahead
audit of `compute_smc()`; fixed by freezing the search window at the
confirmation bar (commit cb4ed93). Does not change the 27-trade q>=0
baseline, since that baseline is unaffected by quality filtering.

### Reporting/documentation errors (2026-08-08 cross-surface numerical audit)

1. Pearson/Spearman correlation (hold_bars vs pnl_pct, 27 baseline trades)
   p-values were reported as "p < 0.001" in two draft documents.
   Independently recomputed via scipy: actual p ~= 0.0094 (Pearson,
   r=+0.4907, t=2.82, df=25) and p ~= 0.0113 (Spearman, rho=+0.4797) -
   still significant at alpha=0.05, wrong significance bucket at
   alpha=0.001. Both source documents corrected.
2. Bootstrap CI on total return has two different, individually-correct
   values depending on computation surface: Python
   (`analysis/bootstrap_power_analysis.py`, B=10,000, seed=42) ->
   [+5.99%, +54.99%], the paper's canonical figure. Dashboard
   (`dashboard-v2/src/components/stats/statsCompute.ts`'s
   `computeOwnBootstrapCI`, B=2,000, seed=42, JS mulberry32 PRNG) ->
   [+7.48%, +54.46%]. Root cause is the B mismatch alone, not a logic
   bug - verified by porting the mulberry32 PRNG to Python and reproducing
   [+7.48%, +54.46%] exactly at B=2,000. Both values are reported and the
   gap is explained; they are not unified into one number.

## Open / unresolved question

The paper reports "190 total qualifying indicator signals" as the
denominator for the claim that 25 of 27 OB-gated trades (92.6%) coincided
with independent indicator signals. That 190 was derived using the
indicators-only ablation's 1.5*ATR entry-anchored stop, not the OB-gated
strategy's own risk rules - the two populations are filtered differently.
This is unresolved; 190 should not be cited as a settled figure until it
is.

## Design decisions

### Dual-system KDJ architecture

Entry gating (every K/D/J reference in entry conditions) reads the static,
full-history KDJ(9,3,3) computed once over the whole dataset. The exit-side
reset period `w` has no effect on entry - confirmed by read-only audit.

The post-entry exit signal uses a separate state machine
(`kdj_reset_init`/`update`/`exit`) seeded from the static KDJ value at the
entry bar (not 50, not backfilled), recursed forward with period = entry_idx
- triggering_OB_bar, frozen for that trade's life. It governs exit timing
only.

Observed `w` range across the 27 baseline trades: 14-439 (median 74); `w`
never approaches single digits. An earlier paper draft's "two-bar window"
example was illustrative only and has been corrected in the text - the code
was not changed.

These are two intentionally separate systems, not an inconsistency - verified
by read-only audit of the entry/exit code paths.

## No-lookahead audit

`compute_smc()` and its helper `_build_order_block_from_crossover()` bound
every forward-search loop (pivot confirmation windows, displacement/FVG/
liquidity-sweep/volume-expansion criteria) by the Order Block's own
confirmation bar, never by dataset length. This is enforced inline with
runtime assertions at each forward-search site, so a regression would fail
immediately on the next run rather than requiring a separate audit pass.

## Reporting notes on the record (not bugs, not silently reconciled)

1. **`compute_indicators()`'s ATR comment is stale.** The comment above the
   ATR block (`research_analysis.py`, Section 3) describes "Wilder's
   smoothing (RMA)" and gives the RMA recurrence; the code is
   `true_range.rolling(atr_period, min_periods=1).mean()`, a plain rolling
   MEAN of True Range. The CODE is what the paper's numbers come from and it
   is intended: an independent recomputation matches the SMA exactly (diff
   0.0) and the dashboard labels it `ATR(14, SMA-of-TR)`. A now-removed
   per-bar formula layer (see "Independent verification surfaces") also
   reproduced the SMA and passed at 1e-5 across all 8,767 bars. Only the
   comment is wrong.
   Recorded rather than patched, per CLAUDE.md's "Known bugs" rule.

2. **The benchmark row mixes two return conventions.** In
   `artifacts/benchmark_vs_passive.json` the OB-gated arm reports
   `total_return_pct` = 30.3065 (the arithmetic SUM of per-trade `pnl_pct`)
   beside `final_capital` = 13417.77, which is the *compounded* +34.1777% on
   $10,000. The two fields in the same row do not correspond to each other.
   Both are individually correct under their own convention; the figure the
   paper cites as the headline total net return is the arithmetic one
   (+30.31%), which is what Section 3C's formula layer independently
   reproduces. Any statement pairing "+30.31%" with "$13,417.77" needs to say
   which convention each number uses.

3. **The 2.0×ATR breakeven rule can never fire (found 2026-10-28, mock judging).**
   In `_check_long/short_exit_conditions` the 1.8×ATR move exit is checked and
   returns before the 2.0×ATR breakeven ratchet, so any close past 2.0×ATR has
   already exited. It changes no reported number. Left as frozen per CLAUDE.md;
   disclosed in the paper's Table 1 note from bitcoin (7) on.

4. **Stops are checked and filled at the candle close only.** Wicks through a
   stop that close back inside never trigger it, and gaps book more than the
   stop (trade 2624: -4.65% on a 2.68% stop). Kept as the baseline; the
   high/low sensitivity is reported separately (see Benchmark section).

## Regression baseline

`scratch/regression.py` holds a golden-master snapshot (fixtures in
`scratch/fixtures/`) of the 27 baseline trades and per-bar indicator series
(MACD_hist, K, D, J, ATR, ATR_200), generated from `artifacts/candles.csv`.
A fresh run is compared against that snapshot bar-by-bar (1e-6 tolerance)
and trade-by-trade (matched on entry_idx, 1e-5 tolerance) to confirm the
engine still reproduces the locked results above.

## Independent verification surfaces

Two surfaces recompute this study's numbers from scratch rather than
displaying Python's. Neither imports anything from the Python side. Cite
either as an independent check; cite both when the claim is that a figure is
implementation-independent.

### 1. TypeScript (`dashboard-v2`) - statistics and OB quality

The dashboard recomputes win rate, the one-sided binomial test,
Pearson/Spearman correlation, and a percentile bootstrap CI from the same
per-trade data the Python pipeline exports, using its own independent
TypeScript implementation (`statsCompute.ts`, `statMath.ts`) rather than
importing any Python-computed statistic. The bootstrap CI gap documented
above is the visible product of that independence: two separate
implementations computing the same statistic from the same trade data.
`obQualityVerification.ts` does the same for the 5 Order Block quality
criteria, exposing a `matchesRecorded` flag per criterion (verified against
all 761 Order Blocks: zero mismatches).

### 2. Native spreadsheet formulas - the published statistics

`research_analysis.py`'s Section 3C emits a spreadsheet that *re-derives* the
nine published statistics instead of receiving them. Same generator, two
targets: a self-contained `artifacts/verification_formulas.xlsx`
(`python research_analysis.py --export-formula-workbook`) and the live Google
Sheets workbook's `Verify Stats <window>` tabs (pushed by `--export-gsheet`,
with `value_input_option=USER_ENTERED` so they land as live formulas). Each
derived value sits beside the published one with an absolute diff and a
PASS/FAIL cell; `Verification Summary` rolls every check group up to one GRAND
TOTAL cell and is deliberately the first sheet, so
`soffice --headless --convert-to csv` grades the whole workbook in one call.

**What it independently derives:** all nine metrics on the `Results <window>`
tab - Total Trades, Wins, Losses, Win Rate (%), Total Net Return (%), Avg
Return/Trade (%), SD (Return/Trade %), and both binomial p-values - each from
the published per-trade `pnl_pct` column, using `COUNT`, `COUNTIF`, `SUM`,
`AVERAGE`, `STDEV.S` and `1-BINOM.DIST(k-1,n,0.5,TRUE)`. Both the derived and
the published side are CELL REFERENCES into the workbook's own published tabs
(the published side via `INDEX`/`MATCH` on the metric NAME, so a row-order
change cannot silently compare two different metrics), which means the check
grades what a reader actually sees rather than values this generator pasted in.

**What it does NOT verify, stated plainly:** the per-trade `pnl_pct` values,
the indicator series, Order Block detection, and trade selection. Those are
inputs here. The check answers "given this trade log, are the published
statistics the correct statistics?" and nothing more. That is a real and
independently checkable question, and it should not be cited as more than it is.

**Conventions the formulas had to match rather than assume** (each verified,
not guessed): `Total Net Return (%)` is an arithmetic SUM of per-trade
`pnl_pct`, not a compounded return (see the mixed-convention note above); SD
is the SAMPLE standard deviation, so `STDEV.S` and not `STDEV.P`, because
pandas `.std()` defaults to `ddof=1`; `Wins` counts `pnl_pct > 0` strictly, so
a hypothetical exactly-flat trade is a loss; `scipy.binomtest(k, n, 0.5,
alternative='greater')` equals `1 - BINOM.DIST(k-1, n, 0.5, TRUE)` exactly
(the upper tail INCLUDING k, hence `k-1`), matched to 10 decimal places; and
at p = 0.5 the distribution is symmetric, so the two-sided p-value is exactly
twice the one-sided one.

**Tolerance:** 1e-9 absolute, visible as a constant on `Verification Summary`.
`_write_trades_sheet()`/`_write_results_sheet()` write raw unrounded floats,
so there is no export rounding to absorb.

**Status:** 18 checks, 0 failures (9 statistics x 2 windows), recalculated
headlessly in LibreOffice rather than read back from a cached value - openpyxl
writes every formula with no cached result, so the spreadsheet is forced to
compute. Negative control: perturbing one published `Results` value produces
exactly one FAIL in that window and none in the other; corrupting one trade's
published `pnl_pct` produces 8 of 9 FAILs (Total Trades is a count and is
correctly unaffected).

**Reading it in Excel:** click "Enable Editing" first. Protected View does not
calculate formulas, so every derived cell renders blank until you leave it.

**Scope history (2026-09-21).** An earlier version of this layer also
reproduced, by formula, all nine per-bar indicator series (MACD/signal/hist,
RSV/K/D/J, ATR, ATR_200), the five Order Block quality criteria, and every
trade's zone edges, stop-loss, structural-or-2R take-profit, frozen KDJ-reset
window, full exit ladder and `pnl_pct` - 17,639 checks at 0 failures across
both windows, with an indicator tolerance of 1e-5 whose observed worst case
(5.0004e-7) was exactly the floor implied by `_format_df_for_export_full()`'s
`.round(6)`. It was REMOVED deliberately, not lost: it quadrupled the
workbook, made Excel recalculation slow enough to discourage the audit it
existed for, and duplicated what `dashboard-v2`'s TypeScript already covers
for the OB criteria. Order Block detection and trade selection were never
ported (selection takes the first *in list order* of ~760 Order Blocks passing
nine filters, and a spreadsheet lookup substitute changes that tie-break to
first-by-key, which would manufacture disagreements that are artifacts of the
port rather than findings). The removal narrowed what the workbook claims; it
did not change any published number.

The current layer reproduces the locked headline figures for the main window
by formula, to the digit: 27 trades, 19 wins, 70.3703703703704%,
+30.3064563560319%, +1.1224613465197%, SD 2.41013571893455%, one-sided p
0.0261194929480553, two-sided exactly 2x that. Formulation-period window:
25 trades, 15 wins, 60%, +21.8245809325413%, +0.87298323730165%, SD
3.14941168288314%, one-sided p 0.212178111076355.
