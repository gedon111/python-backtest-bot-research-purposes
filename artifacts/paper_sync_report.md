# Paper/codebase sync report

Generated: 2026-09-02T12:45:46.756640+00:00

Recomputed live from `artifacts/candles.csv` and this file's own strategy-engine functions, then cross-checked against the figures parsed out of `CLAUDE.md`'s "Locked results" section. A MISMATCH row is a correctness finding, not something this script resolves automatically -- see `CLAUDE.md`'s rule on newly found bugs.

## Cross-check summary

| Metric | Locked (CLAUDE.md) | Live (this run) | Status |
|---|---|---|---|
| Bar count | (not found in CLAUDE.md) | 8767 | NO-PARSE |
| Baseline (q>=0) trades | (not found in CLAUDE.md) | 27 | NO-PARSE |
| Baseline win rate (%) | (not found in CLAUDE.md) | 70.37 | NO-PARSE |
| Baseline total net return (%) | (not found in CLAUDE.md) | 30.31 | NO-PARSE |
| Baseline avg return/trade (%) | (not found in CLAUDE.md) | 1.12 | NO-PARSE |
| Baseline SD (%) | (not found in CLAUDE.md) | 2.41 | NO-PARSE |
| Baseline p (one-sided) | (not found in CLAUDE.md) | 0.026 | NO-PARSE |

## Ablation A/B -- passthrough from CLAUDE.md, UNVERIFIED this run

No function in this file reproduces these figures from current code -- the originating script was never committed. Printed here only as cited from `CLAUDE.md`, not independently recomputed.

| Configuration | N | Win rate | Total return |
|---|---|---|---|
