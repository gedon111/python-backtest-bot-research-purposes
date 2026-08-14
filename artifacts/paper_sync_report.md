# Paper/codebase sync report

Generated: 2026-08-14T03:28:15.931146+00:00

Recomputed live from `artifacts/candles.csv` and this file's own strategy-engine functions, then cross-checked against the figures parsed out of `CLAUDE.md`'s "Locked results" section. A MISMATCH row is a correctness finding, not something this script resolves automatically -- see `CLAUDE.md`'s rule on newly found bugs.

## Cross-check summary

| Metric | Locked (CLAUDE.md) | Live (this run) | Status |
|---|---|---|---|
| Bar count | 8767 | 8767 | MATCH |
| Baseline (q>=0) trades | 27 | 27 | MATCH |
| Baseline win rate (%) | 70.37 | 70.37 | MATCH |
| Baseline total net return (%) | 30.31 | 30.31 | MATCH |
| Baseline avg return/trade (%) | 1.12 | 1.12 | MATCH |
| Baseline SD (%) | 2.41 | 2.41 | MATCH |
| Baseline p (one-sided) | 0.026 | 0.026 | MATCH |
| Total detected Order Blocks | 761 | 761 | MATCH |
| FVG-true count | 253 | 253 | MATCH |
| FVG-true (%) | 33.2 | 33.2 | MATCH |
| OB quality distribution q0 | 93 | 93 | MATCH |
| OB quality distribution q1 | 154 | 154 | MATCH |
| OB quality distribution q2 | 206 | 206 | MATCH |
| OB quality distribution q3 | 197 | 197 | MATCH |
| OB quality distribution q4 | 90 | 90 | MATCH |
| OB quality distribution q5 | 21 | 21 | MATCH |

## Full q0-q5 threshold sweep (live)

| q | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (one-sided) | p (two-sided) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 27 | 19 | 8 | 70.37% | +30.31% | +1.1225% | 2.41 | 0.0261 | 0.0522 |
| 1 | 25 | 17 | 8 | 68.00% | +28.31% | +1.1323% | 2.51 | 0.0539 | 0.1078 |
| 2 | 23 | 15 | 8 | 65.22% | +23.28% | +1.0120% | 2.56 | 0.1050 | 0.2100 |
| 3 | 14 | 8 | 6 | 57.14% | +6.59% | +0.4709% | 2.76 | 0.3953 | 0.7905 |
| 4 | 6 | 3 | 3 | 50.00% | +6.71% | +1.1177% | 3.85 | 0.6562 | 1.0000 |
| 5 | 1 | 0 | 1 | 0.00% | -0.38% | -0.3809% | n/a (n=1) | 1.0000 | 1.0000 |

## Per-criterion Fisher's exact + Welch's t-test (live, q>=0 baseline)

| Criterion | True n (wins) | False n (wins) | Fisher p | Welch t | Welch p |
|---|---|---|---|---|---|
| Displacement | 4 (2) | 23 (17) | 0.5583 | -0.9277 | 0.3775 |
| LargeBar | 20 (14) | 7 (5) | 1.0000 | +0.2895 | 0.7751 |
| FVG | 11 (8) | 16 (11) | 1.0000 | +0.5360 | 0.5996 |
| LiqSweep | 15 (10) | 12 (9) | 0.6957 | -0.8195 | 0.4204 |
| VolExpansion | 15 (9) | 12 (10) | 0.2357 | -0.8835 | 0.3864 |

Welch p-value range across all 5 criteria: **0.3775-0.7751**.

## Ablation A/B -- passthrough from CLAUDE.md, UNVERIFIED this run

No function in this file reproduces these figures from current code -- the originating script was never committed. Printed here only as cited from `CLAUDE.md`, not independently recomputed.

| Configuration | N | Win rate | Total return |
|---|---|---|---|
| Indicators-only (entry-ATR stop) | 140 | 60.00% | -14.63% |
| Indicators-only (swing-pivot stop) | 138 | 55.07% | -25.50% |
