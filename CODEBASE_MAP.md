# Codebase Map

Inventory for the Phase 1 reorg proposal. One line per file: purpose, what
references it, classification, proposed destination. Nothing has been moved
yet — this is the map, not the move. See Phase 2 for the breakage list tied
to each proposed move.

Classification key: **CORE** (strategy/backtest engine), **INFRA**
(pipeline/orchestration/config, not strategy logic), **AUDIT EVIDENCE**
(scratch script/output tied to a CLAUDE.md "Known bugs" entry or a number
cited in the paper — relocate only, never delete), **DASHBOARD** (independent
JS cross-check, per CLAUDE.md must stay independent of Python), **CANDIDATE-
DEAD** (unreferenced/superseded/orphaned — confirmed via exhaustive grep
across tracked files and scratch/, not assumed), **OUT OF SCOPE** (explicitly
excluded from this task).

## Root-level files

| File | Purpose | Referenced by | Class | Proposed destination |
|---|---|---|---|---|
| `.dockerignore` | Docker build exclusions | Docker build only | INFRA | repo root (unchanged) |
| `.gitignore` | Git exclusions (`scratch/`, `__pycache__/`, `artifacts/ml_status.json`) | git only | INFRA | repo root (unchanged) |
| `Binance backtest bot.py` | The strategy/backtest engine itself: indicators, SMC/OB detection, KDJ reset state machine, `simulate_trades` | Loaded by path-string in `export_gui_data.py` (x2) and 9 scratch scripts; imported conceptually by every doc | **CORE** | `src/Binance backtest bot.py` |
| `CLAUDE.md` | Locked results, disclosed bugs, project rules | Read by every session (this one included) as governing context | INFRA | repo root (unchanged — must stay discoverable at root) |
| `backtest_results.db` | SQLite export of candles/OBs/touches/trades, all quality thresholds | `db_manager.get_db_url()` default (`sqlite:///backtest_results.db`, CWD-relative); read by `scratch/calculate_paper_metrics.py`, `scratch/inspect_max_min_trades.py` | CORE (generated data) | repo root (unchanged) — no target folder fits a generated DB better than root, and moving it means updating `db_manager.py`'s default URL for zero organizational gain |
| `chart_theme.json` | Persisted dashboard theme (light/dark) | Read/written by `export_gui_data.py` via hardcoded relative path `"chart_theme.json"` | INFRA | repo root (unchanged) |
| `data.js` | Standalone `window.BOT_DATA = {...}` static data dump | **Nothing** — grepped `gui.js`/`gui.html`/`README.md` for `BOT_DATA` and `data.js`; no script tag in `gui.html`, no read in `gui.js` | **CANDIDATE-DEAD** | none — propose deletion (superseded by the live artifacts/API-driven load path) |
| `db_manager.py` | SQLAlchemy models (`Candle`, `OrderBlock`, `OBTouch`, `Trade`) + session/engine helpers | Imported by `export_gui_data.py`; DB read directly (bypassing this module) by `scratch/calculate_paper_metrics.py`, `scratch/inspect_max_min_trades.py` | INFRA | repo root (unchanged) — tightly coupled to `export_gui_data.py`, moving one without the other breaks the plain `import db_manager` |
| `Dockerfile` | Container build | Docker build only | INFRA | repo root (unchanged) |
| `export_gui_data.py` | Pipeline: fetch/cache candles → indicators → OB detection → simulate at each quality level → write `artifacts/*` + DB → optional local dashboard server | Invoked by `Run_All.py` and `Run_Dashboard.py` via `subprocess.run([..., "export_gui_data.py", ...])`; loads `Binance backtest bot.py` by relative path; imports `db_manager` | INFRA (pipeline orchestrator, not strategy logic) | repo root (unchanged) — see Phase 2 for why moving it is higher-risk than it looks |
| `gui.css` | Dashboard styling | `gui.html` (`<link>`) | **DASHBOARD** | `dashboard/gui.css` |
| `gui.html` | Dashboard shell/layout | Served by `export_gui_data.py`'s local HTTP server | **DASHBOARD** | `dashboard/gui.html` |
| `gui.js` | Dashboard logic: chart rendering, its own independent MACD/KDJ/adaptive-KDJ entry-condition recalculation, OB display (reads `quality_fvg`/etc. as trusted data, does not detect OBs itself) | `gui.html` (`<script>`) | **DASHBOARD** | `dashboard/gui.js` |
| `README.md` | Project README | GitHub landing page; mentions `Binance backtest bot.py` in prose | INFRA | repo root (unchanged) |
| `Run_All.py` | Top-level orchestrator: runs export pipeline twice (headless, then with server) | User-invoked entry point | INFRA | repo root (unchanged — top-level entry point) |
| `Run_Dashboard.py` | Top-level orchestrator: runs export pipeline with `--export-gsheet` | User-invoked entry point | INFRA | repo root (unchanged — top-level entry point) |
| `SERVICE KEY/python-trading-bot-new-strat-10.json` | Credential file (content not inspected, per instructions) | Unknown — out of scope to investigate | **OUT OF SCOPE** | **do not move — explicitly excluded from this task** |

## `artifacts/`

| File | Purpose | Referenced by | Class | Proposed destination |
|---|---|---|---|---|
| `artifacts/candles.csv` | Locked 8,767-bar OHLCV+indicator snapshot; the offline data source for every scratch script | Every scratch script; `export_gui_data.py` cache fallback; `scratch/regression.py` | CORE (data) | `artifacts/` (unchanged) |
| `artifacts/candles.json` | Same data as above, JSON form, for the dashboard | Served/read by `export_gui_data.py` / dashboard | CORE (data) | `artifacts/` (unchanged) |
| `artifacts/manifest.json` | Export metadata (schema version, candle count, timestamp) | `export_gui_data.py` build/consume | CORE (data) | `artifacts/` (unchanged) |
| `artifacts/ml_status.json` | Leftover from the removed ML classifier pipeline | **Nothing** — grepped tracked files and scratch/ for `ml_status`; zero hits outside `.gitignore` itself | **CANDIDATE-DEAD** | none — propose deletion |
| `artifacts/models/model_iter_1.pkl` … `model_iter_8.pkl` (8 files) | Pickled ML classifier iterations from the removed ML pipeline | **Nothing** — grepped tracked files and scratch/ for `model_iter`, `artifacts/models`, `.pkl`, `classifier_model`; zero hits | **CANDIDATE-DEAD** | none — propose deletion |
| `artifacts/orderblocks_default_view.csv` | 761-OB population at the default quality view | Dashboard consumption; matches Known bugs #3 corrected figures | CORE (data) | `artifacts/` (unchanged) |
| `artifacts/runs_by_threshold.json` | Full obs/trades/stats per quality threshold (q0–q3) | Cited directly in this session's audit (Steps 3–5 of the FVG fix verification); dashboard | **AUDIT EVIDENCE** + CORE (data) | `artifacts/` (unchanged) |
| `artifacts/threshold_runs.csv` / `.json` | Threshold-sweep summary stats | Same as above | CORE (data) | `artifacts/` (unchanged) |
| `artifacts/trades_default_view.csv` | 25-trade default view (`MIN_OB_QUALITY=1`) | Dashboard | CORE (data) | `artifacts/` (unchanged) |
| `artifacts/verification_report.json` | Hash-based cross-check report (OHLC/indicator/OB/trade hashes per threshold) | Dashboard "verification" panel | CORE (data) | `artifacts/` (unchanged) |

## `docs/`

| File | Purpose | Class | Proposed destination |
|---|---|---|---|
| `docs/ablation_study_indicators_only.md` | Source of the Ablation A (140-trade) figures cited in CLAUDE.md | **AUDIT EVIDENCE** | `docs/` (unchanged) |
| `docs/ablation_unconfounding_analysis.md` | Source of the Ablation A/B three-way comparison (140/138-trade figures); the actual provenance doc for those locked numbers, given the original script was never committed (see `scratch/02_benchmark_and_risk.py` docstring) | **AUDIT EVIDENCE** | `docs/` (unchanged) |
| `docs/backtest_methodology_defense_walkthrough.md` | Full methodology walkthrough incl. bar-359 end-to-end trace, statistical computation reference | **AUDIT EVIDENCE** | `docs/` (unchanged) |
| `docs/orthogonal_criteria_reference.md` | Orthogonal criteria magnitude/Welch's-t reference table (the doc whose Welch range this session flagged as pending a post-fix update) | **AUDIT EVIDENCE** | `docs/` (unchanged) |
| `docs/research_statistics_reference.md` | Detailed per-trade/per-threshold statistics reference | **AUDIT EVIDENCE** | `docs/` (unchanged) |

## `scratch/` (directory is gitignored; kept flat, no new subfolders)

Correction from the original Phase 1 pass: `scratch/` as a whole is
gitignored, but two files were force-tracked before this session despite
that — `scratch/calculate_all_qualities.py` and
`scratch/calculate_paper_metrics.py` **are** in `git ls-files`. The other 13
files below were found via filesystem walk only and are genuinely untracked.
This surfaced during Phase 3 Batch 2 when `git add` staged
`calculate_all_qualities.py`'s edit without being asked to.

| File | Purpose | Class | Proposed destination |
|---|---|---|---|
| `scratch/regression.py` | Golden-master regression harness, explicitly named in CLAUDE.md | CORE (harness) | `scratch/` root (unchanged — per explicit instruction) |
| `scratch/run_export_offline.py` | This session's offline driver for `export_gui_data.py` (blocks live API calls, forces cache fallback) | INFRA | `scratch/` root (unchanged — per explicit instruction) |
| `scratch/fixtures/baseline_bars.parquet` | Golden-master bar/indicator fixture | CORE (harness data) | `scratch/fixtures/` (unchanged) |
| `scratch/fixtures/baseline_trades.json` | Golden-master 27-trade fixture | CORE (harness data) | `scratch/fixtures/` (unchanged) |
| `scratch/kdj_exit_window_counterfactual.py` | This session: fixed-vs-dynamic exit-window sensitivity grid (CLAUDE.md "KDJ architecture" section) | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/kdj_exit_window_counterfactual_results.json` | Output of the above | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/kdj_exit_window_trade_detail.py` | This session: per-trade win/loss + pnl detail across the exit-window grid | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/kdj_exit_window_trade_detail_results.json` | Output of the above | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/no_lookahead_atr_kdj_check.py` | This session: truncation-equality causality proof for ATR/static KDJ (Known bugs #3 investigation — the PASS half) | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/no_lookahead_fvg_scope_audit.py` | This session: quantifies the FVG/displacement lookahead scope (109/362, 5/112 — the exact numbers now in CLAUDE.md Known bugs #3) | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/02_benchmark_and_risk.py` | Benchmark/risk metrics vs. buy-and-hold; docstring discloses the Ablation A/B reproducibility gap (source script for 140/138 trades was never committed) | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/calculate_all_qualities.py` | OB quality-criteria derivation script | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/calculate_paper_metrics.py` | Reads `backtest_results.db` directly; produces the q0–q3 threshold-sweep paper stats | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/inspect_max_min_trades.py` | Reads `backtest_results.db`; produces best/worst-trade figures (bar 359/2624) | **AUDIT EVIDENCE** | no move — stays at `scratch/` |
| `scratch/inspect_raw_signals.py` | Related to the "190 total qualifying indicator signals" open question in CLAUDE.md | **AUDIT EVIDENCE** | no move — stays at `scratch/` |

## Not inventoried (build artifacts, not source)

`__pycache__/*.pyc` — gitignored, auto-regenerated. Includes bytecode for
`Binance backtest bot (Wilder ATR backup).py` and `ml_optimizer.py`, **source
files that no longer exist on disk** — orphaned bytecode only, no source to
relocate or delete. No action proposed; will regenerate/vanish naturally.

## Summary

- **CANDIDATE-DEAD** (confirmed via exhaustive grep, zero references found): `data.js`, `artifacts/ml_status.json`, `artifacts/models/*.pkl` (8 files) — 10 files total, all leftovers from the already-disclosed ML-pipeline removal.
- **OUT OF SCOPE**: `SERVICE KEY/python-trading-bot-new-strat-10.json` — not moved, not deleted, not opened.
- **AUDIT EVIDENCE**: 5 docs (no move, already in `docs/`) + 12 scratch files (no move, `scratch/` stays flat per revision — no `scratch/kdj_exit_window/`, `scratch/no_lookahead/`, or `scratch/analysis/` subfolders created).
- Only one file is proposed to actually move anywhere in this whole map: `Binance backtest bot.py` → `src/`. `db_manager.py` and `export_gui_data.py` are proposed to stay at repo root despite being Python "core-ish" pipeline code, specifically to minimize the number of relative-path references broken in one batch — see Phase 2 for the full reasoning and the complete breakage list this still causes.
- Net effect: Phase 2 now reduces to 10 deletions + 1 move + that one move's breakage list.
