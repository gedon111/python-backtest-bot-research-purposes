# Paper/codebase sync report

Generated: 2026-09-21T02:38:14.175879+00:00

Recomputed live from `artifacts/candles.csv` and this file's own strategy-engine functions, then cross-checked against the figures parsed out of `docs/SCRATCH_RESULTS_METHODS.md`'s "Locked headline results" section. A MISMATCH row is a correctness finding, not something this script resolves automatically -- see `CLAUDE.md`'s rule on newly found bugs.

## Cross-check summary

| Metric | Locked (SCRATCH_RESULTS_METHODS.md) | Live (this run) | Status |
|---|---|---|---|
| Bar count | 8767 | 8767 | MATCH |
| Baseline (q>=0) trades | 27 | 27 | MATCH |
| Baseline win rate (%) | 70.37 | 70.37 | MATCH |
| Baseline total net return (%) | 30.31 | 30.31 | MATCH |
| Baseline avg return/trade (%) | 1.12 | 1.12 | MATCH |
| Baseline SD (%) | 2.41 | 2.41 | MATCH |
| Baseline p (one-sided) | 0.026 | 0.026 | MATCH |

## Ablation A/B -- passthrough from the locked results, UNVERIFIED this run

No function in this file reproduces these figures from current code -- the originating script was never committed. Printed here only as cited from `docs/SCRATCH_RESULTS_METHODS.md`, not independently recomputed.

| Configuration | N | Win rate | Total return |
|---|---|---|---|
| Indicators-only (entry-ATR stop) | 140 | 60.00% | -14.63% |
| Indicators-only (swing-pivot stop) | 138 | 55.07% | -25.50% |
