# Project context

Research codebase for an ISEF science-fair paper. Backtests a rule-based
BTC/USDT strategy (MACD + KDJ + ATR + SMC Order Blocks) on 4h candles,
Jan 2022 - Jan 2026. This is a scientific artifact, not a production system.
Correctness and auditability outrank performance, elegance, and convenience.

## Architecture - single-file consolidation (2026-08-13)

`research_analysis.py` (repo root) is now THE canonical entrypoint: backtest
engine, statistics pipeline, database manager, and the dashboard's live HTTP
server, all in one file, one process. `python research_analysis.py` runs the
offline stats pipeline; `python research_analysis.py --serve` exports
artifacts + database rows and starts the dashboard server on port 8765
(replaces `Run_All.py`'s former target).

The previously-scattered originals (`src/Binance backtest bot.py`,
`db_manager.py`, `export_gui_data.py`, all 12 `analysis/*.py` scripts) were
moved to `legacy_pre_consolidation/` at the repo root - a git-ignored,
disk-only backup, not part of the running system or tracked in git going
forward. `src/Binance backtest bot.py` was renamed
`Binance backtest bot (legacy).py` inside that folder. Two of the retired
`analysis/*.py` scripts (`oos_validation_analysis.py`'s 8-year backfill
audit, `export_extended_candles.py`'s live-pull builder) were occasional
manual audit tools even before this consolidation and were NOT ported into
`research_analysis.py` - they remain available only in
`legacy_pre_consolidation/` if that audit is ever rerun by hand.
`scratch/regression.py` and the other `scratch/*.py` audit scripts were
repointed to dynamically load `research_analysis.py` instead of the retired
`src/Binance backtest bot.py`.

This was a refactor, not a strategy change: `compute_indicators()`,
`compute_smc()`, `simulate_trades()`, and the `kdj_reset_*` exit state
machine are reproduced unchanged inside `research_analysis.py` (verified
byte-identical against `scratch/regression.py`'s golden-master fixtures
before and after the move). See `research_analysis.py`'s own module
docstring for the full section map.

### `Run_Dashboard.py` removed (2026-08-14)

`Run_Dashboard.py` was deleted - it was a near-duplicate of `Run_All.py`
(same `ensure_dashboard_built()` logic) whose only real differences were
passing `--export-gsheet` through and pausing on error for a Windows
double-click launch. `Run_All.py` is now the single runner script: it
installs Python deps (`pip install -r requirements.txt`), installs
dashboard-v2's npm deps (`npm ci`, only when `node_modules` is missing) and
builds it (only when `dist` is missing/stale), then runs
`research_analysis.py --serve --levels 0,1,2,3` - a fresh clone needs
nothing preinstalled beyond Python/pip and Node/npm themselves. Google
Sheets export has no dedicated runner script anymore; run
`python research_analysis.py --serve --export-gsheet` directly for that
(as already documented in README.md's flags table).

## Locked results - must not change

These numbers appear in the paper. Any code change that alters them is a bug in
the change, not an improvement:

- Baseline (min_ob_quality=0): 27 trades, 70.37% win rate, +30.31% total net
  return, +1.12% avg return/trade, SD 2.41%
- One-sided binomial p = 0.026 (two-sided 0.052) for the q>=0 baseline.
- q>=1 one-sided binomial p: 0.038 (n=26, pre-fix) -> 0.054 (n=25,
  post-fix as of commit cb4ed93). This is a SIGNIFICANCE-CONCLUSION FLIP
  (marginally significant -> not significant at alpha=0.05), not a modest
  revision - driven by a single trade (entry_idx=3100) losing its only
  quality point (FVG) under the corrected no-lookahead computation. See
  Known bugs #3. Consistent with the Limitations section's existing
  small-sample caveat about q>=1's thin N.
- 761 detected Order Blocks; FVG criterion true for 253 (33.2%) as of
  commit cb4ed93 (was 362 / 47.6% pre-fix; corrected, see Known bugs #3).
- OB quality distribution (post-fix, commit cb4ed93): q0=93, q1=154,
  q2=206, q3=197, q4=90, q5=21 (was q0=77, q1=147, q2=200, q3=192, q4=112,
  q5=33 pre-fix; corrected, see Known bugs #3).
- Ablation A (indicators-only, entry-ATR stop): 140 trades, 60.00%, -14.63%
- Ablation B (indicators-only, swing-pivot stop): 138 trades, 55.07%, -25.50%
- Dataset: artifacts/candles.csv, 8,767 bars (1,461 days incl. 2024 leap day
  x 6 bars/day, plus one boundary-inclusive endpoint bar). NOT 8,760 - the
  paper's original figure was arithmetic, since corrected. Do not trim bars.
- Benchmark-vs-passive (research_analysis.py's run_benchmark_vs_passive(),
  Section 5B, originally analysis/benchmark_vs_passive.py, $10,000 notional
  starting capital, gross unless stated): 2022-2026 window - OB-gated
  strategy +30.31% -> $13,417.77 (Sharpe 1.114, Sortino 2.727, MaxDD -6.46%,
  2.63% time-in-market); Weekly DCA into BTC +123.13% -> $22,312.94 (Sharpe
  0.556, MaxDD -27.85%, 100%); Lump-sum B&H +90.07% -> $19,007.32 (Sharpe
  0.564, MaxDD -67.21%, 100%). DCA and lump-sum B&H BOTH beat the strategy
  in raw terminal value this window - do not let a future session state or
  imply the strategy "beats DCA/BTC" without the exposure-time caveat
  (2.63% vs 100%) attached in the same breath. Fee-adjusted variant: strategy
  +24.91% -> $12,719.01. 2018-2022 formulation-period window (NOT
  out-of-sample): strategy +21.82% -> $12,282.53; DCA +439.88% -> $53,987.55;
  lump-sum +236.96% -> $33,696.49.

## Regression harness

scratch/regression.py is the golden master; fixtures in scratch/fixtures/.
Run it after EVERY change. Any diff = revert the change.
It aligns trades by entry_idx and names the first divergent trade.
--generate regenerates fixtures. Never run it without asking first.
As of the single-file consolidation it dynamically loads `research_analysis.py`
(repo root), not the retired `src/Binance backtest bot.py`.

## Google Sheets pipeline

Current, wired-in push (both `--export-gsheet` CLI flag and the dashboard's
push-to-gsheet button call `push_all_gsheet_exports()` in
`research_analysis.py`, Section 6): `push_candles_to_gsheet` (2 tabs, ALL
26 sim-dataframe columns per bar, not a curated subset - see
`_format_df_for_export_full`, Section 3B), `push_trades_and_results_to_gsheet`
(4 tabs, full 40-column trade schema including numeric OB-criteria
diagnostics alongside the booleans, plus `kdj_exit_window` - the frozen-at-
entry KDJ-reset period `w` from `kdj_reset_init()`, added 2026-08-14 so it's
visible per-trade instead of only derivable from entry_idx/entry_ob_bar by
hand), `push_benchmark_vs_passive_to_gsheet`
(2 tabs, gross + fee-adjusted blocks) - all three computed in-process now
(no more subprocess + JSON round-trip through `analysis/*.py`, which is
retired). The OLD `push_all_thresholds_to_gsheet` (per-quality-threshold,
per-bar "Quality 0".."Quality 3" sheets) is left defined in
`research_analysis.py` (Section 3B) but is no longer called by default -
its sheets are actively deleted from the live workbook on every push. Do not
re-wire it back in without asking; it was deliberately superseded, not
deprecated by accident.
`SERVICE KEY/`'s key-file auto-discovery now picks the most-recently-modified
non-"disabled" key file (not a hardcoded "new-strat" filename match) - if a
gsheet push starts failing with an auth error, check whether a stale key
file is now newer than the working one before assuming the code is broken.

## Known bugs - already found, corrected, and DISCLOSED in the paper

Do not "fix" anything that looks related to these without asking. Apparent
oddities nearby may be intentional:

1. The composite 0-5 quality score was non-orthogonal (higher-scored sets were
   nested subsets of lower-scored ones). Replaced by independent per-criterion
   evaluation. The score field still exists and is still computed; it is no
   longer used as an ordinal threshold for analysis.
2. FVG used an adjacent-candle test (lows[j+1] > highs[j]) instead of the
   three-candle definition (lows[j+2] > highs[j]). Corrected.
3. FVG and displacement quality criteria could read 1-2 bars past an Order
   Block's own confirmation bar - the forward-search loop was bounded by
   dataset length, not by the confirmation bar. Found via the no-lookahead
   audit; fixed by freezing the search window at the confirmation bar.
   Affects 110/761 OBs' quality scores (FVG true: 362->253, 47.6%->33.2%;
   displacement true: 112->107). Does not change the 27-trade q>=0 baseline
   (unaffected by quality filtering) but drops q>=1 from 26->25 trades,
   flipping its one-sided binomial significance (0.038->0.054). Corrected
   as of commit cb4ed93. Distinct in kind from bugs #1-2 above (those were
   definitional corrections; this was data leakage across the confirmation
   boundary). Pending: the paper's Results narrative sentence reporting the
   Welch's t-test p-value range across all 5 orthogonal criteria (currently
   "0.38-0.90" pre-fix) should become "0.38-0.78" post-fix (only FVG's
   value moved, from 0.8956 to 0.5996; LargeBar's 0.7751 is now the max).
   The paper itself has not been touched by this correction pass.

If you find a THIRD bug, STOP and report it. Do not fix it silently. A newly
discovered error changes what the paper claims, so I need to see it first.

## Paper reporting corrections (distinct from the backtest-engine bugs above)

Found in a 2026-08-08 cross-surface numerical audit. These are reporting/
documentation errors, NOT backtest-engine bugs - they do not count toward
the "THIRD bug" rule above, and none of them touch a locked result.

1. Pearson/Spearman correlation (hold_bars vs pnl_pct, 27 baseline trades)
   p-values were reported as "p < 0.001" in docs/paper_full_update_2026-08-08.md
   and docs/backtest_methodology_defense_walkthrough.md. Independently
   recomputed via scipy: actual p ~= 0.0094 (Pearson, r=+0.4907, t=2.82,
   df=25) and p ~= 0.0113 (Spearman, rho=+0.4797) - still significant at
   alpha=0.05, wrong significance bucket at alpha=0.001. Both files
   corrected. STUDY_REFERENCE.md does NOT contain this claim (an earlier
   audit pass of this same session initially mis-attributed it there;
   corrected in docs/change_log_2026-08-08.md).
2. Bootstrap CI on total return has two different, individually-correct
   values depending on surface: Python (`analysis/bootstrap_power_analysis.py`,
   B=10,000, seed=42) -> [+5.99%, +54.99%], the paper's canonical figure.
   Website (`dashboard-v2/src/components/stats/statsCompute.ts`'s
   `computeOwnBootstrapCI`, B=2,000, seed=42, JS mulberry32 PRNG) ->
   [+7.48%, +54.46%]. Root cause is the B mismatch alone, not a logic bug -
   verified by porting mulberry32 to Python and reproducing [+7.48%,
   +54.46%] exactly at B=2,000. Do not silently unify these two B values -
   the paper now explicitly discloses both and explains the gap.

## Open question - do not assume resolved

The paper reports "190 total qualifying indicator signals" as the denominator
for the claim that 25 of 27 OB-gated trades (92.6%) coincided with independent
indicator signals. That 190 was derived using the indicators-only ablation's
1.5*ATR entry-anchored stop, NOT the OB-gated strategy's own risk rules. The
two populations are filtered differently. This is unresolved. Do not cite 190
as settled.

## Rules

- No strategy logic, threshold, or formula changes. Refactoring only.
- Parameters are fixed and pre-registered. Never sweep, tune, or optimize them.
- Keep the JS verification dashboard's recalculation INDEPENDENT of the Python
  side. It is an intentional cross-check. Never make it import from Python.
- All scratch scripts run offline from artifacts/candles.csv. No live API calls.
- Report null and unfavorable results as they come. Do not soften them.
- No-lookahead enforcement is a SEPARATE final step, not part of general
  refactoring. If the harness fails after it, do not revert and do not weaken
  the assertion - stop and report the bar, value, and computation that reached
  forward. That would be a correctness finding, not a regression.

## Session memory - always maintain

- At the start of every session, check memory for existing entries about this
  repo before starting work, and verify anything load-bearing (branch names,
  commit hashes, file paths) against current git state before relying on it -
  memory can go stale.
- Keep a running project memory of what the current session is actually doing:
  which branch/commit, what's been done, what's still open, and why. Update it
  as the work materially changes, not just at the end - if the session gets
  interrupted, the memory should still reflect real state.
- Update the existing memory entry for a piece of work rather than creating a
  new one each session; only start a new entry when the topic genuinely
  changes (e.g. a different feature or investigation).

## Git Branching Rules

This applies going forward, to all future sessions, not just the one that
added it:

- New features (a new analysis capability, a new script, a new metric that
  didn't exist before) -> a new feature branch, named `feature/<short-desc>`.
- Development/tweaks on an already-integrated feature (adjusting an
  existing script's parameters, fixing a bug in a promoted script, refining
  existing analysis) -> a `dev/<short-desc>` branch, or the shared
  `development` branch if the change doesn't warrant its own branch. Check
  whether `development` already exists before creating a new dev branch.
- Only fully reviewed, finalized work gets merged to `main`.
- Never commit directly to `main`.
- Do not merge a branch into `development` or `main` unless explicitly
  asked to. Leave finished branches open for review.

## KDJ architecture - two separate systems, by design

- Entry gating (every K/D/J reference in entry conditions) reads the
  STATIC full-history KDJ(9,3,3) from compute_indicators(). w has NO
  effect on entry — confirmed by read-only audit.
- The post-entry EXIT signal uses a separate state machine
  (kdj_reset_init/update/exit) seeded from the static KDJ value AT
  the entry bar (not 50, not backfilled), recursed forward with
  period = entry_idx - triggering_OB_bar, frozen for that trade's
  life. Governs exit timing only.
- Observed w range, 27 baseline trades: 14-439 (median 74). w never
  approaches single digits - the paper's "two-bar window" example is
  illustrative only and is being corrected, not the code.
- Do NOT unify these into one KDJ or change kdj_reset_init's seed
  source without asking. This is a disclosed, deliberate design,
  verified via read-only audit.