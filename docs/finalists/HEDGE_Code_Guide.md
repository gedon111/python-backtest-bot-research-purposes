# HEDGE — Code Guide

**A line-0-to-line-4847 walkthrough of `research_analysis.py`, with a
hand-computable verification for every module.**

Companion to `docs/finalists/HEDGE_Research_Paper.md`. Read this with the
source file open beside it; the guide moves strictly top-to-bottom through
the file, so the two scroll together.

- **Subject:** `research_analysis.py` (repo root), 4,847 lines, the single
  canonical entrypoint for the whole project.
- **Results source of truth:** `docs/SCRATCH_RESULTS_METHODS.md`. Every
  headline number quoted in this guide is traceable there.
- **Paper↔code bridge:** `docs/finalists/HEDGE_Paper_Code_Handoff.md`.

---

# Part 0 — How to read this guide

## 0.1 The four beats

Each module that carries a scientific claim gets the same four beats, in
the same order, every time:

| Beat | What it gives you |
|---|---|
| **WHAT THE PAPER CLAIMS HERE** | The sentence in the manuscript this code is responsible for. |
| **WHAT THE CODE DOES** | Plain English first, then the code itself. |
| **HAND CHECK** | A 4-to-12-value input, the arithmetic written out with intermediates, and the answer. Doable on a calculator. |
| **CONFIRM AGAINST THE CODE** | A short REPL block that runs the *real* function on the *same* input, so you can see the hand answer come back out of the actual engine. |

Plumbing modules — database schema, HTTP routes, Google Sheets formatting —
get a shorter treatment: what it does, and *why it cannot move a published
number.* Every line of the file is still accounted for.

## 0.2 The loader — paste this first, once per session

Every `CONFIRM AGAINST THE CODE` block in this guide assumes these lines
have already been run, from the repository root, in a Python REPL:

```python
import importlib.util, pandas as pd, numpy as np
spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec); spec.loader.exec_module(bot)
```

`bot` is now the live module. `bot.compute_indicators`, `bot.compute_smc`,
`bot.binomial_test` and everything else are the real functions the paper's
numbers came from — not copies, not re-implementations. **No verification in
this guide adds a new `.py` file to the repository.** That is deliberate: a
check that runs a separate script proves the script works, not that the
engine works.

Importing this way, rather than with a plain `import`, is the same
mechanism `scratch/regression.py` uses.

**One presentation convention.** Where a snippet prints a dict of results,
this guide shows the values with NumPy's scalar wrappers elided —
`0.1875` rather than `np.float64(0.1875)` — and long dicts are wrapped
across lines. The digits are verbatim; only the `np.float64(...)` noise and
the line breaks are cosmetic. Where a block is more heavily reformatted, the
caption says so.

## 0.3 The line map

| Section | Lines | Weight | What lives there |
|---|---|---|---|
| Module docstring | 1–87 | — | What the file is, what it is not, the section map |
| 1 — Imports, constants, utilities | 89–281 | **Full** | Every pre-registered parameter; the locked baseline figures |
| 1B — Database manager | 282–460 | Light | 4 SQLAlchemy tables + session lifecycle |
| 2 — Data loading | 461–519 | Light + check | `load_candles`, the (dead) extended-window loader |
| 3 — Strategy / backtest engine | 520–1637 | **Full** | **The protected core.** Indicators, SMC, KDJ state machine, entry gates, exit ladder, driver loop |
| 3B — Live pull + Google Sheets | 1638–2076 | Light | `get_candles`, sheet writers, cell formatting |
| 4 — Ablation study | 2077–2502 | **Full** | The three-arm design and its disclosed non-reproduction |
| 5 — Statistical primitives | 2503–2721 | **Full** | 7 functions: binomial, bootstrap, Pearson, Spearman, max drawdown, Sharpe/Sortino |
| 5B — Applied analyses | 2722–3841 | **Full** | Bootstrap CI, buy-and-hold, DCA blend, fee/slippage, regimes, OOS, the three dollar arms |
| 6 — Artifact export + DB persistence | 3842–4293 | Light + check | The JSON/CSV files the dashboard reads; the SHA-256 manifest |
| 7 — HTTP server | 4294–4563 | Light | The routes `dashboard-v2` talks to |
| 8 — CLI / main | 4564–4847 | Light | `--serve`, `--levels`, `--export-gsheet`, `--include-oos-live` |

## 0.4 What "protected core" means

Lines **129–170** (the constants) and **538–1637** (Section 3) are the only
lines in this file that can change a published number — about 1,180 lines,
24% of the file. Everything else is plumbing that moves data around after
the science is finished.

Those lines are frozen three ways:

1. **Pre-registration.** Every threshold in L129–170 was fixed before the
   evaluation window was scored, and was never swept or optimized.
2. **A golden-master regression harness.** `scratch/regression.py` holds a
   snapshot of all 8,767 bars of indicator output and all 27 trades. A fresh
   run is compared bar-by-bar (tolerance 1e-6) and trade-by-trade (matched
   on `entry_idx`, tolerance 1e-5). Any diff at all is treated as a defect
   in the change, not an improvement.
3. **Runtime no-lookahead assertions.** Every forward-searching loop in
   `compute_smc()` and `_build_order_block_from_crossover()` carries an
   inline `assert` bounding it at the Order Block's own confirmation bar, so
   a regression fails on the next run rather than waiting for an audit.

**If a panelist asks "how do you know you didn't change anything?"** — run
`python scratch/regression.py`. It prints, and must print:

```
PASS: Fresh run matches golden-master fixture EXACTLY across all bars,
indicators, and 27 trades!
```

Never run it with `--generate`. That rewrites the fixtures, which is the one
thing that would make the harness unable to catch anything.

## 0.5 How to do a hand check honestly

Every hand check in this guide was built the same way, and you can rebuild
any of them the same way:

1. Choose an input small enough to do on paper — 4 to 12 bars, round
   numbers. **Never a slice of real BTC data**, because a slice you cannot
   compute by hand proves nothing.
2. Do the arithmetic yourself, writing down the intermediates.
3. *Then* run the real function on the identical input.
4. If they disagree, that is a finding. Do not adjust the hand arithmetic
   until it matches — work out which one is wrong.

Every number printed in this guide's HAND CHECK and CONFIRM blocks was
produced by step 3 on the real function before it was written down. None
were estimated.

Where a computation is genuinely not hand-reproducible — a 10,000-resample
bootstrap, a 761-Order-Block scan over 8,767 bars — the guide says so and
gives a scaled-down version that *is*, plus the one command that reproduces
the full figure.

---

# Part 1 — Imports, constants, shared utilities (L89–281)

## 1.1 The module docstring (L1–87)

Read it. It is the file's own statement of scope, and it makes three
promises a panelist can hold you to:

- **`python research_analysis.py`** runs the offline stats pipeline;
  **`--serve`** exports artifacts + database rows and starts the dashboard
  on port 8765.
- The protected core is a *consolidation*, not a rewrite:
  `compute_indicators()`, `compute_smc()`, `simulate_trades()`, and the
  `kdj_reset_*` state machine are reproduced from the pre-consolidation
  sources with formulas, thresholds and control flow unchanged. Only names,
  comments, grouping and file location moved.
- **Offline by default.** A bare `python research_analysis.py` never touches
  the network. The one live pull, `run_forward_oos_validation()`, is gated
  behind `--include-oos-live`.

The one genuinely new piece of analysis in the whole file is
`spearman_correlation()` (L2630) — nothing in the repository computed
Spearman's rho before. It is a short `scipy.stats.spearmanr` wrapper. Say
that plainly if asked; disclosing it is a strength, not an admission.

## 1.2 Imports (L89–122)

Standard library for I/O, HTTP and hashing; then `numpy`/`pandas` for the
maths, `scipy.stats` for every statistical test, `sqlalchemy` for the
database, `gspread` + `oauth2client` for the Sheets export, and
`binance.client` for the one optional live pull.

**The point to make in a defense:** every statistical test in this project
is a SciPy call. There is no hand-rolled p-value machinery anywhere in the
file. The functions in Section 5 are named, documented wrappers whose job is
to make the call site readable, not to compute anything SciPy doesn't.

## 1.3 The pre-registered parameters (L129–170) — full depth

These 40 lines are the scientific contract of the project. Everything below
them is a consequence.

```python
# --- SMC Order Block detection parameters (L132-134) ---
SWING_STRUCTURE_LOOKBACK_BARS    = 50    # LuxAlgo "swingsLengthInput"
INTERNAL_STRUCTURE_LOOKBACK_BARS = 5     # LuxAlgo internal-structure pivot lookback
MAX_ORDER_BLOCK_AGE_BARS         = 500   # discard Order Blocks older than this

# --- Trade simulation parameters (L139-147) ---
DEFAULT_MIN_OB_QUALITY        = 1
MIN_STOP_LOSS_DISTANCE_RATIO  = 0.015   # SL must be >= 1.5% away from entry
KDJ_J_LONG_CAP                = 60.0
KDJ_K_LONG_CAP                = 50.0
KDJ_K_SHORT_FLOOR             = 70.0
KDJ_J_SHORT_CAP               = 100.0
ATR_MULT_EXIT                 = 1.8     # ATR-multiple forced-exit distance
ATR_MULT_BREAKEVEN            = 2.0     # ATR-multiple breakeven-stop ratchet
MIN_RISK_REWARD_RATIO         = 1.5
```

**Where each value comes from — the answer to "did you tune these?"**

| Constant | Value | Provenance |
|---|---|---|
| `SWING_STRUCTURE_LOOKBACK_BARS` | 50 | LuxAlgo's published TradingView default (`swingsLengthInput`). Not chosen here. |
| `INTERNAL_STRUCTURE_LOOKBACK_BARS` | 5 | LuxAlgo's internal-structure default. Not chosen here. |
| `MAX_ORDER_BLOCK_AGE_BARS` | 500 | Staleness bound. 500 × 4h ≈ 83 days. |
| `MIN_STOP_LOSS_DISTANCE_RATIO` | 0.015 | A stop closer than 1.5% sits inside ordinary 4h noise and is hit before the thesis can play out. |
| `KDJ_K_LONG_CAP` / `KDJ_J_LONG_CAP` | 50 / 60 | Longs only from the oversold half of the oscillator. |
| `KDJ_K_SHORT_FLOOR` / `KDJ_J_SHORT_CAP` | 70 / 100 | Shorts only from genuine overbought (K ≥ 70), but not from already-exhausted extremes (J > 100). |
| `ATR_MULT_EXIT` | 1.8 | Forced exit once the move has run 1.8 × entry ATR in favour. |
| `ATR_MULT_BREAKEVEN` | 2.0 | Stop ratchets to entry once the move has run 2.0 × entry ATR. |
| `MIN_RISK_REWARD_RATIO` | 1.5 | No trade is taken unless the target is at least 1.5× the risk. |
| `DEFAULT_MIN_OB_QUALITY` | 1 | The *default*; **the paper's locked baseline uses 0** — no quality filtering at all. |

**The `DEFAULT_MIN_OB_QUALITY = 1` vs `min_ob_quality=0` distinction is a
likely panel question.** The default exists for the dashboard, which
displays four quality levels (0, 1, 2, 3). The published 27-trade baseline
is the *unfiltered* q≥0 run. That is exactly why the corrected
FVG/displacement lookahead bug (§3.3) does not move the headline figures:
the baseline never consults the quality score.

### The locked figures (L153–165)

```python
LOCKED_BASELINE_TRADE_COUNT      = 27
LOCKED_BASELINE_WIN_RATE_PCT     = 70.37
LOCKED_BASELINE_TOTAL_RETURN_PCT = 30.31
LOCKED_BASELINE_AVG_RETURN_PCT   = 1.12
LOCKED_BASELINE_RETURN_SD_PCT    = 2.41
LOCKED_ABLATION_ARMS = {
    "flat_atr":    {"n": 140, "win_rate_pct": 60.00, "total_return_pct": -14.63},
    "swing_pivot": {"n": 138, "win_rate_pct": 55.07, "total_return_pct": -25.50},
}
```

These are constants *to be checked against*, not values used in any
computation. Every analysis section recomputes its own figure from the data
and then prints an explicit **MATCH** or **DIVERGE** against these. Nothing
is ever silently reconciled. The ablation arms in particular are carried as
*reference* figures — Section 4 discloses that no committed script
reproduces their exact per-trade pools, and a DIVERGE there is expected.

**HAND CHECK — the headline numbers are internally consistent**

- 70.37% of 27 → `0.7037 × 27 = 19.0` wins, and `19 / 27 = 0.703703… = 70.37%` ✓
- `30.31 / 27 = 1.1226…` → `+1.12%` average ✓

If a panelist asks whether the headline numbers came from different runs,
this is the answer: they are three views of one 27-row trade log, and they
cross-multiply.

**CONFIRM AGAINST THE CODE**

```python
df = bot.compute_indicators(bot.load_candles())
t  = bot.simulate_trades(df, min_ob_quality=0).attrs["trades_df"]
print(len(t), (t.pnl_pct > 0).sum(), (t.pnl_pct > 0).mean()*100,
      t.pnl_pct.sum(), t.pnl_pct.mean(), t.pnl_pct.std(ddof=1))
```

Actual output:

```
27 19 70.37037037037037 30.306456356031937 1.1224613465197013 2.4101357189345545
```

## 1.4 `json_safe()` (L171–204) and `write_json_results()` (L207–222)

Serialization only. `json_safe` is passed as `json.dump(..., default=)`, so
it is called *only* for values `json` cannot already handle: numpy scalars
become Python `int`/`float`, numpy arrays become lists, pandas Timestamps
become ISO strings, `NaN` becomes `null`, anything else becomes its `str()`.

**Why this cannot move a number:** it runs after every computation has
finished, and it only ever widens a numpy type to its exact Python
equivalent — `float(np.float64(x)) == x`.

Note the deliberate contrast with `to_native()` at L3867 (Section 6):
`json_safe` *stringifies* what it doesn't recognise (safe as a last-resort
serializer), while `to_native` *passes it through untouched* (correct when
building a dict of records where an unexpected string should stay a string).
Two functions, two different jobs — that duplication is intended.

## 1.5 `report_stat()` (L225–279)

The single shared terminal-reporting utility. Every stats-producing function
in the file calls it, and it always prints **both** the inputs a computation
was called with and everything it produced — never just the headline number.

Formatting convention: floats to 10 decimal places, integers plain, booleans
and strings as-is, `NaN`/`None` printed as `"NaN"` rather than raising.

**Why this matters for a defense:** the terminal transcript of a pipeline
run is itself an audit artifact. Every printed block shows what went into a
test, so a reader can re-run the test by hand from the transcript alone.

---

# Part 1B — Database manager (L282–460)

*Light depth. This section stores results; it never computes one.*

Four SQLAlchemy ORM tables, reproduced verbatim from the retired
`db_manager.py` — no column, index or table added, removed or renamed.

| Table | Class | Line | One row is | Key columns |
|---|---|---|---|---|
| `candles` | `Candle` | 296 | one 4h bar + its indicators | PK `(time, symbol, interval)` |
| `order_blocks` | `OrderBlock` | 330 | one detected Order Block | `ob_id`, `type`, `top`, `bottom`, `created_at`, `ob_bar`, 5 `quality_*` booleans + composite `quality` |
| `ob_touches` | `OBTouch` | 362 | one bar where price touched an OB | FK → `order_blocks.ob_id`, plus the indicator snapshot at that bar |
| `trades` | `Trade` | 388 | one simulated trade | FK → entry OB and (optional) TP OB, plus the `min_ob_quality` used |

Lifecycle helpers: `get_db_url()` (L418 — `DATABASE_URL` env var, else
`sqlite:///backtest_results.db`), `init_db()` (L424), `get_session()`
(L443), `clear_db()` (L449 — deletes children before parents so foreign keys
stay valid).

**Why the database exists at all.** The dashboard's `/api/trades` and
`/api/iterations` routes (Section 7) query it. The JSON files in
`artifacts/` are the *static* export; the database is the *queryable* one.
Both are written from the same `simulate_trades()` output in the same
`--serve` run, so they cannot disagree.

**Why it cannot move a number:** every row is written *after*
`simulate_trades()` returns, and nothing in Sections 3–5 ever reads from it.
Deleting `backtest_results.db` and re-running reproduces it exactly.

---

# Part 2 — Data loading (L461–519)

## 2.1 `load_candles()` (L465–486)

Three lines of body: read `artifacts/candles.csv`, parse `open_time` to
datetime, return. That CSV is the locked dataset every published figure is
computed from.

**HAND CHECK — the 8,767-bar count**

The paper states 8,767 bars over 1,461 days. Both are derivable on paper:

- 2022-01-01 → 2026-01-01 is 4 calendar years = `365 × 4 = 1460` days,
  **plus one leap day (2024-02-29)** = **1,461 days**.
- 4h candles → 6 bars/day → `1461 × 6 = 8,766` bars.
- The window is **boundary-inclusive**: the bar opening at the end timestamp
  is kept → `8,766 + 1 = 8,767` bars.

This matters because an earlier draft reported 8,760, using the plain
`365 × 4 × 6` arithmetic that drops both the leap day and the endpoint bar.
That was corrected; `docs/SCRATCH_RESULTS_METHODS.md` records it.

**CONFIRM AGAINST THE CODE**

```python
df = bot.load_candles()
print(len(df), df["open_time"].iloc[0], df["open_time"].iloc[-1],
      (df["open_time"].iloc[-1] - df["open_time"].iloc[0]).days)
```

Actual output:

```
8767 2022-01-01 08:00:00 2026-01-01 08:00:00 1461
```

(The `08:00` offset is the UTC+8 shift applied at ingestion — see
`get_candles()` at L1719. It shifts every bar identically, so no relative
quantity changes.)

## 2.2 `load_extended_candles_window()` (L489–517) — **dead code**

Loads a date-bounded window out of `artifacts/candles_extended.json`.

**It has zero callers.** The formulation-period window is loaded by
`load_formulation_period_window()` at L3526 instead, which takes a fixed
prefix slice of the same file and asserts its last bar is
`2022-01-01 04:00:00` — one bar before the locked window starts.

Say so if asked. Dead code that is *identified* as dead is a documentation
fact; dead code a panelist finds first is a credibility problem. It is left
in place rather than deleted because deleting it during the paper freeze
would touch the protected file for no scientific gain.

---

# Part 3 — The strategy / backtest engine (L520–1637)

**This is the protected core.** It is the only part of the file that can
change a published number, and it is the part you must be able to explain
line by line. Everything from here to L1637 is reproduced unchanged from
the pre-consolidation sources — formulas, thresholds, and control flow — and
is locked by `scratch/regression.py`.

The section banner at L524–535 explains one abbreviation used relentlessly
below: **`ob` = Order Block**, an SMC price zone where institutional order
flow is inferred to have originated a market-structure shift. It is used as
consistently as `df` is used for DataFrame, because it appears in very dense
per-bar loops.

The eleven functions, in file order:

| § | Function | Lines | Role |
|---|---|---|---|
| 3.1 | `compute_indicators` | 538–612 | MACD, KDJ, ATR(14), ATR(200) |
| 3.2 | `compute_smc` | 615–769 | Pivot → BOS/CHoCH → Order Block scan |
| 3.3 | `_build_order_block_from_crossover` | 770–895 | The 5 quality criteria |
| 3.4 | `get_structural_tp` | 896–926 | Nearest opposing OB as take-profit |
| 3.5 | `kdj_reset_init` / `_update` / `_exit` | 927–1063 | The per-trade exit state machine |
| 3.6 | `_resolve_structural_tp_ob` | 1064–1080 | Which OB produced that TP price |
| 3.7 | `_try_enter_long` / `_try_enter_short` | 1081–1234 | The entry gates |
| 3.8 | `_check_long_exit_conditions` / `_check_short_...` | 1235–1336 | The exit ladder |
| 3.9 | `_record_closed_trade` | 1337–1380 | The 27-field trade record |
| 3.10 | `simulate_trades` | 1381–1637 | The driver loop |

---

## 3.1 `compute_indicators()` — L538–612 · PROTECTED CORE

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Indicators."* Three indicator families are computed causally
— each value uses only past and present candles: MACD(12, 26, 9) for
momentum confirmation, KDJ(9, 3, 3) as a stochastic oscillator with the
extra J line, and two ATR windows (14 and 200) as the volatility measure
that sets stop distance and the regime filter.

### WHAT THE CODE DOES

One pass, three blocks, no loops. Every column is produced by a vectorised
pandas operation over the whole series.

**MACD (L574–579).** Two exponentially weighted moving averages of close,
their difference, and a third EWM of that difference as the signal line:

```python
ema_fast = df["close"].ewm(span=12, adjust=False).mean()
ema_slow = df["close"].ewm(span=26, adjust=False).mean()
df["MACD"]        = ema_fast - ema_slow
df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]
```

`adjust=False` is the important flag: it makes the EWM a *recursive*
filter seeded at the first value, `EMA[t] = EMA[t-1] + k·(x[t] − EMA[t-1])`
with `k = 2/(span+1)`, which is what every charting platform computes and
what you can reproduce by hand. `adjust=True` would use a different
(re-weighted) formula and would not match TradingView.

**KDJ (L581–590).** RSV, then two nested one-third smoothings, then J:

```python
period = int(kdj_period)                                   # 9
rolling_low_min  = df["low"].rolling(period, min_periods=1).min()
rolling_high_max = df["high"].rolling(period, min_periods=1).max()
rsv_denominator  = (rolling_high_max - rolling_low_min).replace(0, np.nan)
raw_stochastic_value = ((df["close"] - rolling_low_min) / rsv_denominator * 100).fillna(50)
kdj_smoothing_alpha = 1.0 / 3.0
df["K"] = raw_stochastic_value.ewm(alpha=kdj_smoothing_alpha, adjust=False).mean()
df["D"] = df["K"].ewm(alpha=kdj_smoothing_alpha, adjust=False).mean()
df["J"] = 3 * df["K"] - 2 * df["D"]
```

Two defensive details worth naming: a flat bar range would divide by zero,
so the denominator's zeros are turned to `NaN` and the resulting `NaN` RSV
is filled with the neutral 50; and `min_periods=1` means the first eight
bars use a shorter window rather than producing `NaN`, so the series is
defined from bar 0 onward.

**ATR (L593–604).** True range as the max of three distances, then a plain
rolling mean at two window lengths:

```python
previous_close = df["close"].shift(1)
true_range = pd.concat([
    df["high"] - df["low"],
    (df["high"] - previous_close).abs(),
    (df["low"]  - previous_close).abs(),
], axis=1).max(axis=1)
df["ATR"]     = true_range.rolling(atr_period, min_periods=1).mean()   # 14
df["ATR_200"] = true_range.rolling(200,        min_periods=1).mean()
```

> **Disclosed discrepancy — know this one before you are asked.** The
> comment above these lines (L593–596) says "Wilder's smoothing (RMA)" and
> describes `ewm(alpha=1/n)`. The executed code is a **plain rolling
> mean**, not Wilder's RMA. The paper discloses this explicitly
> (Methodology, *Average True Range*): "Both ATR windows are computed as a
> simple rolling mean rather than Wilder's original exponential smoothing,
> despite an inherited code comment suggesting otherwise. The executed
> computation is a plain rolling mean, and that is what is reported here."
> The comment is a stale inheritance from an earlier source file. It was
> **not** edited, because editing the protected core during the paper
> freeze for a comment-only fix is not worth touching the regression
> surface. The correct answer to a panelist is: *the code and the paper
> agree; the code comment is wrong and is documented as wrong.*

Finally, L606–610 backfills `num_trades` and `taker_buy_base` if a cached
CSV lacks them, so downstream export code never sees a missing column.

### HAND CHECK A — MACD on six closes

Input (open = high = low = close, so only closes matter):

```
close = [100, 102, 101, 105, 103, 107]
```

Constants: `k12 = 2/(12+1) = 0.15384615`, `k26 = 2/(26+1) = 0.07407407`,
`k9 = 2/(9+1) = 0.2`.

Bar 0 seeds both EMAs at the first close:

```
EMA12[0] = 100,  EMA26[0] = 100  →  MACD[0] = 0  →  signal[0] = 0  →  hist[0] = 0
```

Bar 1:

```
EMA12[1] = 100 + (102 − 100) × 0.15384615 = 100.30769231
EMA26[1] = 100 + (102 − 100) × 0.07407407 = 100.14814815
MACD[1]  = 100.30769231 − 100.14814815    =   0.15954416
signal[1]= 0 + (0.15954416 − 0) × 0.2     =   0.03190883
hist[1]  = 0.15954416 − 0.03190883        =   0.12763533
```

Expected `MACD_hist` for all six bars:
`0, 0.127635, 0.136835, 0.390096, 0.399259, 0.636941`.

### CONFIRM AGAINST THE CODE — A

```python
d = pd.DataFrame({"open":[100,102,101,105,103,107],"high":[100,102,101,105,103,107],
                  "low":[100,102,101,105,103,107],"close":[100,102,101,105,103,107],
                  "volume":[1]*6})
print(bot.compute_indicators(d)[["close","MACD","MACD_signal","MACD_hist"]].round(6).to_string())
```

Actual output:

```
   close      MACD  MACD_signal  MACD_hist
0    100  0.000000     0.000000   0.000000
1    102  0.159544     0.031909   0.127635
2    101  0.202953     0.066118   0.136835
3    105  0.553738     0.163642   0.390096
4    103  0.662715     0.263456   0.399259
5    107  1.059632     0.422692   0.636941
```

Bar 1 matches the hand arithmetic to all six printed digits.

### HAND CHECK B — KDJ on six bars

Input:

```
high  = [110, 112, 111, 115, 113, 117]
low   = [ 90,  92,  91,  95,  93,  97]
close = [100, 102, 101, 105, 103, 107]
```

The KDJ window is 9 bars but `min_periods=1`, so with only 6 bars every
window is "everything so far."

Bar 0: window = bar 0 alone. `RSV = (100 − 90)/(110 − 90) × 100 = 50`.
K and D both seed at 50, so `J = 3(50) − 2(50) = 50`.

Bar 1: window = bars 0–1. Lowest low = 90, highest high = 112.

```
RSV[1] = (102 − 90) / (112 − 90) × 100 = 12/22 × 100 = 54.54545455
K[1]   = 50 + (54.54545455 − 50)/3     = 50 + 1.51515152 = 51.51515152
D[1]   = 50 + (51.51515152 − 50)/3     = 50 + 0.50505051 = 50.50505051
J[1]   = 3(51.51515152) − 2(50.50505051) = 154.54545455 − 101.01010101 = 53.53535354
```

Note the *nesting*: D smooths K, and K has already smoothed RSV. That is why
D lags K, and why J — which amplifies the gap between them by construction —
is the fastest of the three.

### CONFIRM AGAINST THE CODE — B

```python
d2 = pd.DataFrame({"open":[100]*6,"high":[110,112,111,115,113,117],
                   "low":[90,92,91,95,93,97],"close":[100,102,101,105,103,107],
                   "volume":[1]*6})
print(bot.compute_indicators(d2)[["high","low","close","RSV","K","D","J"]].round(6).to_string())
```

Actual output:

```
   high  low  close        RSV          K          D          J
0   110   90    100  50.000000  50.000000  50.000000  50.000000
1   112   92    102  54.545455  51.515152  50.505051  53.535354
2   111   91    101  50.000000  51.010101  50.673401  51.683502
3   115   95    105  60.000000  54.006734  51.784512  58.451178
4   113   93    103  52.000000  53.337823  52.302282  55.408904
5   117   97    107  62.962963  56.546203  53.716922  62.204764
```

### HAND CHECK C — True range and ATR on four bars

Input, with `atr_period=3` so the window is short enough to compute:

```
high  = [105, 108, 104, 110]
low   = [100, 101,  99, 102]
close = [104, 102, 103, 109]
```

True range is the largest of three distances. Bar 0 has no previous close,
so only the first term is defined:

```
TR[0] = 105 − 100 = 5
TR[1] = max(108−101, |108−104|, |101−104|) = max(7, 4, 3) = 7
TR[2] = max(104− 99, |104−102|, | 99−102|) = max(5, 2, 3) = 5
TR[3] = max(110−102, |110−103|, |102−103|) = max(8, 7, 1) = 8
```

ATR(3) is a plain rolling mean with `min_periods=1`:

```
ATR[0] = 5
ATR[1] = (5+7)/2       = 6
ATR[2] = (5+7+5)/3     = 5.666667
ATR[3] = (7+5+8)/3     = 6.666667      # 3-bar window, bar 0 has rolled off
ATR_200[3] = (5+7+5+8)/4 = 6.25        # 200-bar window, nothing rolls off yet
```

The divergence at bar 3 is the whole point of the two windows: ATR(14)
tracks *current* volatility, ATR(200) holds a long-horizon baseline. Their
ratio is the regime filter (`atr_r`, §3.7).

### CONFIRM AGAINST THE CODE — C

```python
d3 = pd.DataFrame({"open":[100]*4,"high":[105,108,104,110],"low":[100,101,99,102],
                   "close":[104,102,103,109],"volume":[1]*4})
r3 = bot.compute_indicators(d3, atr_period=3)
print(r3[["ATR","ATR_200"]].round(6).to_string())
```

Actual output:

```
        ATR   ATR_200
0  5.000000  5.000000
1  6.000000  6.000000
2  5.666667  5.666667
3  6.666667  6.250000
```

---

## 3.2 `compute_smc()` — L615–769 · PROTECTED CORE

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Market structure and Order Blocks."* Order Blocks are located
by detecting confirmed pivots, watching for a close that breaks a tracked
pivot level (a Break of Structure, or a Change of Character when the trend
flips), and then taking the extreme candle between the pivot and the break
as the Order Block. The procedure is a faithful translation of the LuxAlgo
TradingView indicator, run at two structural resolutions.

### WHAT THE CODE DOES

Read it as **four stages**.

**Stage 0 — volatility-parsed highs and lows (L675–677).**

```python
is_high_volatility_bar = (highs - lows) >= (2 * atr_200)
parsed_highs = np.where(is_high_volatility_bar, lows,  highs)
parsed_lows  = np.where(is_high_volatility_bar, highs, lows)
```

On a bar whose range is at least twice the long-horizon ATR, the high and
low are **swapped** for Order-Block-search purposes. This is LuxAlgo's own
filter: an unusually wide bar is treated as a liquidity event rather than a
clean structural extreme, so its body is inverted to stop it dominating the
zone. On every normal bar `parsed_high = high` and `parsed_low = low`.

**Stage 1 — two independent passes (L681–682).**

```python
for pivot_lookback_bars in [INTERNAL_STRUCTURE_LOOKBACK_BARS,   # 5
                            SWING_STRUCTURE_LOOKBACK_BARS]:     # 50
```

The same algorithm runs twice with two lookbacks and the results are pooled.
Each pass keeps its own trend state and its own tracked pivots. "Internal"
finds fast, local structure; "swing" finds slower, major structure. On the
real dataset that produces **659 internal + 102 swing = 761** Order Blocks.

**Stage 2 — pivot confirmation (L704–712).** For each bar `i`, the candidate
pivot is `pivot_bar_candidate = i − pivot_lookback_bars`:

```python
bars_to_the_right_high = highs[pivot_bar_candidate + 1 : i + 1]
if len(bars_to_the_right_high) and highs[pivot_bar_candidate] > bars_to_the_right_high.max():
    tracked_swing_high_price = float(highs[pivot_bar_candidate])
    tracked_swing_high_bar   = pivot_bar_candidate
    swing_high_already_crossed = False
```

A pivot high is a bar whose high has not been exceeded by any of the
`pivot_lookback_bars` bars after it. **This is the structural reason a pivot
cannot be known in real time** — it takes `pivot_lookback_bars` more bars to
confirm. The engine therefore evaluates it at bar `i`, never earlier, and
the `assert` at L698–702 states that invariant in code.

**Stage 3 — crossover, and the OB it produces (L720–735).**

```python
if (not np.isnan(tracked_swing_high_price) and not swing_high_already_crossed
        and closes[i - 1] <= tracked_swing_high_price < closes[i]):
    structure_tag = "CHoCH" if trend == -1 else "BOS"
    swing_high_already_crossed = True
    trend = 1
    ob = _build_order_block_from_crossover(..., ob_type="DEMAND",
            extreme_selector=np.argmin, extreme_source=parsed_lows)
```

Four things happen in that one condition, and each is worth naming:

1. `closes[i-1] <= level < closes[i]` is a **strict upward crossing of the
   close series**, not a wick touch. Intrabar penetration does not count.
2. `swing_high_already_crossed` makes each pivot fire **at most once**. A
   level that is crossed, retested and crossed again does not produce a
   second Order Block; only a *new* confirmed pivot resets the flag.
3. `"CHoCH" if trend == -1 else "BOS"` — a bullish break is a *Change of
   Character* only if the tracked trend was bearish. Otherwise it is a
   continuation, a *Break of Structure*. With `trend` starting at 0, the
   first break of each pass is always tagged BOS.
4. A bullish break produces a **DEMAND** zone anchored on the *lowest*
   parsed low between pivot and break (`np.argmin` over `parsed_lows`) —
   the last down-candle before the up-move. The bearish branch (L737–751)
   is the exact mirror: `np.argmax` over `parsed_highs` → **SUPPLY**.

**Stage 4 — mitigation (L754–765).** After all Order Blocks are collected,
each is walked forward to find the bar where price closes back through it:

```python
if ob["type"] == "DEMAND":
    violations = np.where(close_prices[search_start:] < ob["bottom"])[0]
else:
    violations = np.where(close_prices[search_start:] > ob["top"])[0]
ob["mitigated_at"] = int(search_start + violations[0]) if len(violations) else num_bars
```

A DEMAND zone dies when a close falls below its bottom; a SUPPLY zone dies
when a close rises above its top. Never mitigated → `mitigated_at = num_bars`,
i.e. alive to the end of the dataset. `simulate_trades()` only ever considers
an Order Block on bars strictly between `created_at` and `mitigated_at`
(§3.10), so this is not lookahead — it is a precomputed lifetime that the
driver loop reads causally.

### HAND CHECK — one Order Block from twelve bars

Twelve bars is enough to exercise the **internal** pass (lookback 5, needs
7 bars) while leaving the **swing** pass (lookback 50) inert. Input:

| bar | open | high | low | close | volume |
|---|---|---|---|---|---|
| 0 | 100 | 102 | 99 | 101 | 100 |
| 1 | 101 | **110** | 100 | 105 | 100 |
| 2 | 105 | 106 | 102 | 103 | 100 |
| 3 | 103 | 104 | 100 | 101 | 100 |
| 4 | 101 | 103 | 99 | 100 | 100 |
| 5 | 100 | 103 | **98** | 102 | **200** |
| 6 | 102 | 105 | 101 | 104 | 100 |
| 7 | 104 | 108 | 103 | 107 | 100 |
| 8 | 107 | 112 | 106 | **111** | 100 |
| 9 | 111 | 113 | 109 | 112 | 100 |
| 10 | 112 | 114 | 110 | 113 | 100 |
| 11 | 113 | 115 | 111 | 114 | 100 |

**Step 1 — is any bar high-volatility?** Compute TR, then the running
`ATR_200` (a rolling mean with `min_periods=1`, so at these lengths it is
just the running mean of TR):

```
TR   = 3, 10, 4, 4, 4, 5, 4, 5, 6, 4, 4, 4
ATR_200 = 3.0, 6.5, 5.667, 5.25, 5.0, 5.0, 4.857, 4.875, 5.0, 4.9, 4.818, 4.75
```

Bar 1 is the widest at range 10, and `2 × ATR_200[1] = 13 > 10`. No bar
qualifies, so `parsed_high = high` and `parsed_low = low` everywhere. Good —
the fixture is deliberately clean.

**Step 2 — the pivot high.** The loop starts at `i = 6`
(`pivot_lookback_bars + 1`). At `i = 6`, the candidate is bar 1:

```
highs[2..6] = 106, 104, 103, 103, 105  → max = 106
highs[1] = 110 > 106  ✓  confirmed pivot high at bar 1, level 110
```

At `i = 7` the candidate is bar 2 (`highs[3..7]` max = 108 > 106 ✗), at
`i = 8` bar 3 (max 112 > 104 ✗). So 110 @ bar 1 stays the tracked level.

**Step 3 — the crossover.** Closes are
`101, 105, 103, 101, 100, 102, 104, 107, 111, 112, 113, 114`. The first `i`
with `closes[i-1] ≤ 110 < closes[i]` is `i = 8`: `107 ≤ 110 < 111` ✓.
Trend was 0, so the tag is **BOS**, the level is **internal**, the type is
**DEMAND**, and `created_at = 8`.

**Step 4 — which bar is the Order Block?**

```
ob_bar = pivot_bar + argmin(parsed_lows[1 .. 8])
parsed_lows[1..8] = 100, 102, 100, 99, 98, 101, 103, 106
                     ↑bar1                ↑bar5 = minimum
argmin = 4  →  ob_bar = 1 + 4 = 5
```

So the zone is bar 5: `top = parsed_high[5] = 103`, `bottom = parsed_low[5] = 98`.

**Step 5 — mitigation.** DEMAND, search from bar 9. Closes 112, 113, 114 are
all above 98, so it is never mitigated → `mitigated_at = 12` (= `num_bars`).

**Expected result:** exactly one Order Block —
`DEMAND, top 103, bottom 98, created_at 8, ob_bar 5, internal, BOS,
mitigated_at 12`. Its quality score is derived in §3.3.

### CONFIRM AGAINST THE CODE

```python
o=[100,101,105,103,101,100,102,104,107,111,112,113]
h=[102,110,106,104,103,103,105,108,112,113,114,115]
l=[ 99,100,102,100, 99, 98,101,103,106,109,110,111]
c=[101,105,103,101,100,102,104,107,111,112,113,114]
v=[100]*12; v[5]=200
d4 = pd.DataFrame({"open_time":pd.date_range("2022-01-01",periods=12,freq="4h"),
                   "open":o,"high":h,"low":l,"close":c,"volume":v})
r4 = bot.compute_indicators(d4)
print([round(x,3) for x in r4["ATR_200"]])
for ob in bot.compute_smc(r4): print(ob)
```

Actual output:

```
[3.0, 6.5, 5.667, 5.25, 5.0, 5.0, 4.857, 4.875, 5.0, 4.9, 4.818, 4.75]
{'type': 'DEMAND', 'top': 103.0, 'bottom': 98.0, 'created_at': 8, 'ob_bar': 5,
 'level': 'internal', 'structure': 'BOS', 'quality_displacement': False,
 'quality_large_bar': True, 'quality_fvg': True, 'quality_liquidity_sweep': True,
 'quality_volume_expansion': True, 'quality': 4, 'mitigated_at': 12}
```

Every hand-derived field matches, including the `ATR_200` series.

### Scaling up — the real dataset

```python
df  = bot.compute_indicators(bot.load_candles())
obs = bot.compute_smc(df)
print(len(obs), pd.Series([o["level"] for o in obs]).value_counts().to_dict())
print(pd.Series([o["quality"] for o in obs]).value_counts().sort_index().to_dict())
```

Actual output:

```
761 {'internal': 659, 'swing': 102}
{0: 93, 1: 154, 2: 206, 3: 197, 4: 90, 5: 21}
```

761 Order Blocks over 8,767 bars. The quality distribution is roughly
bell-shaped and centred on 2 — worth knowing, because it shows the composite
score is not degenerate (it is not all zeros or all fives).

---

## 3.3 `_build_order_block_from_crossover()` — L770–895 · PROTECTED CORE

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Order Block quality."* Each Order Block is scored on five
independent binary criteria. The criteria are described as *independent*
because they are — they are summed, never multiplied or ranked, and the sum
is used only as a cumulative eligibility threshold, never as an ordinal
statistic in a test.

**This is also the function that carried the disclosed lookahead bug** and
now carries its fix and its runtime guards. Know it cold.

### WHAT THE CODE DOES

First the zone itself (L789–798):

```python
ob_bar_index = pivot_bar + int(extreme_selector(extreme_source[pivot_bar : confirmation_bar + 1]))
ob = {"type": ob_type,
      "top":    float(parsed_highs[ob_bar_index]),
      "bottom": float(parsed_lows[ob_bar_index]),
      "created_at": confirmation_bar, "ob_bar": ob_bar_index, ...}
```

`extreme_selector` / `extreme_source` are the only difference between the
DEMAND and SUPPLY call sites — `argmin`/`parsed_lows` versus
`argmax`/`parsed_highs`. Everything below is shared.

Note the two distinct bar indices, which panelists confuse constantly:

- **`ob_bar`** — the candle the zone is drawn on.
- **`created_at`** — the later candle whose close confirmed the break, and
  therefore the first moment the zone is *knowable*.

The gap between them is the same quantity that becomes the KDJ exit window
`w` (§3.5).

**Criterion 1 — displacement (L800–826).** A strong-bodied candle in the
zone's direction within 3 bars after the OB bar:

```python
for j in range(ob_bar_index + 1, min(confirmation_bar + 1, ob_bar_index + 4)):
    assert j <= confirmation_bar, "LOOKAHEAD: ..."
    candle_body = float(df.at[j,"close"]) - float(df.at[j,"open"])
    displacement_threshold = 1.5 * float(atr_200[ob_bar_index]) if not np.isnan(atr_200[ob_bar_index]) else 0
    if ob["type"] == "DEMAND" and candle_body > 0 and abs(candle_body) >= displacement_threshold:
        displacement = True; break
```

**Criterion 2 — large bar (L828–833).** The OB candle's own range meets or
exceeds `ATR_200` at that bar. No forward search at all.

**Criterion 3 — fair value gap (L835–856).** The 3-candle FVG definition:
for a DEMAND zone, a gap exists if `low[j+2] > high[j]` for some `j` in the
window — two candles later, price has left an untraded band behind it.

```python
for j in range(ob_bar_index, min(confirmation_bar - 1, ob_bar_index + 3)):
    assert j + 2 <= confirmation_bar, "LOOKAHEAD: ..."
    if ob["type"] == "DEMAND" and float(lows[j+2]) > float(highs[j]):
        fair_value_gap = True; break
```

**Criterion 4 — liquidity sweep (L858–866).** The OB candle's own extreme
takes out the prior 10 bars' extreme. Backward-looking only.

**Criterion 5 — volume expansion (L868–882).** Either the OB candle's volume
is at least 1.25× the trailing 20-bar average, **or** its body occupies more
than 60% of its range. An `or`, not an `and` — a decisive candle counts
whether the decisiveness shows up as volume or as shape.

Then the sum (L884–892):

```python
ob["quality"] = int(ob["quality_displacement"] + ob["quality_large_bar"] + ob["quality_fvg"]
                    + ob["quality_liquidity_sweep"] + ob["quality_volume_expansion"])
```

### THE DISCLOSED BUG, AND HOW THE FIX WORKS

`docs/SCRATCH_RESULTS_METHODS.md`, *Corrected errors → Backtest-engine bug*:
the displacement and FVG forward searches were originally bounded by
**dataset length** instead of by the Order Block's own confirmation bar.
That let them read one to two candles that would not have been available at
the moment the zone became eligible. That is genuine data leakage. It was
found by a dedicated no-lookahead audit and fixed in commit `cb4ed93` by
bounding both loops at `confirmation_bar`.

Read the two bounds carefully — they are not the same, and the difference is
the substance of the fix:

| Criterion | Bound | Why that expression |
|---|---|---|
| Displacement | `min(confirmation_bar + 1, ob_bar_index + 4)` | reads **one** bar `j`, so `j ≤ confirmation_bar` is the constraint |
| FVG | `min(confirmation_bar − 1, ob_bar_index + 3)` | reads bars `j` **and `j+2`**, so `j + 2 ≤ confirmation_bar` is the constraint |

The `−1` in the FVG bound is not a typo or an off-by-one; it is what keeps
the *furthest* read, `j+2`, inside the confirmation bar.

**What happens if the window is too narrow to evaluate the criterion?** The
loop body never executes and the criterion stays `False`. That is a
deliberate choice: the criterion is **frozen at what was knowable at
confirmation time**, not marked unknown and skipped. An Order Block
confirmed one bar after its own candle simply cannot have a confirmed FVG,
and the engine records that as "no", which is the truthful answer at that
moment.

**Why the fix does not move the headline figures.** The published 27-trade
baseline runs at `min_ob_quality=0`. Every Order Block passes a threshold of
zero regardless of its score, so a change in scoring cannot change which
trades fire. The bug is real and disclosed; its effect on the baseline is
nil, and that is verifiable rather than asserted — the regression harness
passes across the fix.

**The `except AssertionError: raise` pattern (L823/L853).** Each criterion is
wrapped in a broad `try/except` so a malformed bar cannot crash a 761-block
scan. But an `AssertionError` is re-raised explicitly *before* the broad
handler can swallow it. Without that line, the no-lookahead assertions would
be silently caught by the very safety net meant to protect the loop, and the
guard would be decorative. This is the single most easily-missed detail in
the function.

### HAND CHECK — score the Order Block from §3.2

Same 12-bar fixture. The zone is `ob_bar = 5`, `confirmation_bar = 8`,
type DEMAND, and `ATR_200[5] = 5.0`.

**1 — Displacement.** Window: `range(6, min(9, 9))` → bars 6, 7, 8.
Threshold `= 1.5 × 5.0 = 7.5`.

```
bar 6 body = 104 − 102 = 2   ( 2 < 7.5 )
bar 7 body = 107 − 104 = 3   ( 3 < 7.5 )
bar 8 body = 111 − 107 = 4   ( 4 < 7.5 )
```

→ **False**

**2 — Large bar.** Bar 5 range `= 103 − 98 = 5`; `ATR_200[5] = 5.0`;
`5 ≥ 5.0` → **True** (a boundary case, and `>=` is the operator).

**3 — FVG.** Window: `range(5, min(7, 8))` → bars 5, 6.

```
j = 5:  low[7] = 103  >  high[5] = 103 ?   103 > 103 is False
j = 6:  low[8] = 106  >  high[6] = 105 ?   True  →  gap found
```

→ **True**. Note `j = 5` failing on an exact tie: the operator is strict `>`.

**4 — Liquidity sweep.** Window `lows[0..4] = 99, 100, 102, 100, 99` → min 99.
`low[5] = 98 ≤ 99` → **True**.

**5 — Volume expansion.** Trailing 20-bar mean of `volume[0..4]` = 100.
`volume[5] = 200 ≥ 1.25 × 100 = 125` → **True**. (The body test would have
failed on its own: `|102 − 100| / 5 = 0.4`, not `> 0.6`. The `or` is what
carries it.)

**Composite:** `0 + 1 + 1 + 1 + 1 = ` **4**.

### CONFIRM AGAINST THE CODE

Re-run the §3.2 snippet; the printed dict already carries every criterion:

```
'quality_displacement': False, 'quality_large_bar': True, 'quality_fvg': True,
'quality_liquidity_sweep': True, 'quality_volume_expansion': True, 'quality': 4
```

All five hand-derived booleans and the composite match.

---

## 3.4 `get_structural_tp()` — L896–926 · PROTECTED CORE

### WHAT THE CODE DOES

Six lines. Given an entry price and a side, find the nearest Order Block of
the *opposing* type on the correct side of price, and return the edge of it
that price would reach first:

```python
if side == "LONG":
    candidate_targets = [ob for ob in valid_order_blocks
                         if ob["type"] == "SUPPLY" and ob["bottom"] > entry_price]
    return min(candidate_targets, key=lambda ob: ob["bottom"])["bottom"] if candidate_targets else None
else:
    candidate_targets = [ob for ob in valid_order_blocks
                         if ob["type"] == "DEMAND" and ob["top"] < entry_price]
    return max(candidate_targets, key=lambda ob: ob["top"])["top"] if candidate_targets else None
```

For a LONG the target is the **bottom** of the nearest SUPPLY zone above —
the near edge, the first price at which supply is expected to appear. For a
SHORT it is the **top** of the nearest DEMAND zone below. Taking the near
edge rather than the middle or far edge is the conservative choice: the
target is the first point of expected resistance, not the optimistic one.

Returns `None` when nothing qualifies. The caller then falls back to a fixed
`2 × risk` target (§3.7). About that fallback: it means "structural" targets
are used when structure exists and a fixed multiple otherwise, and which one
was used is recorded per trade as `tp_is_structural`, so the split is
auditable rather than hidden.

**Why this cannot look ahead:** `valid_order_blocks` is
`active_order_blocks_for_tp`, filtered in the driver loop by
`created_at < i < mitigated_at`. Every zone considered was confirmed
strictly before the current bar.

---

## 3.5 The dual-KDJ architecture — `kdj_reset_init/update/exit`, L927–1063 · PROTECTED CORE

**This is the single most likely question at a defense.** Two KDJ systems
exist in this project on purpose, and a reader who has skimmed the code will
assume it is an inconsistency.

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Exit logic."* Entry gating reads a static, full-history
KDJ(9,3,3). Exit timing uses a separate per-trade oscillator, seeded from
that static series at the entry candle and then recursed forward on a
trade-specific window length `w`.

### THE TWO SYSTEMS, SIDE BY SIDE

| | **System A — entry gating** | **System B — exit timing** |
|---|---|---|
| Where | `compute_indicators()`, L581–590 | `kdj_reset_init/update/exit`, L927–1063 |
| Period | fixed 9 | `w = entry_idx − ob_bar`, per trade |
| Computed | once, over the whole dataset | per trade, bar by bar, from entry |
| Seed | K = D = first RSV | K, D copied from System A at the entry bar |
| Reads | every `kdj_k`, `kdj_d`, `kdj_j` in an entry condition | nothing in an entry condition |
| Affects | which trades open | only when an open trade closes |

`docs/SCRATCH_RESULTS_METHODS.md` records the audit result plainly: *"The
exit-side reset period `w` has no effect on entry — confirmed by read-only
audit."* The two systems never touch. They are separate by design, and
unifying them would be a strategy change, not a cleanup.

### `kdj_reset_init()` — L927–977

```python
period = default_period                                  # 9
if ob_bar is not None and isinstance(ob_bar, int) and ob_bar >= 0:
    period = max(1, entry_idx - ob_bar)
return {"k": float(df.at[entry_idx,"K"]), "d": float(df.at[entry_idx,"D"]),
        "prev_k": float(df.at[entry_idx,"K"]), "prev_d": float(df.at[entry_idx,"D"]),
        "period": int(period), "entry_idx": int(entry_idx), "armed": False}
```

Three design decisions, each of which a panelist may probe:

1. **The seed is the live static K/D at the entry bar** — not 50, not a
   backfill. The exit oscillator therefore starts from the market's actual
   momentum state at entry rather than from a neutral fiction.
2. **`w = entry_idx − ob_bar`** ties the exit window to how *stale* the
   triggering Order Block was. A zone that price returned to quickly gets a
   short, twitchy exit oscillator; a zone price took months to revisit gets
   a long, slow one. The rationale is that the timescale of the setup should
   set the timescale of the exit.
3. **`ob_bar=None` → `period = 9`.** This is not dead code: the ablation
   arms (§4) have no Order Block, and this is the engine's own explicit
   no-OB case, reused rather than reimplemented.

> **Correct the "two-bar window" story if you have heard it.** An earlier
> paper draft used a two-bar `w` as an illustrative example. Across the 27
> baseline trades the observed `w` runs **14 to 439, median 74** — it never
> approaches single digits. The paper text was corrected; the code was not
> changed, because the code was never wrong.

### `kdj_reset_update()` — L978–1031

```python
window_start = max(cur_idx - period + 1, 0)
window_high  = df["high"].iloc[window_start : cur_idx + 1]
window_low   = df["low"].iloc[window_start : cur_idx + 1]
...
raw_stochastic_value = ((df.at[cur_idx,"close"] - window_lowest) / rsv_denominator * 100) if rsv_denominator > 0 else 50.0
state["prev_k"] = state["k"]; state["prev_d"] = state["d"]
state["k"] = state["k"] * (1 - 1/3) + raw_stochastic_value * (1/3)
state["d"] = state["d"] * (1 - 1/3) + state["k"]            * (1/3)
if side == "SHORT" and state["k"] < state["d"]: state["armed"] = True
if side == "LONG"  and state["k"] > state["d"]: state["armed"] = True
```

The smoothing is identical to System A's (α = 1/3, D smooths the *new* K);
only the RSV window length differs. The slice `[window_start : cur_idx + 1]`
ends at the current bar — no forward read.

**The `armed` flag is the part that carries the logic.** The state machine
will not exit on the first crossing it sees. It must first cross *in the
trade's favour* (arming), and only a subsequent cross *against* it is an
exit. That makes the exit a genuine momentum reversal rather than a
coin-flip on the first wobble.

### `kdj_reset_exit()` — L1032–1063

```python
if not state["armed"]: return False
if side == "SHORT": return state["prev_k"] <= state["prev_d"] and state["k"] > state["d"]
else:               return state["prev_k"] >= state["prev_d"] and state["k"] < state["d"]
```

True on exactly the bar of the reversal crossing, using `prev_*` versus
current — a state comparison, not a level test. It cannot fire twice on the
same crossing.

### HAND CHECK — one init and one update

Use the six-bar KDJ fixture from §3.1 Hand Check B, entering at bar 5 with a
triggering Order Block at bar 2.

**Init.** `w = entry_idx − ob_bar = 5 − 2 = 3`. Seeds come straight from
System A at bar 5: `K[5] = 56.546203`, `D[5] = 53.716922`.

```
state = {k: 56.546203, d: 53.716922, prev_k: 56.546203, prev_d: 53.716922,
         period: 3, entry_idx: 5, armed: False}
```

**One update at bar 5, side LONG.** Window start `= max(5 − 3 + 1, 0) = 3`,
so the window is bars 3–5:

```
highs[3..5] = 115, 113, 117  → highest = 117
lows [3..5] =  95,  93,  97  → lowest  =  93
RSV = (close[5] − 93) / (117 − 93) × 100 = (107 − 93)/24 × 100 = 58.33333333

k = 56.546203 × (2/3) + 58.33333333 × (1/3) = 37.697469 + 19.444444 = 57.141913
d = 53.716922 × (2/3) + 57.141913   × (1/3) = 35.811281 + 19.047304 = 54.858586
```

`k > d` and side is LONG → **armed becomes True**. `kdj_reset_exit` is still
`False`: arming is not exiting.

### CONFIRM AGAINST THE CODE

```python
r2 = bot.compute_indicators(d2)          # the six-bar fixture from 3.1B
st = bot.kdj_reset_init(r2, entry_idx=5, ob_bar=2)
print(st)
print(bot.kdj_reset_init(r2, entry_idx=5, ob_bar=None)["period"])
st2 = bot.kdj_reset_update(dict(st), r2, 5, "LONG")
print(st2, bot.kdj_reset_exit(st2, "LONG"))
```

Actual output (rounded to 6 dp):

```
{'k': 56.546203, 'd': 53.716922, 'prev_k': 56.546203, 'prev_d': 53.716922,
 'period': 3, 'entry_idx': 5, 'armed': False}
9
{'k': 57.141913, 'd': 54.858586, 'prev_k': 56.546203, 'prev_d': 53.716922,
 'period': 3, 'entry_idx': 5, 'armed': True} False
```

The `ob_bar=None` fallback returns period 9, as documented.

### CONFIRM THE `w` RANGE ON REAL DATA

```python
print(t.kdj_exit_window.min(), t.kdj_exit_window.max(), t.kdj_exit_window.median())
```

Actual output:

```
14 439 74.0
```

Matching `docs/SCRATCH_RESULTS_METHODS.md` exactly. `kdj_exit_window` is
recorded on every trade row precisely so this is checkable without
recomputing `entry_idx − ob_bar` by hand.

---

## 3.6 `_resolve_structural_tp_ob()` — L1064–1080

Bookkeeping. `get_structural_tp()` returns only a *price*; the closed-trade
record wants to log *which* Order Block that price came from. This finds it
back by matching within a small relative tolerance:

```python
tolerance = 1e-6
candidates = [ob for ob in valid_obs_tp
              if ob["type"] == opposing_type
              and abs(ob[level_key] - structural_tp_price) <= tolerance * max(1.0, abs(structural_tp_price))]
return min(candidates, key=lambda ob: abs(ob[level_key] - structural_tp_price)) if candidates else None
```

The tolerance is *relative* (scaled by the price magnitude, floored at 1.0)
because an exact float equality test on a value that has been through a
`min()`/`max()` and a dict round-trip is fragile. It affects only which
`tp_ob_*` diagnostic fields get filled in, never the take-profit price
itself — that was already decided in §3.4.

---

## 3.7 The entry gates — `_try_enter_long` L1081–1160, `_try_enter_short` L1161–1234 · PROTECTED CORE

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Entry conditions."* A trade opens only when price is inside a
live Order Block **and** momentum, oscillator and volatility conditions all
agree, **and** the resulting risk geometry clears two minimum standards.

### THE LONG GATE AS A CHECKLIST

The function loops over every currently-active DEMAND zone and takes the
first that clears **eight gates in this order**. Every gate is a `continue`,
so one failure moves to the next zone, not to the next bar.

| # | Line | Gate | Code | In words |
|---|---|---|---|---|
| 1 | 1110 | Zone touch | `low <= ob["top"] and close >= ob["bottom"]` | price is inside the zone |
| 2 | 1112 | MACD below zero and rising | `hist < 0 and hist > hist[-1]` | momentum is negative but turning up |
| 3 | 1115 | Rising for ≥ 2 bars | `hist[-1] > hist[-2]` | not a one-bar blip |
| 4 | 1117 | KDJ oversold and turning | `K < 50 and K > K[-1] and J < 60` | oscillator is low and lifting |
| 5 | 1119 | K acceleration in window | `1 <= k_accel <= 6` | accelerating, but not a spike |
| 6 | 1121 | Volatility regime | `not (0.8 <= atr_r <= 1.0)` | skip the dead zone |
| 7 | 1124–1131 | Stop distance | `risk/close >= 0.015` | stop at least 1.5% away |
| 8 | 1133–1136 | Reward:risk | `(tp − close)/risk >= 1.5` | target at least 1.5× the risk |

Gates 5 and 6 are the two most likely to be challenged, so state them
precisely:

**Gate 5 — `k_accel`** is the *second difference* of K over three bars,
computed in the driver loop at L1480:

```python
kdj_k_acceleration = (kdj_k - kdj_k_prev_bar) - (kdj_k_prev_bar - kdj_k_two_bars_ago)
```

The window `[1, 6]` excludes two different failure modes at once.
`k_accel <= 0` means K is not yet accelerating in the trade's favour — the
turn has not happened. `k_accel > 6` means a single-bar spike, which on 4h
BTC data typically mean-reverts on the next candle. The filter wants a turn
that is real but not violent.

**Gate 6 — `atr_r`** is `ATR(14) / ATR(200)`, current volatility against the
long-horizon baseline. The excluded band is `0.8 ≤ atr_r ≤ 1.0`, i.e.
*"current volatility is roughly normal."* This is a **band exclusion, not a
threshold**: both unusually quiet (`< 0.8`) and unusually active (`> 1.0`)
regimes are allowed, and only the ordinary middle is skipped. The reasoning
is that the setup depends on a volatility event, and an average-volatility
market provides no edge either way.

Then the stop and target (L1124–1136):

```python
stop_loss_candidate = ob["bottom"] - atr_14 * 0.5     # half an ATR below the zone
risk = close - stop_loss_candidate
if risk <= 0: continue
if risk / close < MIN_STOP_LOSS_DISTANCE_RATIO: continue          # >= 1.5%
structural_tp_price = get_structural_tp(close, "LONG", valid_obs_tp)
take_profit_price   = structural_tp_price if structural_tp_price else close + risk * 2.0
if (take_profit_price - close) / risk < MIN_RISK_REWARD_RATIO: continue   # >= 1.5
```

The stop sits half an ATR *below the zone*, not below the entry price — it
is anchored to structure, with a volatility buffer. Note that the fallback
target is `2 × risk` while the *minimum acceptable* ratio is 1.5: a
structural target closer than 1.5R is rejected outright rather than being
widened to fit.

### THE SHORT GATE IS NOT A SIGN FLIP

`_try_enter_short` is *not* the mirror image, and glossing it as one is an
error a panelist can catch. It carries **two extra gates the LONG side does
not have**:

```python
if not (kdj_k > 50 and kdj_j > kdj_k > kdj_d): continue   # gate 4, note the ORDERING test
...
if kdj_k < KDJ_K_SHORT_FLOOR: continue    # L1193  K >= 70   — extra
if kdj_j > KDJ_J_SHORT_CAP:   continue    # L1197  J <= 100  — extra
```

So the SHORT side must be genuinely overbought (`K ≥ 70`, stricter than the
`K > 50` in gate 4) *and* not already exhausted (`J ≤ 100`). Gate 4 itself
also tests an **ordering** — `J > K > D` — which has no LONG equivalent.

**Why the asymmetry?** BTC over this window is a structurally upward-drifting
asset. A short is fighting that drift, so it is held to a stricter
oscillator standard. This is a stated design decision, not an oversight. The
resulting split is **15 LONG / 12 SHORT** across the 27 baseline trades —
the extra gates tighten shorts without eliminating them.

### HAND CHECK — walk a real entry through the gates

A contrived bar can only show a gate *rejecting*. To see all eight *pass*,
walk the actual first trade of the baseline. Pull its bar with:

```python
i = int(t.iloc[0].entry_idx)
for col in ["close","MACD_hist","K","D","J","ATR","ATR_200"]:
    print(col, df.at[i-2,col], df.at[i-1,col], df.at[i,col])
```

Actual output, for `i = 335` (`2022-02-26 04:00:00`), a **SHORT**:

```
close      39410.92           38676.14           39219.17
MACD_hist  394.5281944527     363.9833451310     363.6716077851
K          77.7382875909      77.4183549156      80.6206254068
D          65.1791446867      69.2588814297      73.0461294221
J          102.8565733992     93.7373018874      95.7696173764
ATR        1247.8828571429    1248.3514285714    1262.5707142857
ATR_200     901.3945000000     902.5204000000     902.3649000000
```

The entry Order Block is `SUPPLY, top 39494.35, bottom 38909.26, ob_bar 307,
created_at 308, quality 2`. Now walk the SHORT checklist by hand:

| # | Gate | Arithmetic | Verdict |
|---|---|---|---|
| 1 | zone touch | `high 39600.00 ≥ 38909.26` and `close 39219.17 ≤ 39494.35` | pass |
| 2 | hist > 0 and falling | `363.6716 > 0` and `363.6716 < 363.9833` | pass |
| 3 | falling ≥ 2 bars | `363.9833 < 394.5282` | pass |
| 4 | K > 50 and J > K > D | `80.62 > 50`; `95.77 > 80.62 > 73.05` | pass |
| 5 | k_accel in [1,6] | `(80.6206 − 77.4184) − (77.4184 − 77.7383) = 3.2022 + 0.3199 = 3.5222` | pass |
| 6 | atr_r outside [0.8,1.0] | `1262.5707 / 902.3649 = 1.39918` | pass |
| — | K floor | `80.62 ≥ 70` | pass |
| — | J cap | `95.77 ≤ 100` | pass |
| 7 | stop distance | `SL = 39494.35 + 1262.5707 × 0.5 = 40125.6354`; `risk = 906.4654`; `906.4654 / 39219.17 = 2.311%` ≥ 1.5% | pass |
| 8 | reward:risk | `TP = 35515.83` (structural, from the DEMAND zone at bar 325); `(39219.17 − 35515.83) / 906.4654 = 4.085` ≥ 1.5 | pass |

Every intermediate above is reproducible with a calculator from the printed
bar values, and every one is confirmed by the trade record itself:

```
side SHORT | entry_idx 335 | entry 39219.17 | stop_loss 40125.635357
take_profit 35515.83 | tp_is_structural True | tp_ob_bar 325 | kdj_exit_window 28
```

Note `kdj_exit_window = 28 = 335 − 307` — the entry bar minus the OB bar,
exactly as §3.5 specifies.

This trade closed at `-0.664547%` on a trailing exit. **Report it as it is.**
The first trade of the baseline is a loser, and showing that you walk a
losing trade rather than a cherry-picked winner is worth more at a defense
than the number itself.

---

## 3.8 The exit ladder — `_check_long_exit_conditions` L1235–1291, `_check_short_...` L1292–1336 · PROTECTED CORE

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Exit logic."* Five exit mechanisms are evaluated on every bar
of an open position, **in a fixed priority order**. The order is part of the
strategy, not an implementation detail — a different order produces a
different trade log.

### THE FIVE RUNGS, IN ORDER (LONG)

**Rung 1 — trailing 50% retrace (L1259–1263).** Only armed once the trade
has been up ≥ 1.5% at some point:

```python
if peak_pnl_pct >= 1.5:
    trailing_floor = entry_price * (1 + peak_pnl_pct * 0.5 / 100)
    if close <= trailing_floor:
        return "TRAILING EXIT (50% RETRACE)", pnl_pct, ...
```

The floor gives back half of the best unrealised gain. If a trade peaked at
+4%, the floor sits at +2%.

**The state update between rungs 1 and 2 (L1265) — read this twice.**

```python
kdj_state = kdj_reset_update(kdj_state, df, i, "LONG")
```

The KDJ exit machine advances with **this** bar's price action *before* the
KDJ rung is tested — **but only if rung 1 did not already fire**, because
rung 1 returns first. That ordering is preserved deliberately from the
original engine. Moving this line changes which bar's data the KDJ exit is
allowed to react to, and therefore changes the trade log. It is called out
in the function's own docstring for exactly that reason.

**Rung 2 — KDJ reset exit (L1270–1272).**

```python
if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, "LONG"):
    return "KDJ RESET EXIT", pnl_pct, ...
```

The `>= 3` bar guard suppresses single-bar oscillator noise in the first two
bars of a trade, which would otherwise close positions before the thesis has
had a chance to develop.

**Rung 3 — ATR move exit (L1274–1276).** `close >= entry + entry_atr × 1.8`
→ take the move. Note `entry_atr` is **frozen at entry**, not recomputed
each bar; the target distance does not drift with volatility mid-trade.

**Rung 4 — breakeven ratchet (L1278–1280).** Not an exit. Once the move has
run `2.0 × entry_atr` in favour, the stop is raised to the entry price:

```python
if close >= entry_price + entry_atr * ATR_MULT_BREAKEVEN:
    stop_loss_price = max(stop_loss_price, entry_price)
```

The `max()` guarantees the stop can only ratchet **up**, never loosen.

**Rung 5 — hard stop / hard target (L1282–1287).** Last, because everything
above is a *managed* exit and these are the backstops.

```python
if   close <= stop_loss_price:    return "HIT STOP LOSS",   (close-entry)/entry*100, ...
elif close >= take_profit_price:  return "HIT TAKE PROFIT", (close-entry)/entry*100, ...
```

Note that rungs 1–3 return the already-computed running `pnl_pct`, while
rung 5 recomputes from `close` — the same value by construction, but written
explicitly at the two rungs that represent a *price level* being reached.

**The SHORT ladder (L1292–1336)** is the same five rungs with the
inequalities reversed, and — unlike the entry gates — it genuinely is a
mirror image, including `min()` instead of `max()` on the breakeven ratchet.

### WHY THE ORDER MATTERS

Because rungs are `return` statements, at most one fires per bar. On a bar
where several conditions are simultaneously true, the *highest* rung wins.
The empirical distribution over the 27 baseline trades:

```python
print(t.exit_reason.value_counts().to_dict())
```

Actual output:

```
{'ATR MOVE EXIT': 9, 'TRAILING EXIT (50% RETRACE)': 8, 'KDJ RESET EXIT': 8, 'HIT STOP LOSS': 2}
```

Read that carefully, because it is a genuinely useful defense fact: **25 of
27 trades ended on a managed exit; only 2 hit the hard stop, and none hit the
hard take-profit.** The ladder, not the stop, is doing the work. And the two
stop-outs are the reason the loss side of the distribution is bounded, which
is what produces the −6.46% maximum drawdown reported in §5B.

---

## 3.9 `_record_closed_trade()` — L1337–1380

Appends one row, identical schema for LONG and SHORT, and marks the closing
bar's `Trade_Status`. Reproduced from the nested `close_trade()` closures in
the original engine, with **one addition**: `kdj_exit_window`, added so the
frozen-at-entry KDJ period `w` is visible per trade instead of only
recomputable from `entry_idx − entry_ob_bar` by hand.

The row is grouped as: identity (`side`, `entry_idx`, `exit_idx`), prices
(`entry`, `exit`, `stop_loss`, `take_profit`, `pnl_pct`), full entry-OB
provenance (bar, composite quality, **all five criteria as separate
booleans**, `created_at`, level, type), TP provenance (`tp_is_structural`
plus the same fields for the TP zone), and outcome (`hold_bars`,
`exit_reason`, `kdj_exit_window`).

**Why the five booleans are stored separately rather than only the sum:**
the composite score is lossy — a 2 could be `displacement + fvg` or
`large_bar + sweep`, which are different market claims. Storing the
components keeps every downstream analysis able to ask about a specific
criterion without re-running the engine. The Google Sheets export (§3B) and
the dashboard both read these columns directly.

---

## 3.10 `simulate_trades()` — L1381–1637 · PROTECTED CORE

### WHAT THE PAPER CLAIMS HERE

This function *is* the strategy under test. Every headline figure in the
paper is read from its output.

### THE STATE MACHINE

Exactly one position at a time. Three states, and the transitions are the
whole engine:

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼         _try_enter_long()                    │
   ┌─────────┐  ──────────────────►  ┌──────────┐      │
   │  FLAT   │                       │   LONG   │──────┤ exit ladder fires
   │ (None)  │  ──────────────────►  ├──────────┤      │ → _record_closed_trade()
   └─────────┘  _try_enter_short()   │  SHORT   │──────┘ → back to FLAT
                                     └──────────┘
```

**No overlapping positions** is not a simplification, it is a load-bearing
property. It is what makes the equity curve in §5B a plain sequential walk
over exits rather than an approximation, and it is why `hold_bars` can be
summed to give time-in-market without double-counting.

### WALKING THE LOOP

**Warm-up (L1460).** `start_bar = SWING_STRUCTURE_LOOKBACK_BARS + 5 = 55`.
The first 55 bars are never traded — the 50-bar pivot lookback needs history
before it can confirm anything.

**Per-bar reads (L1463–1475).** Price and indicator values for bars `i`,
`i−1`, `i−2` are pulled into locals. Only backward indices appear. There is
no `i+1` anywhere in this loop.

**Derived quantities (L1480, L1484).** `kdj_k_acceleration` and
`atr_regime_ratio`, as detailed in §3.7.

**Order Block activity filter (L1490–1502).** Three filters, all causal:

```python
active_order_blocks_for_entry = [
    ob for ob in order_blocks
    if ob["created_at"] < i < ob["mitigated_at"]              # confirmed, not yet invalidated
    and i - ob["created_at"] <= MAX_ORDER_BLOCK_AGE_BARS      # not older than 500 bars
    and ob.get("quality", 0) >= effective_min_ob_quality      # quality threshold
]
```

`created_at < i` is strict: a zone cannot be traded on the very bar that
confirmed it. Note the **entry** list applies the quality threshold and the
**take-profit** list does not — a low-quality zone is not good enough to
enter *on*, but is still valid market structure to target. That is a
deliberate asymmetry, and it is why `active_order_blocks_for_tp` exists as a
separate list.

**Touch log (L1504–1520).** Every bar where an active zone overlaps the
bar's range is recorded with a full indicator snapshot — **including bars
that did not produce a trade.** This is diagnostic only; it feeds the
dashboard's touch view and the `ob_touches` table. It is worth pointing at
in a defense: the project records its rejected setups, not only its taken
ones.

**Entry attempt (L1547–1562).** LONG is tried first; SHORT only if LONG
returned `None`. On a bar where both sides could theoretically qualify, LONG
wins. Given the mutually contradictory MACD conditions (`hist < 0` for LONG,
`hist > 0` for SHORT), this can never actually arise — but the ordering is
fixed and deterministic either way.

**Position management (L1564–1614).** Compute running `pnl_pct`, update
`peak_pnl_pct` (which the trailing rung needs), write the per-bar status
columns, then call the exit ladder. If it returns a reason, record the trade
and go flat.

**The SMC cache (L1431–1437).**

```python
cache_key = (len(df), float(df["close"].iloc[-1]) if not df.empty else 0.0)
```

Order Block detection is deterministic given the candle series, so it is
cached across repeated `simulate_trades()` calls on the same data — which
matters because `--serve` runs the simulation once per quality level
(0, 1, 2, 3) on the same 8,767 bars. The key `(length, last close)` is a
cheap fingerprint. It is safe here because every caller in this file passes
either the locked dataset or the formulation window, which differ in both
length and last close; it would be unsafe as a general-purpose cache, and
that is worth knowing rather than defending as ideal.

**Summary statistics (L1616–1627).**

```python
total_return_pct = trades_df["pnl_pct"].sum()      # a SUM, not a compounded product
avg_return_pct   = trades_df["pnl_pct"].mean()
win_count        = (trades_df["pnl_pct"] > 0).sum()
```

**The `+30.31%` headline is a simple sum of per-trade percentage returns,
not a compounded equity curve.** Be precise about this. It is the
convention the paper reports and it is stated as such; the *compounded*
figure appears separately as `final_capital` in `_run_strategy_dollar_arm`
(§5B), where $10,000 becomes $13,417.77 — i.e. +34.18% compounded. The two
are different quantities computed from the same trades, both are reported,
and they are never reconciled into one number.

A "win" is `pnl_pct > 0` — strictly greater than zero. A hypothetical exact
break-even trade would count as a loss. None occur in the baseline.

### CONFIRM AGAINST THE CODE — the whole engine end to end

```python
df  = bot.compute_indicators(bot.load_candles())
sim = bot.simulate_trades(df, min_ob_quality=0)
t   = sim.attrs["trades_df"]
print(len(t), (t.pnl_pct>0).sum(), t.pnl_pct.sum(), t.side.value_counts().to_dict())
```

Actual output:

```
27 19 30.306456356031937 {'LONG': 15, 'SHORT': 12}
```

And the authoritative check, which compares all 8,767 bars *and* all 27
trades against the committed golden master:

```
python scratch/regression.py
```

### NOTED DUPLICATION — say it before a panelist finds it

The entry predicate exists in **four** places and the exit ladder in
**four**:

| Logic | Locations |
|---|---|
| Entry conditions | `_try_enter_long` (L1081), `_try_enter_short` (L1161), `ablation_entry_long_ok` (L2120), `ablation_entry_short_ok` (L2146) |
| Exit ladder | `_check_long_exit_conditions` (L1235), `_check_short_exit_conditions` (L1292), and twice inline inside `run_ablation_arm` (L2176) |

This is **not** an accident, and the honest answer has two parts.

*Why they exist:* the ablation copies must be able to differ from the
baseline in exactly one respect — the removal of the Order Block gate —
while remaining identical in every other. Keeping them as separate,
individually readable functions makes that single difference visible by
direct comparison rather than hidden behind a flag argument.

*Why they agree:* the ablation gates were transcribed line-for-line from the
entry functions and can be diffed against them directly. Compare
`_try_enter_long` L1112–1122 against `ablation_entry_long_ok` L2133–2142 —
the same five conditions in the same order, with only the zone-touch check
removed. The ablation's post-entry exit logic reuses this file's own
`kdj_reset_init/update/exit` unmodified rather than reimplementing them.

*The honest caveat:* four copies is four places a future edit could drift.
Consolidating them behind one predicate is a legitimate improvement, and it
is deliberately deferred until after the paper freeze, because refactoring
the protected core carries more risk right now than the duplication does.

---

# Part 3B — Live data pull + Google Sheets export (L1638–2076)

*Light depth. Pure I/O and formatting. No line in this section computes
strategy maths, which is why it sat outside the "no strategy changes" freeze
and could be relocated during consolidation.*

## 3B.1 Two disclosed relocation adjustments (L1655–1667)

Both were forced by the file's new location and are stated in the section
banner rather than left to be discovered:

1. **`BASE_DIR` lost one `dirname()` hop.** This file lives at the repo root;
   the retired `src/Binance backtest bot.py` was one directory deeper.
   `SERVICE KEY/` resolves to the same folder as before.
2. **The Binance client is now constructed lazily** (`_get_binance_client()`,
   L1707) instead of at import time. The original module-level
   `client = Client(...)` could raise before any function was called, which
   would have made a bare `import` of this file fail without API keys. Now
   importing never touches the network — which is what makes every REPL
   block in this guide safe to run offline.

## 3B.2 `resolve_google_service_key_path()` (L1678–1706)

Auto-discovers a service-account JSON under `SERVICE KEY/`, choosing the
**most recently modified non-"disabled" key file**. If a Sheets push starts
failing with an auth error, check whether a stale key file has become newer
than the working one before assuming the code broke.

## 3B.3 `get_candles()` (L1719–1777)

The one routine network call. Paginates Binance klines 1,000 at a time,
keeps eight columns, casts to float, and applies the project's historical
cache convention:

```python
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms") + pd.Timedelta(hours=8)
```

**The UTC+8 shift is a labelling convention, not a data transformation.** It
adds the same eight hours to every bar. Bar ordering, bar spacing, and every
relative quantity in the entire analysis are unchanged; only the printed
timestamps differ. It is why `load_candles()` reports a first bar of
`2022-01-01 08:00:00` rather than `00:00`.

Called only by `--serve` and by the OOS validation function. The default
offline pipeline never reaches it.

## 3B.4 The Sheets writers (L1780–2076)

| Function | Line | Writes |
|---|---|---|
| `_get_or_create_sheet` | 1780 | idempotent worksheet creation |
| `_format_df_for_export_full` | 1789 | **all 26 sim-dataframe columns** per bar — not a curated subset |
| `_write_sheet` | 1810 | the values |
| `_apply_pnl_formatting` | 1815 | green/red cell colouring on P&L |
| `_authorize_gsheet_workbook` | 1864 | credentials |
| `_write_benchmark_sheet` / `push_benchmark_vs_passive_to_gsheet` | 1895 / 1938 | 2 tabs, gross + fee-adjusted |
| `_write_trades_sheet` / `_write_results_sheet` / `push_trades_and_results_to_gsheet` | 1982 / 2014 / 2040 | 4 tabs, the full 40-column trade schema |
| `push_candles_to_gsheet` | 2058 | 2 tabs of per-bar data |

**Why none of this can move a published number.** Every push takes a
finished DataFrame and writes it out. `_apply_pnl_formatting` sets cell
colours — the *values* are already written by `_write_sheet` before it runs.
Delete this entire section and every figure in the paper is unchanged; you
would simply lose the spreadsheet copy.

**One superseded export, deliberately left defined.**
`push_all_thresholds_to_gsheet` (per-quality-threshold, per-bar
"Quality 0".."Quality 3" sheets) is still in the file but is **no longer
called**, and its sheets are actively deleted from the live workbook on every
push. It was superseded on purpose by the full-column exports above, not
deprecated by accident. Do not re-wire it.

---

# Part 4 — The ablation study (L2077–2502)

## 4.1 WHAT THE PAPER CLAIMS HERE

*Methodology, "Design of the three-arm comparison."* Three configurations
are compared on identical data to isolate where the performance comes from:

| Arm | Entry | Stop |
|---|---|---|
| 1 — baseline | indicators **+ Order Block touch** | OB edge ∓ 0.5 × ATR(14) |
| 2 — `flat_atr` | indicators only | `close ∓ 1.5 × ATR(14)` |
| 3 — `swing_pivot` | indicators only | 5-bar low/high (prior bars only) ∓ 0.5 × ATR(14) |

Arms 2 and 3 exist as a *pair* for a specific reason. If only one OB-free arm
were tested and it underperformed, the result would be ambiguous: was it the
missing Order Block gate, or just a worse stop? Two arms with two different
stop schemes separate those explanations.

Both OB-free arms keep `rr_min = 1.5` and `sl_ratio_min = 0.015` identical to
the baseline, and use a **fixed 2R take-profit** rather than a structural one
— using a structural TP would reintroduce an Order Block dependency into a
configuration designed to remove it.

## 4.2 THE DISCLOSED LIMITATION — read this before quoting any ablation number

The section banner (L2085–2098) states it, and it is not softened here:

> The script that originally produced the exact per-trade pools behind the
> published 140/138-trade arms **was never committed to this repository.**
> `run_ablation_arm()` is a fresh, best-faith reconstruction from the
> *documented* design, not a byte-for-byte recovery. It is **not guaranteed
> to reproduce the locked figures.** A prior attempt at the same
> reconstruction already diverged by more than 10 win-rate points.

`run_ablation_study()` (L2430) therefore prints an explicit **MATCH** or
**DIVERGE** against `LOCKED_ABLATION_ARMS` on every run, and a DIVERGE is an
expected, already-known reconstruction-fidelity gap — not a new finding.

**How to answer a panelist on this.** The published arm figures come from a
lost script. The committed code reconstructs the documented design and says
out loud when it disagrees. The honest framing is: *the direction of the
ablation result is supported — removing the Order Block gate turns a
profitable configuration into two unprofitable ones — while the exact
140/138-trade figures are carried as reference numbers whose generating
script is not available for re-execution.* Do not present them as
reproducible-on-demand, because they are not.

## 4.3 `ablation_entry_long_ok` (L2120) / `ablation_entry_short_ok` (L2146)

The baseline entry gates with the zone-touch line removed, and nothing else
changed. Diff them directly against `_try_enter_long` / `_try_enter_short`
(§3.7): the same five LONG conditions in the same order, and the same seven
SHORT conditions including the `K ≥ 70` floor and `J ≤ 100` cap. Returning a
bool instead of a position tuple is the only structural difference.

## 4.4 `run_ablation_arm()` (L2176–2337)

One bar-by-bar simulation per arm. The stop rule is the branch point:

```python
# flat_atr   : SL = close - 1.5 * ATR(14)   (LONG)   /  close + 1.5 * ATR(14)  (SHORT)
# swing_pivot: SL = min(low[i-5 : i]) - 0.5 * ATR(14)  /  max(high[i-5 : i]) + 0.5 * ATR(14)
```

The swing-pivot window is `[i-5 : i]` — **prior bars only**, excluding the
current bar. Post-entry exit logic is copied from `simulate_trades()` and
calls this file's own `kdj_reset_init(..., ob_bar=None)`, which falls back
to `default_period=9` (§3.5) — the engine's own documented no-OB case, not a
special path invented for the ablation.

## 4.5 `summarize_trade_pool()` (L2338–2368)

Six numbers from a `pnl_pct` column: `n`, `wins`, `win_rate`,
`total_return`, `avg_return`, `sd` (`None` when `n ≤ 1`).

**HAND CHECK.** Three trades: `+2.00%`, `+0.15%`, `−1.00%`.

```
n     = 3
wins  = 2                    (strictly > 0)
rate  = 2/3 × 100 = 66.6667%
total = 2.00 + 0.15 − 1.00 = 1.15%
avg   = 1.15 / 3 = 0.383333%
sd    : mean = 0.383333
        deviations = 1.616667, −0.233333, −1.383333
        squares    = 2.613611, 0.054444, 1.913611  → sum 4.581667
        ddof=1     → 4.581667 / 2 = 2.290833  →  √ = 1.513550
```

**CONFIRM AGAINST THE CODE**

```python
tp = pd.DataFrame({"entry_idx":[10,20,30], "pnl_pct":[2.0, 0.15, -1.0]})
print(bot.summarize_trade_pool(tp))
```

Actual output:

```
{'n': 3, 'wins': 2, 'win_rate': 66.66666666666666, 'total_return': 1.15,
 'avg_return': 0.3833333333333333, 'sd': 1.51354991108101}
```

## 4.6 `bootstrap_ablation_arm_vs_baseline()` (L2369–2429)

**Do not confuse this with the paper's headline CI.** They are different
designs answering different questions:

| | `bootstrap_ablation_arm_vs_baseline` (L2369) | `run_bootstrap_ci` (L2737) |
|---|---|---|
| Resamples from | the **ablation arm's** 140/138 trades | the **baseline's own** 27 trades |
| At size | 27 (the baseline's `n`) | 27 (its own `n`) |
| Design | between-arms | within-arm |
| Question | "if the arm were the truth, how often would a 27-trade sample from it look as good as the baseline?" | "how uncertain is the baseline's own return?" |
| Output | empirical p-values | a 95% percentile interval |

They are kept as two functions on purpose. Collapsing them into one would
merge two distinct inferential questions behind one name.

## 4.7 `run_ablation_study()` (L2430–2502)

Runs the baseline plus both arms, bootstraps each against the baseline,
prints the MATCH/DIVERGE verdicts, and returns the results dict that
`--serve` writes to `artifacts/ablation_reconstruction.json`.

---

# Part 5 — Statistical primitives (L2503–2721)

Seven functions. Together they are roughly 40 lines of executable code, and
every one of them is a thin, documented wrapper over `scipy.stats` or a
textbook formula. That is the point: **there is no bespoke statistical
machinery in this project.** The provenance audit
(`docs/PROVENANCE_VERDICT.md`) reached the same conclusion independently.

## 5.1 `binomial_test()` — L2521–2550

### WHAT THE PAPER CLAIMS HERE

*Results, "Overall performance."* Nineteen wins in twenty-seven trades gives
a one-sided exact binomial p of 0.026 against a fair-coin null. The paper
uses the one-sided test as its primary figure — the strategy's construction
supplies a directional prior — and reports the two-sided value alongside it.

### WHAT THE CODE DOES

```python
one_sided = scipy_stats.binomtest(win_count, trade_count, null_win_probability, alternative="greater")
two_sided = scipy_stats.binomtest(win_count, trade_count, null_win_probability, alternative="two-sided")
return {"p_one_sided": one_sided.pvalue, "p_two_sided": two_sided.pvalue}
```

Two SciPy calls. **Exact**, not normal-approximated — with n = 27 the normal
approximation is not trustworthy, and `binomtest` sums actual binomial
probabilities.

### HAND CHECK — small enough to do fully

A 27-term sum is not calculator work, so verify the *mechanism* on a 5-trade
pool, 4 wins, p = 0.5:

```
P(X ≥ 4) = [C(5,4) + C(5,5)] / 2^5 = (5 + 1)/32 = 6/32 = 0.1875
```

Two-sided at p = 0.5 is symmetric, so it is exactly double: `0.375`.

Then the real one, structurally:

```
p_one_sided = Σ(k=19..27) C(27,k) / 2^27
```

`2^27 = 134,217,728`. The numerator is 3,505,867, giving
`3,505,867 / 134,217,728 = 0.0261195`. And because the null is p = 0.5 the
two-sided value is exactly `2 × 0.0261195 = 0.0522390` — a relationship you
can check by eye in the output below, and a quick way to confirm the two
calls are consistent.

### CONFIRM AGAINST THE CODE

```python
print(bot.binomial_test(4, 5))
print(bot.binomial_test(19, 27))
```

Actual output:

```
{'p_one_sided': 0.1875, 'p_two_sided': 0.375}
{'p_one_sided': 0.026119492948055267, 'p_two_sided': 0.052238985896110535}
```

`0.026119…` → the paper's **p = 0.026**. And `2 × 0.026119492948055267 =
0.052238985896110535` exactly.

## 5.2 `bootstrap_resample()` — L2553–2601

### WHAT THE PAPER CLAIMS HERE

*Methodology, "Bootstrap."* Twenty-seven trades, skewed by a few large
winners, is too small and too non-normal for a textbook `mean ± 1.96 SE`
interval. The nonparametric percentile bootstrap assumes nothing about the
distribution's shape; it uses the data's own shape (Efron & Tibshirani,
1993). B = 10,000, n = 27, seed 42.

### WHAT THE CODE DOES

```python
values = np.asarray(values)
n   = resample_size if resample_size is not None else len(values)
rng = np.random.default_rng(seed)
for k in range(bootstrap_resamples):
    sample = rng.choice(values, size=n, replace=True)
    resample_totals[k] = sample.sum()
    resample_means[k]  = sample.mean()
```

Three choices worth defending explicitly:

- **`replace=True`.** Drawing *with* replacement is what lets a resample's
  total differ from the original at all. Without it, every resample would be
  a permutation of the same 27 values and every total would be identical.
- **`size=n`.** Drawing exactly `n` follows Efron's prescription, so the
  spread between resamples reflects genuine sampling uncertainty rather than
  an artifact of a changed sample size.
- **`np.random.default_rng(seed)`**, the modern Generator API rather than the
  legacy `RandomState`. Seeded, so the interval is exactly reproducible.

**What the bootstrap does *not* capture, stated plainly:** it treats the 27
realized trades as the population. It quantifies sampling uncertainty *given
this trade log*. It cannot tell you which trades a different price history
would have produced. The function's own docstring says so.

### HAND CHECK — B = 4 at seed 7

10,000 resamples is not hand work; four is. Values
`[1, −2, 3, −4, 5]`, `B = 4`, `seed = 7`. The draws the generator produces:

```
draw 1:  5, −4, −4,  5,  3   → total   5   mean  1.0
draw 2: −4,  5, −2,  1, −2   → total  −2   mean −0.4
draw 3: −2,  5,  5,  1,  3   → total  12   mean  2.4
draw 4:  5,  1, −4,  1,  3   → total   6   mean  1.2
```

Every draw has repeats and omissions — that is `replace=True` working.

Now the percentile step by hand. Sorted totals: `[−2, 5, 6, 12]`. NumPy's
default linear interpolation puts the 2.5th percentile at position
`0.025 × (4 − 1) = 0.075` along the sorted array:

```
p2.5  = −2 + 0.075 × (5 − (−2)) = −2 + 0.525 = −1.475
p97.5 = position 0.975 × 3 = 2.925  →  6 + 0.925 × (12 − 6) = 6 + 5.55 = 11.55
```

### CONFIRM AGAINST THE CODE

```python
vals = np.array([1.0, -2.0, 3.0, -4.0, 5.0])
br = bot.bootstrap_resample(vals, 4, 7)
print(br["resample_totals"].tolist(), br["resample_means"].tolist())
print(np.percentile(br["resample_totals"], [2.5, 97.5]).tolist())
```

Actual output:

```
[5.0, -2.0, 12.0, 6.0] [1.0, -0.4, 2.4, 1.2]
[-1.4749999999999999, 11.549999999999999]
```

Same draws, same totals, same percentile cuts. The full-scale version is
`bot.run_bootstrap_ci(t)` — §5B.1.

## 5.3 `pearson_correlation()` — L2604–2627 · `spearman_correlation()` — L2630–2662

Both are two-line SciPy wrappers returning `{r|rho, p_value, n}`. Pearson
assumes a straight-line relationship and is sensitive to outliers; Spearman
works on ranks and only assumes a consistent direction. They are reported
**together, on purpose**: if both agree in sign and significance, the
association is not an artifact of a few extreme trades.

`spearman_correlation` is the one genuinely new function in the file
(module docstring, and L2643–2651 restate it). It reproduces figures that
previously existed only in markdown notes.

### HAND CHECK — Pearson on four pairs

```
x = 1, 2, 3, 4        y = 2, 1, 4, 3
x̄ = 2.5              ȳ = 2.5
dx = −1.5, −0.5, 0.5, 1.5
dy = −0.5, −1.5, 1.5, 0.5

Σ dx·dy = 0.75 + 0.75 + 0.75 + 0.75 = 3.0
Σ dx²   = 2.25 + 0.25 + 0.25 + 2.25 = 5.0
Σ dy²   = 0.25 + 2.25 + 2.25 + 0.25 = 5.0

r = 3.0 / √(5.0 × 5.0) = 3.0 / 5.0 = 0.6
```

Because `y` here is a permutation of the ranks of `x`, Spearman's rho on the
same data is also 0.6 — a small, useful sanity property of this fixture.

### CONFIRM AGAINST THE CODE

```python
print(bot.pearson_correlation([1,2,3,4], [2.0,1.0,4.0,3.0]))
print(bot.spearman_correlation([1,2,3,4], [2.0,1.0,4.0,3.0]))
```

Actual output:

```
{'r': 0.6, 'p_value': 0.3999999999999999, 'n': 4}
{'rho': 0.6000000000000001, 'p_value': 0.4, 'n': 4}
```

### THE REAL FIGURES, AND A DISCLOSED CORRECTION

```python
print(bot.pearson_correlation(t.hold_bars.values, t.pnl_pct.values))
print(bot.spearman_correlation(t.hold_bars.values, t.pnl_pct.values))
```

Actual output:

```
{'r': 0.490698051200364,  'p_value': 0.009356041907353906, 'n': 27}
{'rho': 0.47972823534097186, 'p_value': 0.011334889028469911, 'n': 27}
```

Two draft documents once reported these as **p < 0.001**. Independent
recomputation gave p ≈ 0.0094 (Pearson) and p ≈ 0.0113 (Spearman) — still
significant at α = 0.05, but the wrong significance bucket at α = 0.001. Both
documents were corrected;
`docs/SCRATCH_RESULTS_METHODS.md` records the correction. Volunteer this
before a panelist finds it: a project that catches its own reporting errors
is demonstrating the same discipline as one that catches its own code bugs.

## 5.4 `max_drawdown_pct()` — L2665–2686

```python
equity_curve = pd.Series(equity_curve)
running_max  = equity_curve.cummax()
drawdown_pct = (equity_curve - running_max) / running_max * 100
return drawdown_pct.min()
```

Four lines. Drawdown at each point is measured against the **running peak so
far**, not against the global maximum — which is why `cummax()` and not
`max()`. Returns the most negative value.

### HAND CHECK

Equity curve `[100, 120, 90, 110, 105]`:

```
point:      100    120     90     110     105
cummax:     100    120    120     120     120
drawdown:     0      0   −25%   −8.33%  −12.5%
```

`(90 − 120)/120 × 100 = −25%` is the worst → **−25.0**.

Note the deliberate trap in the fixture: the *lowest* equity point is 90 and
the *last* is 105, but the worst drawdown is measured from the 120 peak, not
from the start or the end.

### CONFIRM AGAINST THE CODE

```python
print(bot.max_drawdown_pct([100, 120, 90, 110, 105]))
```

Actual output: `-25.0`

## 5.5 `sharpe_sortino_ratios()` — L2689–2718

```python
mean_return = np.mean(bar_returns)
return_std  = np.std(bar_returns, ddof=1)
sharpe  = (mean_return / return_std) * np.sqrt(periods_per_year) if return_std > 0 else float("nan")

downside_returns   = np.minimum(bar_returns, 0.0)
downside_deviation = np.sqrt(np.mean(np.asarray(downside_returns) ** 2))
sortino = (mean_return / downside_deviation) * np.sqrt(periods_per_year) if downside_deviation > 0 else float("nan")
```

Three things a panelist may probe, answered up front:

1. **The risk-free rate is implicitly zero.** There is no `− r_f` term. Over
   a crypto window with this return magnitude the simplification is
   conventional, but it *is* a simplification and is disclosed as one.
2. **Sharpe uses `ddof=1`** (sample SD) but **Sortino's downside deviation
   uses the plain mean of squares** over *all* periods, with gains set to
   zero — not the SD of the negative subset. That is the standard Sortino
   construction: it penalises downside magnitude while keeping the
   denominator on the same period count as the numerator.
3. **Annualisation is `√(periods_per_year)`**, with
   `PERIODS_PER_YEAR_4H_BARS = 6 × 365.25 = 2191.5` (L2733) — six 4-hour bars
   a day, leap-year-averaged — and `PERIODS_PER_YEAR_WEEKLY = 52` for the
   weekly DCA arms.

### HAND CHECK — six bar returns

```
returns = 0.01, −0.02, 0.03, 0.00, −0.01, 0.02

mean = 0.03 / 6 = 0.005
deviations       = 0.005, −0.025, 0.025, −0.005, −0.015, 0.015
squares          = 0.000025, 0.000625, 0.000625, 0.000025, 0.000225, 0.000225
Σ = 0.00175      → ddof=1 → 0.00175 / 5 = 0.00035  →  SD = 0.018708287

√2191.5 = 46.813460

Sharpe  = (0.005 / 0.018708287) × 46.813460 = 0.267261 × 46.813460 = 12.511423

downside = min(r, 0) = 0, −0.02, 0, 0, −0.01, 0
squares  = 0, 0.0004, 0, 0, 0.0001, 0   → mean = 0.0005/6 = 0.000083333
downside deviation = √0.000083333 = 0.009128709

Sortino = (0.005 / 0.009128709) × 46.813460 = 0.547723 × 46.813460 = 25.640788
```

Sortino exceeds Sharpe here because two of six periods were negative and
their magnitudes were modest — exactly the asymmetry Sortino is built to
reward.

### CONFIRM AGAINST THE CODE

```python
rets = [0.01, -0.02, 0.03, 0.00, -0.01, 0.02]
print(bot.PERIODS_PER_YEAR_4H_BARS)
print(bot.sharpe_sortino_ratios(rets, bot.PERIODS_PER_YEAR_4H_BARS))
```

Actual output:

```
2191.5
(12.51142335171, 25.64078781940992)
```

---

# Part 5B — Applied analyses (L2722–3841)

Each function here applies Part 5's primitives to one question the paper
raises. `PERIODS_PER_YEAR_4H_BARS = 2191.5` and `PERIODS_PER_YEAR_WEEKLY = 52`
are defined at L2733–2734.

## 5B.1 `run_bootstrap_ci()` — L2737–2775

The paper's canonical interval. B = 10,000, seed = 42, resampling the
baseline's own 27 `pnl_pct` values at n = 27, then taking the 2.5th and
97.5th percentiles of the resample totals and means.

**Not hand-reproducible at B = 10,000** — the mechanism is verified at B = 4
in §5.2 instead. The full figure:

```python
print(bot.run_bootstrap_ci(t))
```

Actual output:

```
{'n': 27, 'b': 10000, 'seed': 42,
 'total_return_point_pct': 30.306456356031937,
 'total_return_ci_pct': [5.9866116295368155, 54.98658996206774],
 'avg_return_point_pct': 1.1224613465197013,
 'avg_return_ci_pct': [0.2217263566495117, 2.036540368965472],
 'pct_resamples_total_le_zero': 0.75, 'pct_resamples_avg_le_zero': 0.75}
```

→ the paper's **95% CI [+5.99%, +54.99%]** on total return. Two readings
worth having ready:

- **The interval excludes zero, but not by much at the low end.** +5.99% is
  the honest lower bound, and it should be quoted as often as the +30.31%
  point estimate.
- **`pct_resamples_total_le_zero = 0.75`** means 75 of 10,000 resamples
  (0.75%) came out at or below zero. That is a directly interpretable
  companion to the interval.

### The disclosed two-value CI

`docs/SCRATCH_RESULTS_METHODS.md` records that the bootstrap CI has **two
different, individually correct values** depending on which surface computes
it:

| Surface | B | PRNG | 95% CI |
|---|---|---|---|
| Python (this function) | 10,000 | numpy `default_rng`, seed 42 | **[+5.99%, +54.99%]** — the paper's canonical figure |
| Dashboard (`statsCompute.ts`) | 2,000 | JS mulberry32, seed 42 | [+7.48%, +54.46%] |

The root cause is **the B mismatch alone, not a logic bug** — verified by
porting the mulberry32 PRNG into Python and reproducing [+7.48%, +54.46%]
exactly at B = 2,000. Both values are reported and the gap is explained;
they are deliberately not unified into one number. This is the visible
product of the intentional Python↔TypeScript independence (§7).

## 5B.2 `run_benchmark_vs_buy_and_hold()` — L2778–2857

Strategy versus same-window BTC buy-and-hold on a 100-indexed basis.

The strategy's equity curve is **event-driven** (L2826–2833): flat between
trades, compounding only at each exit bar.

```python
equity_by_bar[0] = 100.0
for i in range(1, n_bars):
    if i in exit_pnl_by_bar:
        running_equity *= (1 + exit_pnl_by_bar[i] / 100)
    equity_by_bar[i] = running_equity
```

This is **exact, not an approximation**, and the reason is §3.10: the engine
never holds overlapping positions, so a sequential walk over exits cannot
miss or double-count anything.

The last block correlates each trade's own return against BTC's return over
that trade's identical holding window — a low or negative correlation
indicates the strategy is not merely capturing directional beta.

```python
print(bot.run_benchmark_vs_buy_and_hold(df, t))
```

Actual output (reformatted):

```
n_bars 8767
strategy      total_return_pct 30.306456  time_in_market_pct 2.634881
              bars_of_exposure 231        return_per_bar_pct 0.131197
              max_drawdown_pct -6.461922  sharpe 1.114203  sortino 2.727302
buy_and_hold  total_return_pct 87.652243  time_in_market_pct 100.0
              bars_of_exposure 8766       return_per_bar_pct 0.009999
              max_drawdown_pct -67.213929 sharpe 0.564186  sortino 0.803381
correlation   pearson_r -0.368753  n 27  p 0.058391
```

**Four things to be able to say about that block.**

1. **Buy-and-hold wins on raw return, 87.65% against 30.31%.** State it
   first, before the favourable numbers. The strategy's case is *never* a
   raw-return case.
2. **Time in market is 2.63% against 100%** — 231 exposed bars out of 8,767.
   Per exposed bar the strategy returns 0.131% against 0.0100%, about
   thirteen times more. That is the actual claim.
3. **Maximum drawdown −6.46% against −67.21%**, and Sharpe 1.114 against
   0.564. The edge is risk- and exposure-adjusted.
4. **Pearson r = −0.369, p = 0.058.** The trades are *mildly negatively*
   correlated with BTC's move over their own holding windows, and that is
   **not significant at α = 0.05**. Report it that way. It is suggestive that
   the strategy is not simply long beta; it is not proof.

**A reconciliation you should expect to be asked about.** This function
reports buy-and-hold at **+87.65%**, while §5B.6's passive benchmark reports
lump-sum buy-and-hold at **+90.07%**. Both are correct and they measure
different things: this one is **close-to-close** (`close.iloc[-1]` vs
`close.iloc[0]`), while `_run_lump_sum_dollar_arm` buys at the first bar's
**open** (L3699). A lower purchase price gives a higher return on the same
sale price. Neither figure is wrong; know which is which.

## 5B.3 `_iso_week_first_bars()` — L2860–2872 · `run_dca_blend_analysis()` — L2875–2993

`_iso_week_first_bars` returns the bar index of the first bar of every ISO
calendar week. It is a **single shared helper** used by both the DCA blend
and the passive benchmark's DCA arm, specifically so the two cannot drift
apart on contribution timing.

`run_dca_blend_analysis` models the paper's "complementary sleeve" question:
an investor already dollar-cost-averaging into BTC diverts 10%, 20% or 30% of
each weekly contribution into the strategy instead. For each split it builds
two portfolios — 100% DCA, and the blend — and compares Sharpe, Sortino and
drawdown.

Two methodological choices, both disclosed in the docstring:

1. **Returns are computed net of each period's own contribution** —
   `(value[k] − contribution[k]) / value[k-1] − 1` — so injected capital is
   never misread as investment return. This is the single most common error
   in DCA calculators, and it is avoided explicitly.
2. **Drawdown is reported two ways**: principal-inclusive percentage (the
   conventional DCA-calculator presentation) *and* a peak-to-trough
   cumulative-P&L retracement in **dollars**. A *percentage* drawdown on
   cumulative P&L is ill-defined early in the series, when P&L is near zero
   or negative, so the dollar figure is used there instead.

## 5B.4 `run_fee_slippage_sensitivity()` — L2996–3073

### WHAT THE PAPER CLAIMS HERE

The headline figures are **gross** — no transaction cost is modelled anywhere
in `simulate_trades()`. This function asks whether the significance
conclusions survive a realistic cost adjustment.

### WHAT THE CODE DOES

A flat round-trip percentage drag subtracted from each trade's `pnl_pct`,
then every headline statistic recomputed:

```python
fee_round_trip_pct      = 2 * taker_fee_bps * 0.01      # 2 × 5bps  = 0.10%
slippage_round_trip_pct = 2 * slippage_bps  * 0.01      # 2 × 5bps  = 0.10%
primary_round_trip_pct  = 0.20%
```

- **GROSS** (0.00%) — as currently reported.
- **FEE ONLY** (0.10%) — 5 bps/side taker, the confirmed Binance USDT-M
  Futures standard tier.
- **PRIMARY** (0.20%) — fees plus 5 bps/side conservative slippage.
- A legacy LOW/MID/HIGH band (0.14 / 0.24 / 0.40%) predating the confirmed
  fee figure, kept for comparison.

Fees and slippage are kept as **separate line items** because the fee is a
published exchange number and the slippage is an estimate. Blending them
would hide which half is evidence and which is judgement.

`flipped_trades` lists every trade that was a winner gross and a loser net —
the most honest single output of the whole function.

### HAND CHECK — three trades at the PRIMARY drag

Trades `+2.00%`, `+0.15%`, `−1.00%`; drag `0.20%`:

```
adjusted: 2.00 − 0.20 = +1.80
          0.15 − 0.20 = −0.05   ← flips from win to loss
         −1.00 − 0.20 = −1.20

total    = 1.80 − 0.05 − 1.20 = +0.55
wins     = 1 of 3  → 33.33%   (was 2 of 3 = 66.67% gross)
flipped  = the +0.15% trade
```

The 0.15% trade is deliberately chosen to sit just inside the drag. It shows
the mechanism that matters: cost sensitivity is concentrated entirely in the
trades whose gross margin is smaller than the drag.

### CONFIRM AGAINST THE CODE

```python
tp = pd.DataFrame({"entry_idx":[10,20,30], "pnl_pct":[2.0, 0.15, -1.0]})
for r in bot.run_fee_slippage_sensitivity(tp, include_legacy_sensitivity_band=False):
    print(r["label"][:28], r["drag_pct"], round(r["total_return_pct"],4),
          r["wins"], round(r["win_rate_pct"],4), r["flipped_trades"])
```

Actual output:

```
GROSS (no fees, no slippage  0.0 1.15 2 66.6667 []
FEE ONLY (confirmed 5.00bps/ 0.1 0.85 2 66.6667 []
PRIMARY: FEE (confirmed) + C 0.2 0.55 1 33.3333 [{'entry_idx': 20, 'gross_pnl_pct': 0.15, 'net_pnl_pct': -0.05000000000000002}]
```

On the real 27 trades the PRIMARY scenario takes the total from **+30.31%**
to **+24.91%** (`docs/SCRATCH_RESULTS_METHODS.md`) — the strategy stays
profitable under confirmed fees plus conservative slippage. That is the
sentence to have ready.

## 5B.5 `run_regime_breakdown()` — L3076–3170

Tags each trade by the macro regime at its entry bar, by **two independent
methods, both reported**:

1. **Calendar** — 2022 = bear, 2023 = chop, 2024+ = bull, the standard BTC
   cycle narrative for this window.
2. **Drawdown from all-time high** — BEAR ≤ −40%, CHOP −40% to −12%,
   BULL > −12%.

```python
running_ath = np.maximum.accumulate(np.concatenate([[ath_seed], df["close"].values]))[1:]
drawdown_pct = (df["close"].values / running_ath - 1.0) * 100.0
```

**The `ath_seed = 69000.0` is the detail to be ready to defend.** It is BTC's
actual 2021-11-10 all-time high, which **predates this dataset's first bar by
seven weeks**. Seeding the running ATH from the dataset's own first bar
instead would read early-2022 — already about 32% below the real high — as
"at the high," and would mislabel a large block of 2022 trades. The seed
imports one fact from outside the window, and that is disclosed rather than
buried.

The −40% / −12% thresholds are explicitly called a judgment call in the
docstring, stated so they can be re-argued.

The two methods **disagree on a meaningful fraction of trades**, and the
function returns `method_agreement` with the full disagreement list rather
than collapsing to one number. Reporting both is the honest choice: they
measure genuinely different things.

## 5B.6 `run_forward_oos_validation()` — L3173–3258 · **the one network call**

Pulls fresh candles live from Binance through a fixed, closed end date,
confirms the locked 27-trade baseline reproduces against the fresh pull, and
reports any trades entered after the locked window's end as genuinely
out-of-sample — those postdate every commit to the strategy code.

**It is off by default.** A bare `python research_analysis.py` never calls
it; only `--include-oos-live` does. Say this if asked whether results depend
on a live connection: they do not, and the flag exists precisely so that is
provable rather than promised.

## 5B.7 Paper-sync machinery — L3261–3525

`run_paper_sync_check()` (L3261), `_parse_claude_md_locked_results()`
(L3332), `_PaperSyncCheck` (L3368) and `generate_paper_sync_report()`
(L3398) recompute the headline figures and diff them against the locked
values, writing `artifacts/paper_sync_report.md`. `--serve` regenerates it
on every run and prints a warning if any mismatch appears.

This is a *guardrail*, not an analysis. Its value is that a number cannot
drift silently between the code and the write-up.

## 5B.8 The formulation window — L3526–3606

`load_formulation_period_window()` (L3526) takes a fixed prefix of
`artifacts/candles_extended.json` and **asserts** its last bar is
`2022-01-01 04:00:00` — one bar before the locked window begins:

```python
assert last_open_time == "2022-01-01 04:00:00", (
    f"expected the formulation-period slice to end at 2022-01-01 04:00:00 ...")
```

That assertion is the guard against the two windows silently overlapping.

**The 2018–2022 window is NOT out-of-sample.** It is the period the strategy's
rule *structure* was originally formed against. It is reported for
comparison, and every reference to it must carry that caveat. It is also
where the paper's disclosed data-completeness gap lives: 8,750 rows against
8,767 expected, seventeen candles missing across eight exchange-side outages,
the largest a run of seven (source: the paper's Methodology → *Data*; this
figure is not carried in `docs/SCRATCH_RESULTS_METHODS.md`). No figure from
the primary window is affected.

`reconcile_formulation_window_trades()` (L3555) cross-checks the trades
computed here against the already-published figures in
`artifacts/oos_validation_analysis.json`.

## 5B.9 The three dollar arms — L3608–3714

| Function | Line | Arm |
|---|---|---|
| `_run_strategy_dollar_arm` | 3608 | capital idle between trades, compounding at each exit |
| `_run_dca_dollar_arm` | 3652 | capital split evenly across every ISO week, bought at that week's first-bar **close** |
| `_run_lump_sum_dollar_arm` | 3695 | all capital deployed at the window's first bar's **open**, held |

**The `final_capital` / `total_return_pct` distinction (L3640–3646).** In the
strategy arm, `final_capital` is the real terminal value of the compounded
sequential curve, **not** back-derived from `total_return_pct`. The two
differ because `total_return_pct` is a simple *sum* of `pnl_pct` (matching
the locked headline convention) while the curve compounds multiplicatively.
Both are shown; they are never reconciled. On the real data that is +30.31%
summed versus $13,417.77 terminal on $10,000 — a compounded +34.18%.

**Where the drag is applied** differs by arm, and the asymmetry is deliberate:
the strategy arm takes a **round-trip** 0.20% per trade, while the DCA and
lump-sum arms take a **one-sided** 0.10% markup on the purchase price only —
because those arms are *held*, not round-tripped, within the window.

### HAND CHECK — the DCA arm over three ISO weeks

Six bars spanning three ISO weeks, prices 100, 110, 120, 130, 140, 150, with
$300 starting capital:

```
ISO weeks:  2022-01-03/05 → W1   2022-01-10/12 → W2   2022-01-17/19 → W3
first bar of each week: indices 0, 2, 4
contribution = 300 / 3 = $100 per week

units bought:  100/100 = 1.000000
               100/120 = 0.833333
               100/140 = 0.714286
                 total = 2.547619

final value = value at the LAST CONTRIBUTION BAR (index 4, price 140)
            = 2.547619 × 140 = $356.666667
total return = (356.666667 − 300) / 300 × 100 = +18.888889%
```

**Note the subtlety, because it is a real convention and a fair question:**
the arm's final value is read at the last *contribution* bar (index 4), not
at the last bar of the data (index 5). The period-return series is defined
on contribution bars, so the terminal value is taken on the same grid. On
8,767 bars the effect is a fraction of one week; on this six-bar fixture it
is visible, which is exactly why the fixture is built this way.

The lump-sum arm buys at bar 0's **open** = 100 → 3 units → 3 × 150 = $450 →
**+50%**.

### CONFIRM AGAINST THE CODE

```python
dts = pd.to_datetime(["2022-01-03","2022-01-05","2022-01-10",
                      "2022-01-12","2022-01-17","2022-01-19"])
d5 = pd.DataFrame({"open_time":dts,"open":[100,110,120,130,140,150],
                   "high":[0]*6,"low":[0]*6,
                   "close":[100,110,120,130,140,150],"volume":[1]*6})
print(bot._iso_week_first_bars(d5).tolist())
a = bot._run_dca_dollar_arm(d5, 300.0);        print(a["total_return_pct"], a["final_capital"], a["n_contributions"])
b = bot._run_lump_sum_dollar_arm(d5, 300.0);   print(b["total_return_pct"], b["final_capital"])
```

Actual output:

```
[0, 2, 4]
18.888888888888893 356.6666666666667 3
50.0 450.0
```

## 5B.10 `run_benchmark_vs_passive()` — L3716–3782

Assembles the three arms into the paper's head-to-head table, for two
windows, gross and fee-adjusted. From
`docs/SCRATCH_RESULTS_METHODS.md`, $10,000 per arm:

**2022–2026 (locked window), gross**

| Arm | Return | Terminal | Sharpe | MaxDD | Time in market |
|---|---|---|---|---|---|
| OB-gated strategy | +30.31% | $13,417.77 | 1.114 | −6.46% | **2.63%** |
| Weekly DCA into BTC | +123.13% | $22,312.94 | 0.556 | −27.85% | 100% |
| Lump-sum buy & hold | +90.07% | $19,007.32 | 0.564 | −67.21% | 100% |

Fee-adjusted strategy: **+24.91% → $12,719.01**.

**2018–2022 (formulation period, NOT out-of-sample)**

| Arm | Return | Terminal |
|---|---|---|
| Strategy | +21.82% | $12,282.53 |
| DCA | +439.88% | $53,987.55 |
| Lump-sum | +236.96% | $33,696.49 |

**Both passive arms beat the strategy on raw terminal value in both
windows.** That is the result, and it is reported as the result.
`docs/SCRATCH_RESULTS_METHODS.md` states the rule directly: *any statement of
the strategy "beating" DCA or BTC must carry the exposure-time caveat (2.63%
vs 100%) in the same sentence.* The defensible claim is about return per unit
of exposure and per unit of drawdown, not about terminal wealth.

## 5B.11 `build_trades_and_results_table()` — L3785–3838

Assembles the per-trade table (sorted by `entry_idx`, with resolved
timestamps) and the extended results summary — the base `trade_stats` plus
wins, losses, SD and the binomial p — for one window. This is what the Sheets
export and the artifact writer both consume, so the spreadsheet and the JSON
cannot disagree.

---

# Part 6 — Artifact export + database persistence (L3842–4293)

*Light depth, with one check worth running.*

## 6.1 What it writes

`export_dashboard_artifacts()` (L3971) is the workhorse. Per run it produces:

| File | Line | Contents |
|---|---|---|
| `artifacts/manifest.json` | 4064 | run parameters + candle count |
| `artifacts/candles.json` | 4066 | every bar with indicators |
| `artifacts/threshold_runs.json` | 4068 | summary per quality level |
| `artifacts/runs_by_threshold.json` | 4070 | OBs + trades + stats per level |
| `artifacts/verification_report.json` | 4072 | SHA-256 hashes and source checks |
| `artifacts/candles.csv` | 4076 | the CSV `load_candles()` reads back |
| `artifacts/threshold_runs.csv` | 4077 | flat summary |
| `artifacts/trades_default_view.csv` | 4079 | the default-quality trade log |
| `artifacts/orderblocks_default_view.csv` | 4080 | the default-quality OB list |

and `write_statistical_artifacts()` (L4258) adds four more:
`bootstrap_power_analysis.json`, `fee_slippage_analysis.json`,
`ablation_reconstruction.json`, `benchmark_vs_passive.json`.

> **A gotcha worth knowing before a live demo.** `--serve` **rewrites**
> `artifacts/candles.csv`. Running it re-pulls candles and overwrites the
> cache the offline pipeline reads. Also note that
> `trades_default_view.csv` is the **default view quality** (1 by default),
> not the q≥0 baseline — that CSV holds a different trade count than 27.
> Quoting a number off the wrong CSV during a defense is an avoidable
> mistake.

## 6.2 The verification report (L3920–3968)

`hash_payload()` (L3896) takes a SHA-256 over a canonical JSON encoding —
sorted keys, no whitespace — so two independently generated exports can be
compared by hash rather than by diffing the full payload.
`build_verification_report()` hashes the OHLC series, the indicator series,
and each quality level's Order Blocks, trades and stats separately, so a
mismatch localises to a specific payload rather than just failing.

**CHECK — reproducibility, in one line**

```python
c = [{"time":1,"open":1.0,"high":2.0,"low":0.5,"close":1.5}]
print(bot.hash_payload(c) == bot.hash_payload(c), bot.hash_payload(c)[:16])
```

The hash is deterministic across processes and machines because the encoding
is canonical. That is the whole mechanism: same data in, same hash out, from
anyone's copy of the repository.

## 6.3 `to_native()` (L3867) and `normalize_records()` (L3890)

Per-cell numpy→Python conversion while building record dicts. See §1.4 for
why this is *not* the same function as `json_safe()`.

## 6.4 `push_all_gsheet_exports()` (L4203)

Calls the three Sheets pushes in sequence. **Every push is non-fatal**: a
failure in one is reported and skipped, never aborting the rest. That is
deliberate — a credentials problem should not cost you an artifact export.

---

# Part 7 — HTTP server (L4294–4563)

*Light depth. Serves already-computed data.*

`DashboardRequestHandler` (L4312) extends Python's built-in static file
server. Static mapping: `dashboard-v2/dist/` under `/dashboard/`, and
`artifacts/*.json|csv` as plain files. An unknown sub-path under
`/dashboard/` falls back to `index.html` (L4329–4333) — the standard SPA
convention; this app keeps its tabs in React state rather than in the URL, so
a hard reload on a sub-path should not 404.

| Route | Method | Handler | Line |
|---|---|---|---|
| `/api/iterations` | GET | `handle_get_iterations` | 4405 |
| `/api/get_theme` | GET | `handle_get_theme` | 4463 |
| `/api/trades…` | GET | `handle_get_trades` | 4354 |
| `/api/push_gsheet` | POST | `handle_push_gsheet` | 4500 |
| `/api/save_theme` | POST | `handle_save_theme` | 4486 |

`run_dashboard_server()` (L4514) starts a threaded server on port 8765, binds
to `127.0.0.1` by default (loopback only, so a native run is not reachable
from the LAN), and honours `DASHBOARD_HOST` — which the Dockerfile sets to
`0.0.0.0`, because `docker run -p` does not forward to a container's loopback
interface.

## THE INDEPENDENCE RULE — the most important paragraph in Part 7

**The dashboard recomputes its statistics in TypeScript, from the exported
per-trade data, and never imports a Python-computed statistic.**
`dashboard-v2/src/components/stats/statsCompute.ts` and `statMath.ts`
independently implement the win rate, the one-sided binomial test,
Pearson/Spearman correlation and a percentile bootstrap CI.

That is **an intentional cross-check, not duplicated effort.** Two
independent implementations, in two languages, computing the same statistics
from the same trade data, and agreeing — which is a far stronger claim than
one implementation agreeing with itself.

The bootstrap CI gap documented in §5B.1 is the *visible product* of that
independence: the two surfaces use different B and different PRNGs, and the
project reports both values with the cause identified, rather than forcing
them to match. **Never make the JS side import from Python.** Doing so would
destroy the only genuine cross-validation in the project.

---

# Part 8 — CLI and main (L4564–4847)

## 8.1 `run_full_analysis_pipeline()` — L4568–4750

The default entrypoint. Loads data, runs the OB-gated baseline, runs the
three-arm ablation, then runs every Section 5/5B analysis against the
baseline trade log, printing each through `report_stat()` and returning one
results dict.

**Offline by default.** Every step runs against the committed
`artifacts/candles.csv` and `artifacts/candles_extended.json`. The one
exception, `run_forward_oos_validation()`, runs only with
`include_oos_live=True`.

## 8.2 `run_serve_mode()` — L4752–4800

The `--serve` path, in order:

1. `export_dashboard_artifacts(...)` — artifacts + database rows.
2. `generate_paper_sync_report(...)` — writes
   `artifacts/paper_sync_report.md`, printing a **warning** if any figure
   mismatches the locked results.
3. `write_statistical_artifacts(...)` — the four analysis JSON files.
4. `run_dashboard_server(port=8765)` — unless `--no-server`.

Steps 2 and 3 are each wrapped in `try/except` and degrade to a warning; a
failure there must not cost you the artifact export.

> **Noted inefficiency.** `--serve` re-simulates the formulation window more
> than once across these steps. It is wasted CPU, not a correctness problem —
> `simulate_trades()` is deterministic, so every repetition produces the same
> trades. Left as-is during the paper freeze; noted here so it is not
> mistaken for something meaningful.

## 8.3 The flags — L4806–4832

| Flag | Default | Effect |
|---|---|---|
| `--serve` | off | export artifacts + DB, then start the dashboard server |
| `--include-oos-live` | off | **the only flag that enables a network call** |
| `--bootstrap-n` | 10000 | B for the canonical CI |
| `--seed` | 42 | RNG seed for all bootstrap resampling |
| `--json-out` | none | write every section's results to one JSON file |
| `--symbol` / `--timeframe` | BTCUSDT / 4h | |
| `--start` / `--end` | 2022-01-01 / 2026-01-01 | the locked window |
| `--levels` | `0,1,2,3` | quality levels to export |
| `--default-view-quality` | 1 | which level the dashboard opens on |
| `--output-dir` | `artifacts` | |
| `--export-gsheet` | off | push the three Sheets exports |
| `--db-url` | none | SQLAlchemy URL; else `sqlite:///backtest_results.db` |
| `--no-server` / `--no-browser` | off | suppress the server / the browser tab |

L4835 coerces `--levels` from a comma string to a list of ints and forces
`--default-view-quality` into that list if it was not already there.

## 8.4 The dispatch — L4839–4847

```python
if cli_args.serve:
    run_serve_mode(cli_args)
else:
    run_full_analysis_pipeline(include_oos_live=..., bootstrap_resamples=..., seed=..., json_out=...)
```

Two paths. That is the entire top-level control flow of a 4,847-line file.

---

# Appendix A — Every hand check, in one table

Run the §0.2 loader first. Each row's expected value was produced by running
the real function on that exact input.

| § | Module | Input | Hand-derived value | Code output |
|---|---|---|---|---|
| 1.3 | headline consistency | 27 trades | 19 wins; 70.37%; 1.12% avg | `27 19 70.37037… 30.30645… 1.12246… 2.41013…` |
| 2.1 | `load_candles` | the locked CSV | 1461 days × 6 + 1 = 8,767 | `8767 … 1461` |
| 3.1A | `compute_indicators` MACD | 6 closes | hist[1] = 0.127635 | `0.127635` |
| 3.1B | `compute_indicators` KDJ | 6 H/L/C | K[1] 51.515152, D[1] 50.505051, J[1] 53.535354 | identical |
| 3.1C | `compute_indicators` ATR | 4 H/L/C, period 3 | TR 5,7,5,8; ATR[3] 6.666667; ATR200[3] 6.25 | identical |
| 3.2 | `compute_smc` | 12 synthetic bars | 1 DEMAND, top 103, bottom 98, ob_bar 5, created_at 8, BOS/internal, mitigated 12 | identical |
| 3.3 | OB quality criteria | same 12 bars | F/T/T/T/T → composite 4 | identical |
| 3.5 | `kdj_reset_init/update` | entry 5, ob_bar 2 | w = 3; k 57.141913, d 54.858586, armed True | identical |
| 3.5 | `w` on real data | 27 trades | — | `14 439 74.0` |
| 3.7 | LONG/SHORT entry gates | real trade @ i=335 | all 8 gates pass; risk 2.311%, R:R 4.085 | trade record matches |
| 3.8 | exit ladder | 27 trades | — | `ATR 9, TRAILING 8, KDJ 8, SL 2` |
| 4.5 | `summarize_trade_pool` | 3 trades | n 3, wins 2, 66.6667%, total 1.15, sd 1.513550 | identical |
| 5.1 | `binomial_test` | 4/5 and 19/27 | 0.1875 / 0.375; 0.0261195 / 0.0522390 | identical |
| 5.2 | `bootstrap_resample` | 5 values, B=4, seed 7 | totals 5, −2, 12, 6; p2.5 −1.475 | identical |
| 5.3 | `pearson_correlation` | 4 (x,y) pairs | r = 3.0/5.0 = 0.6 | `0.6` |
| 5.4 | `max_drawdown_pct` | 5-point curve | −25.0 | `-25.0` |
| 5.5 | `sharpe_sortino_ratios` | 6 returns | 12.511423 / 25.640788 | `12.51142335171, 25.64078781940992` |
| 5B.4 | `run_fee_slippage_sensitivity` | 3 trades, 0.20% drag | total +0.55, 1 win, 1 flip | identical |
| 5B.9 | `_run_dca_dollar_arm` | 3 ISO weeks, $300 | 2.547619 units → $356.666667, +18.888889% | identical |
| 5B.9 | `_run_lump_sum_dollar_arm` | same 6 bars | 3 units → $450, +50% | identical |

# Appendix B — Known imperfections, all disclosed

Volunteering these is stronger than being caught by them.

| # | What | Where | Status |
|---|---|---|---|
| 1 | ATR code comment says "Wilder's RMA"; the code computes a **plain rolling mean** | L592–605 | Paper reports the rolling mean, and discloses the stale comment. Code and paper agree; the comment does not. |
| 2 | FVG/displacement forward searches could read 1–2 bars past the confirmation bar | `_build_order_block_from_crossover` | **Fixed** (`cb4ed93`), guarded by runtime asserts. Does not move the q≥0 baseline. |
| 3 | Correlation p-values once reported as `p < 0.001` | two draft documents | **Corrected** to 0.0094 / 0.0113. |
| 4 | Bootstrap CI has two values: [+5.99, +54.99] Python vs [+7.48, +54.46] dashboard | §5B.1 | Cause identified (B mismatch alone). Both reported; deliberately not unified. |
| 5 | Ablation arms' 140/138-trade pools are not reproducible from committed code | §4.2 | Disclosed. Reconstruction prints MATCH/DIVERGE; a DIVERGE is expected. |
| 6 | "190 qualifying signals" denominator | paper | **Open question.** Derived using the ablation's stop rule, not the OB-gated strategy's. Do not cite as settled. |
| 7 | 2018–2022 formulation window has 8,750 of 8,767 expected rows | §5B.8 | Disclosed. 17 candles across 8 exchange outages. No primary-window figure affected. |
| 8 | Entry predicate exists in 4 places, exit ladder in 4 | §3.10 | Intentional (ablation isolation); consolidation deferred until after the paper freeze. |
| 9 | `load_extended_candles_window` (L489–517) has zero callers | §2.2 | Dead code, identified. Left in place to avoid touching the file during freeze. |
| 10 | `--serve` re-simulates the formulation window more than once | §8.2 | Wasted CPU only; `simulate_trades()` is deterministic. |
| 11 | Risk-free rate implicitly zero in Sharpe/Sortino | §5.5 | Conventional for this window; disclosed as a simplification. |
| 12 | The SMC cache key is `(length, last close)` | §3.10 | Safe for every caller in this file; would be unsafe as a general-purpose cache. |

---

*Generated for the ISEF defense of "Harnessing Bitcoin Volatility." Every
figure in this guide is traceable to `docs/SCRATCH_RESULTS_METHODS.md` or to
a REPL block printed above it.*
