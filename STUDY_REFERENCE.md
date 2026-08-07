# Study Reference

Verified reference document for the ISEF manuscript's Materials and Methods /
Data section. Every quantitative claim below was either (a) reproduced by
executing code in this repository during this session, against
`artifacts/candles.csv` and the current `src/Binance backtest bot.py`, or (b)
read from committed audit-evidence text and marked as such, with no
independent live reproduction. Claims that could not be verified by either
route are explicitly labeled unverified. This document supersedes any
conflicting figures cached in prior chat context or in stale committed docs
(see "Discrepancies found" at the end).

Session verification environment: commit `775d463` (branch `development`),
Python execution against the working tree as of 2026-08-01.

---

## 1. Study identity

**Working title (per repository docs):** *Harnessing Bitcoin Volatility:
Backtesting an Integrated Algorithmic Strategy Combining KDJ, MACD, and Smart
Money Concepts* (`docs/orthogonal_criteria_reference.md`,
`docs/research_statistics_reference.md`).

**Research question:** Does a rule-based entry/exit strategy that gates MACD
and KDJ momentum signals through Smart Money Concepts (SMC) Order Block (OB)
structural zones produce a historical win rate and return on BTC/USDT 4-hour
candles that departs from a zero-edge (50% win probability) null model, and
does OB "quality" (a 5-criterion structural score) modulate that departure?

**Framing:** This is a **rule-based, parameter-fixed historical backtest**,
not a live or production trading system. No parameter in the simulated
strategy was fit, swept, or optimized against the outcome being measured
(`CLAUDE.md`, "Rules"). The codebase explicitly separates this research
artifact from any live-execution path: `simulate_trades()` in
`src/Binance backtest bot.py` runs bar-by-bar over a static historical
DataFrame with no order-execution or live-data code path invoked.

---

## 2. Data

**Source:** Binance `get_klines` REST endpoint, `BTCUSDT` symbol
(`src/Binance backtest bot.py`, `get_candles()`, lines 107-135).

**Interval:** 4-hour candles (`Client.KLINE_INTERVAL_4HOUR`).

**Timestamp convention:** Binance's raw millisecond `open_time` is converted
to a `datetime` and shifted by a **fixed +8 hour offset**
(`get_candles()`, line 132: `pd.to_datetime(..., unit='ms') + pd.Timedelta(hours=8)`).
The `open_time` column in `artifacts/candles.csv` is therefore not raw UTC;
it is UTC+8.

**Date range and bar count (live-verified this session):**

```
python -c "import pandas as pd; df=pd.read_csv('artifacts/candles.csv'); ..."
rows: 8767
first open_time: 2022-01-01 08:00:00
last open_time:  2026-01-01 08:00:00
unique inter-bar deltas: {4h}   (single value -> no missing bars)
```

Arithmetic: 2022-01-01 to 2026-01-01 spans exactly 1,461 calendar days
(365 + 365 + 366 + 365, the 366 accounting for the 2024 leap day). At 6
four-hour bars per day, that is 1,461 x 6 = 8,766 bar-intervals. Because the
final bar (2026-01-01 08:00:00) is itself included as a row rather than used
only as an exclusive upper bound, the row count is 8,766 + 1 = **8,767**,
matching the live count exactly. This reproduces the locked figure in
`CLAUDE.md` and rejects the paper's original 8,760 figure (`CLAUDE.md`,
"Locked results"). The manifest independently records the same value
(`artifacts/manifest.json`: `"candle_count": 8767"`, `generated_at_utc`
2026-08-01T11:12:10Z).

**Gaps:** none. The set of unique timestamp deltas across all 8,767 rows is
the single value 4 hours; no missing or duplicated bars were found in this
session's check.

**Regression-harness confirmation:** `scratch/regression.py` recomputes
indicators and the OB-gated simulation from `artifacts/candles.csv` from
scratch and asserts exact equality (indicator values to 1e-6, all 27 baseline
trade fields exactly) against the committed fixtures in
`scratch/fixtures/`. Run live this session:

```
Executing regression comparison against baseline fixtures...
PASS: Fresh run matches golden-master fixture EXACTLY across all bars, indicators, and 27 trades!
```

---

## 3. Strategy definition

All formulas below are read directly from `src/Binance backtest bot.py`,
`compute_indicators()` (lines 139-187) and `compute_smc()` (lines 190-526),
and from the fixed parameter block inside `simulate_trades()` (lines
603-614).

### 3.1 MACD(12, 26, 9)

Standard EMA-based MACD: `MACD = EMA(close,12) - EMA(close,26)`,
`signal = EMA(MACD,9)`, `hist = MACD - signal`, all EWMs computed with
`adjust=False` (causal, no lookahead).

### 3.2 ATR(14) and ATR_200

True range `TR = max(high-low, |high-prev_close|, |low-prev_close|)`,
smoothed with a rolling mean of window 14 for `ATR` and window 200 for
`ATR_200` (`.rolling(n, min_periods=1).mean()`). `ATR_200` serves as the
volatility baseline used throughout OB quality scoring and the entry ATR
regime filter.

### 3.3 KDJ(9, 3, 3) — two separate, non-interacting computations

This is the single most easily miscommunicated part of the strategy; the two
systems below never share state.

**(a) Static, full-history entry-gating KDJ.** Computed once, over the whole
dataset, by `compute_indicators()`: `RSV = (close - rolling_min(low,9)) /
(rolling_max(high,9) - rolling_min(low,9)) * 100`, then
`K = EWM(RSV, alpha=1/3)`, `D = EWM(K, alpha=1/3)`, `J = 3K - 2D`. Every K/D/J
reference inside the LONG/SHORT entry-condition checks in `simulate_trades()`
reads this static column at the current bar `i`. It has a fixed period (9)
for the entire backtest and is identical regardless of which OB triggers
entry. Nothing about it varies per trade.

**(b) Post-entry exit-window KDJ state machine.** A *separate* recursion,
`kdj_reset_init()` / `kdj_reset_update()` / `kdj_reset_exit()` (lines
542-593), used only to time the "KDJ RESET EXIT" condition after a trade is
already open. At entry, `kdj_reset_init(df, entry_idx, ob_bar)` seeds
`k`/`d`/`prev_k`/`prev_d` directly from the **static** KDJ values already
present in `df` at `entry_idx` (not reseeded to 50, not backfilled from the
OB bar) and sets a lookback window `period = max(1, entry_idx - ob_bar)`,
where `ob_bar` is the bar index of the OB that triggered entry. This `period`
is then held fixed for the rest of that trade's life. Each subsequent bar,
`kdj_reset_update()` recomputes an RSV over a rolling window of that fixed
`period` length and recurses `k`/`d` with the same `alpha = 1/3` smoothing.
`kdj_reset_exit()` fires when a K/D crossover consistent with the trade's
side occurs after the state has "armed." A separate gate in `simulate_trades`
blocks this exit signal for the first 3 bars after entry.

What varies from trade to trade is only the **window length** `period =
entry_idx - ob_bar` (call it `w`) of this second, post-entry recursion — not
the entry-gating KDJ, which is invariant. **`w` never affects which bars
qualify for entry.** This was confirmed by read-only audit (`CLAUDE.md`,
"KDJ architecture") and is not described here as "adaptive" without this
exact definition, per project instruction.

Live-verified `w` distribution across the 27 `min_ob_quality=0` baseline
trades this session (`entry_idx - entry_ob_bar` per trade,
`trades_df` from `simulate_trades()`):

```
n = 27, min = 14, max = 439, median = 74.0
```

This reproduces `CLAUDE.md`'s claim of range 14-439 (median 74) exactly and
confirms no trade has a single-digit `w`.

### 3.4 SMC Order Block detection

`compute_smc()` is a Python translation of the LuxAlgo Smart Money Concepts
market-structure/OB algorithm, run as two independent structural passes over
the same price series:

- **Internal structure**, pivot lookback `INTERNAL_SIZE = 5` bars.
- **Swing structure**, pivot lookback `SWING_SIZE = 50` bars.

For each pass, a bar `pb = i - size` is confirmed as a pivot high/low only by
strictly right-side comparison against bars `pb+1..i` (no future bars). A
Break of Structure (BOS) or Change of Character (CHoCH) is flagged when
`close` crosses a tracked pivot level, and an Order Block is created from the
`parsedHigh`/`parsedLow` array over the segment from the pivot bar to the
crossover bar `i` (`created_at = i`, i.e. the OB is not usable for entry
until strictly after bar `i`, enforced in `simulate_trades` via
`ob['created_at'] < i`). A volatility-parsed high/low substitution applies
when a bar's range is >= 2x `ATR_200` (`compute_smc()` lines 216-222).
Order Blocks age out and stop being eligible for entry after `MAX_OB_AGE =
500` bars, or once price closes through their boundary (`mitigated_at`).

### 3.5 Entry / exit rule summary (fixed, pre-registered parameters)

From the hardcoded block at the top of `simulate_trades()` (never taken from
`iteration_parameters` for strategy-formula values — see the "swept
parameters are dead code" note in §8):

| Parameter | Value |
|---|---|
| `sl_ratio_min` | 0.015 (minimum stop distance, 1.5% of entry) |
| `kdj_j_long_cap` | 60.0 |
| `kdj_k_long_cap` | 50.0 |
| `kdj_k_short_floor` | 70.0 |
| `kdj_j_short_cap` | 100.0 |
| `atr_mult_exit` | 1.8 (ATR-move take-profit exit) |
| `atr_mult_be` | 2.0 (breakeven stop trigger, in ATR) |
| `rr_min` | 1.5 (minimum reward:risk to accept a trade) |

LONG entry requires (all): price interacting with an active, unmitigated
DEMAND OB of sufficient quality; `MACD_hist < 0` and rising for >= 2 bars;
static `K < 50`, `K` rising, `J < 60`; a bounded 2-bar K-acceleration window
`1 <= k_accel <= 6`; ATR regime filter rejecting `0.8 <= ATR/ATR_200 <= 1.0`;
stop distance >= 1.5% of entry; reward:risk >= 1.5 against a structural or
2R-fallback take-profit. SHORT entry is the mirror condition against a
SUPPLY OB with `K > 50`, `J > K > D`, `K >= 70`, `J <= 100`. Exits are the
first of: trailing exit (50% retrace of peak favorable PnL once peak >=
1.5%), ATR-move exit (~1.8x ATR favorable move), KDJ-reset exit (gated to
bar 3+ after entry), breakeven-stop adjustment at 2x ATR favorable move, hard
stop-loss, or hard take-profit.

---

## 4. Order Block quality criteria

Each detected OB is scored on five **independently evaluated** boolean
criteria, summed into a `quality` field (0-5) that is used only as a
cumulative entry filter (`ob.get('quality', 0) >= min_ob_quality`), not as an
ordinal claim that higher scores are "better" in the paper's analysis
(`CLAUDE.md`, Known bug #1). Definitions below are read directly from
`compute_smc()`:

1. **Displacement:** within bars `ob_idx+1` to `min(i, ob_idx+3)` (bounded at
   the OB's own confirmation bar `i`), a candle body move
   `|close-open| >= 1.5 * ATR_200[ob_idx]` occurs in the OB's direction.
2. **LargeBar:** the OB's own bar has `high-low >= ATR_200[ob_idx]`.
3. **FVG (Fair Value Gap):** a 3-candle imbalance exists within
   `ob_idx` to `min(i-1, ob_idx+2)` such that, for some `j` in that range,
   `low[j+2] > high[j]` (DEMAND) or `high[j+2] < low[j]` (SUPPLY), with
   `j+2 <= i` enforced.
4. **LiquiditySweep:** the OB bar's low is `<=` the minimum low of the prior
   10 bars (DEMAND), or its high is `>=` the maximum high of the prior 10
   bars (SUPPLY).
5. **VolumeExpansion:** the OB bar's volume is `>= 1.25x` the prior 20-bar
   average volume, OR the OB bar's body is `> 60%` of its own high-low range.

### 4.1 Disclosed correction history (three bugs)

**Bug #1 — non-orthogonal composite score.** The original 0-5 composite
score was built so that higher-scored OB sets were nested subsets of
lower-scored sets, confounding any claim that "quality" independently
predicted outcome. Corrected by evaluating and reporting each of the 5
criteria independently rather than only via the composite ordinal score
(`CLAUDE.md`, Known bug #1). The `quality` field itself is still computed and
still used as the cumulative entry-filter threshold (verified by reading
`simulate_trades()`, line 679: `ob.get('quality', 0) >= local_min_quality`)
— what changed is how the criteria are used in *analysis*, not that
filtering by quality stopped.

**Bug #2 — FVG two-candle vs. three-candle definition.** The FVG test
originally compared adjacent candles (`lows[j+1] > highs[j]`) instead of the
correct 3-candle imbalance definition (`lows[j+2] > highs[j]`). Corrected;
the current source (`compute_smc()`, lines 341-346 and 466-471) implements
the 3-candle test exclusively. No separate, independently reproducible
before/after magnitude for this specific correction (in isolation from Bug
#3) exists in this repository's committed evidence; only the combined
current-state FVG count is verifiable.

**Bug #3 — lookahead across the OB confirmation boundary.** The FVG and
displacement forward-search loops were originally bounded by dataset length
`n` rather than by the OB's own confirmation bar `i`, so they could read 1-2
bars of data that would not have been available at the moment the OB became
usable for entry. Found via a dedicated no-lookahead audit; fixed by
bounding both search loops at `i` (displacement:
`range(ob_idx+1, min(i+1, ob_idx+4))`; FVG:
`range(ob_idx, min(i-1, ob_idx+3))`), with hard runtime `assert` statements
left in place at the read sites (`compute_smc()`, e.g. lines 296-301,
335-340, 421-426, 460-465) that raise `AssertionError` if a future violation
ever reads past `i`. Fixed in commit `cb4ed93` ("fix: correct
FVG/displacement OB scoring lookahead; remove ML pipeline").

Live-verified impact of Bug #3, this session:

- Assertion-based causality check on ATR(14)/ATR_200/static KDJ(9,3,3)
  (`scratch/no_lookahead_atr_kdj_check.py`, truncation-equality method):
  **PASS, 36 sampled bars x 5 columns = 180/180 checks exact**.
- Scope audit on the current (fixed) `compute_smc()` output
  (`scratch/no_lookahead_fvg_scope_audit.py`, run under `python -O` per its
  own docstring): **0/253 FVG-true OBs and 0/107 displacement-true OBs now
  read past their own confirmation bar**; 0 of the 27 baseline trades are
  affected.
- Current live population counts (`full q0-q5 sweep script`, this session,
  against `artifacts/candles.csv` and current `src/Binance backtest
  bot.py`): **761 total detected Order Blocks; FVG-true 253/761 (33.2%);
  displacement-true 107/761 (14.1%)**. These reproduce the post-fix figures
  in `CLAUDE.md` exactly.
- OB quality-score distribution (live, exact/non-cumulative, sums to 761):
  `q0=93, q1=154, q2=206, q3=197, q4=90, q5=21`. Matches `CLAUDE.md` exactly.

**Note on the commit hash `CLAUDE.md` cites for Bug #3.** `CLAUDE.md`'s text
labels the post-fix figures "as of commit `7ad6caa`." That commit's own
diff (`git show 7ad6caa:CLAUDE.md`) contains only Bugs #1-#2 and the
**pre-fix** FVG figure (362, 47.6%) — Bug #3 and its post-fix numbers do not
appear until the later commit `cb4ed93`, whose commit message explicitly
states "`CLAUDE.md`'s locked-results block is updated accordingly." The
correct commit hash for the Bug #3 fix and its post-fix figures is
**`cb4ed93`**, not `7ad6caa`. See "Discrepancies found" below.

---

## 5. Statistical methods

**One-sided exact binomial test of win rate**, `scipy.stats.binomtest(wins,
n, 0.5, alternative='greater')`, applied to the trade-level binary win/loss
outcome (`pnl_pct > 0`) at each quality threshold. One-sided because the
pre-registered hypothesis is directional — that the strategy's win rate
exceeds the 50% zero-edge null, not merely that it differs from 50% in either
direction. Two-sided values are also reported alongside for reference.

**Fisher's exact test**, applied to a 2x2 win/loss-by-criterion-truth
contingency table for each of the 5 orthogonal OB quality criteria,
independently, over the 27 `min_ob_quality=0` baseline trades. Tests whether
win/loss outcome is independent of a criterion being True vs. False for that
trade's entry OB. Units: binary trade outcome.

**Welch's (unequal-variance) t-test**, `scipy.stats.ttest_ind(..., equal_var=
False)`, applied to per-trade percentage return (`pnl_pct`) between the
True and False subgroups of each of the 5 criteria, over the same 27-trade
set. Welch's (not Student's) form is used because subgroup sizes and
variances are unequal and small (subgroup n ranges from 4 to 23). Units:
per-trade percentage return.

**Ablation-arm tests** (Fisher's exact and Welch's t-test comparing the
OB-gated strategy against an indicators-only ablation) are described in
`docs/ablation_study_indicators_only.md` but could not be independently
reproduced this session — see §8.

---

## 6. Results

### 6.1 Locked q>=0 baseline (live-verified this session)

| Metric | Value | Source |
|---|---|---|
| Total trades | 27 | `scratch/regression.py`; live sweep script |
| Wins / Losses | 19 / 8 | live sweep script, commit `775d463` working tree |
| Win rate | 70.37% | ″ |
| Total net return | +30.31% (+30.3065% unrounded) | ″ |
| Avg return/trade | +1.1225% | ″ |
| SD (return/trade) | 2.4101% | ″ |
| One-sided binomial p (vs. 0.5) | 0.0261 | ″ |
| Two-sided binomial p | 0.0522 | ″ |

All values reproduce `CLAUDE.md`'s locked baseline exactly.

### 6.2 Full threshold sweep, q>=0 through q>=5 (live-verified this session)

Computed by running `simulate_trades(df, min_ob_quality=q)` for `q` in
`0..5` against `artifacts/candles.csv` and the current
`src/Binance backtest bot.py`, with the exact one-sided/two-sided binomial
test recomputed per threshold in the same run:

| Threshold | N | Wins | Losses | Win rate | Total net return | Avg/trade | SD | p (one-sided) | p (two-sided) |
|---|---|---|---|---|---|---|---|---|---|
| q>=0 | 27 | 19 | 8 | 70.37% | +30.31% | +1.1225% | 2.4101% | 0.0261 | 0.0522 |
| q>=1 | 25 | 17 | 8 | 68.00% | +28.31% | +1.1323% | 2.5074% | 0.0539 | 0.1078 |
| q>=2 | 23 | 15 | 8 | 65.22% | +23.28% | +1.0120% | 2.5598% | 0.1050 | 0.2100 |
| q>=3 | 14 | 8 | 6 | 57.14% | +6.59% | +0.4709% | 2.7578% | 0.3953 | 0.7905 |
| q>=4 | 6 | 3 | 3 | 50.00% | +6.71% | +1.1177% | 3.8482% | 0.6562 | 1.0000 |
| q>=5 | 1 | 0 | 1 | 0.00% | -0.38% | -0.3809% | n/a (n=1) | 1.0000 | 1.0000 |

q>=0 through q>=3 exactly match `backtest_results.db` /
`scratch/calculate_paper_metrics.py`'s output (levels 0-3 are the only
levels present in the committed database and `artifacts/manifest.json`; q>=4
and q>=5 have no committed DB/artifact rows and were computed live this
session only, using the identical fixed-parameter `simulate_trades()` call).

**Pre-fix vs. post-fix q>=1 (historical; not independently reproducible
from current code, which no longer contains the bug):** p (one-sided)
0.038 (n=26) -> 0.054 (n=25), a significance-conclusion flip at alpha=0.05,
driven by trade `entry_idx=3100` losing its only quality point (FVG) under
the corrected computation. Cited to `CLAUDE.md` and commit `cb4ed93`'s
commit message, not re-derived here (reproducing it would require reverting
the fix, which is out of scope and against project rules).

### 6.3 Orthogonal-criteria hypothesis tests (live-verified this session)

Fisher's exact (win/loss) and Welch's t-test (PnL%), True vs. False, per
criterion, over the 27 `min_ob_quality=0` baseline trades:

| Criterion | True n (wins) | False n (wins) | Fisher p | Welch t | Welch p |
|---|---|---|---|---|---|
| Displacement | 4 (2) | 23 (17) | 0.5583 | -0.9277 | 0.3775 |
| LargeBar | 20 (14) | 7 (5) | 1.0000 | +0.2895 | 0.7751 |
| FVG | 11 (8) | 16 (11) | 1.0000 | +0.5360 | 0.5996 |
| LiqSweep | 15 (10) | 12 (9) | 0.6957 | -0.8195 | 0.4204 |
| VolExpansion | 15 (9) | 12 (10) | 0.2357 | -0.8835 | 0.3864 |

No criterion crosses p=0.05 in either test, before or after the Bug #3 fix.
This independently reproduces the post-fix values disclosed in `README.md`'s
2026-08-01 dated log entry ("Locked results re-verification..."), including
the exact match on FVG (Fisher p 1.0000, Welch t +0.5360, p 0.5996) — the
only criterion the fix moved. Consequently, the Welch p-value range across
all 5 criteria is **0.3775-0.7751** (max is LargeBar), confirming the
pending correction noted in `CLAUDE.md` Known bug #3 (paper narrative should
read "0.38-0.78" post-fix, not "0.38-0.90").

### 6.4 Ablation studies — cited, not independently verified

`CLAUDE.md`'s locked results list:

- Ablation A (indicators-only, entry-ATR stop): 140 trades, 60.00% win rate,
  -14.63% total net return.
- Ablation B (indicators-only, swing-pivot stop): 138 trades, 55.07% win
  rate, -25.50% total net return.

**These figures could not be independently verified this session.** No
committed script in this repository reproduces them; `scratch/
02_benchmark_and_risk.py`'s own docstring states the original script that
produced these trade-level numbers was never committed, and a best-effort
reconstruction against current production entry/exit code "diverges on win
rate by >10 points and on SD by ~0.3-0.5pp, meaning the underlying per-trade
outcomes are NOT the same trades the paper reports." Cited here to
`CLAUDE.md` and `docs/ablation_study_indicators_only.md` /
`docs/ablation_unconfounding_analysis.md` as committed disclosures, not as
independently reproduced facts.

---

## 7. Limitations and disclosures

**Resolved, with live or committed evidence found this session:**

- **Dashboard independence scope.** The JS dashboard (`gui.js`) does not
  independently detect Order Blocks, FVG, or displacement; those fields are
  read as trusted data from the Python-generated
  `artifacts/runs_by_threshold.json`. What `gui.js` *does* independently
  recompute is the entry-condition/indicator layer (MACD/KDJ/ATR checklist
  and its own from-scratch reimplementation of the post-entry adaptive-KDJ
  recursion). Net effect: the JS cross-check neither caught nor could have
  caught the Bug #3 lookahead defect, because OB/SMC detection was never
  part of what "independent" covers in this dashboard. (`README.md`,
  2026-08-01 log entry, "Dashboard independence check.")
- **No-lookahead enforcement.** ATR(14)/ATR_200/static KDJ(9,3,3) are
  proven causal via truncation-equality testing (180/180 checks pass, this
  session). FVG/displacement are proven free of the Bug #3 defect via the
  same live scope audit (0/253, 0/107 violations, this session). OB pivot
  windows are provably bounded by array slicing (right-side-only comparison,
  read directly from `compute_smc()` source).
- **Small-sample caveats.** q>=1 (n=25) and q>=2 (n=23) are thin samples;
  q>=4 (n=6) and q>=5 (n=1) are too small to test meaningfully (reported
  descriptively only in §6.2, consistent with `README.md`'s 2026-08-01 log
  entry).
- **Nested (non-independent) threshold groups.** Because q>=1 subset q>=0,
  q>=2 subset q>=1, etc. are all drawn from the same 27-trade pool via a
  cumulative `>=` filter (verified directly in `simulate_trades()`, line
  679), the q>=0..q>=5 rows in §6.2 are not independent samples of each
  other. Any cross-threshold comparison must account for this structural
  overlap.

**Not yet resolved, excluded from this reference (per `CLAUDE.md`'s "Open
question" and this session's own findings — do not cite as settled):**

- The paper's "190 total qualifying indicator signals" denominator (for the
  25/27 = 92.6% OB/indicator-signal coincidence claim) was derived under the
  indicators-only ablation's own 1.5x ATR entry-anchored stop, not the
  OB-gated strategy's risk rules. The two populations are filtered
  differently. Unresolved per `CLAUDE.md`.
- Ablation A/B (140-trade, 138-trade) reproducibility gap: see §6.4. The
  originating script was never committed; a reconstruction attempt diverges
  materially from the published per-trade outcomes. This is a distinct,
  additional gap from the 190-signal question above, found via this
  session's reading of `scratch/02_benchmark_and_risk.py`'s docstring — it
  is not itself listed in `CLAUDE.md`'s "Open question" section, so it is
  flagged here separately rather than folded into that item.

---

## 8. Reproducibility

| Script / doc | Produces | Verified live this session? |
|---|---|---|
| `scratch/regression.py` | Golden-master check: bars, indicators, and the 27-trade q>=0 baseline, byte-identical to `scratch/fixtures/` | Yes — PASS |
| `scratch/calculate_paper_metrics.py` | q0-q3 threshold-sweep stats, read from `backtest_results.db` | Yes — matches §6.2 exactly |
| `scratch/no_lookahead_atr_kdj_check.py` | Truncation-equality causality proof for ATR(14)/ATR_200/static KDJ(9,3,3) | Yes — 180/180 checks pass |
| `scratch/no_lookahead_fvg_scope_audit.py` | Quantifies FVG/displacement lookahead scope (must run under `python -O`) | Yes — 0 violations on current code |
| `scratch/calculate_all_qualities.py` | Per-quality-level performance sweep | Not used for this reference — passes an `iteration_parameters` dict that is dead code for every strategy-formula value in `simulate_trades()` (only a `min_ob_quality` override key is read, and that path is unused since `min_ob_quality` is passed positionally); its printed figures are numerically identical to the fixed-parameter path but the script's own framing ("SWEPT PARAMETERS") is misleading given this |
| `scratch/inspect_raw_signals.py` | Raw pre-risk-filter indicator signal count | Not used for the disputed "190" figure — script's own comment states it is not directly comparable without the ablation's risk filter applied |
| `scratch/02_benchmark_and_risk.py` | Benchmark/risk metrics vs. buy-and-hold; does **not** include ablation arms, and its docstring is the source of the Ablation A/B non-reproducibility disclosure in §6.4/§7 | Docstring read, not executed for this reference (out of scope: buy-and-hold benchmarking, not part of the requested sections) |
| `docs/ablation_study_indicators_only.md`, `docs/ablation_unconfounding_analysis.md` | Ablation A/B trade-level figures (140/138 trades) | No — cited as committed disclosure only, per `CLAUDE.md` and §6.4 |
| `docs/orthogonal_criteria_reference.md`, `docs/research_statistics_reference.md` | Pre-fix per-criterion and threshold-sweep tables | **Stale — do not cite.** See "Discrepancies found" below |
| `README.md` (2026-08-01 dated log entries) | Committed narrative disclosure of the full post-Bug-#3 re-verification cascade, including the Fisher/Welch per-criterion re-test | Cross-checked — this session's independent live re-derivation (§6.3) matches it exactly |
| This session's ad hoc sweep/audit script | Full q0-q5 sweep with binomial tests; population/quality-distribution counts; per-criterion Fisher/Welch re-test; `w`-range check | Yes — all reproduced in this session, not previously committed as a named script |

**Relevant commit hashes:**

- `7ad6caa` — `CLAUDE.md` added; contains Bugs #1-#2 disclosures and the
  **pre-fix** FVG figure only.
- `cb4ed93` — the actual Bug #3 fix ("fix: correct FVG/displacement OB
  scoring lookahead; remove ML pipeline"); updates `CLAUDE.md`'s locked
  results to post-fix figures. This is the correct citation for all
  post-fix numbers in this document, notwithstanding `CLAUDE.md`'s own
  internal "as of commit 7ad6caa" label (see §4.1 and "Discrepancies
  found").
- `8ef4076` — tracks the audit-evidence scratch scripts behind Known bug #3
  into git (`scratch/` is otherwise gitignored).
- `76f0efb` — removes confirmed-dead files from the removed ML pipeline.
- `7713638` — moves the core strategy file to `src/`, adds
  `CODEBASE_MAP.md`.
- `775d463` — current `development` HEAD at the time of this session
  ("add: readme documentation for rigor").

---

## Discrepancies found (this session)

1. **`CLAUDE.md`'s commit-hash label for Bug #3 is wrong.** The text says
   post-fix figures are "as of commit `7ad6caa`," but `7ad6caa` predates the
   actual fix and, per its own diff, still contains the pre-fix FVG figure
   (362, 47.6%) and no Bug #3 entry at all. The correct commit is `cb4ed93`.
   This does not change any locked number — the numbers in `CLAUDE.md` are
   themselves correct and match this session's live reproduction exactly —
   only the commit-hash citation is mislabeled.

2. **`docs/orthogonal_criteria_reference.md` and
   `docs/research_statistics_reference.md` contain stale, pre-fix (or
   otherwise inconsistent) figures** that do not match this session's live
   results:
   - `docs/orthogonal_criteria_reference.md`'s Welch's t-test table shows
     FVG `t=+0.1326, p=0.8956` — this is the documented **pre-fix** value
     (`CLAUDE.md`'s own Known bug #3 entry already flags this exact number
     as pending correction to `t=+0.5360, p=0.5996`, which this session's
     live re-derivation confirms in §6.3).
   - `docs/research_statistics_reference.md`'s threshold-sweep table
     reports Q1 N=24, Q2 N=21, Q3 N=10. **None of these three figures match
     either the pre-fix or the post-fix values disclosed anywhere else in
     this repository** (pre-fix q>=1 was 26 per `CLAUDE.md`; post-fix is 25;
     this session's live q>=2/q>=3 are 23/14, and `README.md`'s log states
     pre-fix q>=2 was 24). The Q1=24 figure does not match live q>=1 (25),
     live q>=2 (23), or the disclosed pre-fix q>=2 (24) under its own
     labeled threshold — it appears to be a mislabeled/shifted row, similar
     in kind to the already-disclosed "Finding 1: Threshold 1 Exit Reason
     Table Typo" elsewhere in the same document, but for trade counts rather
     than exit-reason stats, and not previously flagged. **Do not cite
     either document's headline sweep table for the manuscript; use §6.2 of
     this reference instead**, which was computed live this session against
     the current codebase and cross-checked against `backtest_results.db`.

3. No discrepancy was found between this session's live results and any
   number in `CLAUDE.md`'s "Locked results" block, "Known bugs" section, or
   "KDJ architecture" section — every one of those was independently
   reproduced exactly (see §6.1, §6.2's q>=0/q>=1 rows, §4.1, §3.3's `w`
   range).
