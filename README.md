Binance Backtest Bot (Compliance Version)

This project is a Python backtest and reporting bot that pulls BTC/USDT market data, computes indicators, simulates SMC trades, and hosts an interactive visual dashboard.

---

## 🚀 Quick Start: How to Run the Dashboard

The easiest way to run the entire project is using the automated dashboard launcher. This will run the backtests, compile the trade data, start a local server, and open the visual interface in your browser.

### 1. Install Dependencies
Make sure you have the required libraries installed:
```bash
pip install pandas numpy python-binance oauth2client gspread gspread-formatting
```

### 2. Run the Dashboard Launcher
Simply run the runner script:
```bash
python Run_Dashboard.py
```
* **Offline Mode (Default)**: The script will load from the local candles cache and immediately launch the web UI at `http://127.0.0.1:8765/gui.html`.
* **Online Mode (Binance API & Google Sheets Export)**: To pull live data and upload results to Google Sheets, set the following environment variables first:
  ```bash
  # Optional: Binance Keys
  set BINANCE_API_KEY=your_key
  set BINANCE_API_SECRET=your_secret

  # Optional: Google Sheets Credentials
  set GOOGLE_SERVICE_KEY_PATH=path/to/service-key.json
  set GOOGLE_SHEET_ID=your_sheet_id
  ```

### 3. Run with Docker (Alternative Setup)
Alternatively, you can build and run the project inside a Docker container. The included `Dockerfile` installs all dependencies (including NumPy, Pandas, SciPy, and SQLAlchemy) and launches the pipeline:
```bash
# Build the Docker image
docker build -t binance-backtest-bot .

# Run the container (exposes the dashboard on port 8765)
docker run -p 8765:8765 binance-backtest-bot
```
This automatically runs the backtest simulations, saves the trade results locally to `backtest_results.db`, and launches the interactive dashboard server at `http://localhost:8765/gui.html`.

---

## Interactive Backtest Dashboard

The project includes a high-performance web dashboard built with Lightweight Charts for visual verification of backtest results.

Key Features:
- **Unified Crosshair Sync**: A single, synchronized vertical crosshair across all panes (Main, MACD, KDJ, ATR) for precise multi-indicator alignment.
- **Dynamic Trade Labels**: Automatic rendering of entries and exits directly on the chart, with tooltips showing specific exit reasons (e.g., "KDJ RESET EXIT", "ATR MOVE EXIT").
- **Persistent Layout**: Draggable pane resizers with state persistence via `localStorage`, ensuring your custom layout remains between sessions.
- **Technical Analysis Overlays**: Real-time rendering of SMC Order Blocks, Fair Value Gaps, and structural pivots.
- **Indicator Suite**: Fully synchronized sub-panes for MACD (Histogram/Signal), KDJ (K/D/J lines), and ATR (Current/Baseline).

The strategy in this file is the v9 variant documented in the source comments, with two key adjustments from prior versions:
- Minimum SL distance filter: reject entries with risk less than 1.5% of entry.
- KDJ reset exits are blocked for the first 3 bars after entry.

---

File Scope

Main script:
- `src/Binance backtest bot.py`

Expected local structure:
- `SERVICE KEY/` (for Google service account json file)
- optional local `.env` file (if your runtime loads env vars from it)

---

Security and Credentials

The bot is designed to be upload-safe when used correctly:

- **Binance keys**
  - Read from environment variables:
    - `BINANCE_API_KEY`
    - `BINANCE_API_SECRET`
  - No hardcoded Binance key in code.

- **Google Sheets credentials**
  - Read from:
    - `GOOGLE_SERVICE_KEY_PATH` (env var preferred)
    - fallback placeholder path in code:
      - `SERVICE KEY/your-service-account-key.json`
  - Sheet target read from:
    - `GOOGLE_SHEET_ID` (env var preferred)
    - fallback placeholder:
      - `your_google_sheet_id_here`

- **Runtime safety checks**
  - Export step raises clear `ValueError` if placeholders are still unchanged.

Recommended for GitHub:
- Keep real secrets out of repository.
- Commit placeholders/examples only.
- Ignore `SERVICE KEY/*.json`, `.env`, and private key files in `.gitignore`.

---

Data Pipeline Overview

1. Fetch candles (`get_candles`)
   - Source: Binance `get_klines`.
   - Default symbol/interval in main run: `BTCUSDT`, `4H`.
   - Converts numeric columns to float.
   - Converts open time to datetime and applies `+8h` offset.

2. Compute indicators (`compute_indicators`)
   - MACD: `12,26,9`.
   - KDJ: period default `9`, smoothing alpha `1/3`.
   - ATR: period `14`.
   - ATR_200: long volatility baseline.

3. Build market structure/order blocks (`compute_smc`)
   - Two structure passes:
     - internal (`INTERNAL_SIZE=5`)
     - swing (`SWING_SIZE=50`)
   - Detects pivots, BOS/CHoCH crossover events, and creates OBs.
   - OB includes:
     - type (`DEMAND`/`SUPPLY`)
     - top, bottom
     - creation and OB bar indexes
     - structure metadata
     - quality sub-signals and aggregate quality score (0-5)
   - Computes mitigation invalidation bar for each OB.

4. Simulate trades (`simulate_trades`)
   - Runs bar-by-bar with no forward-looking data.
   - Uses active, unmitigated OBs under age constraint (`MAX_OB_AGE=500`).
   - Supports OB quality filtering via `min_ob_quality`.

5. Export to Google Sheets (`push_all_thresholds_to_gsheet`)
   - Runs quality sweep for levels `[0,1,2,3]` unless overridden.
   - Writes each run to its own worksheet.
   - Writes summary worksheet: `Summary — Quality Sweep`.

---

Strategy Logic (Detailed)

SMC and OB quality

Each OB can score up to 5 quality points:
- displacement confirmation
- large-bar behavior
- fair value gap pattern
- liquidity sweep signal
- volume expansion or impulse body

Entry OBs are filtered by `MIN_OB_QUALITY` (default `1`) unless sweep level overrides it.

Entry model

The simulation starts from `SWING_SIZE + 5` bars to ensure indicator/structure context is established.

LONG entry checks (all required)
- Price interaction with active demand zone.
- MACD histogram negative but rising (`hist < 0` and `hist > p_hist`).
- Histogram has risen for at least 2 bars (`p_hist > pp_hist`).
- KDJ condition:
  - `K < 50`
  - `K > K_prev`
  - `J < 60`
- K acceleration window:
  - `1 <= k_accel <= 6`
- ATR regime filter:
  - reject if `0.8 <= ATR/ATR_200 <= 1.0`
- Stop-loss validity:
  - `risk > 0`
  - `risk / close >= 0.015` (v9 minimum 1.5%)
- TP selection:
  - structural TP from nearest valid opposite OB when available
  - else fallback to `entry + 2R`
  - reject if reward/risk < 1.5

SHORT entry checks (all required)
- Price interaction with active supply zone.
- MACD histogram positive but falling (`hist > 0` and `hist < p_hist`).
- Histogram has fallen for at least 2 bars (`p_hist < pp_hist`).
- KDJ condition:
  - `K > 50`
  - `J > K > D`
  - extra short filters:
    - `K >= 70`
    - `J <= 100`
- K acceleration window:
  - `1 <= k_accel <= 6`
- ATR regime filter:
  - reject if `0.8 <= ATR/ATR_200 <= 1.0`
- Stop-loss validity:
  - `risk > 0`
  - `risk / close >= 0.015` (v9 minimum 1.5%)
- TP selection:
  - structural TP from nearest valid opposite OB when available
  - else fallback to `entry - 2R`
  - reject if reward/risk < 1.5

Position management and exits

For both sides, while in position:
- Records running PnL every bar.
- Maintains peak PnL since entry.

Exit conditions:
- Trailing exit:
  - once peak PnL reaches at least 1.5%, exit on 50% retrace.
- KDJ reset exit:
  - dynamically updated KDJ state with entry-based period.
  - **v9 gate:** only active from bar 3 onward (`i - entry_idx >= 3`).
- ATR move exit:
  - closes at approximately `1.8 * ATR` favorable move.
- Stop logic:
  - once price reaches `2 * ATR` favorable move, SL moves to breakeven.
- Hard exits:
  - hit stop loss
  - hit take profit

Trade records include:
- side, entry/exit index and price
- pnl percent
- entry OB metadata
- whether TP came from structural OB
- hold bars

Stats attached to DataFrame attributes:
- Total Trades
- Total Net Return (%)
- Avg Return/Trade (%)
- Win Rate (%)

---

Google Sheets Export Behavior

Per quality threshold sheet:
- Formats core numeric columns.
- Writes all simulation rows.
- Colors closed trade PnL cells:
  - green for positive
  - red for negative
- Appends compact stats block in PnL column.

Summary sheet:
- Name: `Summary — Quality Sweep`
- Includes one row per quality level with:
  - min quality
  - total trades
  - total net return
  - average return/trade
  - win rate
- Rows are tinted green/red by total return sign.

---

Main Execution Defaults

When executed directly (`python "src/Binance backtest bot.py"`), it runs:
- symbol: `BTCUSDT`
- interval: `4H`
- date range:
  - start: `2022-01-01 00:00:00`
  - end: `2026-01-01 00:00:00`
- quality sweep levels: `[0, 1, 2, 3]`

The console prints per-level stats and a final sweep summary.

---

How To Run Safely

1. Set environment variables before running:
   - `BINANCE_API_KEY`
   - `BINANCE_API_SECRET`
   - `GOOGLE_SERVICE_KEY_PATH` (path to your service account json)
   - `GOOGLE_SHEET_ID`
2. Ensure the Google service account has access to the target sheet.
3. Run:
   - `python "src/Binance backtest bot.py"`

If placeholders are still present, export will stop with a clear message.

---

Supplementary Analysis Scripts (`analysis/`)

Permanent, git-tracked, read-only analysis tools that consume the existing
backtest output (`artifacts/candles.csv`, the strategy's own trade log via
`simulate_trades()`). They never modify `simulate_trades()`, never write to
`backtest_results.db` or any `artifacts/*` file, and never change a
locked/reported headline number -- each is an additive lens on the same
27-trade `min_ob_quality=0` baseline. Run from the repo root.

- `analysis/fee_slippage_analysis.py` -- post-hoc transaction-cost
  sensitivity. Applies a confirmed Binance USDT-M Futures standard-tier
  taker fee (0.05%/side) plus a separate, clearly labeled conservative
  slippage estimate to a copy of the trade log, and reruns the exact
  binomial, Fisher's exact, and Welch's t-test statistics on the
  fee-adjusted PnL.
  ```bash
  python analysis/fee_slippage_analysis.py
  # override the fee/slippage assumptions:
  python analysis/fee_slippage_analysis.py --taker-fee-bps 5.0 --slippage-bps 5.0
  # skip the legacy pre-confirmation LOW/MID/HIGH sensitivity band:
  python analysis/fee_slippage_analysis.py --no-sensitivity-band
  ```
- `analysis/bootstrap_power_analysis.py` -- (a) nonparametric percentile
  bootstrap (default B=10,000) giving a 95% confidence interval on the
  baseline's own total and average return, and (b) a minimum-detectable-
  effect (MDE) / power calculation per orthogonal OB quality criterion,
  stating explicitly what size of criterion-level effect the current
  sample could and could not reliably detect.
  ```bash
  python analysis/bootstrap_power_analysis.py
  # more resamples, different seed:
  python analysis/bootstrap_power_analysis.py --bootstrap-n 5000 --seed 7
  # different power/alpha target for the MDE calc:
  python analysis/bootstrap_power_analysis.py --power 0.8 --alpha 0.05
  ```
- `analysis/benchmark_dca_analysis.py` -- two-section strategy-vs-BTC
  comparison. **Section 1**: event-driven strategy equity curve vs.
  buy-and-hold, Sharpe/Sortino, max drawdown, and the Pearson correlation
  between per-trade strategy return and BTC's own return over the same
  holding window. **Section 2**: a "complementary sleeve" model -- a fixed
  amount of new capital arrives every week; compares a 100%-BTC-DCA
  baseline against portfolios that split each week's contribution between
  BTC-DCA and an independently-capitalized strategy sleeve, at configurable
  split ratios (90/10, 80/20, 70/30 by default), reporting Sharpe/Sortino/
  max drawdown for each.
  ```bash
  python analysis/benchmark_dca_analysis.py
  # only the strategy-vs-BTC section:
  python analysis/benchmark_dca_analysis.py --section 1
  # only the DCA-blend section, custom contribution size and splits:
  python analysis/benchmark_dca_analysis.py --section 2 --contribution-amount 50 --splits 0.1,0.2,0.3,0.5
  ```
- `analysis/regime_breakdown_analysis.py` -- tags each baseline trade by
  macro market regime using TWO independent, always-both-reported methods:
  a calendar split (2022 bear / 2023 chop / 2024-25 bull) and a
  price-drawdown-from-all-time-high split (thresholds configurable).
  Reports trade count, win rate, and return contribution per regime under
  each method, plus a direct regime check on the top-N highest-return
  trades.
  ```bash
  python analysis/regime_breakdown_analysis.py
  # different drawdown thresholds or calendar years:
  python analysis/regime_breakdown_analysis.py --bear-threshold -40 --chop-threshold -12
  python analysis/regime_breakdown_analysis.py --bear-year 2022 --chop-year 2023
  ```

---

Known Assumptions and Notes

- Binance data fetch uses API response loops of up to 1000 bars per call.
- Open time is shifted by +8 hours.
- Strategy and comments indicate emphasis on avoiding lookahead bias.
- This script is a backtest/simulation + reporting tool; it is not an order execution live-trading engine.

---

Known Limitations / Future Work

- **Leverage is not modeled; all reported returns are unlevered/notional.**
  This is a deliberate scope decision, not an oversight. `simulate_trades()`
  evaluates every exit condition -- hard stop-loss, take-profit, the
  trailing exit, the ATR-move exit, and the breakeven-stop adjustment -- at
  bar-close resolution only. Intrabar `high`/`low` prices are present in
  `artifacts/candles.csv` and are read into the simulation loop, but are
  used only for order-block touch detection and a subset of the OB quality
  criteria (Displacement, LargeBar) -- never for any exit or
  position-sizing decision. The engine has no concept of a margin or
  liquidation price at any leverage level.
  A defensible leveraged backtest requires intrabar liquidation tracking: a
  position can be liquidated by a price excursion that fully reverses
  within a single 4H bar, which a close-resolution simulation cannot see.
  Applying a leverage multiplier after the fact to the existing close-basis
  trade log would not model that risk -- it would silently assume every
  trade's realized path was free of any intrabar excursion large enough to
  trigger liquidation, which the data cannot confirm one way or the other.
  **If leverage modeling is ever revisited**, the exit-evaluation logic
  would need to check `high`/`low` against a liquidation price intrabar
  (and a deliberate choice made about execution-order-within-bar
  assumptions when both a stop and a target are crossable in the same bar)
  -- a real engine change, not an analysis-layer addition. Until then, this
  codebase reports unlevered returns only, consistent with common practice
  in the technical-trading-rule literature (e.g., Svogun & Bazán-Palomino,
  2022, evaluating moving-average and support/resistance rule profitability
  on cryptocurrency data net of transaction costs on a notional basis).

---

README Logs (Append-Only)

> **Modification policy for this README**  
> Keep the original sections above as canonical baseline documentation.  
> If any future clarification/correction/update is needed, add it as a new dated note below instead of rewriting prior paragraphs directly.  
> If a direct paragraph edit is unavoidable, add a matching note entry documenting exactly what changed and why.

Log Entry Template

- Date:
- Section affected:
- Change type: `clarification` | `correction` | `update`
- Notes:
- Reason:

Entries

- 2026-04-28 | Initial README creation | update | Added full technical documentation based on current script behavior, configuration, strategy logic, export flow, and safety guidance. | Established baseline project documentation and changelog structure.
- 2026-04-30 | Local GUI artifact pipeline | update | Added `export_gui_data.py` local artifact export flow (`artifacts/*.json`, `artifacts/*.csv`, verification report) with optional Google Sheets sync via `--export-gsheet`. Updated `run_dashboard.bat` to start a local HTTP server and open `gui.html` via localhost so JSON fetch works reliably. | Replace Google Sheets-first workflow with local, auditable GUI-ready data and easier validation.
- 2026-05-03 | Execution Optimization & GUI Crash Fix | update | Replaced `run_dashboard.bat` with a native `Run_Dashboard.py` launcher and embedded the web server launch into `export_gui_data.py`. Optimized backend by caching simulations to prevent redundant calculations during GSheet export, halving execution time. Implemented a Track Allocator in `gui.js` to fix LightweightCharts rendering crashes caused by overlapping Order Blocks. | To improve backend performance, fix critical UI crashes, and simplify the local startup process.
- 2026-05-04 | Advanced UI Sync & Visualization | update | Implemented unified crosshair synchronization across all panes using precise price-point alignment. Added dynamic trade exit reason labels to the dashboard. Refactored pane resizing to use pixel-based calculations with `localStorage` persistence. Fixed indicator dot alignment on sub-charts. | To provide a premium, professional-grade analysis experience and resolve synchronization limitations in Lightweight Charts.
- 2026-06-15 | Quick Start Documentation | update | Added a simplified "Quick Start" execution guide explaining the single-command startup via `Run_Dashboard.py`. | To improve user boarding and simplify pipeline run instructions.
- 2026-07-11 | Custom Palette Picker & Visual Themes | update | Replaced native color inputs in settings drawer with custom popup palettes. Added opacity sliders and preset grids. Aligned default visuals and dark mode theme parameters to TradingView standards (#131722 dark canvas, transparent order blocks). | To provide a responsive, premium visual theme and customizable chart elements.
- 2026-07-12 | Performance Optimizations & Dynamic Indicators | update | Debounced logical range scroll changes and paused DOM updates during active navigation to restore 60fps pan/zoom. Replaced full hover rebuilds with updateActiveHighlight selector (<0.3ms). Linked MACD histogram bar colors dynamically to bullish/bearish candle presets. Added scipy to Dockerfile and documented docker run. | To eliminate zoom-out lag and unify technical indicator styles with user customizations.
- 2026-08-01 | KDJ architecture (Strategy Logic / Position management and exits) | clarification | Read-only audit clarified that entry-bar K/D/J always come from the STATIC full-history KDJ(9,3,3) column (`kdj_reset_init`'s seed values are read directly from `df` at `entry_idx`, never reseeded to 50 or backfilled from the triggering OB bar). Only the POST-ENTRY exit-signal state machine (`kdj_reset_update`/`kdj_reset_exit`) uses a variable RSV window, `period = entry_idx - triggering_OB_bar`, frozen for that trade's life and gated to fire no earlier than 3 bars after entry. Observed `w` (= entry_idx - ob_bar) across the 27 baseline (`min_ob_quality=0`) trades: min 14, median 74, max 439 -- no trade has single-digit `w`; the paper's "two-bar window" example is illustrative only. | To settle exactly which computation ("interpretation A" vs "B") the adaptive KDJ actually implements, since the two differ materially in what they claim about lookahead safety and window length.
- 2026-08-01 | KDJ exit-window sensitivity (Strategy Logic / Position management and exits) | update | Additive-only counterfactual grid (`scratch/kdj_exit_window_counterfactual.py`, `scratch/kdj_exit_window_trade_detail.py`) fixed the exit-window `period` to five constants -- 9 (conventional default), 38 (observed p25 of `w`), 74 (median), 114 (observed p75), 439 (observed max) -- with the 27-trade entry set confirmed byte-identical to the dynamic baseline at every point (`period` only governs exit timing, never entry selection). Win rate is flat at 70.37% across p25/median/p75 but the underlying winning-trade SET differs between p25 and {median, p75}: 4 trades flip in a 2-for-2 swap (entry_idx 673, 3196, 7938, 7964). Fixed-74 nearly reproduces the dynamic baseline's win rate/return (+31.89% vs +30.31%); fixed-9 (+28.05%, 59.26% WR) and fixed-439 (+29.51%, 62.96% WR) both underperform. The two commonly-cited reference trades (entry_idx 359, the best winner; entry_idx 2624, the top loser) are completely unaffected by `period` at every grid point -- both exit via non-KDJ-reset paths (`ATR MOVE EXIT`, `HIT STOP LOSS`) with byte-identical pnl in all six configs -- so the ~5.5-point total-return spread across the grid traces entirely to other trades. Exploratory only, not integrated into any paper claim. | To characterize the sensitivity of an already-fixed, disclosed design choice (the OB-relative dynamic exit window) without retuning it, and to separate "the variable window itself adds value" from "a longer fixed window happens to help about as much."
- 2026-08-01 | SMC and OB quality (Strategy Logic / third disclosed bug) | correction | A dedicated no-lookahead audit (hard runtime assertions added directly at the read sites inside `compute_smc()`, all still present and unweakened in `src/Binance backtest bot.py`) found that the FVG (3-candle: `lows[j+2] > highs[j]`) and displacement quality-criteria search loops were bounded by dataset length `n` instead of by the OB's own confirmation bar `i`, so both could read 1-2 bars past the bar at which the OB actually became usable for entry. Fixed by bounding both loops to the confirmation bar: displacement -> `range(ob_idx+1, min(i+1, ob_idx+4))`; FVG -> `range(ob_idx, min(i-1, ob_idx+3))`, preserving `j+2 <= i` as an invariant for every `j` considered; if `i - ob_idx` is too small for any valid `j`, the criterion now stays `False` rather than reading forward. Applied identically in both duplicated BULLISH/BEARISH branches inside `compute_smc()` -- the single source of truth read by population stats, entered-trade analysis, and every quality-threshold-filtered run alike, so one fix covers all three uniformly. ATR(14)/ATR_200/static KDJ(9,3,3) were separately proven causal via truncation-equality testing (`scratch/no_lookahead_atr_kdj_check.py`, 180/180 checks pass: recomputing each on a dataset truncated at bar `i` gives byte-identical values to the full-dataset computation at `i`), and the OB pivot-detection windows (50-bar swing, 5-bar internal) are provably bounded by array slicing. This is the third disclosed bug (`CLAUDE.md`, "Known bugs" #3) -- data leakage across the OB confirmation boundary, distinct in kind from the two previously-disclosed definitional corrections (non-orthogonal composite score; 2-candle-vs-3-candle FVG formula). | The project's no-lookahead enforcement rule requires this class of bug to be found via explicit assertion, disclosed, and fixed rather than patched around or reverted silently; the audit surfaced a genuine correctness finding.
- 2026-08-01 | Locked results re-verification (full cascade after the bug fix above) | correction | (1) `scratch/regression.py`: PASS, the 27-trade `min_ob_quality=0` baseline (bars, indicators, all 27 trades) is byte-identical pre/post-fix, because quality never gates entries at threshold 0. (2) Population stats over the full 761 detected Order Blocks: FVG-true 362->253 (47.6%->33.2%, -14.32pp, 109 of the 362 were lookahead artifacts); displacement-true 112->107 (14.7%->14.1%, 5 OBs); OB quality histogram q0=77->93, q1=147->154, q2=200->206, q3=192->197, q4=112->90, q5=33->21. (3) 4 of the 27 baseline trades' entry-OB quality scores changed (entry_idx 673: 5->4, 1158: 2->1, 3100: 1->0, 6040: 2->1), all via `quality_fvg` flipping True->False, none via displacement. (4) Orthogonal-criteria re-test (Fisher's exact on win/loss, Welch's t-test on return, all 5 criteria, methodology reproduces the pre-fix documented values bit-for-bit): only FVG's numbers move (Fisher p 0.6957->1.0000, Welch t +0.1326->+0.5360, p 0.8956->0.5996); no criterion crosses p=0.05 either before or after, so no significance-conclusion flip at the per-criterion level; the bar-359/2624 discussion claims and the four-criteria-shared-top-trade claim were re-confirmed unchanged. (5) Threshold sweep: q>=1 drops from 26 to 25 trades (69.23%->68.00% win rate, +29.08%->+28.31% return) because entry_idx=3100 loses its only quality point and falls below the q>=1 gate -- this DOES flip the q>=1 one-sided binomial significance from p=0.038 (n=26, marginally significant) to p=0.054 (n=25, not significant), a real conclusion-level flip. q>=2 moves 24->23 trades (p 0.0758->0.1050, non-significant both ways). q>=0 and q>=3 are numerically untouched. q>=4 (n=6, 50.00% WR) / q>=5 (n=1, 0.00% WR) reported descriptively only, too small to test. | `CLAUDE.md` requires locked results to change only as a disclosed consequence of a code-correctness fix, and requires every downstream figure the fix could plausibly touch to be explicitly re-verified rather than assumed unaffected -- including a significance-level flip, reported as a finding rather than folded in silently.
- 2026-08-01 | Locked results block + audit trail (CLAUDE.md, artifacts/*) | update | `CLAUDE.md`'s "Locked results" block updated with old and new values shown side by side (never silently replaced), plus the new "Known bugs" #3 entry described above. `artifacts/candles.csv`/`.json`, `manifest.json`, `orderblocks_default_view.csv`, `runs_by_threshold.json`, `threshold_runs.csv`/`.json`, `trades_default_view.csv`, `verification_report.json`, and `backtest_results.db` regenerated via the existing `export_gui_data.py` pipeline through a purpose-built offline driver (`scratch/run_export_offline.py`) that force-fails the live Binance API call so the pipeline's own existing cache-fallback path loads from the locked `artifacts/candles.csv` snapshot instead -- confirmed zero live API calls made, candle count still 8,767. `scratch/regression.py` re-run clean after every step of this whole cascade. Committed to `development` as `cb4ed93` ("fix: correct FVG/displacement OB scoring lookahead; remove ML pipeline") and fast-forwarded into `main` (`a0f6fc1`->`cb4ed93`, no merge commit needed since main had no divergent history); both pushed to `origin`. | Keep the paper's locked numbers and their disclosed-bug audit trail reproducible and traceable to an exact commit, offline and without touching the live-data path.
- 2026-08-01 | Dashboard independence check (`gui.js`) | clarification | Confirmed via full search of `gui.js` for any pivot/swing-high/BOS/CHoCH/SMC-detection logic that the JS dashboard does NOT independently detect Order Blocks, FVG, or displacement -- those fields (`quality_fvg`, `quality_displacement`, `quality`, `ob_bar`, `created_at`, etc.) are read as trusted data straight from the Python-generated `artifacts/runs_by_threshold.json` (via `processData()`'s `{...ob}` spread) and only rendered (checklist pass/fail rows, chart highlight overlays). What `gui.js` DOES independently recompute is the entry-condition/indicator side: its own from-scratch JS reimplementation of the `kdj_reset_init`/`kdj_reset_update` recursion for the adaptive-KDJ chart trajectory (added this session's dashboard work, dual static/adaptive KDJ panes), plus the existing MACD/KDJ/ATR entry-rule checklist. Net effect: the JS cross-check neither caught nor missed the FVG/displacement lookahead bug above -- OB/SMC detection was never part of what "independent" covers in this dashboard, only the entry/indicator layer is. | To determine, once the lookahead bug was found and fixed on the Python side, whether the intentionally-independent JS verification layer (see Security/Data Pipeline sections) had already caught or could have caught this class of bug.
- 2026-08-01 | Credential tracking status (Security and Credentials) | correction | Read-only check (tracking status only -- file contents never opened, read, or displayed): `SERVICE KEY/python-trading-bot-new-strat-10.json` is currently tracked (`git ls-files`) and was committed in a single commit (`a2db013`, "feat: add docker files and sync 1:1 database/models/credentials", 2026-07-09) that is reachable from essentially every local and `origin` branch, including `main` and `development`. This contradicts the "Recommended for GitHub" guidance further up this file (ignore `SERVICE KEY/*.json`) -- the `.gitignore` rule exists, but this specific file was already committed before the rule could exclude it, and removing it from history was explicitly out of scope for the session that found this. Flagged as a standing credential-exposure finding; left untouched. | The "Security and Credentials" section above describes the intended safe posture; this entry records that the actual repository state currently does not match it, so the gap doesn't go unnoticed.
- 2026-08-01 | Codebase reorganization (File Scope) | update | Full inventory/reorg pass produced `CODEBASE_MAP.md` at repo root (every file: purpose, what references it, CORE / INFRA / AUDIT EVIDENCE / DASHBOARD / CANDIDATE-DEAD classification, proposed destination). After a two-phase proposal + sign-off, executed in two verified batches: **Batch 1** (commit `76f0efb`) deleted 10 files confirmed orphaned by exhaustive grep across tracked files and `scratch/` -- `data.js` (an unreferenced `window.BOT_DATA` static dump superseded by the live artifacts/API load path) and `artifacts/ml_status.json` + `artifacts/models/model_iter_1..8.pkl` (leftovers from the already-disclosed ML-pipeline removal; nothing imports, reads, or globs any of them). **Batch 2** (commit `7713638`) ran `git mv "Binance backtest bot.py" "src/Binance backtest bot.py"` (history preserved) plus every reference that move would otherwise have broken: `BASE_DIR` inside the moved file now goes up one extra directory level so `SERVICE KEY/` (unmoved, out of scope) still resolves correctly (verified `resolve_google_service_key_path()` still finds the real file post-move, existence check only); `export_gui_data.py` (x2 occurrences), `scratch/regression.py`, `scratch/no_lookahead_atr_kdj_check.py`, `scratch/no_lookahead_fvg_scope_audit.py`, `scratch/kdj_exit_window_counterfactual.py`, `scratch/kdj_exit_window_trade_detail.py`, `scratch/02_benchmark_and_risk.py`, `scratch/calculate_all_qualities.py`, and `scratch/inspect_raw_signals.py` all updated to load from `src/`; this README's own path references (File Scope, Main Execution Defaults, How To Run Safely) updated to match. `scratch/regression.py` plus the full locked-figures snapshot re-verified clean (zero diff) after each batch. Separately, 9 of the `scratch/` audit-evidence scripts behind the Known bugs #3 finding and the KDJ-architecture entries above (previously untracked, since `scratch/` is gitignored by default) were force-added and committed on their own (`8ef4076`) after a content scan confirmed no absolute paths, credentials, or machine-specific artifacts in any of them. `db_manager.py`, `export_gui_data.py`, `Run_All.py`, `Run_Dashboard.py`, `Dockerfile`, `chart_theme.json`, and `backtest_results.db` were deliberately left at repo root rather than also moved, to keep the blast radius of broken relative-path references limited to one file move. All reorg commits pushed to `development` only (`cb4ed93..7713638`); `main` intentionally left at `cb4ed93` pending a separate decision on whether to fast-forward it too. | To make the repository's real vs. superseded/dead files explicit and auditable, and give the core strategy engine a conventional `src/` home, without risking the locked results, the disclosed-bug audit trail, or the intentionally-independent JS dashboard cross-check.
- 2026-08-03 | Transaction-cost sensitivity promoted to `analysis/` (Supplementary Analysis Scripts) | update | Promoted `scratch/fee_slippage_audit.py` to a permanent, git-tracked, CLI-runnable script (`analysis/fee_slippage_analysis.py`) on branch `feature/fee-slippage-analysis`. Fee figure corrected from a prior unverified "4-10bps" placeholder to Binance's published USDT-M Futures standard-tier (VIP 0, no BNB discount) taker rate, confirmed 0.05%/side (web-verified against Binance's fee-schedule FAQ, August 2026); slippage kept as a separate, clearly labeled conservative estimate (0.05%/side) rather than bundled into "the fee." Primary scenario (fee + slippage, 0.20% round trip) drops total net return from +30.31% to +24.91% and win rate from 70.37% to 62.96% (17/27), moving the one-sided binomial p from 0.0261 (significant) to 0.1239 (not significant) -- reported plainly as a fragility finding, not minimized. Welch's t-test on all 5 orthogonal criteria is mathematically invariant to this flat per-trade drag (verified identical to 4 decimals pre/post-adjustment). Promotion verified byte-for-byte numerically identical to the scratch predecessor's output before this entry was written (only cosmetic label-text formatting differs). Old LOW/MID/HIGH bundled fee+slippage guesses retained as a labeled pre-confirmation sensitivity band, not as the primary estimate. | To make transaction-cost sensitivity a permanent, reproducible part of the toolchain rather than a one-off scratch finding, using a verified rather than assumed fee figure.
- 2026-08-03 | Bootstrap CI / power analysis promoted to `analysis/` (Supplementary Analysis Scripts) | update | Promoted `scratch/bootstrap_power_audit.py` to a permanent, git-tracked, CLI-runnable script (`analysis/bootstrap_power_analysis.py`) on branch `feature/bootstrap-power-analysis`. Provides (a) a nonparametric percentile bootstrap (B=10,000 default) giving a 95% CI on the 27-trade baseline's own total return (+30.31% point estimate, 95% CI [+5.99%, +54.99%], not crossing zero) and average return/trade, and (b) a minimum-detectable-effect (MDE) calculation per orthogonal OB quality criterion: at 80% power / alpha=0.05, the MDE (2.23-2.91 percentage points across the 5 criteria) is roughly 3-10x larger than the actually-observed True/False subgroup gaps (0.23-0.78 pp) -- meaning the criteria-level null results reflect the study being underpowered to detect effects of the size observed, not necessarily a true absence of effect. Promotion verified numerically identical to the scratch predecessor's output (same seed reproduces the same bootstrap CI exactly; only cosmetic label-text formatting differs). | To make the power/CI framing a permanent, reproducible part of the toolchain so the paper's "no significant difference" language can be replaced with the more precise underpowered-vs-null-effect distinction on demand, not just as a one-off scratch finding.
- 2026-08-03 | Benchmark/DCA-blend analysis promoted to `analysis/` (Supplementary Analysis Scripts) | update | Promoted `scratch/02_benchmark_and_risk.py` and `scratch/dca_blend_audit.py` together to one permanent, git-tracked, CLI-runnable module (`analysis/benchmark_dca_analysis.py`) on branch `feature/benchmark-dca-blend`, since they're the same analysis family. Section 1 (strategy vs. BTC buy-and-hold): Sharpe 1.114 / Sortino 2.727 for the strategy vs. 0.564 / 0.803 for buy-and-hold, at 2.63% time-in-market; Pearson correlation between per-trade strategy return and BTC's return over the same holding window r=-0.3688, p=0.0584 (borderline, not significant at alpha=0.05, but directionally consistent with a complementary/diversifying role). Section 2 (DCA-blend, weekly contributions, configurable split ratios, 90/10/80/20/70/30 by default): Sharpe/Sortino/max-drawdown all improve monotonically as strategy-sleeve allocation increases (e.g. 80/20 split: Sharpe 0.556->0.607, Sortino 0.886->0.978, max drawdown -27.85%->-24.97%, vs. 100%-DCA-only), at the cost of lower absolute final value -- a risk-adjusted-improvement story, not a return-supremacy claim. The scratch predecessor's cumulative-P&L-only drawdown metric produced NaN early in the series (division by a near-zero-or-negative running-max before enough capital had accumulated); fixed in the promoted version by reporting that metric as a peak-to-trough DOLLAR retracement instead of a percentage, which stays well-defined regardless of sign. Promotion verified numerically identical to both scratch predecessors' output (only cosmetic label-text formatting differs). | To make the strategy-vs-benchmark and complementary-sleeve framing a permanent, reproducible, configurable part of the toolchain, with the known NaN bug fixed rather than carried forward silently.
- 2026-08-03 | Regime breakdown promoted to `analysis/` (Supplementary Analysis Scripts) | update | Promoted `scratch/regime_breakdown_audit.py` to a permanent, git-tracked, CLI-runnable script (`analysis/regime_breakdown_analysis.py`) on branch `feature/regime-breakdown`, keeping BOTH the calendar method (2022 bear / 2023 chop / 2024-25 bull) and the price-drawdown-from-all-time-high method (ATH seeded at $69,000, BTC's actual 2021-11-10 peak, predating this dataset's window; thresholds BEAR<=-40%, CHOP<=-12%) rather than collapsing to one -- the two methods agree on only 13/27 trade assignments (most of calendar-2023 was still 57-64% below the real ATH, i.e. drawdown-method BEAR, despite being sideways/recovering rather than crashing), but both agree BULL is the strongest regime (85.71% win rate under both) and both confirm the 3 concentrated top-return trades (entry_idx 359/6366/8280, together 51.7% of total return) are NOT clustered in a single regime -- calendar gives BEAR/BULL/BULL, drawdown gives CHOP/BULL/BULL, union spans all three labels. Promotion verified numerically identical to the scratch predecessor's output (only a cosmetic calendar-label year-range difference: the promoted version's dynamic label includes the window's final boundary bar, "2024-26" vs. the scratch predecessor's hardcoded "2024-25" -- the underlying year-to-regime logic and all numeric rows are unaffected). | To make the regime robustness check (recommended in the Limitations draft as a substitute for an underpowered calendar holdout) a permanent, reproducible, configurable part of the toolchain.
- 2026-08-03 | Known Limitations / Future Work (new section) | update | Added a new "Known Limitations / Future Work" section documenting that leverage is not modeled: `simulate_trades()` evaluates all exit conditions at bar-close resolution only, intrabar `high`/`low` (present in the data, read into the loop) are used only for OB-touch detection and two quality criteria, never for exits, and the engine has no margin/liquidation-price concept at all. States plainly that a leveraged backtest is not defensible without adding intrabar liquidation tracking to the exit-evaluation logic, and that this codebase deliberately does not attempt a leverage-multiplier workaround on the existing close-basis trade log, since that would silently hide the exact risk (intrabar liquidation invisible to a close-only simulation) it claims to model. Cites Svogun & Bazán-Palomino (2022) as consistent precedent for reporting unlevered notional returns in the technical-trading-rule literature. No code changes -- documentation only, per this session's investigation finding that the engine "cannot honestly support this." | To make an already-investigated scope decision (not a gap someone might mistake for an oversight) explicit and discoverable, and to record what a future revisit would actually require rather than leaving it unstated.


