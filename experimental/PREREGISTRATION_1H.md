# Pre-registration: the locked rules on 1-hour candles

Branch: `experimental`. Status: EXPLORATORY. It is not part of the paper
unless the author decides otherwise after reading the results.

This file was committed **before** any backtest was run on 1h data. Nothing
below may change afterwards. Any deviation gets disclosed in the results,
with the reason.

## 0. What has been looked at so far (and nothing else)

- **The pull itself** (`experimental/pull_1h_candles.py`, run once on
  2026-10-26 with the author's approval): BTCUSDT 1h, 77,164 closed bars
  from 2018-01-01 00:00 UTC to 2026-10-26 05:00 UTC. The CSV's sha256
  begins `ec24028427a9029a`; the full value is in
  `data/btcusdt_1h_manifest.json`. There are 27 gaps totalling 122 missing
  hours. All but one are in 2018–2021; the other is 2023-03-24. Gaps are
  left as delivered, not filled, the same as the 4h data.
- **Cross-check against the paper's 4h data:** after correcting for the
  4h files' documented UTC+8 labels, 18,826 of 18,828 4h bars rebuilt from
  1h match `artifacts/candles_extended.json` exactly. The two that don't:
  - 2023-03-24 12:00 UTC: the 1h feed is missing an hour there.
  - 2026-08-07 12:00 UTC: the 4h file's last bar. It was still open when
    that file was pulled at 13:21 UTC, so it is a partial candle. No 4h
    lockbox trade exited on it.
- **Counts and date ranges only.** No 1h prices, indicators, Order Blocks
  or trades have been computed or looked at, and nothing at all from the
  holdout.

## 1. Question

Running the same rule set on 1h candles gives up to 4× as many bars. Does
it produce more trades while keeping a positive edge per trade after fees?

## 2. Windows (true UTC, by bar open time)

| Window | 1h bars | Role |
|---|---|---|
| 2018-01-01 → 2021-12-31 | 34,943 | warm-up + descriptive. The rules were formulated on this period (at 4h), so it is not out-of-sample for them |
| **2022-01-01 → 2025-12-31** | **35,063** | **main test** (same calendar window as the paper) |
| 2026-01-01 → 2026-08-07 | 5,256 | descriptive only. Already seen once at 4h (the spent lockbox) |
| **2026-08-08 → 2026-10-26 05:00** | **1,902** | **one-shot holdout**, never loaded before |

Indicators and Order Blocks are computed once on the continuous series
from 2018-01-01. Each trade is assigned to the window its entry bar falls
in. The `main` phase loads only bars before 2026-08-08 and raises
otherwise. Only the `holdout` phase loads the rest.

## 3. Arms

No other variants will be run. In particular there is no sweep of the
scale factor and no per-constant tuning.

### Primary: LITERAL

`research_analysis.py`'s engine unchanged: `compute_indicators()`,
`compute_smc()`, `simulate_trades(min_ob_quality=0)`. Every constant
stays as written, so bar counts mean hours instead of 4-hour blocks.

### Secondary: TIME-SCALED (×4)

Every bar-count **window/lookback** is multiplied by 4 (= 4h / 1h), so it
spans the same clock time as on 4h. Nothing else changes.

| Scaled | 4h value → 1h value |
|---|---|
| MACD spans | 12 / 26 / 9 → 48 / 104 / 36 |
| KDJ RSV window | 9 → 36 |
| ATR | 14 → 56 |
| ATR baseline (the `ATR_200` column) | 200 → 800 |
| Internal / swing pivot lookbacks | 5 / 50 → 20 / 200 |
| Order Block max age | 500 → 2,000 |

**Kept literal**, because these are pattern shapes or price/ratio
thresholds, not windows:
- KDJ smoothing α = 1/3, in both the static KDJ and the per-trade exit KDJ;
- MACD "rising/falling for ≥ 2 bars";
- the K-acceleration 3-bar second difference and its [1, 6] window;
- the ATR-regime dead zone [0.8, 1.0];
- KDJ-reset exit allowed only from bar 3 onward;
- the ATR-multiple exits (1.8 / 2.0 × ATR); the ATR itself is scaled;
- trailing exit (1.5% peak, 50% retrace);
- SL = 0.5 × ATR beyond the OB, minimum SL 1.5%, minimum R:R 1.5;
- the OB quality criteria's internal windows and multipliers (3-bar
  displacement, FVG pattern, 10-bar sweep, 20-bar volume, 1.5 × /
  1.25 × / 0.6 thresholds) and the 2 × ATR-baseline high-volatility bar
  rule.

Disclosed limitation: these literal pieces mean the scaled arm is only
partly "the same strategy in clock time". For example, K acceleration
measured per 1h bar is a different quantity from per 4h bar.

**Implementation, without editing `research_analysis.py`:** a separately
loaded copy of the engine module has its three module constants
(`INTERNAL_STRUCTURE_LOOKBACK_BARS`, `SWING_STRUCTURE_LOOKBACK_BARS`,
`MAX_ORDER_BLOCK_AGE_BARS`) set ×4. The indicator columns come from
`experimental/` code that reproduces `compute_indicators()` with a scale
factor and writes the same column names. `simulate_trades()` then runs
unchanged, because it skips `compute_indicators()` when the columns are
already present.

## 4. Gates (all must pass before any result is read)

- **G1:** the CSV hash matches the manifest.
- **G2:** the scaled indicator code with factor 1 reproduces
  `compute_indicators()` exactly (every column, bit for bit) on
  `artifacts/candles.csv`.
- **G3:** the meta-labeling candidate builder plus rule policy
  (`ml_meta_labeling.py`) reproduces `simulate_trades()` trade for trade
  on the 1h 2022–2025 run (literal arm). This is the same parity method as
  the 4h study, and it is needed for the random-filter baseline below.
- **G4:** truncation invariance on the 1h series, at 3 random cuts in
  2018–2021.
- **G5:** `scratch/regression.py` passes, and `research_analysis.py` has
  no diff vs `development`.

Any gate failure means: stop and report, no workaround.

## 5. Primary endpoint (the only confirmatory test)

**LITERAL arm, 2022–2025: mean pnl per trade net of 0.20% round-trip
(`BENCHMARK_ROUND_TRIP_DRAG_PCT`) > 0.**
- Test: stationary block bootstrap of the net per-trade sequence in entry
  order, B = 10,000, expected block length max(1, round(n^(1/3))),
  seed 20260808.
- One-sided p = share of resample means ≤ 0. α = 0.05.
- If the arm takes fewer than 10 trades, p is still computed and reported,
  flagged as underpowered.

## 6. Secondary and descriptive (no confirmatory claims)

- **S1. Scaled arm:** the same statistic as the primary, reported as a
  descriptive one-sided p.
- **S2. Versus the paper's 4h result** (27 trades, +1.12% gross): the
  difference in net mean per trade (independent bootstrap, B = 2,000), and
  trades per year.
- **S3. Do the gates add value on 1h?** A random filter over the 1h
  geometry-valid OB-touch candidates, at the literal arm's candidate
  take-rate, 1,000 seeds, run with the same sequential policy. Reports the
  share of seeds at or above the literal arm's mean.
- **S4. Stability:** 50 random 12-month windows inside 2022–2025. Reports
  the share with net total > 0 and the share beating buy & hold, for both
  arms.
- **S5. Fees:** net totals at 0.10%, 0.20% and 0.30% round trip.
- **S6. Passive benchmarks:** buy & hold and weekly DCA over the same
  window, using the paper's helpers.
- **S7. Other windows:** 2018–2021 and Jan–Aug 2026, each with the
  label from section 2.

Common to every arm and window: trade count, win rate, mean / total pnl
gross and net, Sharpe and max drawdown via `_run_strategy_dollar_arm`
on 1h bars (annualised with 24 × 365.25 periods per year), and hold
time in hours.

## 7. Holdout (2026-08-08 → 2026-10-26 05:00 UTC)

`--phase holdout --i-understand-this-is-one-shot` runs only after the main
results are committed. It writes a marker file first and refuses to run
twice. Both arms are reported (n, mean / total gross and net, win rate),
along with buy & hold. With about 11 weeks of data, a handful of trades is
expected, so it is reported as a check and not as a test.

## 8. Reporting

`RESULTS_1H.md` is generated from `results_1h/*.json`. Null and
unfavorable results are reported as they come. The paper, its artifacts
and `research_analysis.py` stay untouched.
