# HEDGE — Paper ↔ Code Handoff

**Every number in the manuscript, mapped to the function and line range that
produced it, the artifact it is written to, and the hand-check that confirms
it.**

Companion to `docs/finalists/HEDGE_Research_Paper.md` and
`docs/finalists/HEDGE_Code_Guide.md`.

**Source of truth for every figure below:** `docs/SCRATCH_RESULTS_METHODS.md`.
Any figure that does not appear there is flagged in-line as unsourced.
**Everything runs from one file:** `research_analysis.py` (repo root, 4,847
lines).

**How to use this document.** During a defense, a question about a number has
three parts: *what is it*, *where does it come from*, and *can you show me*.
This table answers all three in one row. The § references point into
`HEDGE_Code_Guide.md`, where the hand-check for that computation is written
out.

---

## 0. Reproduce everything, from a clean clone

```bash
python research_analysis.py                # the whole offline stats pipeline
python scratch/regression.py               # golden-master check: must print PASS
python research_analysis.py --serve        # artifacts + DB + dashboard on :8765
```

The default run is **strictly offline**. The only network call in the
project, `run_forward_oos_validation()` (L3173), is gated behind
`--include-oos-live` and is off by default.

To reproduce any single number interactively, load the module and call the
function directly:

```python
import importlib.util, pandas as pd, numpy as np
spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec); spec.loader.exec_module(bot)

df = bot.compute_indicators(bot.load_candles())
t  = bot.simulate_trades(df, min_ob_quality=0).attrs["trades_df"]
```

Everything in §1 below is one call away from that `t`.

---

## 1. Number → code map

### 1.1 Dataset

| Reported figure | Value | Function | Lines | Artifact | Guide § |
|---|---|---|---|---|---|
| Primary window bars | 8,767 | `load_candles` | 465–486 | `artifacts/candles.csv` | 2.1 |
| Window span | 1,461 days (2022-01-01 → 2026-01-01) | `load_candles` | 465–486 | same | 2.1 |
| Order Blocks detected | 761 (659 internal / 102 swing) | `compute_smc` | 615–769 | `artifacts/runs_by_threshold.json` | 3.2 |
| Formulation window bars | 8,750 of 8,767 expected | `load_formulation_period_window` | 3526–3552 | `artifacts/candles_extended.json` | 5B.8 |

The 8,767 figure is **derivable on paper**: `365 × 4 = 1460`, `+1` leap day
(2024-02-29) `= 1461` days, `× 6` bars/day `= 8,766`, `+1` boundary-inclusive
endpoint bar `= 8,767`. An earlier draft's 8,760 dropped both the leap day
and the endpoint bar; corrected and recorded.

### 1.2 Headline performance — the locked baseline (`min_ob_quality=0`)

| Reported figure | Value | Function | Lines | Guide § |
|---|---|---|---|---|
| Trades | **27** | `simulate_trades` | 1381–1637 | 3.10 |
| Win rate | **70.37%** (19 of 27) | `simulate_trades` | 1616–1627 | 3.10 |
| Total net return | **+30.31%** (sum of `pnl_pct`) | `simulate_trades` | 1619 | 3.10 |
| Average return / trade | **+1.12%** | `simulate_trades` | 1620 | 3.10 |
| SD of returns | **2.41%** | `build_trades_and_results_table` | 3785–3838 | 5B.11 |
| LONG / SHORT split | 15 / 12 | `simulate_trades` | 1547–1562 | 3.7 |
| Exit-reason split | ATR 9, trailing 8, KDJ 8, stop 2 | exit ladder | 1235–1336 | 3.8 |

**Artifacts:** `artifacts/trades_default_view.csv` (⚠️ default view is
quality 1, **not** the q≥0 baseline — see §4), `artifacts/runs_by_threshold.json`
(level `0` block holds the 27-trade run).

**Be precise about the return convention.** `+30.31%` is a **simple sum** of
per-trade percentage returns, not a compounded equity curve. The compounded
figure is reported separately as `final_capital` (§1.5): $10,000 → $13,417.77,
i.e. +34.18%. Both are reported; they are never reconciled into one number.

### 1.3 Statistical inference

| Reported figure | Value | Function | Lines | Artifact | Guide § |
|---|---|---|---|---|---|
| Binomial p (one-sided) | **0.026** | `binomial_test` | 2521–2550 | `artifacts/bootstrap_power_analysis.json` | 5.1 |
| Binomial p (two-sided) | 0.052 | same | same | same | 5.1 |
| 95% bootstrap CI, total return | **[+5.99%, +54.99%]** | `run_bootstrap_ci` → `bootstrap_resample` | 2737–2775 → 2553–2601 | same | 5B.1, 5.2 |
| 95% bootstrap CI, avg return | [+0.22%, +2.04%] | same | same | same | 5B.1 |
| Resamples ≤ 0 | 0.75% of 10,000 | same | same | same | 5B.1 |
| Pearson r (hold_bars vs pnl) | **+0.4907**, p = 0.0094 | `pearson_correlation` | 2604–2627 | same | 5.3 |
| Spearman rho | **+0.4797**, p = 0.0113 | `spearman_correlation` | 2630–2662 | same | 5.3 |

Bootstrap parameters: **B = 10,000, n = 27, seed = 42**, `np.random.default_rng`.

Exact values, printed by the code:

```
binomial   : {'p_one_sided': 0.026119492948055267, 'p_two_sided': 0.052238985896110535}
bootstrap  : total_return_ci_pct [5.9866116295368155, 54.98658996206774]
             avg_return_ci_pct   [0.2217263566495117, 2.036540368965472]
pearson    : {'r': 0.490698051200364,   'p_value': 0.009356041907353906, 'n': 27}
spearman   : {'rho': 0.47972823534097186,'p_value': 0.011334889028469911, 'n': 27}
```

**`spearman_correlation` is the one genuinely new function in the file** — no
`.py` in this repository computed Spearman's rho before consolidation. It is
a `scipy.stats.spearmanr` wrapper mirroring the Pearson call, and it
reproduces figures that previously lived only in markdown notes. Disclose
this rather than letting it be discovered.

### 1.4 Risk and benchmark

| Reported figure | Value | Function | Lines | Guide § |
|---|---|---|---|---|
| Sharpe (strategy) | **1.114** | `sharpe_sortino_ratios` via `run_benchmark_vs_buy_and_hold` | 2689–2718 / 2778–2857 | 5.5, 5B.2 |
| Sortino (strategy) | 2.727 | same | same | 5.5 |
| Max drawdown (strategy) | **−6.46%** | `max_drawdown_pct` | 2665–2686 | 5.4 |
| Time in market | **2.63%** (231 of 8,767 bars) | `run_benchmark_vs_buy_and_hold` | 2778–2857 | 5B.2 |
| Return per exposed bar | 0.1312% (vs B&H 0.0100%) | same | same | 5B.2 |
| Buy-and-hold (close-to-close) | +87.65%, Sharpe 0.564, MaxDD −67.21% | same | same | 5B.2 |
| Trade return vs BTC-window return | Pearson r = **−0.369, p = 0.058** | `pearson_correlation` | 2604–2627 | 5B.2 |

Annualisation: `PERIODS_PER_YEAR_4H_BARS = 6 × 365.25 = 2191.5` (L2733).

⚠️ **The −0.369 correlation is NOT significant at α = 0.05** (p = 0.058).
Report it as suggestive that the strategy is not simply long beta — never as
established.

### 1.5 Head-to-head against passive strategies

`run_benchmark_vs_passive()` (L3716–3782), $10,000 notional per arm, gross
unless stated.

**2022–2026, the locked window**

| Arm | Return | Terminal | Sharpe | MaxDD | Time in market | Function |
|---|---|---|---|---|---|---|
| OB-gated strategy | +30.31% | **$13,417.77** | 1.114 | −6.46% | **2.63%** | `_run_strategy_dollar_arm` (3608) |
| Weekly DCA into BTC | **+123.13%** | **$22,312.94** | 0.556 | −27.85% | 100% | `_run_dca_dollar_arm` (3652) |
| Lump-sum buy & hold | **+90.07%** | **$19,007.32** | 0.564 | −67.21% | 100% | `_run_lump_sum_dollar_arm` (3695) |

Fee-adjusted strategy: **+24.91% → $12,719.01**
(`BENCHMARK_ROUND_TRIP_DRAG_PCT` = 0.20% on the strategy arm;
`BENCHMARK_ONE_SIDE_DRAG_PCT` = 0.10% one-sided on the passive arms, which
are held rather than round-tripped).

**2018–2022, the formulation period — NOT out-of-sample**

| Arm | Return | Terminal |
|---|---|---|
| Strategy | +21.82% | $12,282.53 |
| DCA | +439.88% | $53,987.55 |
| Lump-sum | +236.96% | $33,696.49 |

**Artifact:** `artifacts/benchmark_vs_passive.json`.

> **The mandatory caveat, verbatim from `docs/SCRATCH_RESULTS_METHODS.md`:**
> *"DCA and lump-sum B&H both beat the strategy in raw terminal value over
> this window. Any statement of the strategy 'beating' DCA/BTC must carry the
> exposure-time caveat (2.63% vs 100%) in the same sentence — the strategy's
> edge is risk/exposure-adjusted, not a raw-return claim."*

**Two buy-and-hold numbers, both correct.** §1.4 reports +87.65% and §1.5
reports +90.07%. `run_benchmark_vs_buy_and_hold` measures **close-to-close**;
`_run_lump_sum_dollar_arm` buys at the first bar's **open** (L3698). A lower
purchase price on the same sale price gives a higher return. Know which
figure you are quoting.

### 1.6 Transaction costs

`run_fee_slippage_sensitivity()` (L2996–3073), artifact
`artifacts/fee_slippage_analysis.json`.

| Scenario | Round-trip drag | Total return |
|---|---|---|
| GROSS — as headline-reported | 0.00% | +30.31% |
| FEE ONLY — confirmed 5 bps/side taker | 0.10% | — |
| **PRIMARY** — fee + 5 bps/side slippage | **0.20%** | **+24.91%** |
| Legacy band LOW / MID / HIGH | 0.14 / 0.24 / 0.40% | — |

The 5 bps/side taker fee is the **confirmed** Binance USDT-M Futures standard
tier. The 5 bps/side slippage is a **conservative estimate**, kept as a
strictly separate line item because it is a judgement and the fee is a
published number. **The strategy stays profitable under the PRIMARY
scenario** — that is the sentence to have ready.

### 1.7 Regime breakdown

`run_regime_breakdown()` (L3076–3170). Two independent tagging methods, both
reported, never collapsed:

1. **Calendar** — 2022 = bear, 2023 = chop, 2024+ = bull.
2. **Drawdown from ATH** — BEAR ≤ −40%, CHOP −40% to −12%, BULL > −12%,
   with the running ATH **seeded at $69,000**.

**Be ready to defend the $69,000 seed.** It is BTC's real 2021-11-10
all-time high, which predates the dataset's first bar by seven weeks.
Seeding from the dataset's own first bar would read early-2022 — already
about 32% below the true high — as "at the high," and would mislabel a large
block of 2022 trades. The seed imports one fact from outside the window, and
it is disclosed rather than buried. The −40% / −12% thresholds are stated in
the docstring as a judgment call so they can be re-argued.

The two methods **disagree on some trades**, and `method_agreement` returns
the full disagreement list.

### 1.8 The ablation arms — reference figures, not reproducible

| Arm | n | Win rate | Total return | Source |
|---|---|---|---|---|
| 1 — OB-gated baseline | 27 | 70.37% | +30.31% | `simulate_trades` (1381) |
| 2 — indicators-only, flat-ATR stop | **140** | **60.00%** | **−14.63%** | `LOCKED_ABLATION_ARMS` (L163) |
| 3 — indicators-only, swing-pivot stop | **138** | **55.07%** | **−25.50%** | `LOCKED_ABLATION_ARMS` (L164) |

⚠️ **The script that produced the 140/138-trade pools was never committed to
this repository.** `run_ablation_arm()` (L2176) is a fresh, best-faith
reconstruction from the *documented* design — not a byte-for-byte recovery —
and it is **not guaranteed to reproduce those figures**.
`run_ablation_study()` (L2430) prints an explicit MATCH or DIVERGE on every
run and never silently reconciles. A prior reconstruction attempt already
diverged by more than 10 win-rate points, so a DIVERGE is an expected,
already-known reconstruction-fidelity gap, not a new finding.

**How to state this at a defense.** *The direction of the ablation result is
supported — removing the Order Block gate turns a profitable configuration
into two unprofitable ones. The exact 140/138 figures are carried as
reference numbers whose generating script is not available for
re-execution.* Do not present them as reproducible on demand.

**Artifact:** `artifacts/ablation_reconstruction.json`.

---

## 2. Pre-registered parameters — the full list

Every value below is fixed at L129–170 and was never swept, tuned or
optimized. Guide § 1.3 gives the provenance of each.

| Constant | Value | Line |
|---|---|---|
| `SWING_STRUCTURE_LOOKBACK_BARS` | 50 | 132 |
| `INTERNAL_STRUCTURE_LOOKBACK_BARS` | 5 | 133 |
| `MAX_ORDER_BLOCK_AGE_BARS` | 500 | 134 |
| `DEFAULT_MIN_OB_QUALITY` | 1 | 139 |
| `MIN_STOP_LOSS_DISTANCE_RATIO` | 0.015 | 140 |
| `KDJ_J_LONG_CAP` | 60.0 | 141 |
| `KDJ_K_LONG_CAP` | 50.0 | 142 |
| `KDJ_K_SHORT_FLOOR` | 70.0 | 143 |
| `KDJ_J_SHORT_CAP` | 100.0 | 144 |
| `ATR_MULT_EXIT` | 1.8 | 145 |
| `ATR_MULT_BREAKEVEN` | 2.0 | 146 |
| `MIN_RISK_REWARD_RATIO` | 1.5 | 147 |
| `PERIODS_PER_YEAR_4H_BARS` | 2191.5 | 2733 |
| `PERIODS_PER_YEAR_WEEKLY` | 52 | 2734 |
| bootstrap `B` / `seed` | 10,000 / 42 | 2737 |
| regime ATH seed | $69,000 | 3076 |
| benchmark starting capital | $10,000 | 3716 |

**The 50 and the 5 are LuxAlgo's published TradingView defaults, not choices
made here.** That matters: two of the three structural parameters are
inherited from a public indicator rather than selected against this dataset.

⚠️ **`DEFAULT_MIN_OB_QUALITY = 1` is the *default*; the paper's locked
baseline runs at `min_ob_quality=0`** — no quality filtering at all. The
default exists for the dashboard's four-level view. This distinction is why
the corrected quality-criteria lookahead bug cannot move the headline
figures.

---

## 3. Disclosed corrections, each with the code that implements the fix

### 3.1 The backtest-engine bug — FVG / displacement lookahead

**What it was.** The forward-search loops for two Order Block quality
criteria were bounded by **dataset length** rather than by each Order Block's
own confirmation bar. They could read one to two candles that would not have
been available at the moment the zone became eligible for entry. That is
genuine data leakage.

**How it was found.** A dedicated no-lookahead audit of `compute_smc()`.

**The fix** (commit `cb4ed93`), in `_build_order_block_from_crossover`:

| Criterion | Line | Bound | Why that expression |
|---|---|---|---|
| Displacement | 800–826 | `min(confirmation_bar + 1, ob_bar_index + 4)` | reads one bar `j` → needs `j ≤ confirmation_bar` |
| FVG | 835–856 | `min(confirmation_bar − 1, ob_bar_index + 3)` | reads `j` **and `j+2`** → needs `j + 2 ≤ confirmation_bar` |

The `−1` in the FVG bound is not an off-by-one; it is what keeps the furthest
read inside the confirmation bar.

**The guards.** Runtime `assert`s at L810 and L841 restate the invariant at
the read site, and each criterion's broad `except Exception` is preceded by
`except AssertionError: raise` (L823, L853) so the safety net cannot swallow
the guard. A regression fails on the next run rather than waiting for another
audit.

**Effect on published figures: none.** The q≥0 baseline never consults the
quality score, and `scratch/regression.py` passes across the fix.

**Independent verification, from the paper:** truncation-equality testing on
ATR(14), ATR(200) and the fixed KDJ(9,3,3) series passed **180 of 180**
sampled checks — recomputing each indicator on a shortened dataset gave
identical values, which is what must happen if no future data is used. A
scope audit of the corrected Order Block code found no FVG-true or
displacement-true Order Block reading past its own confirmation candle.

### 3.2 The correlation p-value reporting error

Two draft documents reported the hold-duration/return correlation as
**p < 0.001**. Independent recomputation via SciPy gave **p ≈ 0.0094**
(Pearson, r = +0.4907, t = 2.82, df = 25) and **p ≈ 0.0113** (Spearman,
rho = +0.4797). Still significant at α = 0.05; the wrong significance bucket
at α = 0.001. Both source documents were corrected.

Present this as a strength. A project whose own closing audit catches its own
reporting errors is demonstrating the same discipline as one that catches its
own code bugs.

### 3.3 The two bootstrap confidence intervals

| Surface | B | PRNG | 95% CI on total return |
|---|---|---|---|
| Python — `run_bootstrap_ci` (L2737) | 10,000 | numpy `default_rng`, seed 42 | **[+5.99%, +54.99%]** — the paper's canonical figure |
| Dashboard — `statsCompute.ts` `computeOwnBootstrapCI` | 2,000 | JS mulberry32, seed 42 | [+7.48%, +54.46%] |

**Root cause: the B mismatch alone, not a logic bug.** Verified by porting
the mulberry32 PRNG into Python and reproducing [+7.48%, +54.46%] *exactly*
at B = 2,000.

Both values are reported and the gap is explained. They are **deliberately
not unified**, because the gap is the visible product of the project's
intentional Python↔TypeScript independence (§5).

### 3.4 The dataset-size correction

8,760 → **8,767** bars. The earlier figure used plain `365 × 4 × 6`
arithmetic, dropping the 2024 leap day and the boundary-inclusive endpoint
bar. Bars are not trimmed.

### 3.5 The KDJ "two-bar window" text correction

An earlier paper draft used a two-bar exit window `w` as an illustrative
example. Across the 27 baseline trades the observed `w` runs **14 to 439,
median 74** — it never approaches single digits. **The paper text was
corrected; the code was not changed,** because the code was never wrong.
`kdj_exit_window` is recorded on every trade row so this is checkable
directly:

```python
print(t.kdj_exit_window.min(), t.kdj_exit_window.max(), t.kdj_exit_window.median())
# 14 439 74.0
```

### 3.6 The ATR smoothing comment

The code comment at L593–596 says "Wilder's smoothing (RMA)" and describes
`ewm(alpha=1/n)`. **The executed code is a plain rolling mean** (L603–604).
The paper reports the plain rolling mean and discloses the stale comment
explicitly. **The code and the paper agree; the comment does not.** The
comment was deliberately left unedited rather than touching the protected
core during the paper freeze for a comment-only change.

---

## 4. Open questions — do not overclaim

### 4.1 The "190 qualifying signals" denominator

The paper reports 190 total qualifying indicator signals as the denominator
for the claim that 25 of 27 OB-gated trades (92.6%) coincided with
independent indicator signals.

**That 190 was derived using the indicators-only ablation's
`1.5 × ATR` entry-anchored stop, not the OB-gated strategy's own risk
rules.** The two populations are filtered differently, so the ratio is not
apples-to-apples.

**This is unresolved. Do not cite 190 as a settled figure.** If asked, say
exactly that: the denominator comes from a differently-filtered population
and the comparison has not been re-derived under matched rules.

### 4.2 The ablation arms' trade pools

See §1.8. The generating script was never committed; the committed
reconstruction is not guaranteed to reproduce the published pools.

### 4.3 The formulation window's missing candles

The 2018–2022 window holds 8,750 rows against 8,767 expected under the same
counting convention — **seventeen candles missing across eight separate
exchange-side outages, the largest a run of seven consecutive candles.**
Source: `HEDGE_Research_Paper.md`, Methodology → *Data* (this figure is not
carried in `docs/SCRATCH_RESULTS_METHODS.md`). Disclosed rather than left
unstated. **No figure reported from the primary
window is affected**; the primary window is verified complete.

### 4.4 Structural limitations to concede without prompting

- **No transaction costs inside the engine.** `simulate_trades()` models
  none; costs are applied afterwards as a flat drag by
  `run_fee_slippage_sensitivity()`. The headline figures are gross.
- **The bootstrap treats the 27 realized trades as the population.** It
  quantifies sampling uncertainty *given this trade log*. It cannot say what
  a different price history would have produced.
- **Sharpe and Sortino use an implicit risk-free rate of zero.**
  Conventional for this window and this return magnitude, but a
  simplification.
- **Sharpe, Sortino and max drawdown each come from a single realized price
  path.** Each is one observation, not a sample, so no sampling distribution
  exists behind it and no legitimate p-value can be formed. Welch's t-test
  and Fisher's exact test were considered for the sleeve comparison and
  **rejected on exactly that basis**; the sleeve result is resolved
  descriptively, which is a weaker standard and is treated as one.
- **The 2018–2022 window is not out-of-sample.** It is the period the rule
  structure was formed against. Every reference must carry that caveat.

---

## 5. The independent cross-check

The dashboard (`dashboard-v2`) recomputes the win rate, the one-sided
binomial test, Pearson/Spearman correlation and a percentile bootstrap CI
from the same exported per-trade data, using its **own independent
TypeScript implementation** (`statsCompute.ts`, `statMath.ts`) rather than
importing any Python-computed statistic.

That is a deliberate design constraint, not duplicated work. Two independent
implementations, in two languages, computing the same statistics from the
same trade data, and agreeing, is a materially stronger claim than one
implementation agreeing with itself.

The bootstrap CI gap in §3.3 is the visible product of that independence: two
separate implementations, different B, different PRNGs, both correct, gap
explained rather than papered over.

**The JS side must never import from Python.** Doing so would eliminate the
only genuine cross-validation in the project.

---

## 6. Anticipated panel questions, with the line to open

| Question | Open | Short answer |
|---|---|---|
| "Did you tune these parameters?" | L129–170 | No. Pre-registered and never swept. Two of the three structural values are LuxAlgo's published defaults. |
| "Why two KDJ systems? Isn't that inconsistent?" | L581–590 and L927–1063 | Two systems by design. Entry reads the static full-history KDJ(9,3,3); exit uses a separate machine seeded from it at entry, with period `w = entry_idx − ob_bar`. `w` has **no** effect on entry — confirmed by read-only audit. |
| "How do you know there is no lookahead?" | L698–702, L810, L841 | Runtime asserts at every forward-search site, plus a truncation-equality audit that passed 180/180. |
| "27 trades is a very small sample." | L2553–2601 | Agreed, and it is why the interval is a nonparametric bootstrap rather than a normal-theory one. The CI is [+5.99%, +54.99%] — quote the lower bound as readily as the point estimate. |
| "Isn't 70% just luck?" | L2521–2550 | Exact binomial, one-sided p = 0.026 against a fair coin. Two-sided 0.052 — say both. |
| "Buy-and-hold beat you." | L3716–3782 | Yes, on raw return, in both windows. The claim is per unit of exposure (2.63% vs 100% time in market) and per unit of drawdown (−6.46% vs −67.21%). |
| "What about fees?" | L2996–3073 | Headline figures are gross. Under confirmed 5 bps/side fees plus 5 bps/side conservative slippage the total goes +30.31% → +24.91%. Still profitable. |
| "Show me one trade end to end." | Guide §3.7 | The first baseline trade, `entry_idx = 335`, walked gate by gate — and it is a **loss** (−0.66%). Walking a loser is the right demonstration. |
| "Why is the first trade a loss?" | Guide §3.8 | It exited on the trailing 50%-retrace rung after peaking. 25 of 27 trades ended on a managed exit; only 2 hit the hard stop and none hit the hard take-profit. |
| "Can I reproduce this?" | `scratch/regression.py` | Golden-master fixtures for all 8,767 bars and all 27 trades, compared at 1e-6 / 1e-5 tolerance. It must print PASS. |
| "Where does $69,000 come from?" | L3076 | BTC's real 2021-11-10 ATH, seven weeks before the dataset starts. Seeding from the dataset's own first bar would mislabel most of 2022. |
| "Is the ablation reproducible?" | L2085–2098 | No — and that is disclosed in the code's own section banner. The generating script was never committed; the reconstruction prints MATCH/DIVERGE. |
| "What is the 190 signals figure?" | §4.1 above | An open question. It used the ablation's stop rule, not the strategy's. Do not cite it as settled. |
| "Did an AI write this code?" | module docstring, `docs/PROVENANCE_VERDICT.md` | The file is a documented consolidation; every statistical function is a SciPy call or a standard-formula translation, none copied from a paper. AI co-authorship is disclosed rather than concealed. |

---

## 7. Artifact index

| File | Written by | Line | Holds |
|---|---|---|---|
| `artifacts/candles.csv` | `export_dashboard_artifacts` | 4076 | the locked 8,767-bar dataset |
| `artifacts/candles.json` | same | 4066 | bars + indicators |
| `artifacts/manifest.json` | `build_artifact_manifest` | 3905 | run parameters, candle count |
| `artifacts/verification_report.json` | `build_verification_report` | 3920 | SHA-256 hashes + source checks |
| `artifacts/runs_by_threshold.json` | `export_dashboard_artifacts` | 4070 | OBs, trades and stats per quality level |
| `artifacts/threshold_runs.json` / `.csv` | same | 4068 / 4077 | per-level summary |
| `artifacts/trades_default_view.csv` | same | 4079 | ⚠️ **default-view quality (1), not the q≥0 baseline** |
| `artifacts/orderblocks_default_view.csv` | same | 4080 | default-view Order Blocks |
| `artifacts/bootstrap_power_analysis.json` | `write_statistical_artifacts` | 4274 | binomial, bootstrap CI, correlations |
| `artifacts/fee_slippage_analysis.json` | same | 4278 | every cost scenario |
| `artifacts/ablation_reconstruction.json` | same | 4282 | three-arm results + MATCH/DIVERGE |
| `artifacts/benchmark_vs_passive.json` | same | 4288 | strategy vs DCA vs lump-sum, both windows |
| `artifacts/paper_sync_report.md` | `generate_paper_sync_report` | 3398 | recomputed figures diffed against the locked values |
| `artifacts/candles_extended.json` | (committed snapshot) | — | 2018–2026 history; source of the formulation window |
| `backtest_results.db` | `export_dashboard_artifacts` | 3971 | the queryable copy the dashboard's `/api/*` routes read |

> **Two traps worth knowing before a live demo.** `--serve` **rewrites**
> `artifacts/candles.csv`. And `trades_default_view.csv` holds the
> default-view quality run, **not** the 27-trade q≥0 baseline — quoting a
> number off that CSV is an avoidable error.

---

## 8. Document map

| Document | Role |
|---|---|
| `docs/SCRATCH_RESULTS_METHODS.md` | **Canonical results record.** Cite this for any number, correction or methodological decision. |
| `docs/finalists/HEDGE_Research_Paper.md` | The manuscript. |
| `docs/finalists/HEDGE_Code_Guide.md` | Line-0-to-4847 walkthrough with a hand check per module. |
| **this file** | Number → code → artifact → hand-check bridge. |
| `docs/study_guide.html` | Plain-language methodology guide with figures. |
| `docs/PROVENANCE_VERDICT.md` | Provenance audit of every statistical function. |
| `docs/MATH_CORRECTNESS_AND_COMPREHENSION.md` | Line-by-line formula check + plain-English derivations. |
| `scratch/regression.py` | The golden-master harness. Run it; never run `--generate`. |
