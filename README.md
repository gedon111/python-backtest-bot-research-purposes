# Binance Backtest Bot (Compliance Version)

A Python research toolkit that backtests a rule-based BTC/USDT trading
strategy (MACD + KDJ + ATR + Smart Money Concepts order blocks) on 4-hour
candles, then serves the results through a local interactive dashboard. It
also includes a full statistical-significance and robustness suite
(binomial test, bootstrap confidence intervals, correlation analysis,
fee/slippage sensitivity, regime breakdown, an indicators-only ablation
study, out-of-sample validation, and benchmark-vs-passive comparisons).

**This is a research/reporting artifact for an ISEF science-fair paper, not
a live-trading system.** It simulates trades against historical data and
reports the results; it never places, or is designed to place, real orders.
Correctness and auditability of the backtest outrank performance or
convenience — see `CLAUDE.md` for the project's locked results, disclosed
bugs, and hard rules, and `CHANGELOG.md` for the full dated history of
corrections and audit findings.

---

## Contents

- [Requirements](#requirements)
- [Project layout](#project-layout)
- [Running without Docker](#running-without-docker)
- [Running with Docker](#running-with-docker)
- [Migrating to a new machine](#migrating-to-a-new-machine)
- [Verifying the backtest engine is untouched](#verifying-the-backtest-engine-is-untouched)
- [Data pipeline overview](#data-pipeline-overview)
- [Strategy logic (detailed)](#strategy-logic-detailed)
- [Statistical analyses (part of `research_analysis.py`)](#statistical-analyses-part-of-research_analysispy)
- [`research_analysis.py` — the single entrypoint](#research_analysispy--the-single-entrypoint)
- [Security and credentials](#security-and-credentials)
- [Known limitations / future work](#known-limitations--future-work)

---

## Requirements

### To run without Docker

| Requirement | Version tested against this repo | Needed for |
|---|---|---|
| Python | **3.11 or newer** (this repo is developed and tested on 3.14.3) | Everything — backtest engine, analysis scripts, dashboard backend |
| pip | any recent version | Installing `requirements.txt` |
| Node.js | **20 or newer** (tested on 24.14.0) | Building `dashboard-v2` (`npm run build`, invoked automatically) or running its dev server |
| npm | ships with Node.js (tested on 11.9.0) | Same as above |
| OS | Windows, macOS, or Linux | No OS-specific code paths; tested on Windows 11 |

All Python dependencies are pinned in `requirements.txt` (`pandas 3.0.0`,
`numpy 2.4.2`, `scipy 1.18.0`, `python-binance 1.0.34`, `oauth2client
4.1.3`, `gspread 6.2.1`, `gspread-formatting 1.2.1`, `SQLAlchemy 2.0.50`).
This is the single source of truth — the Docker build installs from the
same file, so the two paths cannot drift apart. **Nothing needs to be
installed beyond `requirements.txt` to view the dashboard or reproduce the
locked backtest results, and no API keys are ever required** — the repo
ships a committed candle cache (`artifacts/candles.csv`) and SQLite
database (`backtest_results.db`) that every run falls back to if it can't
reach Binance (see [Running without Docker](#running-without-docker) for
exactly when that fallback triggers).

### To run with Docker

| Requirement | Notes |
|---|---|
| Docker | Any version supporting multi-stage builds (tested on Docker 29.4.2 / Docker Desktop) |

Docker builds everything (Python deps + the `dashboard-v2` frontend) inside
the image — no local Python or Node.js install needed on the host at all.

### Optional (only if you need Google Sheets export)

- A Google Cloud service-account JSON key + a target Google Sheet (for
  `GOOGLE_SERVICE_KEY_PATH` / `GOOGLE_SHEET_ID`) — only needed to push
  results to Google Sheets (`--export-gsheet`).
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` are read from the environment
  and passed to the Binance client, but the pipeline only ever calls
  `get_klines` (a public, unauthenticated endpoint) — candle data has
  worked with no keys set at all in every test run, including inside a
  freshly built Docker container with no credentials mounted. Set them
  only if you have a specific reason to (e.g. wanting requests attributed
  to your own account for Binance's rate-limit accounting).

---

## Project layout

```
.
├── research_analysis.py          # THE single-file entrypoint: backtest
│                                  # engine (indicators, SMC/order-block
│                                  # detection, simulate_trades()), every
│                                  # statistical test, the SQLAlchemy
│                                  # database manager, Google Sheets export,
│                                  # and the dashboard's live HTTP server.
│                                  # `python research_analysis.py` runs the
│                                  # offline stats pipeline; `--serve` exports
│                                  # artifacts/DB and starts the dashboard
│                                  # server (see below).
├── dashboard-v2/                 # React + Vite + Lightweight Charts
│                                  # frontend (dark, terminal-style UI)
├── Run_All.py                    # THE entry point: installs Python deps
│                                  # (pip) and dashboard-v2's npm deps/build
│                                  # if needed, then runs the pipeline and
│                                  # serves the dashboard. This is what
│                                  # Docker runs. No Google Sheets export
│                                  # (run research_analysis.py directly for
│                                  # that - see below).
├── artifacts/                    # Committed, regeneratable pipeline output
│                                  # (candles.csv, per-quality-level trade
│                                  # logs, JSON for the dashboard/analysis)
├── backtest_results.db           # Committed SQLite export of the same data
├── legacy_pre_consolidation/     # Git-ignored, disk-only backup of the
│                                  # pre-consolidation files this repo used
│                                  # to run from (src/Binance backtest bot.py,
│                                  # db_manager.py, export_gui_data.py,
│                                  # analysis/*.py) — not part of the running
│                                  # system, kept only as a reference copy.
├── scratch/                      # Git-ignored, one-off audit/investigation
│                                  # scripts (not part of the shipped
│                                  # pipeline; see CODEBASE_MAP.md)
├── docs/                         # Paper drafts and reference documents
├── SERVICE KEY/                  # (git-ignored) Google service-account
│                                  # JSON goes here — never committed
├── requirements.txt               # Pinned Python deps (source of truth)
├── Dockerfile / .dockerignore    # Container build
├── CLAUDE.md                     # Locked results, disclosed bugs, hard
│                                  # project rules (for both humans and AI
│                                  # assistants working in this repo)
└── CHANGELOG.md                  # Full dated history of README/doc
                                    # corrections and audit findings
```

---

## Running without Docker

### 1. Clone and enter the repo

```bash
git clone <this-repo-url>
cd "Binance Backtest Bot Package (compliance ver)"
```

### 2. (Recommended) Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Run the launcher

```bash
python Run_All.py
```

This is a fresh-clone-to-running-dashboard one-liner: it installs Python
dependencies (`pip install -r requirements.txt`), installs and builds
`dashboard-v2` if its npm deps/build output are missing or stale, runs the
full pipeline (fetch/load candles → compute indicators → detect order
blocks → simulate trades at quality levels `0,1,2,3` → write `artifacts/*`
and `backtest_results.db`), starts a local server, and opens your browser to
`http://127.0.0.1:8765/dashboard/`. (If you'd rather manage the virtual
environment/npm install yourself first, `pip install -r requirements.txt`
and `cd dashboard-v2 && npm ci` remain valid — `Run_All.py` just skips
whichever of those steps is already satisfied.)

- **Candle fetch is network-first, cache-fallback — not offline by
  default.** Every run first tries a live Binance `get_klines` pull over
  the requested date range (this works with no API keys at all, since
  candle data is a public endpoint — `python-binance`'s `Client(None,
  None)` still succeeds). **Only if that live call raises an exception**
  (no network, blocked egress, Binance unreachable) does it fall back to
  the committed `artifacts/candles.csv` cache. On a normal machine with
  internet access, this means every run re-pulls live data and can take a
  couple of minutes and print little output in between (see
  `PYTHONUNBUFFERED=1` in the Docker section for why `docker logs` can look
  quiet during this). No API keys are required either way. Either data
  source reproduces the paper's locked results — Binance does not revise
  historical candles (verified; see `CHANGELOG.md`'s `oos_validation_analysis.py`
  entries) — so a live pull over the same date range and the committed
  cache agree exactly; a machine with no network access simply falls back
  to the cache automatically instead of raising an error.
- **Google Sheets export**: not attempted by `Run_All.py` at all — run
  `python research_analysis.py --serve --export-gsheet` directly instead
  (see the flags table below), gated behind the credentials below. Set the
  following environment variables *before* running (this project does
  **not** auto-load a `.env` file — copy `.env.example` to `.env` for your
  own reference only, then export the real values into your shell):

  ```bash
  # Windows (cmd)
  set BINANCE_API_KEY=your_key
  set BINANCE_API_SECRET=your_secret
  set GOOGLE_SERVICE_KEY_PATH=SERVICE KEY\your-service-account-key.json
  set GOOGLE_SHEET_ID=your_sheet_id

  # Windows (PowerShell)
  $env:BINANCE_API_KEY = "your_key"
  $env:BINANCE_API_SECRET = "your_secret"
  $env:GOOGLE_SERVICE_KEY_PATH = "SERVICE KEY\your-service-account-key.json"
  $env:GOOGLE_SHEET_ID = "your_sheet_id"

  # macOS/Linux
  export BINANCE_API_KEY=your_key
  export BINANCE_API_SECRET=your_secret
  export GOOGLE_SERVICE_KEY_PATH="SERVICE KEY/your-service-account-key.json"
  export GOOGLE_SHEET_ID=your_sheet_id
  ```

  If any of these are unset, the backtest pipeline is unaffected (candle
  fetch and simulation need none of them); a Google Sheets export attempt
  without real credentials fails with a clear `ValueError` rather than
  silently doing nothing.

### Alternative: run the pipeline script directly

`research_analysis.py` has **two mutually exclusive modes**, selected by
whether `--serve` is passed. Most flags only take effect in one of the two
modes — passing a flag from the wrong mode is not an error (argparse
accepts it either way), it is just silently ignored, since the other
mode's code path never reads it.

```bash
# Mode 1 (default): offline statistics pipeline only, prints to console.
python research_analysis.py

# Mode 2: export artifacts/DB + start the dashboard server.
python research_analysis.py --serve --levels 0,1,2,3
```

`python research_analysis.py --help` prints the full list at any time.

#### Mode 1 — offline statistics pipeline (default, no `--serve`)

Runs `run_full_analysis_pipeline()`: loads candles, simulates the baseline
`min_ob_quality=0` trade log, then runs every statistical analysis in the
[table above](#statistical-analyses-part-of-research_analysispy)
(binomial test, bootstrap CI, fee/slippage sensitivity, regime breakdown,
benchmark-vs-passive, paper-sync check, etc.) and prints each section's
results to the console. Nothing is written to disk unless `--json-out` is
given. This is the fastest way to get statistical results without touching
the dashboard, database, or `artifacts/*` files.

| Flag | Default | Purpose |
|---|---|---|
| `--include-oos-live` | off | Also run `run_forward_oos_validation()` — the one section that makes a live Binance API call. Off by default so the pipeline stays fully offline. |
| `--bootstrap-n` | `10000` | Number of resamples for the bootstrap confidence interval (`run_bootstrap_ci()`). Lower it (e.g. `--bootstrap-n 500`) for a quick smoke-test run; the locked/reported CI uses the default. |
| `--seed` | `42` | RNG seed for all bootstrap resampling. Reproducibility only — never change this to "improve" a result. |
| `--json-out` | none | Path to write every section's results as one JSON file, e.g. `--json-out artifacts/stats_run.json`. |

```bash
python research_analysis.py                                # full pipeline, console output only
python research_analysis.py --json-out out.json             # also dump results to JSON
python research_analysis.py --bootstrap-n 500 --seed 1      # quick, non-canonical smoke test
python research_analysis.py --include-oos-live              # also run the live-Binance OOS check
```

#### Mode 2 — `--serve`: export artifacts/DB + run the dashboard

Runs `run_serve_mode()`: fetches/loads candles, sweeps the requested
`--levels`, writes `artifacts/*.json`/`*.csv` and `backtest_results.db`,
regenerates `artifacts/paper_sync_report.md`, regenerates the four
statistical-artifact JSON files (`bootstrap_power_analysis.json`,
`fee_slippage_analysis.json`, `ablation_reconstruction.json`,
`benchmark_vs_passive.json` — each readable directly without opening the
dashboard at all), optionally pushes to Google Sheets, then starts the
dashboard HTTP server. **`--bootstrap-n`, `--seed`, `--json-out`, and
`--include-oos-live` have no effect here** — this mode always calls
`run_bootstrap_ci()` with its own defaults (`10000`/`42`, same as Mode 1's
defaults) and never runs the live OOS section.

| Flag | Default | Purpose |
|---|---|---|
| `--symbol` | `BTCUSDT` | Trading pair |
| `--timeframe` | `4h` | Candle interval |
| `--start` / `--end` | `2022-01-01 00:00:00` / `2026-01-01 00:00:00` | Backtest date range |
| `--levels` | `0,1,2,3` | Comma-separated min order-block quality thresholds to sweep |
| `--default-view-quality` | `1` | Which quality level the dashboard opens to by default |
| `--output-dir` | `artifacts` | Where JSON/CSV output is written |
| `--export-gsheet` | off | Attempt a Google Sheets export (needs the env vars above) |
| `--db-url` | `sqlite:///backtest_results.db` | Override the SQLAlchemy database URL |
| `--no-server` | off | Run the export pipeline only; skip starting the dashboard web server (useful if you just want the `artifacts/*.json` result files) |
| `--no-browser` | off | Start the server but don't auto-open a browser tab |

```bash
python research_analysis.py --serve                                   # export + serve dashboard at :8765
python research_analysis.py --serve --no-server                       # export artifacts/DB only, no server
python research_analysis.py --serve --no-browser                      # serve without opening a browser tab
python research_analysis.py --serve --levels 0,1,2,3 --export-gsheet  # also push to Google Sheets
```

**Picking a mode for what you want:**

| You want... | Run |
|---|---|
| Statistical results printed to console, quickly | `python research_analysis.py` |
| Statistical results as a single JSON file | `python research_analysis.py --json-out out.json` |
| The dashboard, browsable in a browser | `python research_analysis.py --serve` |
| Just the per-analysis JSON files (`artifacts/*.json`) without a running server | `python research_analysis.py --serve --no-server` |
| A one-off custom bootstrap run (different N/seed) | `python research_analysis.py --bootstrap-n <N> --seed <S>` (Mode 1 only — Mode 2 ignores these) |

### Frontend dev mode (hot reload)

For active frontend work on `dashboard-v2/`, run its Vite dev server
instead of (or alongside) `Run_All.py`:

```bash
cd dashboard-v2
npm install
npm run dev
```

`npm run dev` automatically starts the Python backend
(`research_analysis.py --serve --no-browser`) if one isn't already running
on port 8765, waits for it to become ready, then starts Vite at
`http://localhost:5173` with hot reload — no separate terminal/manual
backend step needed. If you already have a backend running yourself (e.g.
`Run_All.py` in another terminal, or you're iterating on backend code
and don't want it restarted), use `npm run dev:vite-only` instead, which
just runs Vite against whatever backend is already up.

Other useful `dashboard-v2` scripts: `npm run build` (production build to
`dist/`, what `Run_All.py` invokes automatically when needed),
`npm run typecheck`, `npm run lint`, `npm run preview`.

---

## Running with Docker

The `Dockerfile` is a two-stage build: a `node:24-slim` stage compiles
`dashboard-v2` to static assets, then a `python:3.14-slim` stage installs
Python dependencies from `requirements.txt` and copies in the pre-built
frontend. The final image needs no Node.js/npm at runtime.

### 1. Build the image

```bash
docker build -t binance-backtest-bot .
```

### 2. Run the container (no keys needed)

```bash
docker run -p 8765:8765 binance-backtest-bot
```

This runs the same pipeline as `python Run_All.py` inside the container and
serves the dashboard at **`http://localhost:8765/dashboard/`**. The
container binds the server to `0.0.0.0` internally
(`DASHBOARD_HOST=0.0.0.0`, set in the `Dockerfile`) so `docker run -p`'s
port forwarding reaches it — you do not need to set this yourself.
No credentials are required to reach this point.

Verified end-to-end against this exact Dockerfile: with the container's
default network access, the pipeline pulls fresh candles live from Binance
(no keys needed — see the Requirements section above) before serving the
dashboard, which takes roughly 2-3 minutes and prints little in between
until each pipeline step completes (`docker logs -f <container>` to watch
it live — `PYTHONUNBUFFERED=1` in the `Dockerfile` keeps that output
flowing as it happens rather than only at the end). If the container has
no network access, the pipeline falls back to the committed
`artifacts/candles.csv` cache automatically and finishes in seconds.

### 3. Run with live Binance/Google Sheets credentials (optional)

Credentials are **never baked into the image** — `.dockerignore` excludes
`SERVICE KEY/` and `.env*` from the build context on purpose, so a
`docker build` run by someone else can never accidentally ship your key.
Supply them at `docker run` time instead:

```bash
docker run -p 8765:8765 \
  -e BINANCE_API_KEY=your_key \
  -e BINANCE_API_SECRET=your_secret \
  -e GOOGLE_SHEET_ID=your_sheet_id \
  -e GOOGLE_SERVICE_KEY_PATH="SERVICE KEY/your-service-account-key.json" \
  -v "$(pwd)/SERVICE KEY:/app/SERVICE KEY:ro" \
  binance-backtest-bot python research_analysis.py --serve --levels 0,1,2,3 --export-gsheet
```

The `-v` mount makes your local `SERVICE KEY/` folder available inside the
container read-only, without it ever being part of an image layer. Drop
the `-v` line and the three Google-related `-e` flags entirely if you only
need a live Binance pull without Google Sheets export.

### 4. Persist results outside the container (optional)

By default, `artifacts/` and `backtest_results.db` written inside the
container are lost when it's removed. To persist them on the host:

```bash
docker run -p 8765:8765 \
  -v "$(pwd)/artifacts:/app/artifacts" \
  -v "$(pwd)/backtest_results.db:/app/backtest_results.db" \
  binance-backtest-bot
```

### Rebuilding after code changes

`docker build` re-runs whenever you change source files — Docker's layer
cache means only the `RUN npm ci` / `RUN pip install` layers are skipped
when `package-lock.json` / `requirements.txt` haven't changed, so most
rebuilds are fast:

```bash
docker build -t binance-backtest-bot . && docker run -p 8765:8765 binance-backtest-bot
```

---

## Migrating to a new machine

Everything needed to run this project is tracked in this git repository
(source, `artifacts/candles.csv` cache, `backtest_results.db`, dashboard
source) except two things that are deliberately git-ignored:

1. `git clone` the repo on the new machine.
2. Run `python Run_All.py` (or the Docker equivalent), which installs
   Python deps and dashboard-v2's npm deps/build itself — or install them
   yourself first (`pip install -r requirements.txt`; `cd dashboard-v2 &&
   npm ci`) if you'd rather. No keys are required to view the dashboard or
   reproduce the locked backtest results; a machine with no network access
   falls back to the committed `artifacts/candles.csv` cache automatically.
3. **Manually** copy your Google service-account key JSON into a local
   `SERVICE KEY/` folder at the repo root (e.g. via a password manager or
   encrypted transfer). Never commit it or send it through git — `SERVICE
   KEY/` is git-ignored (and Docker-ignored) on purpose.
4. Only if you need Google Sheets export: set the 2 Google-related
   environment variables listed in `.env.example` in your shell/session
   (this project does not auto-load a `.env` file), then run
   `python research_analysis.py --serve --export-gsheet` directly (no
   runner script does this). The 2 Binance variables are optional in every
   case — candle data is fetched from a public endpoint that needs no key.

---

## Verifying the backtest engine is untouched

`scratch/regression.py` is this repo's golden-master regression test. It
re-runs the strategy engine against the committed fixtures in
`scratch/fixtures/` and reports a bar-by-bar, trade-by-trade diff — any
difference means a change altered the backtest's behavior.

```bash
python scratch/regression.py
```

A clean run prints a `PASS` confirming the fresh run matches the golden
fixture exactly across all bars, indicators, and the 27-trade
`min_ob_quality=0` baseline. Run this after any change touching
`research_analysis.py`'s strategy engine (Sections 2-3), before trusting
new results. **Never run it with `--generate`** (which regenerates the
fixtures themselves) without explicit sign-off — that flag defines what
"correct" means for every future run.

---

## Data pipeline overview

1. **Fetch candles** (`get_candles`)
   - Source: Binance `get_klines`.
   - Default symbol/interval in main run: `BTCUSDT`, `4H`.
   - Converts numeric columns to float; converts open time to datetime and
     applies a `+8h` offset.

2. **Compute indicators** (`compute_indicators`)
   - MACD: `12,26,9`.
   - KDJ: period default `9`, smoothing alpha `1/3`.
   - ATR: period `14`. ATR_200: long volatility baseline.

3. **Build market structure/order blocks** (`compute_smc`)
   - Two structure passes: internal (`INTERNAL_SIZE=5`) and swing
     (`SWING_SIZE=50`).
   - Detects pivots, BOS/CHoCH crossover events, and creates order blocks
     (type `DEMAND`/`SUPPLY`, top/bottom, creation/OB bar indexes,
     structure metadata, 5 independent quality sub-signals plus an
     aggregate 0-5 quality score, and a mitigation-invalidation bar).

4. **Simulate trades** (`simulate_trades`)
   - Runs bar-by-bar with no forward-looking data.
   - Uses active, unmitigated order blocks under an age constraint
     (`MAX_OB_AGE=500`).
   - Supports order-block quality filtering via `min_ob_quality`.

5. **Export** (`research_analysis.py`'s `export_dashboard_artifacts()`, `--serve` mode)
   - Runs the quality sweep for the requested levels (default `0,1,2,3`).
   - Writes `artifacts/*.json`/`*.csv` for the dashboard and
     `backtest_results.db` (SQLite, via the database-manager section of
     `research_analysis.py`).
   - Optionally pushes results to Google Sheets (`--export-gsheet`).

---

## Strategy logic (detailed)

The strategy is the v9 variant documented in the source comments, with two
key adjustments from prior versions: a minimum stop-loss distance filter
(reject entries with risk less than 1.5% of entry), and KDJ reset exits
blocked for the first 3 bars after entry.

### SMC and order-block quality

Each order block can score up to 5 independent quality points:
displacement confirmation, large-bar behavior, fair value gap (3-candle
definition), liquidity sweep signal, and volume expansion/impulse body.
Entry order blocks are filtered by `min_ob_quality` (default `1`) unless a
quality-sweep level overrides it.

### Entry model

The simulation starts from `SWING_SIZE + 5` bars in, so indicator/structure
context is established before the first possible entry.

**LONG entry (all required):**
- Price interaction with an active demand zone.
- MACD histogram negative but rising (`hist < 0` and `hist > p_hist`), and
  risen for at least 2 bars (`p_hist > pp_hist`).
- KDJ: `K < 50`, `K > K_prev`, `J < 60`.
- K-acceleration window: `1 <= k_accel <= 6`.
- ATR regime filter: reject if `0.8 <= ATR/ATR_200 <= 1.0`.
- Stop-loss validity: `risk > 0` and `risk / close >= 0.015`.
- TP: structural TP from the nearest valid opposite order block when
  available, else `entry + 2R`; reject if reward/risk < 1.5.

**SHORT entry (all required):**
- Price interaction with an active supply zone.
- MACD histogram positive but falling (`hist > 0` and `hist < p_hist`), and
  fallen for at least 2 bars (`p_hist < pp_hist`).
- KDJ: `K > 50`, `J > K > D`, plus `K >= 70`, `J <= 100`.
- K-acceleration window: `1 <= k_accel <= 6`.
- ATR regime filter: reject if `0.8 <= ATR/ATR_200 <= 1.0`.
- Stop-loss validity: `risk > 0` and `risk / close >= 0.015`.
- TP: structural TP from the nearest valid opposite order block when
  available, else `entry - 2R`; reject if reward/risk < 1.5.

### Position management and exits

While in position, the engine records running PnL every bar and tracks the
peak PnL since entry. Exit conditions, evaluated at bar-close resolution:
- **Trailing exit**: once peak PnL reaches at least 1.5%, exit on a 50%
  retrace from that peak.
- **KDJ reset exit**: a dynamically updated KDJ state machine seeded from
  the static KDJ value at the entry bar, recursed with a period equal to
  `entry_idx - triggering_OB_bar` (frozen for that trade's life). Gated to
  fire no earlier than 3 bars after entry.
- **ATR move exit**: closes at approximately `1.8 * ATR` favorable move.
- **Breakeven stop**: once price reaches `2 * ATR` favorable move, the stop
  loss moves to breakeven.
- **Hard exits**: stop loss hit, or take profit hit.

Each trade record includes side, entry/exit index and price, PnL percent,
entry order-block metadata, whether the TP came from a structural order
block, and hold-bar count. Aggregate stats (Total Trades, Total Net Return
%, Avg Return/Trade %, Win Rate %) are attached to the resulting
DataFrame's `.attrs`.

> **Note on two separate KDJ systems**: entry gating always reads the
> static, full-history KDJ(9,3,3) column. Only the post-entry exit signal
> uses the dynamic, per-trade state machine described above. These are
> deliberately not unified — see `CLAUDE.md`'s "KDJ architecture" section.

---

## Statistical analyses (part of `research_analysis.py`)

Every analysis below (formerly a separate script under `analysis/`) is now
a function inside `research_analysis.py`, run automatically as one step of
`python research_analysis.py`'s full offline pipeline (Section 5B — see the
file's own module docstring for the section map). They consume the existing
backtest output (`artifacts/candles.csv`, the strategy's own trade log via
`simulate_trades()`), never modify `simulate_trades()` itself, and never
change a locked/reported headline number — each is an additive lens on the
same 27-trade `min_ob_quality=0` baseline. Pass `--json-out PATH` to
`research_analysis.py` to write every section's results as one JSON file.

| Function | What it does |
|---|---|
| `run_fee_slippage_sensitivity()` | Applies Binance's confirmed USDT-M Futures taker fee (0.05%/side) plus a labeled conservative slippage estimate, reruns the binomial test on the fee-adjusted PnL. |
| `run_bootstrap_ci()` | Nonparametric percentile bootstrap (default B=10,000) for a 95% CI on total/average return. |
| `run_benchmark_vs_buy_and_hold()` / `run_dca_blend_analysis()` | Strategy vs. buy-and-hold equity curve, Sharpe/Sortino/max drawdown, Pearson correlation of per-trade return vs. BTC's return over the same window, plus a DCA "complementary sleeve" blend. |
| `run_benchmark_vs_passive()` | Dollar-denominated head-to-head: OB-gated strategy vs. weekly DCA vs. lump-sum buy-and-hold, both the locked 2022-2026 window and the 2018-2022 formulation-period window, gross and fee-adjusted. |
| `run_regime_breakdown()` | Tags each baseline trade by macro regime under two independent methods (calendar split, and price-drawdown-from-ATH), reports win rate/return contribution per regime. |
| `run_forward_oos_validation()` | **Makes live Binance API calls** (the one disclosed exception to the offline-only rule) — gated behind `--include-oos-live`, off by default. Forward out-of-sample test against data postdating every strategy commit. |
| `run_paper_sync_check()` / `generate_paper_sync_report()` | Recomputes every checkable figure fresh and diffs against `CLAUDE.md`'s locked numbers; the latter also regenerates `artifacts/paper_sync_report.md` (part of `--serve` mode). |
| `build_trades_and_results_table()` | Full trade/results table builder, including numeric order-block-criteria diagnostics. |

See `CLAUDE.md` for the exact locked figures each is checked against.

---

## `research_analysis.py` — the single entrypoint

`research_analysis.py` is THE canonical, single-file entrypoint for this
project: the strategy/backtest engine, the database manager, every
statistical test and downstream analysis above, the Google Sheets export,
and the dashboard's live HTTP server, all in one file, one process — not a
reference copy alongside separately-maintained originals. The previously
scattered files it replaces (`src/Binance backtest bot.py`, `db_manager.py`,
`export_gui_data.py`, `analysis/*.py`) were moved to the git-ignored
`legacy_pre_consolidation/` folder as a disk-only backup; nothing runs from
there anymore.

```bash
python research_analysis.py                       # full offline stats pipeline
python research_analysis.py --json-out out.json    # also write JSON output
python research_analysis.py --include-oos-live      # also run the one
                                                      # network-touching
                                                      # OOS section (off by
                                                      # default)
python research_analysis.py --serve                 # export artifacts/DB,
                                                      # push to Google Sheets
                                                      # (--export-gsheet),
                                                      # and start the
                                                      # dashboard server
```

See [Alternative: run the pipeline script directly](#alternative-run-the-pipeline-script-directly)
above for the full flag reference, split by which of the two modes
(default offline pipeline vs. `--serve`) each flag actually affects.

---

## Security and credentials

The bot is designed to be upload-safe when used correctly:

- **Binance keys** — read from environment variables `BINANCE_API_KEY` /
  `BINANCE_API_SECRET`. No hardcoded key in code.
- **Google Sheets credentials** — read from `GOOGLE_SERVICE_KEY_PATH` (env
  var preferred; falls back to the placeholder path `SERVICE
  KEY/your-service-account-key.json` in code) and `GOOGLE_SHEET_ID` (env
  var preferred; falls back to the placeholder `your_google_sheet_id_here`).
- **Runtime safety checks** — the export step raises a clear `ValueError`
  if placeholders are still unchanged, instead of silently doing nothing or
  writing to the wrong sheet.
- **`.gitignore`/`.dockerignore`** both exclude `SERVICE KEY/*.json`,
  `.env`, and `.env.*` (with `.env.example` explicitly re-included) —
  credentials are never committed to git and never baked into a Docker
  image layer.

Recommended for anyone forking or publishing this repo: keep real secrets
out of the repository, commit placeholders/examples only, and confirm
`git log -- 'SERVICE KEY/'` is empty before making a private repo public
(this repo currently has a standing, disclosed exception to that — see
`CHANGELOG.md`'s 2026-08-01 "Credential tracking status" entry).

---

## Known limitations / future work

- **Leverage is not modeled; all reported returns are unlevered/notional.**
  This is a deliberate scope decision, not an oversight. `simulate_trades()`
  evaluates every exit condition — hard stop-loss, take-profit, the
  trailing exit, the ATR-move exit, and the breakeven-stop adjustment — at
  bar-close resolution only. Intrabar `high`/`low` prices are present in
  `artifacts/candles.csv` and read into the simulation loop, but used only
  for order-block touch detection and two quality criteria (displacement,
  large-bar) — never for any exit or position-sizing decision. The engine
  has no concept of a margin or liquidation price at any leverage level.
  A defensible leveraged backtest requires intrabar liquidation tracking,
  which is a real engine change, not an analysis-layer addition — see
  `CHANGELOG.md`'s 2026-08-03 entry for the full reasoning. Until then,
  this codebase reports unlevered returns only, consistent with common
  practice in the technical-trading-rule literature.
- The statistical-analysis functions in `research_analysis.py` (Section 5B)
  are read-only lenses on the same 27-trade baseline; they are not
  independent replications on new data (except `run_forward_oos_
  validation()`'s live-pull section).
- See `CLAUDE.md`'s "Open question" and "Known bugs" sections for
  currently-unresolved methodological questions, and `CHANGELOG.md` for
  every prior correction's full reasoning and verification trail.
