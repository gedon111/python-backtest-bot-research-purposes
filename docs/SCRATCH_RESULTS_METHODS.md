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
