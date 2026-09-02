# Study Guide — Content Handoff

**Deliverable this feeds:** a single interactive HTML/React artifact — a
plain-language, heavily-visual study and defense-prep guide covering
methodology → results → discussion for the ISEF paper *"Harnessing Bitcoin
Volatility: Backtesting an Integrated Algorithmic Strategy Combining KDJ,
MACD, and Smart Money Concepts."*

**This file is source material, not the artifact.** It carries the complete
content, every real figure with its source, and a specification for every
visual. The artifact is built separately from this file alone.

**Prepared:** 2026-08-21 · branch `development` · HEAD `7154d43` (working
tree dirty — see §9.3)

---

## 0. Instructions for whoever builds the artifact

### 0.1 Audience and voice — this governs everything

The reader is **the student who did this work**, preparing to explain it
cold, and secondarily an ISEF-panel-adjacent audience. Write for a smart
newcomer, not a statistician.

Hard rules:

1. **Define every technical term the first time it appears**, in one or two
   plain sentences, before or immediately after first use. After that, use it
   normally. The full first-use list is in §8.
2. **Prefer a concrete analogy to a formal definition** where the analogy is
   genuinely accurate. Example: a p-value is "how surprising this result would
   be if the strategy had no edge at all," not "the probability of observing a
   test statistic at least as extreme as…"
3. **Do not oversimplify into wrongness.** Explain the precise thing in
   accessible words. Where a caveat is load-bearing (exposure time, sample
   size, cost sensitivity), the caveat travels in the same breath as the
   claim — never in a footnote.
4. Active voice. Short sentences. No filler, no throat-clearing.
5. **Report the unfavorable results as plainly as the favorable ones.** DCA
   beat the strategy. The out-of-sample test lost money. The significance
   claim dies under realistic fees. These are in the guide because they are in
   the paper.

### 0.2 Visual-first rule

A paragraph that describes a *structure*, a *sequence*, or a *comparison*
must be replaced by, or paired with, a graphic organizer. Every visual in
this handoff is specified in a block like this:

> **VISUAL V-n — Name**
> **Type:** flowchart | SVG diagram | table | callout | comparison card
> **Shows:** the one idea it must communicate
> **Data:** exact values, with source
> **Build notes:** layout, labels, what must be legible

There are **33 specified visuals**. They are not decorative — each one
replaces prose that would otherwise be harder to follow.

### 0.3 Section order

1. The big picture — what is actually being asked (§1)
2. Methodology (§2)
3. Codebase architecture (§3)
4. The statistical toolkit (§4)
5. Results — the 20 locked figures (§5)
6. Discussion and the two disclosed divergences (§6)
7. The Displacement inclusion question (§7)
8. Glossary (§8)
9. Source and verification appendix (§9)

### 0.4 Numbers policy

Every number in this handoff was pulled from a committed artifact or
recomputed live during preparation of this file. §9 maps each one to its
source. **Do not round differently, restate from memory, or add a figure
that is not in §9.** If the artifact needs a number that is not here, it does
not go in.

---

## 1. The big picture — what this research actually asks

### 1.1 The one-sentence version

> Bitcoin's price swings violently. This study asks whether a **fixed set of
> mechanical rules** — no human judgment, no discretion — could have picked
> entry and exit points on Bitcoin over four years and beaten a coin flip,
> and whether the structural "quality" of the price zones it traded off
> mattered.

### 1.2 The formal research question (from the paper, §0)

> Does a rule-based entry/exit strategy that gates MACD and KDJ momentum
> signals through Smart Money Concepts (SMC) Order Block structural zones
> produce a historical win rate and return on BTC/USDT 4-hour candles that
> departs from a zero-edge (50% win probability) null model, and does OB
> "quality" (a 5-criterion structural score) modulate that departure?

**Unpacked for a newcomer, term by term:**

| Phrase in the question | What it means plainly |
|---|---|
| *rule-based* | A computer program decides. Every condition is written down in advance. Run it twice, get the same answer twice. |
| *MACD and KDJ momentum signals* | Two standard indicators calculated from price history. They try to detect "this move is losing steam" or "this move is picking up." |
| *gates … through Order Block zones* | The momentum signal alone is not enough. Price must *also* be sitting inside a specific structural price zone before a trade is allowed. The zone acts as a filter — a gate. |
| *BTC/USDT 4-hour candles* | The price data. Each row summarizes 4 hours of Bitcoin trading: open, high, low, close, volume. |
| *departs from a zero-edge (50%) null model* | The comparison baseline is a coin flip. If the rules have no skill, roughly half the trades win. The test asks whether the real result is far enough from half to be surprising. |
| *does OB "quality" modulate that departure* | Each zone gets scored on five structural features. Second question: do the higher-scoring zones actually produce better trades? |

### 1.3 What this study is, and what it is not

> **VISUAL V-1 — Is / Is Not card pair**
> **Type:** two-column comparison card, visually distinct (e.g. green-tinted / amber-tinted)
> **Shows:** the scope boundary, before any methodology detail
> **Data:**
>
> **This IS:** a historical backtest · a fixed, pre-registered rule set · a
> scientific artifact built for auditability · a study that reports its own
> failures and correction history
>
> **This is NOT:** a live trading system · financial advice · a
> profit-maximization exercise · a parameter search (nothing was tuned,
> swept, or optimized) · a claim that the strategy beats buy-and-hold
>
> **Build notes:** keep it to short phrases, no sentences. This card sets
> expectations for the whole guide, so it should sit high on the page.

**Define here (first use):**

- **Backtest** — running a trading rule over price history that already
  happened, to see what it *would* have done. It is a simulation, not a
  track record.
- **Pre-registered** — the rules and their numeric settings were fixed
  *before* measuring results, and never adjusted afterward to make the
  results look better. This is what separates a test from a fishing
  expedition.

### 1.4 Why "no tuning" is the central methodological commitment

If you are allowed to keep adjusting the rules until the backtest looks
good, you will always produce a good-looking backtest — and it will mean
nothing. The repository enforces this structurally: parameters are constants
at the top of the code, a golden-master regression test fails if any locked
result moves, and every headline figure is checked against a committed list
on every run.

> **VISUAL V-2 — The overfitting trap**
> **Type:** two-path flowchart, side by side
> **Shows:** why parameter freezing is the load-bearing choice
> **Data:** no numbers — conceptual
> **Build notes:**
> Left path (red, labeled "What we did NOT do"): Try rules → Bad result →
> Adjust a threshold → Try again → *(loop back)* → Good-looking result →
> **Meaningless: the result was manufactured by the search**
> Right path (green, "What this study did"): Fix all 8 parameters → Run once
> → Report whatever comes out → **Result means something, good or bad**
> Draw the loop arrow on the left path prominently — the loop *is* the
> problem.

### 1.5 The honest headline

> **VISUAL V-3 — The three-part headline callout**
> **Type:** three stacked callout bars — green / amber / red
> **Shows:** the whole result in one glance, with the caveats attached
> **Data:**
> - **Green (holds up):** 27 trades, 70.37% win rate, +30.31% total return.
>   The return finding survives a bootstrap stress test — 99.25% of 10,000
>   resamples were positive.
> - **Amber (fragile):** The win-rate significance claim (p = 0.026) survives
>   trading fees alone, but flips to non-significant (p = 0.124) once
>   realistic slippage is added.
> - **Red (unfavorable, reported anyway):** Simply dollar-cost-averaging into
>   Bitcoin over the same window returned +123.13% — far more than the
>   strategy's +30.31%. And the only genuinely forward-looking test (4 trades
>   in 2026) lost money.
>
> **Build notes:** these three must appear together. Never render the green
> bar alone.

---

## 2. Methodology

### 2.1 The data

| Property | Value | Plain meaning |
|---|---|---|
| Asset | BTC/USDT | Bitcoin priced in a dollar-pegged stablecoin |
| Source | Binance `get_klines` REST endpoint | The exchange's own historical price API |
| Timeframe | 4-hour candles | Each row = 4 hours of trading |
| Window | 2022-01-01 08:00 → 2026-01-01 08:00 | Four calendar years |
| Rows | **8,767 bars** | See the arithmetic below |
| Gaps | None | Every gap between consecutive rows is exactly 4 hours |
| Timestamp convention | UTC+8 | Binance's raw millisecond timestamp, shifted +8 hours. Must be stated whenever a specific bar time is quoted. |
| Storage | `artifacts/candles.csv`, `artifacts/candles.json`, `backtest_results.db` | Flat files plus a SQLite database |

**Define (first use):**

- **Candle** — one row of price data covering a fixed time slice, recording
  four prices (open, high, low, close) plus volume. Drawn as a rectangle with
  a line through it: the body spans open-to-close, the wick spans low-to-high.
- **Volume** — how much Bitcoin changed hands during that slice.

**The 8,767 figure is worth showing, because the paper originally got it
wrong.** The first draft said 8,760, which was a plain arithmetic slip.

> **VISUAL V-4 — Why 8,767 and not 8,760**
> **Type:** stepped arithmetic diagram (each step a labeled box, arrow to the next)
> **Shows:** the bar-count derivation, including the leap day and the
> inclusive endpoint
> **Data:**
> 2022 (365 days) + 2023 (365) + 2024 (**366 — leap year**) + 2025 (365) =
> **1,461 days** → × 6 bars/day (24h ÷ 4h) = **8,766 intervals** → **+1**
> because the final boundary bar is stored as its own row, not used only as
> an exclusive endpoint → **8,767 rows**
> **Source:** live recompute, `len(load_candles())` = 8767
> **Build notes:** highlight the leap-day box and the +1 box in a different
> color — those are the two places the original arithmetic went wrong. Add a
> small caption: *"The paper's original 8,760 was corrected. Do not trim
> bars to make the number rounder."*

### 2.2 The three indicators

An **indicator** is a number calculated from recent price history, used to
summarize something a chart shows visually.

> **VISUAL V-5 — Indicator anatomy, three panels**
> **Type:** stacked SVG panel diagram (illustrative, not real data)
> **Shows:** what each indicator looks like and what it is for
> **Data:** conceptual — draw a stylized price series across the top, then
> three aligned sub-panels beneath it
> **Build notes:**
> - Panel 1, **MACD** — two lines converging/diverging plus a histogram of
>   bars above/below zero. Caption: *"Momentum. Bars below zero and shrinking
>   = downward pressure easing."*
> - Panel 2, **KDJ** — three oscillating lines bounded roughly 0–100 with
>   marked zones. Caption: *"Overbought / oversold timing. K below 50 and
>   rising = recovering from a dip."*
> - Panel 3, **ATR** — a single smooth line that rises when the price series
>   above gets choppy. Caption: *"Volatility, in dollars. How far price
>   typically travels in one bar."*
> Align all panels to the same x-axis so the reader sees they are three
> readings of one price series.

**MACD (12, 26, 9) — "is the momentum turning?"**

Take two exponential moving averages of the closing price — a fast one (12
bars) and a slow one (26 bars). Subtract them. When the fast average pulls
away from the slow one, price is accelerating; when they converge, it is
stalling. A third average (9 bars) of that difference is the "signal line,"
and the gap between them is the **histogram**. The strategy reads the
histogram only.

- **Exponential moving average (EMA)** — a rolling average that weights
  recent bars more than old ones, so it reacts faster than a plain average.
- `adjust=False` in the code means the EMA is **causal**: bar *t*'s value
  uses only bars up to *t*. No peeking ahead.

**KDJ (9, 3, 3) — "is this overbought or oversold?"**

Ask where the current close sits inside the high/low range of the last 9
bars, as a percentage (0 = at the bottom of the range, 100 = at the top).
That is the **RSV**. Smooth it once to get **K**, smooth K again to get
**D**, then compute **J = 3K − 2D**, an amplified line that overshoots and so
reacts sooner.

**ATR (14) and ATR (200) — "how violent is this market right now?"**

For each bar, compute the **true range**: the largest of (high − low),
|high − previous close|, |low − previous close|. Average it over 14 bars for
short-term volatility, and over 200 bars for a long-term baseline. ATR is in
price units, so "1.5 × ATR" means "1.5 typical bar-moves of room."

> **Precision note the artifact must preserve:** a comment in the code says
> the ATR uses *Wilder's smoothing (RMA)*, but the executed line is a plain
> rolling mean — a **simple moving average**. The paper correctly describes
> the SMA. The comment is wrong; the code and paper are right. This is
> disclosed, not hidden, and it changes no figure.
> *(Source: `research_analysis.py:592-596`; paper §1.2.)*

**ATR does double duty:** ATR(14) sizes stop-losses and drives two exit
rules; ATR(200) is the yardstick for the volatility-regime filter and for two
of the five quality criteria.

### 2.3 Order Blocks — the structural gate

This is the part of the strategy that is not a standard indicator, and the
part most worth a diagram.

**Define (first use):**

- **Order Block (OB)** — the last candle before a decisive move that breaks
  through a prior price level. The idea from Smart Money Concepts trading:
  large players accumulated positions in that candle's price range, so if
  price returns there later, that range may act as support or resistance
  again. In this study it is simply a **price zone with a birth certificate**
  — an origin bar and a confirmation bar.
- **Smart Money Concepts (SMC)** — a family of chart-structure trading ideas
  focused on where large orders likely sit. The detection code here is a
  faithful translation of the widely-used LuxAlgo TradingView indicator, so
  the zone definition is not this study's invention.
- **DEMAND OB** — a zone below price, a candidate place to buy (go LONG).
- **SUPPLY OB** — a zone above price, a candidate place to sell short.

**How one is detected, in four steps:**

1. **Find a pivot.** A bar is a *pivot high* if its high is strictly greater
   than every high in the bars that follow it, up to the current bar. It can
   only be confirmed after those later bars exist — which is exactly why the
   confirmation lag matters.
2. **Watch for a structure break.** If a later close crosses that pivot
   level, structure has broken. If it continues the existing trend it is a
   **Break of Structure (BOS)**; if it reverses the trend it is a **Change of
   Character (CHoCH)**.
3. **Name the Order Block.** Scan back from the pivot to the breaking bar and
   pick the extreme candle. Its high/low become the zone's top and bottom.
4. **Score it** on five quality criteria (§2.4).

Two bar indices matter and are easy to confuse:

| Index | Name in code | What it is |
|---|---|---|
| The origin candle | `ob_bar` | Where the zone's own extreme candle sits |
| The confirmation candle | `created_at` | Where the breakout candle *closes* — the OB is not usable for entry until strictly after this bar |

**The zone dies two ways:** it expires after **500 bars**
(`MAX_ORDER_BLOCK_AGE_BARS`, ≈ 83 days), or price closes straight through it
(`mitigated_at`).

**Two passes run over the same price series** with different pivot
sensitivities: *internal structure* (5-bar lookback, catches small local
swings) and *swing structure* (50-bar lookback, catches major turns). Both
contribute Order Blocks.

**Result: 761 Order Blocks detected across the window.**

> **VISUAL V-6 — Anatomy of an Order Block**
> **Type:** illustrative SVG price chart (hand-built candles, not real data)
> **Shows:** the pivot → break → zone sequence, plus the two bar indices
> **Data:** conceptual. Draw ~12 candles left to right.
> **Build notes:**
> - Mark one candle high with a dashed horizontal line labeled **"pivot high
>   — confirmed only after later bars fail to exceed it."**
> - Show a later strong bullish candle closing *above* that line; label it
>   **"structure break (BOS / CHoCH) — bar `created_at`."**
> - Shade the origin candle's high-to-low range as a translucent rectangle
>   extending rightward; label it **"DEMAND Order Block"** and mark that
>   candle **`ob_bar`**.
> - Add a later candle whose low dips into the rectangle, labeled **"price
>   returns to the zone → entry becomes possible (if every other filter
>   agrees)."**
> - Per the project's established visual convention: **Order Blocks are
>   rectangles, never arrows.**

> **VISUAL V-7 — BOS vs CHoCH**
> **Type:** two small side-by-side SVG chart snippets
> **Shows:** the difference between the two structure-break types
> **Data:** conceptual
> **Build notes:** Left = **BOS**: price already trending up, breaks another
> high, trend continues. Right = **CHoCH**: price trending down, then breaks
> a swing high, trend flips. One line of caption each. This distinction is
> stored per-OB and is worth 30 seconds of a panel's attention, no more.

### 2.4 The five orthogonal quality criteria

**Define (first use):**

- **Orthogonal** — independent of each other. Each criterion is evaluated on
  its own and can be true or false regardless of the others. This matters
  because of a real bug that was found and fixed (§2.7): the original scoring
  scheme made higher-scoring zones *nested subsets* of lower-scoring ones, so
  "higher quality" and "different sample" were tangled together and no clean
  claim could be made.

Each of the 761 Order Blocks is scored on five yes/no questions.

| # | Criterion | The plain-English question | The precise test | True count (of 761) |
|---|---|---|---|---|
| 1 | **Displacement** | Did a forceful candle burst out of this zone right after it formed? | Within bars `ob_bar+1` to `min(created_at, ob_bar+3)`, a candle body \|close − open\| ≥ 1.5 × ATR(200) in the zone's own direction | **107 (14.1%)** |
| 2 | **LargeBar** | Was the origin candle itself unusually big? | The OB bar's high − low ≥ ATR(200) at that bar | **444 (58.3%)** |
| 3 | **FVG** (Fair Value Gap) | Did price move so fast it left an untraded gap behind? | For some *j* in `[ob_bar, min(created_at−1, ob_bar+2)]`: low(*j*+2) > high(*j*) for DEMAND, or high(*j*+2) < low(*j*) for SUPPLY | **253 (33.2%)** |
| 4 | **LiqSweep** (Liquidity Sweep) | Did this candle spike past the recent extreme — likely knocking out other traders' stop-losses — before reversing? | OB bar's low ≤ the minimum low of the prior 10 bars (DEMAND); high ≥ the max high of the prior 10 bars (SUPPLY) | **406 (53.4%)** |
| 5 | **VolExpansion** (Volume Expansion) | Was there unusual participation in that candle? | Volume ≥ 1.25 × the prior 20-bar average volume, **OR** the candle body is > 60% of its own high-low range | **412 (54.1%)** |

The five booleans are summed into a 0–5 `quality` integer. **That integer is
used only as an entry filter threshold** (`quality >= min_ob_quality`) —
never as an "higher is better" ordinal claim in the analysis. That
restriction is the direct consequence of bug #1.

> **VISUAL V-8 — The five criteria, illustrated**
> **Type:** 5-panel grid of small illustrative SVG candle diagrams
> **Shows:** what each criterion physically looks like on a chart
> **Data:** conceptual drawings + the real True-count from the table above in
> each panel's corner
> **Build notes:** one panel each, all the same size, all drawn at the same
> scale so they read as a set.
> 1. **Displacement** — the zone rectangle, then one long-bodied candle
>    shooting away from it. Annotate the body with "≥ 1.5 × ATR(200)."
> 2. **LargeBar** — one candle noticeably taller than its neighbors, with a
>    dashed bracket labeled "ATR(200)" beside it for comparison.
> 3. **FVG** — three consecutive candles where candle 3's low sits *above*
>    candle 1's high; shade the untouched band between them and label it
>    "gap — no trading happened at these prices."
> 4. **LiqSweep** — a candle with a long lower wick poking below a dashed
>    line marking the prior 10-bar low, then closing back above it. Label the
>    dashed line "prior 10-bar low" and the wick "stops swept."
> 5. **VolExpansion** — a candle plus a volume bar beneath it that is clearly
>    taller than the surrounding volume bars, with a dashed line at "1.25 ×
>    20-bar average."
> Each panel needs a one-line caption in plain words, plus its true-count
> badge (e.g. "true for 253 / 761 zones").

> **VISUAL V-9 — Quality score distribution**
> **Type:** bar chart (6 bars), plus a second row showing the trade counts
> **Shows:** that high-quality zones are rare, and that filtering on quality
> shrinks the sample fast
> **Data (source: live `compute_smc()`, matches `artifacts/paper_sync_report.md`):**
> q=0 → 93 · q=1 → 154 · q=2 → 206 · q=3 → 197 · q=4 → 90 · q=5 → 21 zones
> Second row — trades surviving each **cumulative** threshold: q≥0 → 27 ·
> q≥1 → 25 · q≥2 → 23 · q≥3 → 14 · q≥4 → 6 · q≥5 → 1
> **Build notes:** the caption must say plainly: *"These six columns are not
> six independent experiments. Every q≥1 trade is also a q≥0 trade. They are
> nested subsets of one 27-trade pool, so they cannot be compared as if they
> were separate samples."*

### 2.5 The trading rules

**Define (first use):**

- **LONG** — betting price goes up. Buy, then sell higher.
- **SHORT** — betting price goes down. Sell borrowed coin, buy it back
  cheaper.
- **Stop-loss (SL)** — a pre-set exit price that caps the loss if the trade
  goes wrong.
- **Take-profit (TP)** — a pre-set exit price that banks the gain.
- **Reward-to-risk ratio (R:R)** — potential gain divided by potential loss.
  R:R = 1.5 means risking $1 to make $1.50. Trades below the minimum are
  refused *before* they are taken.

**The eight pre-registered parameters — fixed, never swept:**

| Parameter | Value | What it does |
|---|---|---|
| `sl_ratio_min` | 0.015 | The stop must sit at least 1.5% away from entry. Tighter stops sit inside normal 4-hour noise and get hit before the move starts. |
| `kdj_j_long_cap` | 60.0 | J must be below this to allow a LONG |
| `kdj_k_long_cap` | 50.0 | K must be below this to allow a LONG |
| `kdj_k_short_floor` | 70.0 | K must be at or above this to allow a SHORT |
| `kdj_j_short_cap` | 100.0 | J ceiling for a SHORT |
| `atr_mult_exit` | 1.8 | Exit once price has moved 1.8 × ATR in your favor |
| `atr_mult_be` | 2.0 | At 2.0 × ATR in your favor, pull the stop up to breakeven |
| `rr_min` | 1.5 | Minimum reward:risk to accept a trade |

*(Plus the three SMC constants: pivot lookbacks 5 and 50, max OB age 500.)*

**A LONG entry requires ALL of these, in order:**

1. Price is touching an active, unmitigated **DEMAND** Order Block of
   sufficient quality
2. MACD histogram is **below zero and rising for at least 2 bars** —
   downward pressure is easing, not yet reversed
3. KDJ **K < 50 and rising**, and **J < 60** — oversold and turning up
4. K-acceleration is inside the window **1 ≤ k_accel ≤ 6** — excludes both
   "not actually accelerating" and "one-bar spike noise"
5. The volatility regime ratio ATR(14)/ATR(200) is **outside [0.8, 1.0]** — a
   deliberate dead zone; the strategy declines to trade when short-term
   volatility is merely ordinary
6. The resulting stop distance is **≥ 1.5% of entry price**
7. The resulting reward:risk is **≥ 1.5**

A SHORT entry is the mirror image against a SUPPLY OB (K > 50, J > K > D,
K ≥ 70, J ≤ 100).

> **VISUAL V-10 — The entry gate**
> **Type:** vertical funnel / sieve flowchart
> **Shows:** that seven independent conditions must *all* pass, and that any
> one failure kills the candidate
> **Data:** the seven conditions above, in order
> **Build notes:** draw as a narrowing funnel with seven stacked filters.
> Each has a green "pass ↓" arrow continuing down and a red "fail ✕" arrow
> exiting sideways to a single "no trade" sink. The bottom outputs "ENTER."
> Caption: *"Over 8,767 bars and 761 detected zones, only 27 candidates
> cleared all seven — about one trade every two months."*
> This visual replaces the entry-rule prose. Do not print the list twice.

**Exits — six rules, checked every bar, first match wins:**

| Priority | Rule | Plain meaning |
|---|---|---|
| 1 | Trailing exit — 50% retrace | Once the trade is up ≥ 1.5%, if it gives back half its best gain, get out |
| 2 | KDJ-reset exit (only from bar 3 onward) | A separate KDJ state machine says momentum has reset — leave. Blocked in the first two bars so one-bar wobbles cannot eject the trade |
| 3 | ATR-move exit | Price moved 1.8 × ATR in your favor — bank it |
| 4 | Breakeven ratchet | At 2.0 × ATR in your favor, move the stop up to entry price. *Not an exit* — it just removes the downside |
| 5 | Hard stop-loss | Price closed through the stop |
| 6 | Hard take-profit | Price closed through the target |

> **VISUAL V-11 — Exit priority ladder**
> **Type:** numbered vertical ladder / priority stack
> **Shows:** that exits are ordered and the first match wins, and that rule 4
> is not an exit at all
> **Data:** the six rules above, **plus the real observed counts across the
> 27 baseline trades** (source: live recompute of `trades_df.exit_reason`):
> ATR MOVE EXIT **9** · TRAILING EXIT (50% RETRACE) **8** · KDJ RESET EXIT
> **8** · HIT STOP LOSS **2** · HIT TAKE PROFIT **0**
> **Build notes:** show each rule's real count as a badge. Style rule 4
> differently (dashed border) since it fires no exits. Caption the striking
> fact: *"The hard take-profit never fired once. Trades were resolved by the
> trailing, KDJ-reset, and ATR-move rules first — which is why changing the
> take-profit distance barely moves the results (§6.1)."*

### 2.6 The two KDJ systems — the single most confusable design detail

There are **two different KDJ calculations** in this strategy. Conflating
them is the most likely way to misexplain the work to a panel.

| | **(a) Entry-gating KDJ** | **(b) Exit-timing KDJ state machine** |
|---|---|---|
| Period | Fixed at 9, always | `w = max(1, entry_idx − ob_bar)`, frozen per trade |
| Computed | Once, over the entire 8,767-bar history | Recursively forward, from the entry bar |
| Seeded from | n/a | The **static** K/D values already present at the entry bar — not reset to 50, not backfilled |
| Used for | Deciding whether to enter | Deciding when to leave |
| Varies per trade? | **No, never** | Only `w` varies |
| Code | `compute_indicators()` | `kdj_reset_init` / `kdj_reset_update` / `kdj_reset_exit` |

**Observed `w` across the 27 baseline trades: range 14 to 439, median 74.**
*(Source: live recompute of `trades_df.kdj_exit_window`.)* Any paper language
implying a "two-bar window" is illustrative only and does not describe the
data.

> **VISUAL V-12 — Two KDJs, one strategy**
> **Type:** split diagram with a clear dividing line
> **Shows:** that these are two separate systems with two separate jobs
> **Data:** the table above plus the real `w` range 14–439, median 74
> **Build notes:** left half = "BEFORE the trade: static KDJ(9,3,3), computed
> once over all history, decides IF we enter." Right half = "AFTER the trade
> opens: a separate recursion with a per-trade window w, decides WHEN we
> leave." Put a thick vertical divider between them with the label "the
> entry decision is already made." Add a small histogram or number line
> showing the observed w spread (14 … 74 … 439) on the right side.
> **This is a deliberate, disclosed design choice, verified by a read-only
> audit — not an inconsistency to apologize for.**

### 2.7 Method as self-audit — three bugs found, fixed, and disclosed

The paper presents its own correction history as evidence of process. The
guide should too. This is a defense strength, not a liability.

> **VISUAL V-13 — The three bugs**
> **Type:** three stacked cards, each with Before → After → Impact
> **Shows:** what broke, what fixed it, and — crucially — whether any
> published number moved
> **Data:**
>
> **Bug 1 — Non-orthogonal quality score.** *Before:* the 0–5 score was built
> so that higher-scoring zone sets were nested subsets of lower-scoring ones,
> tangling "quality" with "different sample." *After:* the five criteria are
> evaluated and tested independently; the integer survives only as an entry
> threshold. *Impact:* changed the analysis method, not the trade log.
>
> **Bug 2 — FVG used the wrong definition.** *Before:* tested adjacent
> candles, low(*j*+1) > high(*j*). *After:* the correct three-candle
> imbalance, low(*j*+2) > high(*j*). *Impact:* corrected which zones counted
> as having a gap.
>
> **Bug 3 — Lookahead across the confirmation boundary.** *Before:* the FVG
> and displacement forward-searches were bounded by *dataset length*, so they
> could read 1–2 bars that would not have existed yet when the zone became
> usable. *After:* both searches are bounded by the zone's own confirmation
> bar, with live runtime assertions at the read sites. *Impact:* **this one
> moved published numbers** — see V-14.
>
> **Build notes:** color bugs 1 and 2 neutral; color bug 3 amber, since it
> is the one with numeric consequences.

**Define (first use):**

- **Lookahead (data leakage)** — when a backtest accidentally uses
  information that would not have been available at that moment in real time.
  It is the classic way a backtest flatters itself. Bug 3 was a genuine, if
  small, instance.

> **VISUAL V-14 — What bug 3 actually changed**
> **Type:** before/after comparison table with a highlighted flip row
> **Shows:** that a real data-leakage fix reversed a significance conclusion
> **Data (source: CLAUDE.md locked block; q≥1 p-value confirmed live at
> 0.053876):**
>
> | Quantity | Pre-fix | Post-fix |
> |---|---|---|
> | Order Blocks with FVG true | 362 (47.6%) | **253 (33.2%)** |
> | Order Blocks with Displacement true | 112 | **107** |
> | Zones whose score changed | — | 110 of 761 |
> | q≥0 baseline trades | 27 | **27 (unchanged)** |
> | q≥1 trades | 26 | **25** |
> | q≥1 one-sided binomial p | 0.038 | **0.054** |
> | q≥1 conclusion at α = 0.05 | significant | **not significant** |
>
> **Build notes:** highlight the last two rows. Caption: *"One trade
> (`entry_idx = 3100`) lost its only quality point under the corrected
> computation, dropping the q≥1 sample from 26 to 25 — and that flipped the
> conclusion. The headline 27-trade baseline was untouched, because it
> applies no quality filter at all. This is disclosed in the paper, not
> smoothed over."*

**The no-lookahead proof, independent of the bug narrative:**

- **180 / 180** truncation-equality checks pass (36 sampled bars × 5
  indicator columns) — recomputing an indicator using only data up to bar *t*
  gives the same value as computing it over the full series.
- **0 / 253** FVG-true zones and **0 / 107** displacement-true zones read past
  their own confirmation bar.
- Runtime `assert` statements sit at the read sites
  (`research_analysis.py:813, :843`) and fire on any violation. None fired in
  any run during the 2026-08-20 audit.

### 2.8 Reproducibility infrastructure

> **VISUAL V-15 — Three independent guards**
> **Type:** three-column card row
> **Shows:** how the project defends against silent drift
> **Data:**
>
> **1. Golden-master regression** (`scratch/regression.py`) — recomputes
> indicators and the full simulation from raw candles and asserts exact
> equality against committed fixtures: indicators to 1e-6, all 27 baseline
> trade fields exactly. Run after every change. Any difference means revert
> the change, not update the fixture. *Status at last audit: PASS.*
>
> **2. Independent JavaScript re-implementation** (the dashboard) — a second
> codebase, written from scratch in TypeScript, recomputes the indicator and
> entry-condition layer client-side and compares. It never imports from
> Python. **Stated scope limit:** it does *not* independently detect Order
> Blocks, FVG, or displacement — it reads those as trusted data. So it could
> not have caught bug 3. It verifies a narrower layer.
>
> **3. Content hashing** (`artifacts/verification_report.json`) — SHA-256
> hashes over the candles, indicators, order blocks, trades, and stats at
> each quality level. 14 hashes; all 14 reproduced byte-identically during
> the 2026-08-20 audit, and again after a full pipeline re-run.
>
> **Build notes:** the scope limit on guard 2 is not optional — it must be
> visible on the card. A cross-check that oversells its own coverage is worse
> than none.

---

## 3. Codebase architecture

### 3.1 The one-file design, and why

Everything — the backtest engine, the statistics, the database layer, and
the dashboard's web server — lives in **`research_analysis.py`**, a single
~5,400-line file at the repository root, organized into eight numbered
sections.

This was a deliberate consolidation (2026-08-13). Previously the same logic
was spread across ~15 files, with each analysis script dynamically loading
the strategy module and shelling out to others via subprocess + JSON. For a
research artifact, one auditable file beats fifteen convenient ones: there is
exactly one definition of `simulate_trades()`, and a reviewer can read the
pipeline top to bottom.

The superseded originals were moved to `legacy_pre_consolidation/` — a
git-ignored, disk-only backup. **It was a refactor, not a strategy change:**
`compute_indicators()`, `compute_smc()`, `simulate_trades()`, and the
`kdj_reset_*` state machine were verified byte-identical against the golden-
master fixtures before and after the move.

> **VISUAL V-16 — The eight sections of research_analysis.py**
> **Type:** vertical labeled stack / file map
> **Shows:** the internal structure of the one canonical file
> **Data:**
>
> | § | Name | Job |
> |---|---|---|
> | 1 | Imports, constants, shared utilities | Every pre-registered parameter and locked figure declared as a named constant |
> | 1B | Database manager | SQLAlchemy models: Candle, OrderBlock, OBTouch, Trade |
> | 2 | Data loading / preprocessing | Read `artifacts/candles.csv`; load the extended 2018-start window |
> | 3 | **Strategy / backtest engine** | The protected core. `compute_indicators`, `compute_smc`, `simulate_trades`, the KDJ exit state machine |
> | 3B | Live data pull + Google Sheets export | Binance API; 8-tab spreadsheet push |
> | 4 | Ablation study | The three-arm comparison and its disclosed reconstruction gap |
> | 5 | Statistical test primitives | Binomial, Fisher, Welch, bootstrap, Pearson, Spearman, MDE, Sharpe/Sortino, max drawdown |
> | 5B | Application-level analyses | Benchmark vs passive, DCA blend, fee/slippage, regime breakdown, out-of-sample, paper-sync |
> | 6 | Artifact export + DB persistence | Writes every `artifacts/*.json` and every database row |
> | 7 | HTTP server / frontend endpoints | Port 8765; serves the dashboard and the `/api/*` routes |
> | 8 | CLI / main execution | `python research_analysis.py` (offline stats) or `--serve` (export + dashboard) |
>
> **Build notes:** mark § 3 visually as "protected core — no logic changes
> permitted, refactoring only." That constraint is a project rule, not a
> style preference.

### 3.2 The data flow, end to end

> **VISUAL V-17 — The master pipeline flowchart**
> **Type:** left-to-right flowchart with labeled stages, function names on
> the arrows, and file names on the data nodes. **This is the single most
> important visual in the guide.**
> **Shows:** how raw price becomes a paper figure, and where each artifact
> is produced
> **Data / stages:**
>
> 1. **Binance API** (`get_candles`, or the committed cache)
>    → `artifacts/candles.csv` — *8,767 bars*
> 2. → **`compute_indicators(df)`** — adds MACD, MACD_signal, MACD_hist, K,
>    D, J, RSV, ATR, ATR_200 as columns
> 3. → **`compute_smc(df)`** — two structural passes → **761 Order Blocks**,
>    each with 5 quality booleans + `mitigated_at`
> 4. → **`simulate_trades(df, min_ob_quality=0)`** — bar-by-bar entry gating
>    and exit gating → **27 trades**, attached as `df.attrs['trades_df']`
>    alongside `trade_stats` and `touches_df`
> 5. → **`run_quality_sweep(df, levels=(0,1,2,3))`** — repeats step 4 at each
>    threshold → 27 / 25 / 23 / 14 trades
> 6. → **Section 5 statistical primitives** — binomial, Fisher, Welch,
>    bootstrap, Pearson/Spearman, MDE
> 7. → **Section 5B application analyses** — benchmark vs passive, DCA
>    blend, fee/slippage, regime breakdown, out-of-sample, paper-sync
> 8. → **`export_dashboard_artifacts()`** → `artifacts/*.json` + `*.csv` +
>    `backtest_results.db`, then `build_verification_report()` hashes
>    everything
> 9. → **Two consumers, in parallel:**
>    - **The dashboard** — `research_analysis.py --serve` starts the HTTP
>      server on :8765; the React app fetches `artifacts/*.json` statically
>      and `/api/trades` dynamically, then **recomputes the statistics
>      independently in TypeScript**
>    - **The paper** — `generate_paper_sync_report()` writes
>      `artifacts/paper_sync_report.md`, which cross-checks every live figure
>      against the locked block in `CLAUDE.md` and prints MATCH or MISMATCH
>      per row
>
> **Build notes:**
> - Put a **branch marker after step 8** — the two consumers are parallel,
>   not sequential, and the dashboard branch must be visibly labeled
>   *"independent re-implementation — never imports from Python."*
> - Show a **feedback arrow** from `scratch/regression.py` pointing at steps
>   2–4, labeled *"golden-master check — run after every change."*
> - Annotate the arrow between steps 3 and 4 with **"761 zones in → 27 trades
>   out"** so the funnel's severity is visible.
> - Data nodes (files) and process nodes (functions) should be
>   distinguishable at a glance — e.g. rectangles vs rounded boxes.

### 3.3 What each major function does, and why it exists

| Function | Section | Job | Why it exists as its own function |
|---|---|---|---|
| `load_candles()` | 2 | Read the committed CSV snapshot | Guarantees the offline default. No network call in the default run |
| `compute_indicators(df)` | 3 | Add MACD/KDJ/ATR columns | Computed **once**, over the whole series, before any simulation — so there is no per-trade recomputation and no place for lookahead to creep into the indicator layer |
| `compute_smc(df)` | 3 | Detect Order Blocks + score the 5 criteria | Isolates the only non-standard component. This is where the no-lookahead assertions live |
| `_build_order_block_from_crossover(...)` | 3 | Build one OB dict and score it | Shared by the bullish and bearish branches, which are otherwise identical. One definition of the five criteria, not two |
| `get_structural_tp(...)` | 3 | Pick the nearest opposing OB as a take-profit target | Makes the TP structural rather than arbitrary — the target is a real price level, not a fixed multiple |
| `kdj_reset_init / _update / _exit` | 3 | The per-trade exit state machine | Kept deliberately separate from the entry KDJ (§2.6) |
| `_try_enter_long / _try_enter_short` | 3 | Evaluate the entry gate against every active OB | Extracted so the seven filters are readable in order, and so the ablation arms can reuse the identical indicator conditions with the OB requirement removed |
| `_check_long_exit_conditions / _check_short_...` | 3 | Evaluate the six exit rules in priority order | Preserves a subtle ordering detail: the KDJ state is updated with *this* bar before the KDJ exit is tested — but only if the trailing exit did not already fire |
| `simulate_trades(df, min_ob_quality)` | 3 | **The strategy itself.** Bar-by-bar backtest | Every headline figure in the paper is read from this function's output |
| `run_quality_sweep(df, levels)` | 3 | Re-run the simulation at each quality threshold | Produces the q0–q5 table. OB detection is cached across calls, since it is deterministic given the same candles |
| `run_ablation_arm(df, stop_mode)` | 4 | Run an indicators-only arm with a chosen stop scheme | Isolates *what the Order Block gate contributes* by removing it |
| `binomial_test`, `fisher_exact_test`, `welch_t_test`, `bootstrap_resample`, `pearson_correlation`, `spearman_correlation`, `mde_power_analysis` | 5 | The statistical primitives | Thin, individually documented wrappers over `scipy.stats`. Deduplicated from six former scripts that each called them separately — consolidation, not a methodology change |
| `run_criteria_significance_tests(trades_df)` | 5B | Fisher + Welch per criterion | Produces the five-row table at the heart of the quality question |
| `run_bootstrap_ci(trades_df)` | 5B | The canonical B = 10,000 confidence interval | Isolated so the resample count is a visible, single-source parameter |
| `run_benchmark_vs_passive(...)` | 5B | Strategy vs weekly DCA vs lump-sum, both windows, gross and fee-adjusted | The exposure-time comparison. Produces the numbers that must never be quoted without their caveat |
| `run_fee_slippage_sensitivity(...)` | 5B | Six cost scenarios | Turns "would fees matter?" into a specific, checkable answer |
| `generate_paper_sync_report(...)` | 5B | Recompute everything and diff it against CLAUDE.md's locked block | The automated drift alarm. A MISMATCH row is treated as a correctness finding, not auto-reconciled |
| `export_dashboard_artifacts(...)` | 6 | Write every artifact and DB row | One export path, so the dashboard and the paper read the same bytes |
| `build_verification_report(...)` | 6 | SHA-256 hash the whole snapshot | Makes "nothing drifted" mechanically checkable |
| `run_dashboard_server(...)` | 7 | HTTP server on :8765 | Serves the built React app under `/dashboard/`, `artifacts/*` statically, and `/api/trades` from the database |
| `run_full_analysis_pipeline(...)` | 8 | The 10-step end-to-end run | Includes a hard `assert` that the baseline is still 27 trades — the pipeline refuses to continue if the locked result moved |

### 3.4 The dashboard, and why it is written twice

> **VISUAL V-18 — Deliberate double implementation**
> **Type:** two-column diagram with a "no connection" barrier between them
> **Shows:** why the same statistics are computed twice in two languages
> **Data:**
> **Left — Python** (`research_analysis.py` § 5): scipy-backed. Produces the
> paper's canonical figures.
> **Right — TypeScript** (`dashboard-v2/src/components/stats/statsCompute.ts`,
> `statMath.ts`, `benchmarkMath.ts`): from-scratch re-implementations,
> including its own Welch–Satterthwaite degrees-of-freedom calculation and
> its own `mulberry32` pseudo-random generator for bootstrapping.
> **Barrier label:** *"The JavaScript side never imports from the Python
> side. That independence is the whole point — two codebases agreeing is
> evidence; one codebase agreeing with itself is not."*
> **Build notes:** show a real agreement example beneath: Welch df for
> Displacement — scipy **9.102077**, hand-computed numpy **identical**,
> TypeScript **9.10**. Three independent routes, one answer.

The React app has four tabs — **Chart** (price with Order Block rectangles
and trade markers), **Stats** (the statistical tables), **Solutions** (every
derivation shown step by step in LaTeX), and **Sandbox** (interactive
calculators). It fetches `artifacts/*.json` as static files and `/api/trades`
from the SQLite database via the Python server.

### 3.5 Running it

| Command | What happens |
|---|---|
| `python research_analysis.py` | The offline statistics pipeline. Ten steps, no network. Prints every headline figure |
| `python research_analysis.py --serve --levels 0,1,2,3` | Pull/load candles, run all thresholds, write every artifact + database row, start the dashboard on :8765 |
| `python research_analysis.py --serve --export-gsheet` | The same, plus an 8-tab Google Sheets push |
| `python Run_All.py` | The one runner script: install Python deps, `npm ci` and build the dashboard if needed, then `--serve`. A fresh clone needs only Python and Node preinstalled |
| `python scratch/regression.py` | The golden-master check. Run after **every** change. Any difference = revert |

---

## 4. The statistical toolkit

Open this section with the idea that unifies it: **every test here answers
"could this have happened by chance?" — they differ in what "this" is.**

> **VISUAL V-19 — Which test answers which question**
> **Type:** decision-tree flowchart (or a routing table if a tree gets busy)
> **Shows:** that the choice of test follows from the question, not from
> preference
> **Data:**
>
> - *"Did we win more often than a coin flip?"* → one number vs a fixed
>   baseline → **Binomial test**
> - *"Do zones with feature X win more OFTEN than zones without it?"* →
>   comparing two win **rates**, small groups → **Fisher's exact test**
> - *"Do zones with feature X earn MORE per trade than zones without it?"* →
>   comparing two **averages**, unequal sizes and variances → **Welch's
>   t-test**
> - *"Do longer-held trades earn more?"* → association between two
>   continuous measurements → **Pearson r** (straight-line) and **Spearman ρ**
>   (rank-based, outlier-resistant)
> - *"How much would this total return have wobbled with a different draw of
>   trades?"* → uncertainty around one statistic → **Bootstrap resampling**
> - *"Our test found nothing — does that mean nothing is there?"* → **MDE /
>   power analysis**
>
> **Build notes:** each leaf should carry the actual result reached, so the
> tree doubles as a results index.

### 4.1 The p-value — define this before any test

> **VISUAL V-20 — What a p-value is (and is not)**
> **Type:** callout card, two halves
> **Shows:** the correct plain-language reading and the three standard
> misreadings
> **Data:**
> **It IS:** *"Suppose the strategy had no edge at all — pure coin flips. How
> often would random chance alone produce a result this good or better?"*
> A small p means "this would be a surprising fluke." p = 0.026 means: about
> **1 in 38** coin-flip runs would look this good.
> **It is NOT:** the probability the strategy works · the probability the
> result is real · a measure of how *big* the effect is (a tiny, useless edge
> can be highly significant given enough data, and a large edge can be
> non-significant with too little)
> **The α = 0.05 line** is a convention, not a law of nature. p = 0.054 and
> p = 0.046 are nearly identical pieces of evidence that land on opposite
> sides of an arbitrary line. This study hits exactly that situation (§2.7,
> V-14) and says so.

### 4.2 The binomial test — "better than a coin flip?"

**Question:** with 27 trades and 19 wins, how surprising is that if each
trade were a 50/50 coin flip?

**Plain mechanism:** count every possible way to get 19 or more heads in 27
flips, add up their probabilities. That total is the p-value.

$$p = \sum_{k=19}^{27}\binom{27}{k}(0.5)^{27} = 0.0261$$

**Result: one-sided p = 0.0261, two-sided p = 0.0522.**

**One-sided vs two-sided** — one-sided asks "is it better than chance?";
two-sided asks "is it different from chance, in either direction?" The paper
uses one-sided as its primary figure because the hypothesis was directional
and pre-registered (the strategy was built to *beat* the null, not merely to
differ from it), and reports the more conservative two-sided value alongside.

> **VISUAL V-21 — The coin-flip distribution**
> **Type:** bar chart of the binomial distribution for n = 27, p = 0.5
> **Shows:** exactly what "p = 0.026" means, geometrically
> **Data:** bars for k = 0…27 wins under a fair coin; shade k ≥ 19 in a
> highlight color; annotate the shaded tail as "2.6% of all possible
> coin-flip outcomes"; put a marker on k = 19 labeled "observed: 19 wins."
> **Build notes:** this single chart carries more understanding than any
> paragraph about p-values. Make it large.

### 4.3 Fisher's exact test — "different win RATES?"

**Question, per criterion:** do trades whose entry zone had this feature win
*more often* than trades whose zone did not?

**Plain mechanism:** build a 2×2 table of wins and losses in each group, then
count — exactly, not approximately — how many ways the same totals could be
shuffled into a split at least this lopsided by chance.

**Why Fisher and not chi-square:** chi-square uses an approximation that
becomes unreliable with small counts. Here one group is as small as **n = 4**.
Fisher's test is exact at any size, so it is the defensible choice.

> **VISUAL V-22 — A 2×2 contingency table, worked**
> **Type:** annotated 2×2 grid using real Displacement data
> **Shows:** what the test actually looks at
> **Data (source: live `run_criteria_significance_tests()`):**
> Displacement TRUE: 2 wins, 2 losses (n = 4) · Displacement FALSE: 17 wins,
> 6 losses (n = 23) · **Fisher p = 0.5583**
> **Build notes:** show the win rates beside the grid (50.0% vs 73.9%) and
> then the punchline: *"A 24-point gap in win rate — and still p = 0.56. With
> only four trades in one cell, a gap that large is entirely ordinary luck.
> This is what an underpowered test looks like."*

### 4.4 Welch's t-test — "different AVERAGE returns?"

Fisher counts wins. Welch compares **averages**, so it uses the size of each
trade's gain or loss, not just its sign.

$$t = \frac{\bar X_T - \bar X_F}{\sqrt{\dfrac{s_T^2}{n_T}+\dfrac{s_F^2}{n_F}}}$$

**Plain reading of *t*:** the gap between the two group averages, measured in
units of "how much wobble we'd expect anyway." A *t* near 0 means the gap is
smaller than the noise. All five criteria here land between −0.93 and +0.54.

**Why Welch and not Student's:** the standard t-test assumes both groups have
the same underlying variability, and pools them. Here the groups have
different sizes (4 vs 23, 20 vs 7 …) and there is no reason to assume matched
variability — nothing about a structural criterion implies its two subgroups
should be equally volatile. Welch's version drops that assumption.

**The Welch–Satterthwaite degrees of freedom.** Because the variances are not
pooled, the reference distribution's **degrees of freedom** — roughly, how
much independent information the sample carries — is no longer the tidy
integer *n₁ + n₂ − 2*. It becomes a fractional effective value:

$$\nu = \frac{\left(\dfrac{s_T^2}{n_T}+\dfrac{s_F^2}{n_F}\right)^{2}}{\dfrac{(s_T^2/n_T)^2}{n_T-1}+\dfrac{(s_F^2/n_F)^2}{n_F-1}}$$

**Plain reading:** ν is a penalty for lopsidedness. A balanced split keeps
most of its information; a 4-vs-23 split does not. Displacement has n = 27
trades in total but only **ν = 9.10** — the four-trade group is the
bottleneck. LiqSweep, split nearly evenly at 15-vs-12, reaches **ν = 24.62**
from the same 27 trades.

The code reads ν off the same scipy result object that produced *p*
(`TtestResult.df`) rather than recomputing it, so the reported ν is by
construction the one the reported *p* came from.

> **VISUAL V-23 — How Welch compares two groups, and what ν measures**
> **Type:** two-part diagram
> **Shows:** (a) the mechanics, (b) why ν differs across criteria
> **Data:**
> **Part (a):** two overlapping distribution curves labeled "criterion TRUE"
> and "criterion FALSE," with their means marked and the gap between them
> annotated. Show the gap as small relative to the spread. Caption: *"Welch
> asks whether that gap is bigger than the spread justifies. Here, it never
> is."*
> **Part (b):** a bar chart of ν per criterion against a reference line at
> n = 27, using the real values —
> Displacement **9.10** (split 4 / 23) · FVG **15.41** (11 / 16) · LargeBar
> **20.87** (20 / 7) · VolExpansion **22.21** (15 / 12) · LiqSweep **24.62**
> (15 / 12).
> Caption: *"Same 27 trades, five very different amounts of usable
> information — because ν tracks how lopsided the split is, not how many
> trades there are."*

### 4.5 Pearson and Spearman correlation — "do longer holds earn more?"

**Pearson *r*** measures how well a straight line fits the relationship
between two measurements. It runs −1 (perfect inverse) to +1 (perfect
direct), with 0 meaning no linear relationship. It is sensitive to outliers.

**Spearman *ρ*** does the same on **ranks** — 1st longest, 2nd longest, and
so on. It catches any consistently-increasing relationship, straight-line or
not, and one extreme trade cannot dominate it.

**Both are reported, deliberately.** If the two agree in sign and
significance, the association is not an artifact of a few extreme trades.

**Result across the 27 baseline trades (hold duration vs return):**

| | Value | *t* | df | p |
|---|---|---|---|---|
| Pearson *r* | **+0.4907** | 2.8158 | 25 | **0.009356** |
| Spearman *ρ* | **+0.4797** | — | — | **0.011335** |

Plain reading: trades held longer tended to earn more — a moderate positive
association, significant at α = 0.05 and at α = 0.01.

> **Reporting correction that must be shown, not hidden:** both p-values were
> originally published in this repository's documents as "p < 0.001." That
> was wrong by roughly an order of magnitude. The correct values are ≈ 0.0094
> and ≈ 0.0113 — still significant, but a different significance bucket. The
> error was caught by the project's own 2026-08-08 cross-surface audit,
> corrected in both documents, and disclosed. *(Source: CLAUDE.md, "Paper
> reporting corrections" #1; confirmed live via scipy.)*

### 4.6 Bootstrap resampling — "how much could this have wobbled?"

**The problem:** the study has exactly one set of 27 trades. What would a
*different* 27 have looked like? There is no second history to check.

**The bootstrap answer:** treat those 27 outcomes as a stand-in for the
population and draw new 27-trade samples **from them, with replacement** —
some trades appear twice, some not at all. Do that 10,000 times, total each
sample, and look at the spread of totals. The middle 95% of that spread is
the confidence interval.

> **VISUAL V-24 — How bootstrap resampling works**
> **Type:** three-panel process diagram plus a histogram
> **Shows:** the resampling mechanic and the interval it produces
> **Data:**
> **Panel 1:** a row of 27 small tiles labeled "the actual trades: +6.69%,
> −4.65%, …" *(source: live — best trade +6.6888%, worst −4.6544%)*
> **Panel 2:** three example draws of 27 tiles each, with visible duplicates
> and visible omissions, labeled "draw with replacement — some trades appear
> twice, some not at all."
> **Panel 3:** a histogram of the 10,000 resampled totals, with the 2.5th and
> 97.5th percentiles marked at **+5.99%** and **+54.99%**, a marker at the
> observed **+30.31%**, and a vertical line at zero clearly outside the
> shaded interval.
> **Caption:** *"95% CI [+5.99%, +54.99%] — wide, but it excludes zero.
> 99.25% of the 10,000 resamples were positive."*
> **Source:** `artifacts/bootstrap_power_analysis.json` (B = 10,000, seed 42)
>
> **Build notes:** the "with replacement" mechanic is the one thing readers
> misunderstand. Panel 2's duplicates must be visually obvious.

**Also reported:** average return per trade, 95% CI **[+0.22%, +2.04%]**.

**Honest limit of the method, worth stating:** the bootstrap captures
uncertainty about *which of these trades you happened to get*. It cannot
capture uncertainty about *which trades would have existed at all* under a
different price history. It is a real but bounded stress test.

### 4.7 MDE and power analysis — "was the test even capable of finding it?"

This is the most important statistical idea in the whole study, because it
governs how the null results are reported.

**Define:**

- **Statistical power** — the chance a test detects a real effect that is
  actually there. Convention: 80%.
- **Minimum Detectable Effect (MDE)** — given the sample sizes and
  variability you actually have, the *smallest true difference* your test
  could reliably catch. Anything smaller will usually be missed even if
  real.

$$\text{MDE} = (z_{\alpha/2} + z_\beta)\sqrt{\frac{s_T^2}{n_T}+\frac{s_F^2}{n_F}}$$

**Why this matters here:** none of the five criteria reached significance. If
the MDE is much larger than the observed gaps, that non-result says *"this
sample could not have detected an effect of this size"* — not *"no effect
exists."* Those are very different claims, and the paper is careful to make
only the first.

> **VISUAL V-25 — Observed gap vs. what the test could detect**
> **Type:** grouped horizontal bar chart, one pair per criterion
> **Shows:** that every observed gap sits far inside the detection floor
> **Data (source: `artifacts/bootstrap_power_analysis.json` → `mde_power`;
> α = 0.05, power = 0.80):**
>
> | Criterion | Observed gap | MDE | Ratio |
> |---|---|---|---|
> | Displacement | 0.740 pp | 2.234 pp | 3.02× |
> | VolExpansion | 0.778 pp | 2.468 pp | 3.17× |
> | LiqSweep | 0.740 pp | 2.531 pp | 3.42× |
> | FVG | 0.557 pp | 2.914 pp | 5.23× |
> | LargeBar | 0.232 pp | 2.246 pp | 9.68× |
>
> **Build notes:** draw the MDE as a wide translucent "detection floor" bar
> and the observed gap as a narrow solid bar inside it, so the observed bar
> visibly fails to reach the floor in every row.
> **Caption — this exact wording matters:** *"Every observed gap is 3× to 10×
> smaller than the smallest gap this sample could reliably detect. The correct
> conclusion is 'insufficient power to distinguish quality-criterion effects
> at this sample size' — not 'no significant difference,' and certainly not
> 'the criteria carry no signal.'"*
>
> *(Note for the builder: the paper's §2.4 sentence names VolExpansion and
> FVG as the "roughly 3×" pair. By the table above the two nearest 3× are
> Displacement (3.02×) and VolExpansion (3.17×); FVG is 5.23×. The overall
> 3–10× range is correct. Use the table's own numbers; do not reproduce the
> mismatched exemplar pairing.)*

### 4.8 Risk metrics — Sharpe, Sortino, max drawdown

Not hypothesis tests. Descriptions of the *shape* of a return stream.

- **Sharpe ratio** — average return divided by total volatility, annualized.
  "How much return per unit of bumpiness." Higher is better.
- **Sortino ratio** — the same, but only *downside* volatility counts in the
  denominator. Upside surprises are not penalized. Usually the more
  appropriate measure for a strategy with an asymmetric payoff.
- **Maximum drawdown** — the worst peak-to-trough fall the equity curve ever
  suffered, in percent. What it would have felt like to hold at the worst
  moment.
- **Time in market** — the share of all bars during which a position was
  actually open. **This is the number that makes the strategy's Sharpe
  incomparable to a buy-and-hold Sharpe**, and it must appear beside them
  every time.

> Both Sharpe and Sortino here are computed with an **implicit risk-free rate
> of zero** — the excess-return numerator is the raw mean return, not mean
> minus a T-bill yield. Standard for crypto backtests and disclosed in
> `docs/MATH_CORRECTNESS_AND_COMPREHENSION.md`, but it should be stated,
> since a non-zero risk-free rate would lower every Sharpe reported here.

---

## 5. Results

### 5.1 The 20 locked headline figures

These appear in the paper. The project treats them as frozen: **any code
change that alters one of them is a bug in the change, not an improvement.**
All 20 were independently reproduced during the 2026-08-20 audit and again
while preparing this handoff.

> **VISUAL V-26 — The locked-figures table**
> **Type:** the master results table, with a status column
> **Shows:** every headline number, its source, and its verification status
> **Data:**
>
> | # | Figure | Locked value | Source of truth | Status |
> |---|---|---|---|---|
> | 1 | Baseline trades (q≥0) | 27 | `paper_sync_report.md`; live | ✓ verified |
> | 2 | Baseline win rate | 70.37% (19 W / 8 L) | `paper_sync_report.md`; live | ✓ |
> | 3 | Total net return | +30.31% | `paper_sync_report.md`; live | ✓ |
> | 4 | Avg return / trade | +1.12% | `paper_sync_report.md`; live | ✓ |
> | 5 | SD of return / trade | 2.41% | `paper_sync_report.md`; live | ✓ |
> | 6 | Binomial p (one- / two-sided) | 0.026 / 0.052 | `paper_sync_report.md`; live | ✓ |
> | 7 | q≥1 one-sided p (post bug-3 fix) | 0.054 (n = 25) | CLAUDE.md; live `binomtest` | ✓ |
> | 8 | Detected Order Blocks | 761 | live `compute_smc()` | ✓ |
> | 9 | FVG-true Order Blocks | 253 (33.2%) | live `compute_smc()` | ✓ |
> | 10 | OB quality distribution q0–q5 | 93 / 154 / 206 / 197 / 90 / 21 | live `compute_smc()` | ✓ |
> | 11 | Ablation A (indicators-only, entry-ATR stop) | 140 · 60.00% · −14.63% | CLAUDE.md | ⚠ diverges — §6.1 |
> | 12 | Ablation B (indicators-only, swing-pivot stop) | 138 · 55.07% · −25.50% | CLAUDE.md | ⚠ diverges — §6.1 |
> | 13 | Dataset size | 8,767 bars | live `artifacts/candles.csv` | ✓ |
> | 14 | Strategy 2022–26, gross | +30.31% → $13,417.77 | `benchmark_vs_passive.json` | ✓ |
> | 15 | Strategy risk profile | Sharpe 1.114 · Sortino 2.727 · MaxDD −6.46% · time-in-market 2.63% | `benchmark_vs_passive.json` | ✓ |
> | 16 | Weekly DCA into BTC | +123.13% → $22,312.94 · Sharpe 0.556 · MaxDD −27.85% · TIM 100% | `benchmark_vs_passive.json` | ✓ |
> | 17 | Lump-sum buy-and-hold | +90.07% → $19,007.32 · Sharpe 0.564 · MaxDD −67.21% · TIM 100% | `benchmark_vs_passive.json` | ✓ |
> | 18 | Strategy, fee-adjusted | +24.91% → $12,719.01 | `benchmark_vs_passive.json` | ✓ |
> | 19 | 2018–22 formulation window (**not** out-of-sample) | strategy +21.82% → $12,282.53 | `benchmark_vs_passive.json` | ✓ |
> | 20 | 2018–22 passive arms | DCA +439.88% → $53,987.55 · lump-sum +236.96% → $33,696.49 | `benchmark_vs_passive.json` | ✓ |
>
> **Build notes:** rows 11 and 12 need a visually distinct status treatment
> and a link/anchor to §6.1. Rows 16, 17, 19, 20 are the unfavorable
> comparisons — do not de-emphasize them.

### 5.2 The baseline in context

**What each headline number actually means:**

| Figure | What it means |
|---|---|
| **27 trades** | Over four years and 8,767 four-hour bars, the rules found 27 setups where every filter agreed. About **0.56 trades per month** — roughly one trade every two months. The strategy's defining behavior is *refusing* to trade. |
| **70.37% win rate** | 19 of the 27 made money. Against a 50% coin-flip baseline, that is a real gap — but on 27 trades, chance alone produces a gap this large about 1 run in 38 (p = 0.0261). |
| **+30.31% total return** | The sum of all 27 percentage returns. Not annualized; not compounded across a continuously-invested account. Applied to $10,000 of notional capital that compounds only at each trade's exit, it becomes **$13,417.77**. |
| **+1.12% average per trade** | Small per trade. The edge, if real, is thin and accumulates slowly. |
| **2.41% standard deviation** | Trade-to-trade scatter is about twice the average return — normal for this kind of strategy, and the reason the bootstrap interval is so wide. |
| **2.63% time in market** | A position was open in only 231 of 8,766 bar-intervals. This is the single most important context number in the study. |

> **VISUAL V-27 — The 27 trades at a glance**
> **Type:** dot/strip plot of per-trade returns, plus three small summary
> panels
> **Shows:** the actual shape of the result — a handful of solid winners, a
> cluster near zero, a few losers
> **Data (all from live recompute of the baseline `trades_df`):**
> - 27 dots on a horizontal axis of pnl_pct; zero line marked; best
>   **+6.6888%**, worst **−4.6544%**
> - **Direction:** 15 LONG, 12 SHORT
> - **Exit reason:** ATR move 9 · trailing 8 · KDJ reset 8 · stop-loss 2 ·
>   take-profit **0**
> - **Hold duration:** 1 to 16 bars, median 10 bars (≈ 40 hours)
> **Build notes:** color winners and losers differently. The caption should
> note that the three most concentrated winners together account for **51.7%**
> of total net return *(source: paper §2.6)* — the result is not evenly
> spread, and that is a genuine fragility.

### 5.3 The quality-threshold sweep

| Threshold | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (1-sided) | p (2-sided) |
|---|---|---|---|---|---|---|---|---|---|
| q≥0 | 27 | 19 | 8 | 70.37% | +30.31% | +1.1225% | 2.41% | 0.0261 | 0.0522 |
| q≥1 | 25 | 17 | 8 | 68.00% | +28.31% | +1.1323% | 2.51% | 0.0539 | 0.1078 |
| q≥2 | 23 | 15 | 8 | 65.22% | +23.28% | +1.0120% | 2.56% | 0.1050 | 0.2100 |
| q≥3 | 14 | 8 | 6 | 57.14% | +6.59% | +0.4709% | 2.76% | 0.3953 | 0.7905 |
| q≥4 | 6 | 3 | 3 | 50.00% | +6.71% | +1.1177% | 3.85% | 0.6562 | 1.0000 |
| q≥5 | 1 | 0 | 1 | 0.00% | −0.38% | −0.3809% | n/a | 1.0000 | 1.0000 |

*(Source: `artifacts/paper_sync_report.md`; q0–q3 confirmed against
`artifacts/threshold_runs.json` and live recompute.)*

**The interesting, unfavorable reading:** demanding *higher*-quality zones
made results **worse**, monotonically, all the way to a single q≥5 trade that
lost money. That is the opposite of the hypothesis the quality score was
built on.

**The mandatory caveat, stated inline and not as a footnote:** these six rows
are **not six independent experiments.** The filter is cumulative, so every
q≥1 trade is also a q≥0 trade — nested subsets of one 27-trade pool. Any
cross-threshold comparison must say so.

### 5.4 The five criteria — the central null result

| Criterion | True n (wins) | False n (wins) | Fisher p | Welch t | Welch ν | Welch p | MDE |
|---|---|---|---|---|---|---|---|
| Displacement | 4 (2) | 23 (17) | 0.5583 | −0.9277 | 9.10 | 0.3775 | 2.23 pp |
| LargeBar | 20 (14) | 7 (5) | 1.0000 | +0.2895 | 20.87 | 0.7751 | 2.25 pp |
| FVG | 11 (8) | 16 (11) | 1.0000 | +0.5360 | 15.41 | 0.5996 | 2.91 pp |
| LiqSweep | 15 (10) | 12 (9) | 0.6957 | −0.8195 | 24.62 | 0.4204 | 2.53 pp |
| VolExpansion | 15 (9) | 12 (10) | 0.2357 | −0.8835 | 22.21 | 0.3864 | 2.47 pp |

*(Source: `artifacts/paper_sync_report.md` and
`artifacts/fee_slippage_analysis.json` at full precision; independently
confirmed live.)*

**No criterion crosses p = 0.05 in either test.** Welch p-range across all
five: **0.3775 – 0.7751**. See §7 for the framing question this range raises.

**How to say this correctly:** *"This sample is underpowered to distinguish
quality-criterion effects."* **Not** *"the criteria don't work."*

### 5.5 Cost sensitivity — where the significance claim breaks

Confirmed Binance USDT-M futures standard taker fee: **0.05% per side**
(0.10% round trip). Slippage — the gap between the price you expect and the
price you get — is modeled separately at a conservative 0.05% per side.

| Scenario | Total net return | Win rate | Binomial p (1-sided) |
|---|---|---|---|
| Gross (as reported) | +30.31% | 70.37% (19/27) | 0.0261 |
| + fee only (0.10% RT) | +27.61% | 70.37% (19/27) | 0.0261 |
| **+ fee + slippage (0.20% RT — primary)** | **+24.91%** | **62.96% (17/27)** | **0.1239** |

*(Source: `artifacts/fee_slippage_analysis.json`, all six scenarios.)*

> **VISUAL V-28 — Where the significance claim dies**
> **Type:** three-step stepped bar / waterfall with a significance threshold
> line at p = 0.05
> **Shows:** the exact point at which the headline claim stops holding
> **Data:** the three scenarios above; plot p on one axis with the α = 0.05
> line drawn across, so the third bar visibly crosses it
> **Build notes:** annotate the two trades that flip — gross +0.12% and
> +0.13%, both landing slightly negative under a 0.20% round-trip drag
> (`entry_idx` 7938 and 8188).
> **Caption:** *"Two nearly-breakeven trades change sign, the win rate drops
> from 19/27 to 17/27, and p moves from 0.026 to 0.124. This is a
> significance-conclusion flip and the paper reports it as one."*

**The asymmetry worth explaining:** the **Welch t-tests are mathematically
unaffected** by a flat per-trade drag. Subtracting the same constant from
every trade shifts both group means equally, leaving the *difference* between
them — and each group's variance — untouched. Verified: identical to four
decimals, gross vs fee-adjusted. So the *return-magnitude* story is robust to
costs; the *win-rate* story is not. Both facts belong in the same paragraph.

**One sensitivity-band caution:** across a wider drag range (0.14%–0.40% RT),
VolExpansion's Fisher p crosses 0.05 (reaching 0.0185) only at the most
pessimistic 0.40% end; at the primary 0.20% scenario it is 0.1071, not
significant. Flagged as a multiple-comparisons artifact (5 criteria × several
drag levels), **not** a finding.

### 5.6 Against the passive benchmarks

Same $10,000 notional, same 2022–2026 window, three independently computed
arms.

| Arm | Total return | Final capital | Sharpe | Sortino | Max drawdown | Time in market |
|---|---|---|---|---|---|---|
| OB-gated strategy | +30.31% | $13,417.77 | 1.114 | 2.727 | −6.46% | **2.63%** |
| Weekly DCA into BTC | **+123.13%** | **$22,312.94** | 0.556 | 0.886 | −27.85% | 100% |
| Lump-sum buy-and-hold | +90.07% | $19,007.32 | 0.564 | 0.803 | −67.21% | 100% |

*(Source: `artifacts/benchmark_vs_passive.json`, main window, gross block.)*

> **NEVER state without the caveat attached.** Both passive arms beat the
> strategy in raw terminal value over this window, and by a wide margin. What
> the strategy offers instead is a better risk-adjusted *shape* — Sharpe 1.114
> vs 0.556 and 0.564, max drawdown −6.46% vs −27.85% and −67.21% — achieved
> while holding a position only **2.63%** of the time against 100% continuous
> exposure. These are not like-for-like comparisons. No sentence anywhere in
> the artifact may state or imply that the strategy "beats DCA" or "beats
> BTC" without the exposure-time figure in the same breath.

**The defensible framing is the complementary sleeve.** Blending a small
strategy allocation into an existing DCA plan improves the portfolio's
risk-adjusted shape monotonically:

| Split (BTC-DCA / Strategy) | Sharpe | Sortino | Max drawdown |
|---|---|---|---|
| 100% / 0% | 0.556 | 0.886 | −27.85% |
| 90% / 10% | 0.581 | 0.930 | −26.51% |
| 80% / 20% | 0.607 | 0.978 | −24.97% |
| 70% / 30% | 0.637 | 1.032 | −23.18% |

*(Source: `artifacts/benchmark_dca_analysis.json` → `section_2_dca_blend`.)*

Absolute final value is **lower** at every split versus 100% DCA, because the
strategy sleeve sits idle most of the time. The claim is "improves the shape,"
never "replaces DCA."

**The 2018–2022 formulation window** (explicitly *not* out-of-sample —
this is the period the rule structure was originally designed against):

| Arm | Total return | Final capital | Sharpe | Max drawdown | Time in market |
|---|---|---|---|---|---|
| OB-gated strategy | +21.82% | $12,282.53 | 0.681 | −6.00% | 1.87% |
| Weekly DCA into BTC | +439.88% | $53,987.55 | 0.824 | −46.16% | 100% |
| Lump-sum buy-and-hold | +236.96% | $33,696.49 | 0.789 | −81.42% | 100% |

That window contained a much larger crash-and-recovery cycle, which
mechanically favors DCA's lower average cost basis. This is a property of the
benchmark's mechanics under that price path — not evidence about the
strategy's edge in either direction.

### 5.7 Out-of-sample and history-extension checks

**Forward out-of-sample test** — BTC/USDT 4H, 2026-01-01 through 2026-07-31,
data that genuinely postdates every commit to the strategy code:

| Metric | Value |
|---|---|
| New trades | 4 |
| Wins / losses | 1 / 3 |
| Win rate | 25.00% |
| Total return | **−3.45%** |
| Avg return / trade | −0.86% |

*(Source: `artifacts/oos_validation_analysis.json` → `section_1_forward_oos`.)*

**Reported as-is: small, and directionally unfavorable.** Four trades cannot
confirm or refute an edge on their own — the same MDE logic from §4.7 applies
— but this is the only genuinely prospective evidence that exists for this
rule set, and it does not add reassurance.

**8-year backfill integrity check.** MACD's EMAs and the static KDJ are
recursive, so in principle they carry memory back to the start of the data.
Would four extra years of warm-up change the locked window's results? The
frozen pipeline was re-run from 2018-01-01. **Result: PASS** — all 27 locked
trades matched by entry timestamp, maximum PnL difference **0.0000000000%**
(exact).

**Formulation-period comparison:**

| Window | N | Win rate | Total return | Binomial p (1-sided) |
|---|---|---|---|---|
| 2018-01 → 2022-01 (formulation, **not** OOS) | 25 | 60.00% | +21.82% | 0.2122 |
| 2022-01 → 2026-01 (locked baseline) | 27 | 70.37% | +30.31% | 0.0261 |
| Combined 2018–2026 (mixed provenance) | 56 | 62.50% | +48.68% | 0.0407 |

**The combined row must never be cited alone** — about half of it comes from
the formulation period, so its p = 0.0407 partly reflects performance on data
the rules could see during development. Notably the strategy did *worse* on
its own formulation period than on the reported window — the opposite of what
naive overfitting would predict.

### 5.8 Regime dependence

| Regime (calendar split) | Trades | Win rate | Return contribution | Share of total |
|---|---|---|---|---|
| BEAR (2022) | 7 | 57.14% | +10.45% | +34.5% |
| CHOP (2023) | 6 | 50.00% | −5.39% | −17.8% |
| BULL (2024–25) | 14 | 85.71% | +25.25% | +83.3% |

| Regime (drawdown-from-ATH split) | Trades | Win rate | Return contribution | Share of total |
|---|---|---|---|---|
| BEAR (≤ −40% dd) | 12 | 50.00% | −1.63% | −5.4% |
| CHOP (−40% to −12% dd) | 8 | 87.50% | +18.89% | +62.3% |
| BULL (> −12% dd) | 7 | 85.71% | +13.05% | +43.1% |

*(Source: `artifacts/regime_breakdown_analysis.json`, via paper §2.6.)*

The two classification methods agree on only **13 of 27** trade assignments —
they measure different things, since most of calendar-2023 was still 57–64%
below the all-time high. But they agree on the conclusion that matters: **the
bull regime is strongest under both methods (85.71% win rate).** The
strategy's aggregate performance leans on the 2024–25 bull phase. The three
most-concentrated winners are *not* all drawn from one regime under either
method, which is a modest point in its favor — but it does not offset the
broader regime-concentration finding.

---

## 6. Discussion and the two disclosed divergences

### 6.1 D1 — The ablation reconstruction gap

**What an ablation is:** remove one component and re-run, to see how much
that component was contributing. Standard practice — the same idea as
removing one ingredient to find out what it was doing to the recipe.

**The ablation design here — three arms:**

| Arm | Entry rule | Where the stop goes | N | Win rate | Total return |
|---|---|---|---|---|---|
| 1 — OB-gated baseline | OB touch **+** MACD/KDJ/ATR | OB boundary − 0.5 × ATR | 27 | 70.37% | +30.31% |
| 2 — Indicators only (flat-ATR stop) | MACD/KDJ/ATR **only** | close − 1.5 × ATR | 140 | 60.00% | −14.63% |
| 3 — Indicators only (swing-pivot stop) | MACD/KDJ/ATR **only** | 5-bar swing pivot ± 0.5 × ATR | 138 | 55.07% | −25.50% |

**What it establishes:** without the Order Block gate, the same indicator
conditions fire **five times more often** and **lose money**. And arm 3 exists
specifically to un-confound two explanations: maybe the ungated arms failed
because of their *stop placement*, not their *entry selection*. Giving arm 3 a
structural swing-anchored stop changed the candidate count negligibly (138 vs
140, −1.4%) and did **not** rescue performance. So the gate's contribution is
about *which trades get taken*, not about where the stop sits.

**The disclosed problem:**

> **No committed script in this repository reproduces the published
> 140/138-trade win rates from scratch. The script that originally produced
> them was never committed.**

A best-faith reconstruction was built from the documented design. It
reproduces the trade **counts exactly** — but not the per-trade outcomes:

| Arm | N (locked) | N (reconstructed) | Win rate locked | Win rate reconstructed | Return locked | Return reconstructed |
|---|---|---|---|---|---|---|
| A — flat-ATR | 140 | **140 ✓** | 60.00% | **47.14%** (66/140) | −14.63% | −13.72% |
| B — swing-pivot | 138 | **138 ✓** | 55.07% | **43.48%** (60/138) | −25.50% | −23.85% |

*(Source: `artifacts/ablation_reconstruction.json`, `status_vs_locked:
"DIVERGE"` for both arms; independently reproduced during the 2026-08-20
audit.)*

**Why this is disclosed rather than fixed, and why it does not sink the
paper's conclusion:**

1. **The exact N match is informative.** 140 and 138, hit exactly, means the
   *entry-side* logic is faithfully reproduced. The gap is somewhere
   post-entry.
2. **It was investigated, not merely noted.** Twenty combinations were tested
   and ruled out: fixed 1R / 1.5R / 2R / 3R take-profits, an OB-structural
   take-profit, and four exit-stack orderings. Only the unmodified
   configuration reproduces the locked counts; every variant that touches
   take-profit distance or exit ordering also shifts N away from 140/138.
3. **Fixed-2R and fixed-3R give identical results**, which proves the
   take-profit is almost never the operative exit at this distance — so the
   take-profit formula cannot be the cause. (This matches V-11: the hard
   take-profit fired zero times in the baseline too.)
4. **An independent earlier reconstruction failed the same way**, 13 days
   earlier, arrived at separately. Converging evidence.
5. **The conclusion does not depend on the exact win rates.** Both the locked
   figures (60.00% / 55.07%) and the reconstruction (47.14% / 43.48%) say the
   same thing: the ungated arms take five times as many trades and lose money.
   The direction and magnitude of the finding are unchanged.
6. **Two candidate explanations remain untested and are named as such:**
   (a) the original script may have checked intrabar high/low against
   stop/target levels rather than close-price-only, which would raise win
   rate without necessarily moving N or aggregate return much; (b) different
   trailing-exit or KDJ-reset parameters in a no-OB context.

> **VISUAL V-29 — D1: what matches and what doesn't**
> **Type:** side-by-side comparison panel with match/mismatch indicators
> **Shows:** that the entry side is reproduced exactly and only the
> post-entry outcomes diverge
> **Data:** the reconstruction table above
> **Build notes:** put green check marks on the two N rows and amber markers
> on the win-rate and return rows. Beneath, a short "ruled out" strip listing
> the 20 tested combinations as a single compact row of chips, and a "still
> open" strip with the two named candidates. The visual argument is: *this is
> a documented investigation with a known boundary, not an unexplained
> discrepancy.*

**How to present this to a panel:** it converts "we can't reproduce it" into
"we ruled out the twenty most likely mechanical causes and named exactly what
remains." That is a stronger position, not a weaker one. The locked figures
remain the paper's canonical numbers; the reconstruction exists to document
the gap, not to replace them.

### 6.2 D2 — The bootstrap resample-count mismatch

**The observation:** the paper reports a 95% confidence interval on total
return of **[+5.99%, +54.99%]**. The interactive dashboard shows
**[+7.48%, +54.46%]**. Same data, same seed, different numbers.

| Surface | B (resamples) | Seed | Random generator | 95% CI |
|---|---|---|---|---|
| Python — `run_bootstrap_ci()` (**paper canonical**) | 10,000 | 42 | numpy `default_rng` | **[+5.99%, +54.99%]** |
| JavaScript — `statsCompute.ts` | 2,000 | 42 | `mulberry32` | **[+7.48%, +54.46%]** |

**Why the gap exists:** the bootstrap is a random procedure. Its percentile
estimates settle down as the number of resamples grows. Ten thousand draws
land in a slightly different place than two thousand. Both intervals are
individually correct estimates of the same thing.

**Why the dashboard uses fewer:** it runs in the browser, live, on every
page load. Two thousand resamples is a responsiveness choice.

**The root cause was proven, not assumed.** The dashboard's `mulberry32`
pseudo-random generator was ported to Python and run at B = 2,000 — it
reproduces **[+7.48%, +54.46%] exactly**. That rules out a logic difference,
a different seed, and a different trade set, and pins the entire gap on the
resample count.

**Why it is not unified:** the JavaScript dashboard is a deliberately
independent cross-check of the Python pipeline. Forcing the two to share a
parameter would erode exactly the independence that makes the agreement
meaningful. The dashboard labels the row MISMATCH on screen with both B
values visible. The paper discloses both intervals and explains the gap.

> **VISUAL V-30 — Why two intervals, and why both are right**
> **Type:** overlaid interval bars on one shared axis, plus a small
> "convergence" inset
> **Shows:** that the two intervals nearly coincide and the difference is
> resolution, not disagreement
> **Data:** two horizontal bars on a shared % axis — Python B=10,000
> [+5.99%, +54.99%] and JS B=2,000 [+7.48%, +54.46%] — with the point
> estimate +30.31% marked on both and zero marked well outside both.
> **Build notes:** a small inset sketch showing an interval estimate steadying
> as B rises makes the "resolution, not disagreement" point instantly.
> Caption: *"Root cause proven by porting the browser's random-number
> generator to Python and reproducing the JS interval exactly at B = 2,000."*

### 6.3 What the evidence supports, and what it does not

> **VISUAL V-31 — Supported / not supported ledger**
> **Type:** two-column ledger, deliberately balanced in visual weight
> **Shows:** the honest scope of the conclusions
> **Data:**
>
> **Supported**
> - A historically observed, directionally robust return edge for this
>   specific rule set on this specific window. Bootstrap 95% CI
>   [+5.99%, +54.99%] excludes zero; 99.25% of 10,000 resamples positive.
> - The Order Block gate materially changes outcomes: 27 gated trades at
>   +30.31% vs ~140 ungated trades losing money — and that survives
>   disentangling entry selection from stop placement.
> - The return-magnitude finding is robust to transaction costs (the Welch
>   tests are mathematically invariant to a flat per-trade drag).
> - An audited, disclosed self-correction history, with a golden-master
>   regression harness, a no-lookahead proof, and an independent second
>   implementation.
>
> **Not supported**
> - That any individual quality criterion predicts outcome. **Underpowered,
>   not disproven** — every observed gap is 3–10× below the detection floor.
> - That the win-rate significance claim survives realistic trading costs
>   (p: 0.026 → 0.124).
> - That the strategy beats buy-and-hold or DCA. It did not, in raw terminal
>   value, in either window tested.
> - That the edge generalizes evenly across market regimes — it concentrates
>   in bull conditions (85.71% win rate under both classification methods).
> - That the edge persists prospectively. The only prospective evidence — 4
>   trades in 2026 — was unfavorable.
> - That the ablation trade-level figures, or the "190 qualifying indicator
>   signals" denominator, are independently reproducible from this repository
>   as currently committed.
>
> **Build notes:** the two columns must be the same size and the same visual
> weight. A guide that makes the left column bigger is doing rhetoric, not
> science.

### 6.4 Two open items, explicitly unresolved

**The "190 qualifying indicator signals" denominator.** The paper states that
25 of 27 OB-gated trades (92.6%) coincided with independent indicator
signals, using 190 as the denominator. That 190 was derived under the
*indicators-only ablation's* 1.5 × ATR entry-anchored stop — **not** the
OB-gated strategy's own risk rules. The two populations are filtered
differently. **Do not cite 190 as settled.** It is listed in the paper's own
future-work section as something to either re-derive under the correct rules
or drop.

**The ablation reproducibility gap** (§6.1) — open, disclosed, and with two
named untested candidate explanations.

### 6.5 Known limitations to state plainly

| Limitation | Why it matters |
|---|---|
| **n = 27** | Small. Subgroups as small as n = 4. Everything about the power analysis flows from this. |
| **~0.56 trades/month** | Statistical power will only accumulate slowly. More years is the only fix, and it is a slow one. |
| **Single asset, single timeframe** | BTC/USDT, 4-hour. No claim extends beyond that. |
| **One window** | 2022–2026 happened to contain a substantial bull phase that contributed 83.3% of total return share under the calendar method. |
| **Return concentration** | Three trades account for 51.7% of the total return. |
| **Close-price execution** | Entries and exits are evaluated on bar closes. Real fills happen intrabar. This is also one of the two open candidate explanations for D1. |
| **No risk-free rate** | Sharpe and Sortino use an implicit Rf = 0. Disclosed; a non-zero rate lowers every Sharpe here. |
| **Cost sensitivity** | The win-rate significance claim does not survive a realistic 0.20% round-trip drag. |
| **Prospective evidence is negative** | 4 trades, −3.45%. Too small to conclude from, reported anyway. |

---

## 7. The Displacement inclusion question (F1)

This is an open decision, not a settled result. It should be presented to the
reader as a live methodological choice with two defensible answers — that is
the honest state of it.

### 7.1 The setup

Five criteria were tested. Five Welch p-values came back, none significant:

| Criterion | Split (True / False) | Welch ν | Welch p |
|---|---|---|---|
| **Displacement** | **4 / 23** | **9.10** | **0.3775** ← lowest of all five |
| VolExpansion | 15 / 12 | 22.21 | 0.3864 ← lowest of the other four |
| LiqSweep | 15 / 12 | 24.62 | 0.4204 |
| FVG | 11 / 16 | 15.41 | 0.5996 |
| **LargeBar** | 20 / 7 | 20.87 | **0.7751** ← highest, either way |

### 7.2 The question

The paper summarizes these five results as a **range** — "the p-values ran
from X to Y, none significant." Which range?

| | Range | Floor set by | Ceiling set by |
|---|---|---|---|
| **Full range** — all 5 criteria | **0.3775 – 0.7751** ("0.38–0.78") | Displacement | LargeBar |
| **Restricted range** — 4 criteria, Displacement excluded | **0.3864 – 0.7751** ("0.39–0.78") | VolExpansion | LargeBar |

The ceiling is identical either way. **Only the floor moves, and only by
0.0089.**

### 7.3 Why the question exists at all

Displacement's split is **4 trades vs 23**. Only four of the 27 baseline
trades entered on a zone that had the Displacement feature. That is thin
enough that the paper's own methodology text describes Displacement as
excluded from the formally-tested set for insufficient sample — while
`CLAUDE.md`'s pending correction note quotes the *full* five-criterion range.
The document currently uses both framings in different places.

The Welch degrees-of-freedom figure quantifies exactly how thin: from the
same 27 trades, Displacement retains only **ν = 9.10** of effective
information, against LiqSweep's **24.62**. That is the numerical form of "this
split is too lopsided to lean on."

> **VISUAL V-32 — Full range vs restricted range**
> **Type:** two number lines stacked on a shared axis, plus the decision
> flowchart beneath
> **Shows:** how little actually turns on the choice, and what the choice is
> **Data:**
> **Top:** a p-axis from 0.30 to 0.85. Plot all five criteria as labeled dots
> at 0.3775, 0.3864, 0.4204, 0.5996, 0.7751. Draw the α = 0.05 threshold far
> off to the left, clearly outside the plotted region, with a note: *"the
> significance line is nowhere near any of these — none of the five comes
> close."*
> **Middle:** two bracket bars beneath the same axis — one spanning
> 0.3775→0.7751 labeled "all 5 criteria (0.38–0.78)", one spanning
> 0.3864→0.7751 labeled "4 criteria, Displacement excluded (0.39–0.78)". Mark
> the 0.0089 difference at the left end.
> **Bottom — decision flowchart:**
> "Is Displacement inside the formally-tested set?"
> → **YES** → report **0.38–0.78** → *then* the Limitations section and §2.4
> and §3 must all describe the n = 4 subgroup as *tested but underpowered*
> → **NO** → report **0.39–0.78** → *then* those same sections must describe
> it as *excluded for insufficient sample*, and say so consistently
> **Build notes:** the flowchart's point is that the choice is not local to
> one sentence — it propagates to §2.4, §3 and the Limitations section
> together. That is why it needs a human decision rather than a find-and-
> replace.

### 7.4 What the paper currently does, and how to explain it

**The paper reports both, and flags the tension explicitly rather than
picking one silently.** The draft's §2.3 contains a standing note stating that
both ranges are internally correct, that the inclusion question is a
methodological choice, and that whichever framing is chosen must be made
consistent across §2.3, §2.4, §3 and Limitations before the paper is
finalized.

**How the student should answer if a judge asks:**

> "We tested all five criteria and got five p-values, none of them close to
> significant — the lowest was 0.38 and the highest 0.78. One of them,
> Displacement, only had four trades on the 'true' side, which is thin enough
> that we flag it separately. If you drop it, the range becomes 0.39 to 0.78.
> Either way the conclusion is identical: not one criterion is anywhere near
> the significance line, and the power analysis shows this sample couldn't
> have detected an effect of the size we observed anyway. We report both
> ranges rather than quietly choosing the one we prefer."

> **VISUAL V-33 — "Does the choice change any conclusion?" checklist**
> **Type:** small three-row check table
> **Shows:** that the answer is no, three times over
> **Data:**
> | Does the framing change… | Answer |
> |---|---|
> | Whether any criterion is significant? | **No** — none is, under either framing |
> | The highest p-value? | **No** — LargeBar's 0.7751 either way |
> | The MDE / power conclusion? | **No** — all five gaps stay 3–10× below the detection floor |
> **Build notes:** three green "No" marks. This is the reassurance card that
> closes the section — the decision is about internal consistency of wording,
> not about what the study found.

---

## 8. Glossary — first-use definitions

Every one of these must be defined at first use in the artifact. Listed here
in a suggested order of first appearance so the builder can check coverage.

| # | Term | One-line plain definition |
|---|---|---|
| 1 | Backtest | Running a trading rule over price history that already happened, to see what it would have done. A simulation, not a track record. |
| 2 | Pre-registered | The rules and their numbers were fixed before results were measured, and never adjusted afterward to improve them. |
| 3 | Candle | One row of price data for a fixed time slice: open, high, low, close, volume. |
| 4 | 4-hour timeframe | Each candle summarizes 4 hours of trading. |
| 5 | Indicator | A number calculated from recent price, summarizing something a chart shows visually. |
| 6 | Moving average / EMA | A rolling average of price; the exponential version weights recent bars more heavily, so it reacts faster. |
| 7 | MACD | Momentum indicator built from the gap between a fast and a slow moving average. |
| 8 | KDJ | Oscillator showing where the current price sits inside its recent high–low range; used for overbought/oversold timing. |
| 9 | ATR | Average True Range — typical distance price travels in one bar. A volatility measure, in price units. |
| 10 | Volatility | How much and how fast price moves around. |
| 11 | Order Block (OB) | The last candle before a decisive structural break; treated as a price zone that may act as support or resistance if price returns. |
| 12 | Smart Money Concepts (SMC) | A family of chart-structure trading ideas about where large orders sit. |
| 13 | DEMAND / SUPPLY zone | A zone below price (buy candidate) / above price (sell-short candidate). |
| 14 | Pivot high / low | A bar whose high (low) exceeds every bar after it up to now — confirmable only in hindsight. |
| 15 | BOS / CHoCH | Break of Structure (trend continues) / Change of Character (trend flips). |
| 16 | Mitigated | The zone is dead — price closed straight through it. |
| 17 | Fair Value Gap (FVG) | A three-candle price gap where the middle move was so fast that a band of prices never traded. |
| 18 | Liquidity sweep | A spike past a recent extreme that likely triggers other traders' stop-losses, then reverses. |
| 19 | Displacement | A forceful, large-bodied candle moving away from a zone right after it forms. |
| 20 | Orthogonal | Independent — each criterion is evaluated on its own, and being true tells you nothing about the others. |
| 21 | LONG / SHORT | Betting price rises / betting price falls. |
| 22 | Stop-loss | A pre-set exit price that caps the loss if the trade goes wrong. |
| 23 | Take-profit | A pre-set exit price that banks the gain. |
| 24 | Reward-to-risk (R:R) | Potential gain ÷ potential loss. R:R = 1.5 means risking $1 to make $1.50. |
| 25 | Breakeven ratchet | Moving the stop up to the entry price once a trade is comfortably ahead, removing the downside. |
| 26 | Slippage | The gap between the price you expect and the price you actually get. |
| 27 | Round trip | Both sides of a trade — entry plus exit — so costs count twice. |
| 28 | Basis point (bp) | One hundredth of a percent. 5 bps = 0.05%. |
| 29 | Null hypothesis | The boring explanation: nothing is going on, the results are chance. |
| 30 | p-value | How often pure chance alone would produce a result this good or better. Small = surprising fluke. |
| 31 | α (alpha) = 0.05 | The conventional line for calling a result "statistically significant." A convention, not a law. |
| 32 | One-sided / two-sided | Testing "is it better?" vs "is it different, either way?" |
| 33 | Binomial test | Tests a win count against a fixed baseline probability, like a coin flip. |
| 34 | Fisher's exact test | Tests whether two groups' win *rates* differ; exact, so it works with tiny groups. |
| 35 | Contingency table | The 2×2 grid of wins and losses in each group that Fisher's test reads. |
| 36 | Welch's t-test | Tests whether two groups' *average* values differ, without assuming equal variability. |
| 37 | Variance / standard deviation | How spread out the numbers are around their average. |
| 38 | Degrees of freedom | Roughly, how much independent information a sample carries. |
| 39 | Welch–Satterthwaite df (ν) | The fractional effective degrees of freedom Welch's test uses; it shrinks when the split is lopsided. |
| 40 | Pearson r | Strength of a straight-line association between two measurements, from −1 to +1. |
| 41 | Spearman ρ | The same idea computed on ranks — catches any consistent trend and resists outliers. |
| 42 | Bootstrap resampling | Re-drawing your own data with replacement, many times, to see how much a result could have wobbled. |
| 43 | Confidence interval | The range that contains the middle 95% of those re-drawn results. |
| 44 | Statistical power | The chance a test finds a real effect that is actually there. Convention: 80%. |
| 45 | Minimum Detectable Effect (MDE) | The smallest true difference this sample size could reliably detect. |
| 46 | Underpowered | The test could not have found the effect even if it were real — so "no result" means "no information," not "no effect." |
| 47 | Ablation | Removing one component and re-running, to measure what that component contributed. |
| 48 | Lookahead / data leakage | Accidentally using information a real trader would not have had yet. |
| 49 | Golden-master regression | A test that stores known-correct outputs and fails on any deviation. |
| 50 | Sharpe ratio | Return per unit of total volatility, annualized. |
| 51 | Sortino ratio | Return per unit of *downside* volatility only. |
| 52 | Maximum drawdown | The worst peak-to-trough fall in the equity curve. |
| 53 | Time in market | The share of all bars during which a position was open. |
| 54 | DCA (dollar-cost averaging) | Buying a fixed dollar amount on a fixed schedule, regardless of price. |
| 55 | Lump-sum buy-and-hold | Buying once at the start and holding, untouched, to the end. |
| 56 | Equity curve | Account value plotted over time. |
| 57 | Out-of-sample | Data the rules had never seen — here, genuinely postdating every code commit. |
| 58 | Formulation period | The period the rules were originally designed against. **Not** out-of-sample. |
| 59 | Regime | A market phase — bull, bear, or choppy. |
| 60 | Multiple comparisons | Run enough tests and one crosses p = 0.05 by chance alone; an artifact, not a finding. |

---

## 9. Source and verification appendix

### 9.1 Verification method

Every numeric claim in this handoff was obtained one of two ways, and no
other way:

1. **Read from a committed artifact** in `artifacts/` or `docs/` — the source
   file is named beside the figure.
2. **Recomputed live** on 2026-08-21 by loading `research_analysis.py`,
   running `load_candles()` → `compute_indicators()` → `compute_smc()` →
   `simulate_trades(min_ob_quality=0)`, and calling the Section 5 statistical
   primitives directly.

No figure in this document was carried over from memory, restated from a
prose summary, or estimated.

### 9.2 Figure-to-source map

| Figure(s) | Source |
|---|---|
| 8,767 bars; window 2022-01-01 08:00 → 2026-01-01 08:00 | live `len(load_candles())` = 8767; `artifacts/verification_report.json` → `source_checks.first_candle_utc` / `last_candle_utc` |
| 27 trades · 70.37037% · +30.30646% · +1.12246% · SD 2.41014% | live `simulate_trades(min_ob_quality=0).attrs['trade_stats']` + `pnl_pct.std(ddof=1)`; matches `artifacts/paper_sync_report.md` and `artifacts/threshold_runs.json` |
| 19 wins / 8 losses | live `(trades_df.pnl_pct > 0).sum()` = 19 |
| Binomial p 0.026119 / 0.052239 | live `binomial_test(19, 27)` |
| q≥1: 25 trades · 68.00% · +28.3068% · p 0.053876 | live `simulate_trades(min_ob_quality=1)` + `binomial_test(17, 25)` |
| q0–q3 sweep (27/25/23/14) | `artifacts/threshold_runs.json`; live |
| q≥4, q≥5 rows | `artifacts/paper_sync_report.md` § "Full q0–q5 threshold sweep (live)" |
| 761 Order Blocks | live `len(compute_smc(df))` = 761 |
| Quality distribution 93/154/206/197/90/21 | live `Counter(ob['quality'])`; matches `artifacts/paper_sync_report.md` |
| Criterion true-counts: Displacement 107 (14.06%), LargeBar 444 (58.34%), FVG 253 (33.25%), LiqSweep 406 (53.35%), VolExpansion 412 (54.14%) | live per-criterion count over the 761 OBs |
| Fisher p, Welch t, Welch ν, Welch p — all 5 criteria | live `run_criteria_significance_tests(trades_df)`; matches `artifacts/paper_sync_report.md` and `artifacts/fee_slippage_analysis.json` (full precision) |
| MDE table (observed gap, MDE, per criterion) | `artifacts/bootstrap_power_analysis.json` → `mde_power` |
| Bootstrap CI [+5.9866%, +54.9866%]; avg CI [+0.2217%, +2.0365%]; 99.25% positive | live `run_bootstrap_ci(trades_df)` (B = 10,000, seed 42); matches `artifacts/bootstrap_power_analysis.json` (`pct_resamples_total_le_zero` = 0.75) |
| JS bootstrap CI [+7.48%, +54.46%] (B = 2,000, mulberry32) | CLAUDE.md "Paper reporting corrections" #2; `dashboard-v2/src/components/stats/statsCompute.ts` |
| Pearson r +0.490698, p 0.009356; Spearman ρ +0.479728, p 0.011335 | live `pearson_correlation` / `spearman_correlation` on (hold_bars, pnl_pct), n = 27 |
| Exit-reason counts (ATR 9 / trailing 8 / KDJ 8 / SL 2 / TP 0) | live `trades_df.exit_reason.value_counts()` |
| 15 LONG / 12 SHORT | live `trades_df.side.value_counts()` |
| Hold bars 1–16, median 10 | live `trades_df.hold_bars` |
| Best +6.6888%, worst −4.6544% | live `trades_df.pnl_pct.max()` / `.min()` |
| KDJ exit window w: 14–439, median 74 | live `trades_df.kdj_exit_window` |
| ~0.56 trades/month | 27 ÷ 48 months = 0.5625 |
| Fee/slippage: +30.31%/70.37%/0.0261 · +27.61%/70.37%/0.0261 · +24.91%/62.96%/0.1239 | `artifacts/fee_slippage_analysis.json`, scenarios at drag 0.0 / 0.1 / 0.2 |
| Flipped trades `entry_idx` 7938 (+0.1196% → −0.0804%) and 8188 (+0.1264% → −0.0736%) | `artifacts/fee_slippage_analysis.json`, drag 0.2 scenario → `flipped_trades` |
| VolExpansion Fisher 0.1071 @ 0.20% RT, 0.0185 @ 0.40% RT | `artifacts/fee_slippage_analysis.json`, drag 0.2 / 0.4 scenarios |
| Benchmark 2022–26 gross: strategy +30.31%/$13,417.77/1.114/2.727/−6.46%/2.63%; DCA +123.13%/$22,312.94/0.556/0.886/−27.85%; lump-sum +90.07%/$19,007.32/0.564/0.803/−67.21% | `artifacts/benchmark_vs_passive.json` → `main_window.gross` |
| Fee-adjusted strategy +24.91% → $12,719.01 | `artifacts/benchmark_vs_passive.json` → `main_window.fee_adjusted` |
| 2018–22: strategy +21.82%/$12,282.53/0.681/−6.00%/1.87%; DCA +439.88%/$53,987.55/0.824/−46.16%; lump-sum +236.96%/$33,696.49/0.789/−81.42% | `artifacts/benchmark_vs_passive.json` → `formulation_period_window.gross` |
| 231 bars of exposure | `artifacts/benchmark_dca_analysis.json` → `section_1_benchmark.strategy.bars_of_exposure` |
| DCA blend Sharpe/Sortino/MaxDD at 100/0, 90/10, 80/20, 70/30 | `artifacts/benchmark_dca_analysis.json` → `section_2_dca_blend.splits` |
| Forward OOS: 4 trades, 1 W / 3 L, 25.00%, −3.4471%, −0.8618% | `artifacts/oos_validation_analysis.json` → `section_1_forward_oos.oos_summary` |
| Formulation window 25 trades / 60.00% / +21.8246%; combined 56 / 62.50% / +48.6839% | `artifacts/oos_validation_analysis.json` → `section_2_backfill_audit` |
| Formulation-window binomial p 0.2122; combined p 0.0407 | `docs/paper_full_update_2026-08-08.md` § 2.8 |
| 8-year backfill: all 27 trades matched, max PnL difference 0.0000000000% | `docs/paper_full_update_2026-08-08.md` § 2.8; `oos_validation_analysis.json` → `methodological_verdict: true` |
| Regime tables (calendar and drawdown), 13/27 agreement, top-3 = 51.7% | `artifacts/regime_breakdown_analysis.json`, via `docs/paper_full_update_2026-08-08.md` § 2.6 |
| Ablation locked: 140 / 60.00% / −14.63% and 138 / 55.07% / −25.50% | CLAUDE.md "Locked results"; `artifacts/ablation_reconstruction.json` → `arms.*.locked` |
| Ablation reconstructed: 140 / 47.1429% (66 W) / −13.7214% and 138 / 43.4783% (60 W) / −23.8461% | `artifacts/ablation_reconstruction.json` → `arms.*.reconstructed`; `status_vs_locked: "DIVERGE"` |
| 20 ruled-out TP/exit combinations; the two remaining candidate explanations | `research_analysis.py` § 4 header, lines 2311–2367 |
| Bug 3 impact: FVG 362→253, displacement 112→107, 110/761 OBs affected, q≥1 26→25, p 0.038→0.054, `entry_idx` 3100 | CLAUDE.md "Known bugs" #3; post-fix values confirmed live |
| No-lookahead proof: 180/180 checks; 0/253 FVG and 0/107 displacement OBs read past confirmation | `docs/paper_full_update_2026-08-08.md` § 1.8 |
| Welch df three-way agreement (scipy 9.102077 / numpy identical / TypeScript 9.10) | `docs/handoff_2026-08-20.html` § 3.3; `artifacts/fee_slippage_analysis.json` at full precision |
| 14/14 verification hashes reproduced | `docs/AUDIT_REPORT_2026-08-20.md` § B4 / B4b |
| Regression harness PASS | `docs/AUDIT_REPORT_2026-08-20.md` § B1 |
| Parameter values (all 8, plus the 3 SMC constants) | `research_analysis.py:133-147` |
| The "190 signals" open question | CLAUDE.md "Open question"; `docs/paper_full_update_2026-08-08.md` § 3, § 5 item 4 |
| Displacement F1 framing: 0.3775–0.7751 vs 0.3864–0.7751 | `docs/paper_full_update_2026-08-08.md` § 2.3 (the standing flag) and § 5 item 3; both endpoints confirmed live |

### 9.3 Repository state at time of writing

- Branch `development`, HEAD `7154d43`
- Working tree **dirty** — uncommitted: `research_analysis.py`,
  `dashboard-v2/src/types/artifacts.ts`,
  `dashboard-v2/src/components/tabs/StatsTab.tsx`,
  `docs/paper_full_update_2026-08-08.md`, five files under `artifacts/`,
  `backtest_results.db`. Untracked: `PLAN.md`, `docs/AUDIT_REPORT_2026-08-20.md`,
  `docs/MATH_CORRECTNESS_AND_COMPREHENSION.md`, `docs/PROVENANCE_VERDICT.md`,
  `docs/license_verification.md`, `docs/handoff_2026-08-20.html`, and this file.
- Regression harness: **PASS** as of the 2026-08-20 audit; not re-run for this
  document, which changed no code.
- The figures above reflect the current working tree, which is the state the
  2026-08-20 audit verified.

### 9.4 Two things the artifact must never do

1. **Never state or imply that the strategy "beats DCA" or "beats BTC"**
   without the exposure-time figure (2.63% vs 100%) in the same sentence.
   Both passive arms won on raw terminal value in both windows tested.
2. **Never report a non-significant criterion result as "no difference" or
   "the criteria don't work."** The supported statement is *"insufficient
   power to distinguish quality-criterion effects at this sample size."*

---

*Prepared 2026-08-21 from `research_analysis.py`, `artifacts/*.json`,
`artifacts/paper_sync_report.md`, `docs/paper_full_update_2026-08-08.md`,
`docs/AUDIT_REPORT_2026-08-20.md`, `CLAUDE.md`, and live recomputation.*
