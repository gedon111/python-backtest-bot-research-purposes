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

## Results, corrections, and disclosed design decisions

`docs/SCRATCH_RESULTS_METHODS.md` is the canonical reference for locked
headline results, the benchmark-vs-passive figures, corrected errors
(backtest-engine bug and reporting corrections), the open 190-signals
question, and the dual-system KDJ design decision. Read it before citing
any number from this project, and update it (not this file) when a result,
correction, or open question changes. Any code change that alters a number
recorded there is a bug in the change, not an improvement.

## Regression harness

scratch/regression.py is the golden master; fixtures in scratch/fixtures/.
Run it after EVERY change. Any diff = revert the change.
It aligns trades by entry_idx and names the first divergent trade.
--generate regenerates fixtures. Never run it without asking first.
As of the single-file consolidation it dynamically loads `research_analysis.py`
(repo root), not the retired `src/Binance backtest bot.py`.
See `docs/SCRATCH_RESULTS_METHODS.md` for the locked figures this harness
protects.

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

## Known bugs

Do not "fix" anything that looks related to the disclosed backtest-engine
bug in `docs/SCRATCH_RESULTS_METHODS.md` without asking - apparent oddities
nearby may be intentional. If you find a SECOND bug, STOP and report it. Do
not fix it silently. A newly discovered error changes what the paper claims,
so it needs review before any fix.

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

## KDJ architecture

Two separate systems by design - see `docs/SCRATCH_RESULTS_METHODS.md` for
the full detail. Do NOT unify these into one KDJ or change
`kdj_reset_init`'s seed source without asking.