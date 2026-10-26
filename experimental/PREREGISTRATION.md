# Pre-registration: ML meta-labeling of Order Block candidates

Branch: `experimental`. Status: EXPLORATORY. It is not part of the paper
unless the author decides otherwise after reading `RESULTS.md`.

This file was committed **before** any model was fitted and before any
2022+ bar was evaluated. Everything below is fixed. If any of it is changed
after the commit, `RESULTS.md` must disclose the change and give the reason.

What had been looked at before this file was written (and nothing else):

- The parity gate (`results/parity.json`).
- Counts and class balance of the 2018–2021 candidates: 2,192 resolved
  candidates on 468 distinct OBs, 47.7% with pnl > 0, longest hold 30 bars.
  These were used for the go/no-go check below.
- On the locked 2022–2026 window: candidate count 1,869, rule-passing 47.
  This was a by-product of the parity run. No model touched it.

## 1. Question

The locked rule set takes 27 trades in 2022–2026 (`docs/SCRATCH_RESULTS_METHODS.md`).
If its four indicator gates become features, and a model trained only on
2018–2021 decides which Order Block touches to take, does the selection
beat chance out of sample, and does it hold across resamples?

## 2. Data and windows (by bar index of `artifacts/candles_extended.json`)

| Window | Bars | Role |
|---|---|---|
| 2018-01-01 → 2021-12-31 | `[0, 8750)` | training and model selection only |
| 2022-01-01 → 2025-12-31 | `[8750, 17517)` | out-of-sample (OOS), evaluated once after the freeze commit |
| 2026-01-01 → 2026-08-07 | `[17517, 18828)` | lockbox, one shot |

Each phase loads only the bars it is allowed to see. The guard in
`load_extended_series` raises otherwise. Indicators and Order Blocks are
recomputed on the loaded prefix, and truncation invariance is tested in
`parity.json`. Offline only.

## 3. Candidates and labels

- **Candidate.** A (bar i, active Order Block) pair. The bar touches the OB
  the way the entry rule defines a touch, and the engine's risk geometry
  holds: SL = OB edge ∓ 0.5·ATR14, SL distance ≥ 1.5%, TP = structural OB
  else 2R, R:R ≥ 1.5. Active OB means: created before i, not mitigated,
  age ≤ 500 bars, min quality 0 (the locked baseline's setting).
- **Gates recorded, not applied.** The MACD-hist gate, the KDJ gate, the
  K-acceleration window [1, 6], and the ATR-regime dead zone [0.8, 1.0].
  These are the exact expressions and constants from `_try_enter_long` and
  `_try_enter_short`.
- **Outcome.** The engine's own exit helpers, run bar by bar from the entry
  (`simulate_one`). Label = `pnl_pct > 0`. A candidate whose trade has not
  exited by the end of the loaded window is unresolved and gets no label.
- **Parity (passed before this file was written).** The rule policy on
  these candidates reproduces all 27 locked trades exactly.

## 4. Features (fixed)

All are known at bar i's close. Bar-level features are oriented so LONG
semantics hold for both sides: the MACD/return terms are multiplied by the
side sign, and K/D/J are mirrored as 100 − x for shorts.

| Group | Columns |
|---|---|
| MACD_hist_gate | hist/ATR, Δhist/ATR, Δhist(prev)/ATR, gate flag |
| KDJ_gate | K, D, J, ΔK, gate flag |
| K_acceleration | K acceleration, gate flag |
| ATR_regime | ATR14/ATR200, ATR14/close, gate flag |
| OB_quality | quality score + its 5 boolean components |
| OB_geometry | OB age, OB width/ATR, penetration into OB/ATR, swing-vs-internal, SL %, R:R, structural-TP flag |
| Price_volume_context | 6-bar and 30-bar log return, 30-bar log-volume z-score, side |

## 5. Model selection (2018–2021 only)

- **Go/no-go:** ≥ 150 resolved training candidates and minority class
  ≥ 20%. Observed 2,192 and 47.7%, so GO.
- **CV:** walk-forward. Resolved candidates are split into 5 contiguous
  blocks by bar. Folds 2–5 are the test blocks, and each trains on every
  earlier block (expanding window). Three things are dropped from a fold's
  training set:
  - candidates whose exit bar ≥ the test block's first bar (purge);
  - candidates entered within 30 bars before the test block (embargo; 30 =
    longest hold);
  - candidates on any OB that also appears in the test block (grouping).
- **Model families and grids (17 configs):**
  - L2 logistic regression with standardization: C ∈ {0.001, 0.01, 0.1, 1, 10}.
  - RandomForest: 500 trees, max_features = sqrt, max_depth ∈ {3, 5, None}
    × min_samples_leaf ∈ {20, 50}.
  - HistGradientBoosting: 200 iterations, min_samples_leaf = 40, L2 = 1.0,
    learning_rate ∈ {0.03, 0.1} × max_depth ∈ {2, 3, 4}.
  - Seeds fixed from `MASTER_SEED = 20260101`.
- **Selection metric:** mean test-fold log-loss, lowest wins. Ties go to
  the earlier config in the list above.
- **Threshold:** for the chosen config only, out-of-fold probabilities pick
  the take threshold t ∈ {0.40, 0.45, …, 0.70}. The objective is the
  highest mean pnl per trade from the one-position sequential policy run
  inside each test fold, with folds pooled. A threshold needs ≥ 30 pooled
  trades to qualify, ties go to the lower t, and t = 0.50 is used if none
  qualifies.
- **Lookahead test (a):** re-run CV for the chosen config with bar-level
  features taken from bar i−1 (lagged) and from bar i+1 (lead, a positive
  control). This is reported only.

## 6. Freeze

Refit the chosen config on all resolved 2018–2021 candidates. Save the
model to `results/frozen_model.pkl`, and save its SHA-256 together with
the config, the feature list and the threshold to
`results/frozen_model.json`. Commit both. The `oos` phase refuses to run
if the hash does not match.

## 7. Arms (same OOS candidate stream, same simulator, same one-position policy)

| Arm | Take a candidate when |
|---|---|
| A0 | all four rule gates pass (locked rule on the extended series) |
| A1 | always (every geometry-valid candidate) |
| **A2** | **frozen model p ≥ t (primary)** |
| A3 | all four rule gates pass AND p ≥ t |
| A4 | Bernoulli(q), where q = share of OOS candidates with p ≥ t; 1,000 seeds |
| A5 | shuffled-label null: the frozen config refit on 2018–21 with labels permuted, 200 times. Each null takes p_null ≥ its own training-set quantile matching A2's training-set take-rate |

Fees: every arm is also reported net of `BENCHMARK_ROUND_TRIP_DRAG_PCT`
(0.20% per trade). For B&H and DCA the paper's own helpers
(`_run_lump_sum_dollar_arm`, `_run_dca_dollar_arm`) are used, and Sharpe
and max drawdown come from `_run_strategy_dollar_arm`.

## 8. Primary endpoint (the only confirmatory test)

**A2's mean pnl per trade in 2022–2025 vs. the A5 null distribution,
one-sided, α = 0.05.**
p = (1 + #{null ≥ observed}) / (1 + 200). A null run with zero trades
counts as mean 0. The fee subtracts the same constant from every trade, so
this test reads the same gross or net.

Everything else is descriptive or exploratory.

## 9. Resamples ("at least 50")

- **R1:** stationary block bootstrap of each arm's OOS trade sequence,
  B = 1,000, expected block length = max(1, round(n^(1/3))). Reports the
  95% CI of mean and total pnl, and P(total ≤ 0).
- **R2:** 50 random contiguous 12-month windows (2,190 bars), with start
  uniform inside the OOS window. Uses each arm's trades whose entry falls
  in the window, from the full sequential run. Reports the share of
  windows where A2 total > 0, A2 > A1, A2 > A0, and A2 > buy-and-hold
  over that window.

## 10. Individual indicator effects (exploratory)

- **Rule side (B arms).** These run per window: 2018–21, 2022–25, and the
  lockbox in the lockbox run.
  - B-LOO: the locked rule minus one gate, for each of the 4 gates.
  - B-ONLY: one gate alone, for each of the 4 gates.
  - B+Q: the locked rule plus an OB quality ≥ 1 filter (the engine's
    `DEFAULT_MIN_OB_QUALITY`). The locked baseline has no quality filter,
    so this is "add one" instead of "leave one out".
  - Each arm vs A0: difference in mean pnl per trade, independent
    bootstrap, B = 2,000, a 95% CI, and a two-sided bootstrap p. Holm
    correction across the 9 arms in each window.
  - Sanity: all four gates on must equal A0 trade for trade.
- **ML side (A6), 2022–25.**
  - Drop-column: refit the frozen config without one group (7 groups) on
    2018–21, and keep the frozen threshold. Report Δ OOS log-loss and
    Δ mean pnl per trade vs A2 (independent bootstrap, B = 2,000, a 95%
    CI, and a two-sided p), Holm-corrected across the 7 groups.
  - Group permutation importance on OOS candidates: the group's columns
    are permuted jointly, 30 repeats, scored on Δ log-loss.
- **Limitation.** One-at-a-time ablation misses interactions. B-ONLY is
  there to give the other side of that.

## 11. Lockbox

`--phase lockbox --i-understand-this-is-one-shot` writes
`results/LOCKBOX_USED.marker` first and refuses to run if the marker
exists. It runs A0, A1, A2, A3 and the B arms on 2026-01 → 2026-08 once
with the frozen model. Whatever comes out gets reported.

## 12. Reporting

Every number in `RESULTS.md` is read from `results/*.json`. Null and
unfavorable results are reported as they come. `research_analysis.py` and
the locked baseline are not modified. The check is
`git diff development -- research_analysis.py` (empty) plus
`scratch/regression.py`.
