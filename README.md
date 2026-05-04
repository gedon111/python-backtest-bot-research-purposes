Binance Backtest Bot (Compliance Version)

This project is a Python backtest and reporting bot that:
- Pulls BTC/USDT OHLCV candles from Binance.
- Computes indicators (MACD, KDJ, ATR, ATR_200).
- Builds Smart Money Concepts (SMC) order blocks (internal + swing).
- Simulates LONG/SHORT trade entries and exits using rule-based filters.
- Exports per-quality simulation results to Google Sheets, including a summary sheet.

The strategy in this file is the v9 variant documented in the source comments, with two key adjustments from prior versions:
- Minimum SL distance filter: reject entries with risk less than 1.5% of entry.
- KDJ reset exits are blocked for the first 3 bars after entry.

---

File Scope

Main script:
- `Binance backtest bot.py`

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

When executed directly (`python "Binance backtest bot.py"`), it runs:
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
   - `python "Binance backtest bot.py"`

If placeholders are still present, export will stop with a clear message.

---

Known Assumptions and Notes

- Binance data fetch uses API response loops of up to 1000 bars per call.
- Open time is shifted by +8 hours.
- Strategy and comments indicate emphasis on avoiding lookahead bias.
- This script is a backtest/simulation + reporting tool; it is not an order execution live-trading engine.

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

