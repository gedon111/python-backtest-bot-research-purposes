"""
research_analysis.py
=====================

THE single, canonical entrypoint for the full research pipeline behind the
ISEF paper "Harnessing Bitcoin Volatility": a rule-based BTC/USDT strategy
(MACD + KDJ + ATR + SMC Order Blocks) backtested on 4-hour candles, Jan 2022
- Jan 2026. This one file IS the backtest engine, the statistics pipeline,
the database manager, and the dashboard's live HTTP server -- not a
reference copy alongside separately-maintained originals.

    python research_analysis.py                 run the offline stats pipeline
    python research_analysis.py --serve          export artifacts/DB + start
                                                  the dashboard server (port 8765)

WHAT THIS FILE IS
------------------
A single-file, heavily-commented CONSOLIDATION of logic that previously lived
scattered across ~15 files in this repository. Every function is declared
once, documented individually (NumPy-style docstring + "Statistical/
analytical question answered" + provenance note), and grouped into numbered
sections (banner comments below) rather than left scattered across modules.
The superseded original files (`src/Binance backtest bot.py`, `db_manager.py`,
`export_gui_data.py`, `Run_All.py`'s former target, and the `analysis/*.py`
scripts) have been moved to `legacy_pre_consolidation/`
at the repo root -- a git-ignored, disk-only backup, not part of the running
system or the repository history going forward. Two of the retired
`analysis/*.py` scripts (`oos_validation_analysis.py`'s 8-year backfill audit,
`export_extended_candles.py`'s live-pull builder) were occasional manual
audit tools even before this consolidation, not part of the routine
export/`--serve` pipeline -- they were not ported, and remain available only
in `legacy_pre_consolidation/` if that audit is ever rerun by hand.

WHAT THIS FILE IS NOT
----------------------
- It is NOT a rewrite of the strategy. Every formula, threshold, and
  control-flow branch of the protected core logic (compute_indicators(),
  compute_smc(), simulate_trades(), the kdj_reset_* exit state machine) is
  reproduced from the original source unchanged; only variable names,
  organization, comments, and physical file location changed. Where an
  original file's docstring already explained a design decision, that
  explanation is preserved here (sometimes verbatim) rather than re-derived.
- The plumbing around that core (GSheet export, the HTTP server, database
  I/O, live Binance pulls) WAS reorganized -- relocated, de-duplicated
  (e.g. dynamic per-script "load the strategy module" indirection removed,
  since the strategy IS this module now), and in a few cases simplified
  (subprocess+JSON round-trips to analysis/*.py scripts replaced by direct
  in-process function calls) -- but not behaviorally changed. Every such
  change is called out at its point of use.
- The one exception that is genuinely new analysis, not a port: `spearman_
  correlation()`. No file in this repository previously computed Spearman's
  rho (only Pearson existed); it's a thin `scipy.stats.spearmanr` wrapper
  mirroring the existing Pearson call.

SECTION MAP
------------
  1    Imports, constants, shared utilities (json_safe, report_stat)
  1B   Database manager (Candle/OrderBlock/OBTouch/Trade ORM, init/session/clear)
  2    Data loading / preprocessing
  3    Strategy / backtest engine (protected core logic, see above)
  3B   Live data pull (get_candles) + Google Sheets export plumbing
  4    Ablation study (three-arm design)
  5    Statistical test primitives (binomial/Fisher/Welch/bootstrap/etc.)
  5B   Application-level analyses (benchmark/DCA/fee-slippage/regime/OOS/
       paper-sync/benchmark-vs-passive)
  6    Dashboard artifact export + database persistence
  7    HTTP server / frontend endpoints (what dashboard-v2 talks to)
  8    Main execution block / CLI (default stats pipeline, or --serve)

OFFLINE BY DEFAULT
-------------------
The default (no `--serve`) stats pipeline runs strictly offline against
`artifacts/candles.csv` (and `artifacts/candles_extended.json` for the
2018-2022 formulation-period window). The one disclosed exception --
run_forward_oos_validation()'s live Binance pull -- is gated behind an
explicit `--include-oos-live` CLI flag, off by default, so a bare
`python research_analysis.py` never touches the network. `--serve` mode
does pull live candles (get_candles(), falling back to the local cache on
failure) since exporting a fresh dashboard snapshot is its whole purpose.

NO STRATEGY LOGIC, THRESHOLD, OR FORMULA CHANGES were made to the protected
core (see "WHAT THIS FILE IS NOT" above). If you are comparing this file
against `legacy_pre_consolidation/`'s originals and find a discrepancy in
that core logic, that is a transcription bug in THIS file, not a revision to
the paper's methodology -- report it rather than "fixing" either side
silently.
"""

import argparse
import glob
import hashlib
import http.server
import importlib.util
import json
import os
import re
import socketserver
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

import gspread
import numpy as np
import pandas as pd
from binance.client import Client
from gspread_formatting import CellFormat, Color, TextFormat, format_cell_ranges
from oauth2client.service_account import ServiceAccountCredentials
from scipy import stats as scipy_stats
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker


# ============================================================================
# SECTION 1: IMPORTS, CONSTANTS, AND SHARED UTILITIES
# ============================================================================

# --- SMC (Smart Money Concepts) Order Block detection parameters ----------
# Match LuxAlgo's default TradingView indicator settings; unchanged from
# src/Binance backtest bot.py.
SWING_STRUCTURE_LOOKBACK_BARS = 50    # LuxAlgo "swingsLengthInput"
INTERNAL_STRUCTURE_LOOKBACK_BARS = 5  # LuxAlgo internal-structure pivot lookback
MAX_ORDER_BLOCK_AGE_BARS = 500        # discard Order Blocks older than this

# --- Trade simulation parameters -------------------------------------------
# Pre-registered, fixed for the paper. Never swept or optimized (see
# CLAUDE.md's "Rules" section) -- reproduced verbatim from simulate_trades().
DEFAULT_MIN_OB_QUALITY = 1
MIN_STOP_LOSS_DISTANCE_RATIO = 0.015   # SL must be >= 1.5% away from entry
KDJ_J_LONG_CAP = 60.0
KDJ_K_LONG_CAP = 50.0
KDJ_K_SHORT_FLOOR = 70.0
KDJ_J_SHORT_CAP = 100.0
ATR_MULT_EXIT = 1.8                    # ATR-multiple forced-exit distance
ATR_MULT_BREAKEVEN = 2.0               # ATR-multiple breakeven-stop ratchet
MIN_RISK_REWARD_RATIO = 1.5

# --- Locked baseline figures (from CLAUDE.md's "Locked results" section) --
# These are the paper's published, audited numbers. Every analysis section
# below cross-checks its own fresh recomputation against these and reports
# MATCH/DIVERGE explicitly -- never silently reconciled.
LOCKED_BASELINE_TRADE_COUNT = 27
LOCKED_BASELINE_WIN_RATE_PCT = 70.37
LOCKED_BASELINE_TOTAL_RETURN_PCT = 30.31
LOCKED_BASELINE_AVG_RETURN_PCT = 1.12
LOCKED_BASELINE_RETURN_SD_PCT = 2.41
LOCKED_ABLATION_ARMS = {
    # Ablation A / "flat-ATR stop" and Ablation B / "swing-pivot stop".
    # See Section 4's docstring: no committed script reproduces the exact
    # per-trade pool that generated these, so they are carried here as
    # reference figures only, not re-derived from a verified source.
    "flat_atr": {"n": 140, "win_rate_pct": 60.00, "total_return_pct": -14.63},
    "swing_pivot": {"n": 138, "win_rate_pct": 55.07, "total_return_pct": -25.50},
}

ARTIFACTS_CANDLES_CSV = "artifacts/candles.csv"
ARTIFACTS_CANDLES_EXTENDED_JSON = "artifacts/candles_extended.json"


def json_safe(value):
    """
    Convert a numpy/pandas value into something json.dump() can serialize.

    Statistical question answered: none -- this is a serialization utility,
    not an analysis step. It exists because numpy scalar types (np.int64,
    np.float64), numpy arrays, and pandas Timestamps are not natively
    JSON-serializable, and every analysis section below produces results
    dicts full of them.

    Parameters
    ----------
    value : Any
        A single value encountered while walking a results dict/list.

    Returns
    -------
    A JSON-serializable equivalent of `value` (int, float, list, str, or
    None for NaN).
    """
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def write_json_results(data, path):
    """
    Write an analysis results dict to disk as indented JSON.

    Statistical question answered: none -- output utility only.

    Parameters
    ----------
    data : dict
        Results dict (may contain numpy/pandas values; see json_safe()).
    path : str
        Destination file path.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=json_safe)
    print(f"\n[json-out] wrote {path}")


def report_stat(name, inputs, outputs):
    """
    Print one labeled block of a statistical result to the terminal, showing
    both the named inputs a test/computation was called with and everything
    it computed -- never just the headline number.

    Statistical question answered: none -- this is the single shared
    terminal-reporting utility used by every stats-producing function in
    this file, so that "what did this test take as input and what did it
    compute" is always visible on stdout, not just written to a results
    dict. Introduced during the single-file consolidation so that terminal
    output formatting isn't repeated ad hoc at each call site.

    Formatting convention
    ----------------------
    - Every float value (input or output) is printed to 10 decimal places
      (`.10f`), per this project's terminal-reporting requirement.
    - Integers (trade counts, sample sizes, seeds, resample counts) are
      printed as plain integers, not padded with decimals.
    - Booleans and strings are printed as-is.
    - NaN/None print as "NaN" rather than raising.

    Parameters
    ----------
    name : str
        Label for this result block, e.g. "Binomial test (q>=0 baseline)".
    inputs : dict
        The named arguments/data the computation was actually called with,
        e.g. {"win_count": 19, "trade_count": 27, "null_win_probability": 0.5}.
    outputs : dict
        Everything the computation produced, e.g.
        {"p_one_sided": 0.02604..., "p_two_sided": 0.05208...}.
    """
    def _fmt(value):
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        if isinstance(value, (float, np.floating)):
            if pd.isna(value):
                return "NaN"
            return f"{float(value):.10f}"
        if value is None:
            return "NaN"
        return str(value)

    print(f"\n[stat] {name}")
    if inputs:
        print("  inputs:")
        for key, value in inputs.items():
            print(f"    {key:<28} = {_fmt(value)}")
    if outputs:
        print("  computed:")
        for key, value in outputs.items():
            print(f"    {key:<28} = {_fmt(value)}")


# ============================================================================
# SECTION 1B: DATABASE MANAGER
# ============================================================================
# Consolidated from db_manager.py (now retired to legacy_pre_consolidation/).
# SQLAlchemy ORM schema + session/lifecycle helpers for the SQLite (default)
# or arbitrary DATABASE_URL-backed database that stores per-run candles,
# detected Order Blocks, OB touch events, and simulated trades -- the same
# data the dashboard-v2 frontend's live /api/trades and /api/iterations
# routes query (see Section 8's HTTP server). Schema is reproduced verbatim
# from db_manager.py; no column, index, or table was added/removed/renamed.

Base = declarative_base()


class Candle(Base):
    """One OHLCV bar plus its computed indicators, keyed by (time, symbol,
    interval). Populated by export_artifacts() (Section 7) from the same
    DataFrame simulate_trades() operates on."""

    __tablename__ = "candles"

    time = Column(Integer, primary_key=True)
    symbol = Column(String(20), primary_key=True)
    interval = Column(String(10), primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    k = Column(Float)
    d = Column(Float)
    j = Column(Float)
    atr_14 = Column(Float)
    atr_200 = Column(Float)
    volume_ma_ratio = Column(Float)
    taker_buy_ratio = Column(Float)
    body_wick_ratio = Column(Float)
    time_hour = Column(Integer)
    time_day_of_week = Column(Integer)

    __table_args__ = (
        Index("idx_candles_sym_int_time", "symbol", "interval", "time"),
    )


class OrderBlock(Base):
    """One detected SMC Order Block, including its 5 independent quality
    criteria and the legacy composite 0-5 score (see CLAUDE.md Known bug
    #1 -- the composite score is still stored/computed but is no longer
    used as an ordinal threshold for analysis)."""

    __tablename__ = "order_blocks"

    ob_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    interval = Column(String(10), nullable=False)
    type = Column(String(10), nullable=False)  # 'DEMAND' or 'SUPPLY'
    top = Column(Float, nullable=False)
    bottom = Column(Float, nullable=False)
    created_at = Column(Integer, nullable=False)  # bar index
    ob_bar = Column(Integer, nullable=False)  # bar index
    level = Column(String(10), nullable=False)  # 'internal' or 'swing'
    structure = Column(String(10), nullable=False)  # 'CHoCH' or 'BOS'
    mitigated_at = Column(Integer)  # bar index or NULL
    quality = Column(Integer, nullable=False)  # composite 0-5 (legacy, see above)
    quality_displacement = Column(Boolean, nullable=False)
    quality_large_bar = Column(Boolean, nullable=False)
    quality_fvg = Column(Boolean, nullable=False)
    quality_liquidity_sweep = Column(Boolean, nullable=False)
    quality_volume_expansion = Column(Boolean, nullable=False)

    __table_args__ = (
        Index("idx_obs_sym_int", "symbol", "interval"),
        Index("idx_obs_created", "created_at"),
    )


class OBTouch(Base):
    """One bar where price touched an Order Block, with the indicator
    snapshot at that touch -- FK'd to the OrderBlock it belongs to."""

    __tablename__ = "ob_touches"

    touch_id = Column(Integer, primary_key=True, autoincrement=True)
    ob_id = Column(Integer, ForeignKey("order_blocks.ob_id"), nullable=False)
    time = Column(Integer, nullable=False)  # bar index / timestamp
    touch_price = Column(Float, nullable=False)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    k = Column(Float)
    d = Column(Float)
    j = Column(Float)
    k_accel = Column(Float)
    atr_14 = Column(Float)
    atr_200 = Column(Float)

    __table_args__ = (
        Index("idx_touches_ob_id", "ob_id"),
        Index("idx_touches_time", "time"),
    )


class Trade(Base):
    """One simulated trade from simulate_trades(), FK'd to its entry and
    (optional) structural-TP Order Blocks, keyed additionally by the
    min_ob_quality threshold used for that simulation run."""

    __tablename__ = "trades"

    trade_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    interval = Column(String(10), nullable=False)
    side = Column(String(10), nullable=False)  # 'LONG' or 'SHORT'
    min_ob_quality = Column(Integer, nullable=False)  # quality threshold used
    entry_time = Column(Integer, nullable=False)  # bar index / timestamp
    exit_time = Column(Integer, nullable=False)  # bar index / timestamp
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    pnl_pct = Column(Float, nullable=False)
    hold_bars = Column(Integer, nullable=False)
    exit_reason = Column(String(50), nullable=False)
    entry_ob_id = Column(Integer, ForeignKey("order_blocks.ob_id"), nullable=False)
    tp_ob_id = Column(Integer, ForeignKey("order_blocks.ob_id"), nullable=True)

    __table_args__ = (
        Index("idx_trades_sym_int", "symbol", "interval"),
        Index("idx_trades_entry_time", "entry_time"),
    )


def get_db_url():
    """Retrieve the database URL from the DATABASE_URL env var, falling back
    to the local SQLite file `backtest_results.db` at the repo root."""
    return os.getenv("DATABASE_URL", "sqlite:///backtest_results.db")


def init_db(db_url=None):
    """Create the engine and all tables (if they don't already exist).

    Parameters
    ----------
    db_url : str, optional
        Defaults to get_db_url() (env var or local SQLite file).

    Returns
    -------
    sqlalchemy.Engine
    """
    if db_url is None:
        db_url = get_db_url()
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Return a new SQLAlchemy session bound to `engine`."""
    Session = sessionmaker(bind=engine)
    return Session()


def clear_db(engine):
    """Delete all rows from candles/order_blocks/ob_touches/trades, in
    FK-safe order (children before parents), ahead of a fresh export run."""
    tables = ["ob_touches", "trades", "order_blocks", "candles"]
    with engine.begin() as conn:
        for table in tables:
            try:
                conn.execute(text(f"DELETE FROM {table}"))
            except Exception as e:
                print(f"Warning: Failed to clear table {table}: {e}")


# ============================================================================
# SECTION 2: DATA LOADING / PREPROCESSING
# ============================================================================

def load_candles(path=ARTIFACTS_CANDLES_CSV):
    """
    Load the locked BTC/USDT 4H candle dataset from CSV.

    Statistical question answered: none -- data loading only. This is the
    fixed dataset (8,767 bars, 2022-01-01 .. 2026-01-01, see CLAUDE.md) that
    every locked figure in the paper is computed from.

    Parameters
    ----------
    path : str
        Path to the candles CSV (default: the locked baseline dataset).

    Returns
    -------
    pandas.DataFrame
        Columns: open_time (datetime), open, high, low, close, volume,
        num_trades, taker_buy_base.
    """
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"])
    return df


def load_extended_candles_window(start_date, end_date, path=ARTIFACTS_CANDLES_EXTENDED_JSON):
    """
    Load a sub-window of the extended (2018-2026) candle history from the
    committed JSON snapshot, used for the 2018-2022 "formulation period"
    window (the period the strategy's rule structure was originally tuned
    against -- explicitly NOT out-of-sample; see Section 5's benchmark
    functions).

    Statistical question answered: none -- data loading only.

    Parameters
    ----------
    start_date, end_date : str
        Inclusive/exclusive datetime bounds (ISO format) for the window.
    path : str
        Path to the extended-history JSON snapshot.

    Returns
    -------
    pandas.DataFrame
        Same schema as load_candles(), restricted to [start_date, end_date).
    """
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    records = manifest["records"] if isinstance(manifest, dict) and "records" in manifest else manifest
    df = pd.DataFrame(records)
    df["open_time"] = pd.to_datetime(df["open_time"])
    mask = (df["open_time"] >= pd.Timestamp(start_date)) & (df["open_time"] < pd.Timestamp(end_date))
    return df.loc[mask].reset_index(drop=True)


# ============================================================================
# SECTION 3: STRATEGY / BACKTEST LOGIC
# ============================================================================
#
# Ported verbatim (formulas, thresholds, and control flow unchanged) from
# src/Binance backtest bot.py's compute_indicators(), compute_smc(),
# get_structural_tp(), kdj_reset_init/update/exit(), simulate_trades(), and
# run_quality_sweep(). Only variable names and comments were changed for
# readability -- see this file's module docstring.
#
# A note on the "ob" abbreviation used throughout this section: it stands
# for "Order Block", the SMC (Smart Money Concepts) structure this engine
# detects -- a price zone where institutional order flow is inferred to have
# originated a market structure shift. It is used as consistently as "df"
# is used for DataFrame, rather than spelled out at every call site, because
# it appears in extremely dense per-bar loops below.


def compute_indicators(df, kdj_period=9, atr_period=14):
    """
    Compute MACD(12,26,9), KDJ(kdj_period,3,3), ATR(14), and ATR(200) on a
    candle DataFrame.

    Statistical/analytical question answered: none directly -- this produces
    the raw technical-indicator inputs that the entry/exit gating logic in
    simulate_trades() reads. KDJ is a stochastic-oscillator variant (K, D
    lines plus J = 3K - 2D) commonly used for overbought/oversold timing;
    MACD is a trend/momentum indicator; ATR is a volatility measure used
    here both for stop-loss sizing and as a regime filter (see atr_r in
    simulate_trades()).

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with open/high/low/close/volume columns.
    kdj_period : int, default 9
        Lookback window (bars) for the KDJ RSV calculation. Standard
        stochastic-oscillator default.
    atr_period : int, default 14
        Lookback window (bars) for the primary ATR. A second ATR with a
        fixed 200-bar window (ATR_200) is always computed alongside it, used
        as a longer-horizon volatility baseline for the atr_r regime ratio.

    Returns
    -------
    pandas.DataFrame
        A copy of `df` with added columns: MACD, MACD_signal, MACD_hist, K,
        D, J, RSV, ATR, ATR_200.
    """
    df = df.copy()
    for column_name in ["open", "high", "low", "close", "volume"]:
        if column_name in df.columns:
            df[column_name] = pd.to_numeric(df[column_name], errors="coerce")

    # --- MACD (12, 26, 9) ---
    ema_fast = df["close"].ewm(span=12, adjust=False).mean()
    ema_slow = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    # --- KDJ -- EWM alpha = 1/3, matching the standard KDJ smoothing ---
    period = int(kdj_period)
    rolling_low_min = df["low"].rolling(period, min_periods=1).min()
    rolling_high_max = df["high"].rolling(period, min_periods=1).max()
    rsv_denominator = (rolling_high_max - rolling_low_min).replace(0, np.nan)
    raw_stochastic_value = ((df["close"] - rolling_low_min) / rsv_denominator * 100).fillna(50)
    kdj_smoothing_alpha = 1.0 / 3.0
    df["K"] = raw_stochastic_value.ewm(alpha=kdj_smoothing_alpha, adjust=False).mean()
    df["D"] = df["K"].ewm(alpha=kdj_smoothing_alpha, adjust=False).mean()
    df["J"] = 3 * df["K"] - 2 * df["D"]
    df["RSV"] = raw_stochastic_value

    # --- ATR -- true range, Wilder's smoothing (RMA) ---
    # Seed: first `period` bars use a plain SMA (identical to
    # TradingView/MT4). Then ATR = (ATR_prev * (n-1) + TR_current) / n,
    # which is equivalent to ewm(alpha=1/n, adjust=False) in pandas.
    previous_close = df["close"].shift(1)
    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR"] = true_range.rolling(atr_period, min_periods=1).mean()
    df["ATR_200"] = true_range.rolling(200, min_periods=1).mean()

    # Safeguard for missing columns in cached files.
    if "num_trades" not in df.columns:
        df["num_trades"] = 0.0
    if "taker_buy_base" not in df.columns:
        df["taker_buy_base"] = df["volume"] * 0.5

    return df


def compute_smc(df):
    """
    Detect Smart Money Concepts (SMC) Order Blocks via BOS/CHoCH structure
    breaks, faithfully translated from the LuxAlgo TradingView indicator.

    Statistical/analytical question answered: none directly -- this
    identifies the price zones (Order Blocks) that simulate_trades() gates
    entries against, and scores each one on 5 independent quality criteria
    used later by the per-criterion Fisher's-exact/Welch's-t tests in
    Section 5.

    Method: runs two independent passes over the candle series -- a "swing"
    pass (50-bar pivot lookback) and an "internal" pass (5-bar pivot
    lookback). Within each pass, bar by bar:
      1. Check if the bar `size` bars back is a new pivot high/low (a
         right-side-confirmed local extreme -- i.e. no bar since has broken
         it -- which is why this cannot be evaluated until `size` bars
         later without lookahead).
      2. Detect whether the current close crosses a tracked pivot level
         (a "Break of Structure" / BOS if trend continues, a "Change of
         Character" / CHoCH if trend reverses).
      3. On a crossover, construct an Order Block from the
         volatility-parsed high/low arrays between the pivot bar and the
         crossover bar, then score it on 5 orthogonal quality criteria
         (displacement, large_bar, fvg, liquidity_sweep, volume_expansion).

    No-lookahead guarantee: every quality-criterion forward search below is
    bounded by `i` (the Order Block's own confirmation/created_at bar), not
    by dataset length -- see the inline asserts. This was itself a
    corrected bug (CLAUDE.md Known bug #3): the forward-search loops used
    to be bounded by dataset length, letting quality criteria read 1-2 bars
    past an OB's own confirmation bar.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data already passed through compute_indicators() (needs
        ATR_200).

    Returns
    -------
    list of dict
        One dict per detected Order Block: type ('DEMAND'/'SUPPLY'), top,
        bottom, created_at (confirmation bar index), ob_bar (the actual OB
        candle's index), level ('swing'/'internal'), structure
        ('CHoCH'/'BOS'), the 5 boolean quality_* fields, the integer
        `quality` composite (0-5, kept for reference but not used as an
        ordinal threshold -- see CLAUDE.md Known bug #1), and
        `mitigated_at` (the bar index at which price closed back through
        the zone, invalidating it).
    """
    num_bars = len(df)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    atr_200 = df["ATR_200"].values

    # Volatility-parsed high/low (LuxAlgo OB filter): on high-volatility
    # bars, the body is inverted for OB-search purposes.
    #   parsed_high = low  if bar range >= 2*ATR_200 else high
    #   parsed_low  = high if bar range >= 2*ATR_200 else low
    is_high_volatility_bar = (highs - lows) >= (2 * atr_200)
    parsed_highs = np.where(is_high_volatility_bar, lows, highs)
    parsed_lows = np.where(is_high_volatility_bar, highs, lows)

    all_order_blocks = []

    for pivot_lookback_bars in [INTERNAL_STRUCTURE_LOOKBACK_BARS, SWING_STRUCTURE_LOOKBACK_BARS]:
        level_tag = "internal" if pivot_lookback_bars == INTERNAL_STRUCTURE_LOOKBACK_BARS else "swing"

        # Mutable state for this structure level.
        tracked_swing_high_price = np.nan
        tracked_swing_high_bar = -1
        swing_high_already_crossed = False

        tracked_swing_low_price = np.nan
        tracked_swing_low_bar = -1
        swing_low_already_crossed = False

        trend = 0  # +1 bullish, -1 bearish, 0 neutral

        for i in range(pivot_lookback_bars + 1, num_bars):
            pivot_bar_candidate = i - pivot_lookback_bars

            # NO-LOOKAHEAD: pivot windows must never read past bar i.
            assert pivot_bar_candidate + 1 <= i + 1 and (i + 1) - (pivot_bar_candidate + 1) == pivot_lookback_bars, (
                f"LOOKAHEAD: pivot window at i={i} pivot_bar_candidate={pivot_bar_candidate} "
                f"pivot_lookback_bars={pivot_lookback_bars} spans an unexpected range."
            )

            # --- Pivot HIGH confirmation ---
            # high[pivot_bar_candidate] > max(high[pivot_bar_candidate+1 .. i]) means
            # that bar is a right-side-confirmed swing high.
            bars_to_the_right_high = highs[pivot_bar_candidate + 1: i + 1]
            if len(bars_to_the_right_high) and highs[pivot_bar_candidate] > bars_to_the_right_high.max():
                tracked_swing_high_price = float(highs[pivot_bar_candidate])
                tracked_swing_high_bar = pivot_bar_candidate
                swing_high_already_crossed = False  # reset -- new pivot to watch

            # --- Pivot LOW confirmation ---
            bars_to_the_right_low = lows[pivot_bar_candidate + 1: i + 1]
            if len(bars_to_the_right_low) and lows[pivot_bar_candidate] < bars_to_the_right_low.min():
                tracked_swing_low_price = float(lows[pivot_bar_candidate])
                tracked_swing_low_bar = pivot_bar_candidate
                swing_low_already_crossed = False

            # --- BULLISH BOS / CHoCH ---
            if (not np.isnan(tracked_swing_high_price) and not swing_high_already_crossed
                    and closes[i - 1] <= tracked_swing_high_price < closes[i]):

                structure_tag = "CHoCH" if trend == -1 else "BOS"
                swing_high_already_crossed = True
                trend = 1

                if tracked_swing_high_bar >= 0:
                    ob = _build_order_block_from_crossover(
                        df, highs, lows, atr_200, parsed_highs, parsed_lows,
                        pivot_bar=tracked_swing_high_bar, confirmation_bar=i,
                        ob_type="DEMAND", level_tag=level_tag, structure_tag=structure_tag,
                        extreme_selector=np.argmin, extreme_source=parsed_lows,
                    )
                    all_order_blocks.append(ob)

            # --- BEARISH BOS / CHoCH ---
            if (not np.isnan(tracked_swing_low_price) and not swing_low_already_crossed
                    and closes[i - 1] >= tracked_swing_low_price > closes[i]):

                structure_tag = "CHoCH" if trend == 1 else "BOS"
                swing_low_already_crossed = True
                trend = -1

                if tracked_swing_low_bar >= 0:
                    ob = _build_order_block_from_crossover(
                        df, highs, lows, atr_200, parsed_highs, parsed_lows,
                        pivot_bar=tracked_swing_low_bar, confirmation_bar=i,
                        ob_type="SUPPLY", level_tag=level_tag, structure_tag=structure_tag,
                        extreme_selector=np.argmax, extreme_source=parsed_highs,
                    )
                    all_order_blocks.append(ob)

    # --- Mitigation: the bar at which price closes back through the zone ---
    close_prices = df["close"].values
    for ob in all_order_blocks:
        search_start = ob["created_at"] + 1
        if search_start >= num_bars:
            ob["mitigated_at"] = num_bars
            continue
        if ob["type"] == "DEMAND":
            violations = np.where(close_prices[search_start:] < ob["bottom"])[0]
        else:
            violations = np.where(close_prices[search_start:] > ob["top"])[0]
        ob["mitigated_at"] = int(search_start + violations[0]) if len(violations) else num_bars

    return all_order_blocks


def _build_order_block_from_crossover(df, highs, lows, atr_200, parsed_highs, parsed_lows,
                                       pivot_bar, confirmation_bar, ob_type, level_tag,
                                       structure_tag, extreme_selector, extreme_source):
    """
    Construct one Order Block dict (with its 5 quality criteria scored) from
    a confirmed BOS/CHoCH crossover. Shared helper for the bullish (DEMAND)
    and bearish (SUPPLY) branches of compute_smc(), which are otherwise
    identical aside from which array they search for the defining extreme.

    Statistical/analytical question answered: this is where each Order
    Block's 5 independent (orthogonal, per CLAUDE.md Known bug #1) quality
    criteria are evaluated -- displacement, large_bar, fvg (Fair Value Gap),
    liquidity_sweep, and volume_expansion. These feed the per-criterion
    Fisher's-exact/Welch's-t tests in Section 5, which ask: "do trades whose
    entry Order Block had this criterion TRUE earn significantly different
    returns than trades whose entry OB did not?"

    Parameters mirror the two call sites in compute_smc() -- see there for
    the no-lookahead invariants each forward-search loop below enforces.
    """
    ob_bar_index = pivot_bar + int(extreme_selector(extreme_source[pivot_bar: confirmation_bar + 1]))
    ob = {
        "type": ob_type,
        "top": float(parsed_highs[ob_bar_index]),
        "bottom": float(parsed_lows[ob_bar_index]),
        "created_at": confirmation_bar,
        "ob_bar": ob_bar_index,
        "level": level_tag,
        "structure": structure_tag,
    }

    # --- Displacement: a strong-bodied bar within 3 bars after the OB bar ---
    displacement = False
    try:
        # NO-LOOKAHEAD FIX (CLAUDE.md Known bug #3): bound the forward search
        # by the OB's own confirmation bar (confirmation_bar), not by
        # dataset length. If confirmation_bar - ob_bar_index is too small for
        # any j to satisfy j <= confirmation_bar within this range, the loop
        # is empty and the criterion stays False -- frozen at what was
        # knowable at confirmation time, not "unknown/skip".
        for j in range(ob_bar_index + 1, min(confirmation_bar + 1, ob_bar_index + 4)):
            assert j <= confirmation_bar, (
                f"LOOKAHEAD: displacement check for OB at ob_bar_index={ob_bar_index} "
                f"(type={ob['type']}, level={level_tag}) reads bar j={j}, but the OB is "
                f"not confirmed until created_at={confirmation_bar}."
            )
            candle_body = float(df.at[j, "close"]) - float(df.at[j, "open"])
            displacement_threshold = 1.5 * float(atr_200[ob_bar_index]) if not np.isnan(atr_200[ob_bar_index]) else 0
            if ob["type"] == "DEMAND" and candle_body > 0 and abs(candle_body) >= displacement_threshold:
                displacement = True
                break
            if ob["type"] == "SUPPLY" and candle_body < 0 and abs(candle_body) >= displacement_threshold:
                displacement = True
                break
    except AssertionError:
        raise
    except Exception:
        displacement = False

    # --- Large bar: the OB candle's own range meets/exceeds ATR_200 ---
    try:
        ob_bar_range = float(highs[ob_bar_index]) - float(lows[ob_bar_index])
        large_bar = (not np.isnan(atr_200[ob_bar_index]) and ob_bar_range >= float(atr_200[ob_bar_index]))
    except Exception:
        large_bar = False

    # --- FVG (Fair Value Gap): 3-candle gap definition (CLAUDE.md bug #2) ---
    fair_value_gap = False
    try:
        # NO-LOOKAHEAD FIX: bound the forward search by confirmation_bar, not
        # dataset length. min(confirmation_bar-1, ob_bar_index+3) keeps
        # j+2 <= confirmation_bar an invariant for every j considered.
        for j in range(ob_bar_index, min(confirmation_bar - 1, ob_bar_index + 3)):
            assert j + 2 <= confirmation_bar, (
                f"LOOKAHEAD: FVG check for OB at ob_bar_index={ob_bar_index} "
                f"(type={ob['type']}, level={level_tag}) reads bar j+2={j + 2} (j={j}), "
                f"but the OB is not confirmed until created_at={confirmation_bar}."
            )
            if ob["type"] == "DEMAND" and float(lows[j + 2]) > float(highs[j]):
                fair_value_gap = True
                break
            if ob["type"] == "SUPPLY" and float(highs[j + 2]) < float(lows[j]):
                fair_value_gap = True
                break
    except AssertionError:
        raise
    except Exception:
        fair_value_gap = False

    # --- Liquidity sweep: OB bar's extreme sweeps the prior 10-bar extreme ---
    try:
        prior_window_start = max(0, ob_bar_index - 10)
        if ob["type"] == "DEMAND":
            liquidity_sweep = float(lows[ob_bar_index]) <= float(lows[prior_window_start:ob_bar_index].min())
        else:
            liquidity_sweep = float(highs[ob_bar_index]) >= float(highs[prior_window_start:ob_bar_index].max())
    except Exception:
        liquidity_sweep = False

    # --- Volume expansion: elevated volume OR a high body-to-range ratio ---
    try:
        volume_window_start = max(0, ob_bar_index - 20)
        if ob_bar_index > 0:
            ob_bar_volume = float(df.at[ob_bar_index, "volume"])
            trailing_avg_volume = float(df["volume"].iloc[volume_window_start:ob_bar_index].mean())
            volume_is_elevated = (trailing_avg_volume > 0 and ob_bar_volume >= 1.25 * trailing_avg_volume)
        else:
            volume_is_elevated = False
        ob_bar_body = abs(float(df.at[ob_bar_index, "close"]) - float(df.at[ob_bar_index, "open"]))
        ob_bar_range = float(highs[ob_bar_index]) - float(lows[ob_bar_index])
        body_dominates_range = (ob_bar_range > 0 and ob_bar_body / ob_bar_range > 0.6)
        volume_expansion = (volume_is_elevated or body_dominates_range)
    except Exception:
        volume_expansion = False

    ob["quality_displacement"] = bool(displacement)
    ob["quality_large_bar"] = bool(large_bar)
    ob["quality_fvg"] = bool(fair_value_gap)
    ob["quality_liquidity_sweep"] = bool(liquidity_sweep)
    ob["quality_volume_expansion"] = bool(volume_expansion)
    ob["quality"] = int(
        ob["quality_displacement"] + ob["quality_large_bar"] + ob["quality_fvg"]
        + ob["quality_liquidity_sweep"] + ob["quality_volume_expansion"]
    )
    return ob


def get_structural_tp(entry_price, side, valid_order_blocks):
    """
    Pick the nearest opposing Order Block as a structural take-profit target.

    Statistical/analytical question answered: none -- entry/exit rule logic.
    A "structural" TP anchors the target to actual detected market
    structure rather than a fixed risk-multiple, when one is available on
    the correct side of price.

    Parameters
    ----------
    entry_price : float
    side : str
        'LONG' or 'SHORT'.
    valid_order_blocks : list of dict
        Currently-active Order Blocks (see simulate_trades()'s valid_obs_tp).

    Returns
    -------
    float or None
        The nearest qualifying opposing-zone price level, or None if no
        Order Block exists on the correct side of `entry_price`.
    """
    if side == "LONG":
        candidate_targets = [ob for ob in valid_order_blocks if ob["type"] == "SUPPLY" and ob["bottom"] > entry_price]
        return min(candidate_targets, key=lambda ob: ob["bottom"])["bottom"] if candidate_targets else None
    else:
        candidate_targets = [ob for ob in valid_order_blocks if ob["type"] == "DEMAND" and ob["top"] < entry_price]
        return max(candidate_targets, key=lambda ob: ob["top"])["top"] if candidate_targets else None


def kdj_reset_init(df, entry_idx, ob_bar=None, default_period=9):
    """
    Initialize a per-trade KDJ exit state machine, seeded from the STATIC
    full-history KDJ value at the entry bar.

    Statistical/analytical question answered: none -- exit-signal
    infrastructure. Governs exit timing only; the entry gate itself always
    reads the static full-history KDJ from compute_indicators() (see
    CLAUDE.md's "KDJ architecture" section -- these are deliberately two
    separate systems).

    The exit-side KDJ period is dynamic: if the triggering Order Block's own
    bar (`ob_bar`) is known, the period is set to the bar-distance between
    entry and that OB bar (min 1), rather than the fixed default. This
    means each trade's KDJ-reset exit is recomputed on a period tied to how
    "fresh" its triggering Order Block was.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with K/D columns already computed.
    entry_idx : int
        Bar index of trade entry.
    ob_bar : int or None
        Bar index of the triggering Order Block, if any (None for the
        ablation arms, which have no Order Block gate -- see Section 4).
    default_period : int, default 9
        Fallback KDJ period when `ob_bar` is not available.

    Returns
    -------
    dict
        Mutable per-trade state: k, d (current), prev_k, prev_d, period,
        entry_idx, armed (bool, becomes True once K/D have crossed once in
        the trade's favor -- see kdj_reset_update()).
    """
    period = default_period
    if ob_bar is not None and isinstance(ob_bar, int) and ob_bar >= 0:
        period = max(1, entry_idx - ob_bar)

    return {
        "k": float(df.at[entry_idx, "K"]),
        "d": float(df.at[entry_idx, "D"]),
        "prev_k": float(df.at[entry_idx, "K"]),
        "prev_d": float(df.at[entry_idx, "D"]),
        "period": int(period),
        "entry_idx": int(entry_idx),
        "armed": False,
    }


def kdj_reset_update(state, df, cur_idx, side):
    """
    Advance the per-trade KDJ exit state machine by one bar.

    Statistical/analytical question answered: none -- exit-signal
    infrastructure. Recomputes K/D each bar using the trade-specific period
    (fixed for the trade's life, set by kdj_reset_init()), then arms the
    exit flag once K/D cross in the trade's favor.

    Parameters
    ----------
    state : dict
        Mutable state from kdj_reset_init() (updated in place and returned).
    df : pandas.DataFrame
    cur_idx : int
        Current bar index being processed.
    side : str
        'LONG' or 'SHORT'.

    Returns
    -------
    dict
        The same `state` dict, updated in place.
    """
    kdj_smoothing_alpha = 1.0 / 3.0
    period = max(1, int(state.get("period", 9)))

    window_start = max(cur_idx - period + 1, 0)
    window_high = df["high"].iloc[window_start:cur_idx + 1]
    window_low = df["low"].iloc[window_start:cur_idx + 1]

    if len(window_high) == 0 or len(window_low) == 0:
        raw_stochastic_value = 50.0
    else:
        window_highest = window_high.max()
        window_lowest = window_low.min()
        rsv_denominator = window_highest - window_lowest
        raw_stochastic_value = (
            (df.at[cur_idx, "close"] - window_lowest) / rsv_denominator * 100
        ) if rsv_denominator > 0 else 50.0

    state["prev_k"] = state["k"]
    state["prev_d"] = state["d"]
    state["k"] = state["k"] * (1 - kdj_smoothing_alpha) + raw_stochastic_value * kdj_smoothing_alpha
    state["d"] = state["d"] * (1 - kdj_smoothing_alpha) + state["k"] * kdj_smoothing_alpha

    if side == "SHORT" and state["k"] < state["d"]:
        state["armed"] = True
    if side == "LONG" and state["k"] > state["d"]:
        state["armed"] = True

    return state


def kdj_reset_exit(state, side):
    """
    Return True if the armed per-trade KDJ state has just cross-reversed
    (the exit signal).

    Statistical/analytical question answered: none -- exit-signal
    infrastructure.

    Parameters
    ----------
    state : dict
        Current state from kdj_reset_update().
    side : str
        'LONG' or 'SHORT'.

    Returns
    -------
    bool
        True exactly on the bar K/D crosses back against the trade's
        favorable-crossed state.
    """
    if not state["armed"]:
        return False
    if side == "SHORT":
        return state["prev_k"] <= state["prev_d"] and state["k"] > state["d"]
    else:
        return state["prev_k"] >= state["prev_d"] and state["k"] < state["d"]


_smc_detection_cache = {}


def _resolve_structural_tp_ob(valid_obs_tp, structural_tp_price, opposing_type, level_key):
    """
    Find the specific Order Block dict that produced a given structural TP
    price (get_structural_tp() returns only the price, not the OB), so the
    closed-trade record can log which OB the TP was structurally anchored
    to. Matches within a small relative tolerance to absorb float rounding.
    """
    if structural_tp_price is None:
        return None
    tolerance = 1e-6
    candidates = [
        ob for ob in valid_obs_tp
        if ob["type"] == opposing_type and abs(ob[level_key] - structural_tp_price) <= tolerance * max(1.0, abs(structural_tp_price))
    ]
    return min(candidates, key=lambda ob: abs(ob[level_key] - structural_tp_price)) if candidates else None


def _try_enter_long(df, i, close, low, high, macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                     kdj_k, kdj_k_prev_bar, kdj_j, kdj_k_acceleration, atr_regime_ratio, atr_14,
                     demand_obs, valid_obs_tp):
    """
    Evaluate the LONG entry gate against every currently-active DEMAND Order
    Block, in order, entering on the first one that passes every filter.

    Statistical/analytical question answered: none -- this is the strategy's
    entry rule itself, reproduced unchanged from simulate_trades()'s LONG
    branch (src/Binance backtest bot.py lines ~753-811). Filters, in order:
    price must be touching the OB zone; MACD histogram must be negative and
    rising for >= 2 bars; KDJ K must be below its cap and rising, J below
    its cap; K-acceleration must be in the [1, 6] window (excludes both
    non-accelerating and single-bar-spike noise); the ATR regime ratio must
    be outside the [0.8, 1.0] "dead zone"; the resulting stop-loss distance
    must be >= 1.5% of entry price; and the resulting take-profit (a
    structural OB target if one exists, else 2x risk) must clear a 1.5
    minimum risk:reward ratio.

    Returns
    -------
    tuple
        (position, entry_price, stop_loss_price, take_profit_price,
        entry_atr, peak_pnl_pct, entry_idx, kdj_state, current_entry_ob,
        current_tp_ob, entry_tp_is_structural, entry_tp_ob_bar,
        entry_tp_ob_quality) -- position is None if no Order Block passed
        every filter.
    """
    for ob in demand_obs:
        if not (low <= ob["top"] and close >= ob["bottom"]):
            continue
        if not (macd_hist_current < 0 and macd_hist_current > macd_hist_prev_bar):
            continue
        # hist must have been rising for >= 2 bars.
        if not (macd_hist_prev_bar > macd_hist_two_bars_ago):
            continue
        if not (kdj_k < KDJ_K_LONG_CAP and kdj_k > kdj_k_prev_bar and kdj_j < KDJ_J_LONG_CAP):
            continue
        if not (1 <= kdj_k_acceleration <= 6):
            continue
        if 0.8 <= atr_regime_ratio <= 1.0:
            continue

        stop_loss_candidate = ob["bottom"] - atr_14 * 0.5
        risk = close - stop_loss_candidate
        if risk <= 0:
            continue
        # SL must be >= 1.5% from entry -- thin OBs sit inside normal 4H
        # noise and get stopped before the move even starts.
        if risk / close < MIN_STOP_LOSS_DISTANCE_RATIO:
            continue

        structural_tp_price = get_structural_tp(close, "LONG", valid_obs_tp)
        take_profit_price = structural_tp_price if structural_tp_price else close + risk * 2.0
        if (take_profit_price - close) / risk < MIN_RISK_REWARD_RATIO:
            continue

        entry_price = close
        stop_loss_price = stop_loss_candidate
        entry_atr = atr_14
        entry_idx = i
        kdj_state = kdj_reset_init(df, i, ob_bar=ob.get("ob_bar", None))

        current_entry_ob = ob
        tp_ob = _resolve_structural_tp_ob(valid_obs_tp, structural_tp_price, "SUPPLY", "bottom")
        entry_tp_is_structural = tp_ob is not None
        entry_tp_ob_bar = tp_ob.get("ob_bar") if tp_ob else None
        entry_tp_ob_quality = tp_ob.get("quality") if tp_ob else None

        df.at[i, "Trade_Status"] = "OPEN LONG"
        df.at[i, "Entry_Price"] = entry_price
        df.at[i, "Stop_Loss"] = stop_loss_price
        df.at[i, "Take_Profit"] = take_profit_price

        return ("LONG", entry_price, stop_loss_price, take_profit_price, entry_atr, 0.0, entry_idx,
                kdj_state, current_entry_ob, tp_ob, entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality)

    return (None, 0.0, 0.0, 0.0, 0.0, 0.0, 0, None, None, None, False, None, None)


def _try_enter_short(df, i, close, low, high, macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                      kdj_k, kdj_d, kdj_j, kdj_k_acceleration, atr_regime_ratio, atr_14,
                      supply_obs, valid_obs_tp):
    """
    Evaluate the SHORT entry gate against every currently-active SUPPLY
    Order Block, in order, entering on the first one that passes every
    filter. Mirror image of _try_enter_long() -- reproduced unchanged from
    simulate_trades()'s SHORT branch (src/Binance backtest bot.py lines
    ~814-881). Additional SHORT-only filters: K must be overbought (>= 70
    floor) and J must not already be in exhaustion territory (<= 100 cap).

    Returns
    -------
    tuple
        Same 13-element shape as _try_enter_long(); position is 'SHORT' or
        None.
    """
    for ob in supply_obs:
        if not (high >= ob["bottom"] and close <= ob["top"]):
            continue
        if not (macd_hist_current > 0 and macd_hist_current < macd_hist_prev_bar):
            continue
        # hist must have been falling for >= 2 bars.
        if not (macd_hist_prev_bar < macd_hist_two_bars_ago):
            continue
        if not (kdj_k > 50 and kdj_j > kdj_k > kdj_d):
            continue
        if not (1 <= kdj_k_acceleration <= 6):
            continue
        if 0.8 <= atr_regime_ratio <= 1.0:
            continue
        # SHORT K floor: must be genuinely overbought to enter a SHORT.
        if kdj_k < KDJ_K_SHORT_FLOOR:
            continue
        # SHORT J cap: J > 100 means the overbought move is already in
        # extreme exhaustion territory.
        if kdj_j > KDJ_J_SHORT_CAP:
            continue

        stop_loss_candidate = ob["top"] + atr_14 * 0.5
        risk = stop_loss_candidate - close
        if risk <= 0:
            continue
        if risk / close < MIN_STOP_LOSS_DISTANCE_RATIO:
            continue

        structural_tp_price = get_structural_tp(close, "SHORT", valid_obs_tp)
        take_profit_price = structural_tp_price if structural_tp_price else close - risk * 2.0
        if (close - take_profit_price) / risk < MIN_RISK_REWARD_RATIO:
            continue

        entry_price = close
        stop_loss_price = stop_loss_candidate
        entry_atr = atr_14
        entry_idx = i
        kdj_state = kdj_reset_init(df, i, ob_bar=ob.get("ob_bar", None))

        current_entry_ob = ob
        tp_ob = _resolve_structural_tp_ob(valid_obs_tp, structural_tp_price, "DEMAND", "top")
        entry_tp_is_structural = tp_ob is not None
        entry_tp_ob_bar = tp_ob.get("ob_bar") if tp_ob else None
        entry_tp_ob_quality = tp_ob.get("quality") if tp_ob else None

        df.at[i, "Trade_Status"] = "OPEN SHORT"
        df.at[i, "Entry_Price"] = entry_price
        df.at[i, "Stop_Loss"] = stop_loss_price
        df.at[i, "Take_Profit"] = take_profit_price

        return ("SHORT", entry_price, stop_loss_price, take_profit_price, entry_atr, 0.0, entry_idx,
                kdj_state, current_entry_ob, tp_ob, entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality)

    return (None, 0.0, 0.0, 0.0, 0.0, 0.0, 0, None, None, None, False, None, None)


def _check_long_exit_conditions(df, i, close, entry_price, stop_loss_price, take_profit_price, entry_atr,
                                 peak_pnl_pct, pnl_pct, entry_idx, kdj_state):
    """
    Evaluate every LONG exit rule for the current bar, in priority order:
    trailing 50%-retrace exit, KDJ-reset exit (only once >= 3 bars held),
    ATR-multiple move exit, breakeven-stop ratchet, then hard SL/TP.
    Reproduced unchanged from simulate_trades()'s LONG running-position
    branch (src/Binance backtest bot.py lines ~933-962).

    Statistical/analytical question answered: none -- exit rule logic.

    IMPORTANT ordering detail preserved from the original: kdj_state is
    updated with THIS bar's price action (kdj_reset_update()) before the
    KDJ-reset exit is evaluated against it -- but only if the trailing exit
    did not already fire this bar. Reordering this would change which bar's
    data the KDJ exit signal is allowed to react to.

    Returns
    -------
    tuple
        (exit_reason, exit_pnl_pct, updated_stop_loss_price,
        updated_kdj_state). exit_reason is None if the position remains
        open.
    """
    if peak_pnl_pct >= 1.5:
        trailing_floor = entry_price * (1 + peak_pnl_pct * 0.5 / 100)
        if close <= trailing_floor:
            df.at[i, "Exit_Price"] = close
            return "TRAILING EXIT (50% RETRACE)", pnl_pct, stop_loss_price, kdj_state

    kdj_state = kdj_reset_update(kdj_state, df, i, "LONG")

    # KDJ reset only allowed after bar 3 in trade -- single-bar KDJ
    # fluctuations in bars 1-2 should not exit the trade (see the v9
    # changelog note at the top of Section 3).
    if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, "LONG"):
        df.at[i, "Exit_Price"] = close
        return "KDJ RESET EXIT", pnl_pct, stop_loss_price, kdj_state

    if entry_atr > 0 and close >= entry_price + entry_atr * ATR_MULT_EXIT:
        df.at[i, "Exit_Price"] = close
        return "ATR MOVE EXIT", pnl_pct, stop_loss_price, kdj_state

    if close >= entry_price + entry_atr * ATR_MULT_BREAKEVEN:
        stop_loss_price = max(stop_loss_price, entry_price)
        df.at[i, "Stop_Loss"] = stop_loss_price

    if close <= stop_loss_price:
        df.at[i, "Exit_Price"] = close
        return "HIT STOP LOSS", (close - entry_price) / entry_price * 100, stop_loss_price, kdj_state
    elif close >= take_profit_price:
        df.at[i, "Exit_Price"] = close
        return "HIT TAKE PROFIT", (close - entry_price) / entry_price * 100, stop_loss_price, kdj_state

    return None, None, stop_loss_price, kdj_state


def _check_short_exit_conditions(df, i, close, entry_price, stop_loss_price, take_profit_price, entry_atr,
                                  peak_pnl_pct, pnl_pct, entry_idx, kdj_state):
    """
    Mirror image of _check_long_exit_conditions() for SHORT positions.
    Reproduced unchanged from simulate_trades()'s SHORT running-position
    branch (src/Binance backtest bot.py lines ~1014-1041). See that
    function's docstring for the kdj_state update-ordering detail this
    preserves.

    Returns
    -------
    tuple
        (exit_reason, exit_pnl_pct, updated_stop_loss_price,
        updated_kdj_state).
    """
    if peak_pnl_pct >= 1.5:
        trailing_floor = entry_price * (1 - peak_pnl_pct * 0.5 / 100)
        if close >= trailing_floor:
            df.at[i, "Exit_Price"] = close
            return "TRAILING EXIT (50% RETRACE)", pnl_pct, stop_loss_price, kdj_state

    kdj_state = kdj_reset_update(kdj_state, df, i, "SHORT")

    if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, "SHORT"):
        df.at[i, "Exit_Price"] = close
        return "KDJ RESET EXIT", pnl_pct, stop_loss_price, kdj_state

    if entry_atr > 0 and close <= entry_price - entry_atr * ATR_MULT_EXIT:
        df.at[i, "Exit_Price"] = close
        return "ATR MOVE EXIT", pnl_pct, stop_loss_price, kdj_state

    if close <= entry_price - entry_atr * ATR_MULT_BREAKEVEN:
        stop_loss_price = min(stop_loss_price, entry_price)
        df.at[i, "Stop_Loss"] = stop_loss_price

    if close >= stop_loss_price:
        df.at[i, "Exit_Price"] = close
        return "HIT STOP LOSS", (entry_price - close) / entry_price * 100, stop_loss_price, kdj_state
    elif close <= take_profit_price:
        df.at[i, "Exit_Price"] = close
        return "HIT TAKE PROFIT", (entry_price - close) / entry_price * 100, stop_loss_price, kdj_state

    return None, None, stop_loss_price, kdj_state


def _record_closed_trade(closed_trades, df, i, side, entry_idx, entry_price, exit_price, stop_loss_price,
                          take_profit_price, pnl_pct, exit_reason, current_entry_ob, current_tp_ob,
                          entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality, kdj_exit_window):
    """
    Append one closed-trade record (27 fields, identical schema for LONG and
    SHORT) to `closed_trades`, and mark the closing bar's Trade_Status.
    Reproduced unchanged from the nested close_trade() closures inside
    simulate_trades()'s LONG and SHORT branches, plus one addition:
    `kdj_exit_window` records the frozen-at-entry KDJ-reset period (`w` in
    CLAUDE.md's "KDJ architecture" section, `entry_idx - triggering_OB_bar`
    when an OB triggered the trade) so it's visible per-trade downstream
    instead of only recomputable from entry_idx/entry_ob_bar by hand.

    Statistical/analytical question answered: none -- output-record
    construction. This is the exact per-trade schema every downstream
    analysis in Section 5 (and every analysis/*.py script) reads from.
    """
    df.at[i, "Trade_Status"] = exit_reason
    df.at[i, "Running_PnL_%"] = pnl_pct
    closed_trades.append({
        "side": side, "entry_idx": entry_idx, "exit_idx": i, "entry": entry_price, "exit": exit_price,
        "stop_loss": stop_loss_price, "take_profit": take_profit_price, "pnl_pct": pnl_pct,
        "entry_ob_bar": (current_entry_ob.get("ob_bar") if current_entry_ob else None),
        "entry_ob_quality": (current_entry_ob.get("quality") if current_entry_ob else None),
        "entry_ob_quality_displacement": (bool(current_entry_ob.get("quality_displacement")) if current_entry_ob else False),
        "entry_ob_quality_large_bar": (bool(current_entry_ob.get("quality_large_bar")) if current_entry_ob else False),
        "entry_ob_quality_fvg": (bool(current_entry_ob.get("quality_fvg")) if current_entry_ob else False),
        "entry_ob_quality_liquidity_sweep": (bool(current_entry_ob.get("quality_liquidity_sweep")) if current_entry_ob else False),
        "entry_ob_quality_volume_expansion": (bool(current_entry_ob.get("quality_volume_expansion")) if current_entry_ob else False),
        "entry_ob_created_at": (current_entry_ob.get("created_at") if current_entry_ob else None),
        "entry_ob_level": (current_entry_ob.get("level") if current_entry_ob else None),
        "entry_ob_type": (current_entry_ob.get("type") if current_entry_ob else None),
        "tp_is_structural": entry_tp_is_structural,
        "tp_ob_bar": entry_tp_ob_bar,
        "tp_ob_quality": entry_tp_ob_quality,
        "tp_ob_created_at": (current_tp_ob.get("created_at") if (entry_tp_is_structural and current_tp_ob) else None),
        "tp_ob_level": (current_tp_ob.get("level") if (entry_tp_is_structural and current_tp_ob) else None),
        "tp_ob_type": (current_tp_ob.get("type") if (entry_tp_is_structural and current_tp_ob) else None),
        "hold_bars": i - entry_idx,
        "exit_reason": exit_reason,
        "kdj_exit_window": kdj_exit_window,
    })


def simulate_trades(df, min_ob_quality=None, iteration_parameters=None):
    """
    Run the full bar-by-bar backtest: compute indicators and Order Blocks if
    not already present, then apply entry gating (Order Block price touch +
    MACD/KDJ/ATR filters) and exit gating (trailing stop, KDJ-reset exit,
    ATR-multiple move exit, breakeven ratchet, hard SL/TP) for both LONG and
    SHORT positions.

    Statistical/analytical question answered: this IS the strategy under
    test -- every headline figure in the paper (win rate, total return,
    trade count) is read from this function's output. It answers: "what
    trades would this fixed rule set have taken, and what would each have
    returned?"

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data. compute_indicators() is called automatically if MACD
        columns are not already present.
    min_ob_quality : int or None
        Minimum composite quality score (0-5) an Order Block must have to
        gate an entry. None defaults to DEFAULT_MIN_OB_QUALITY (1). The
        paper's locked 27-trade baseline uses min_ob_quality=0 (no
        filtering) -- see run_quality_sweep() and CLAUDE.md's "Locked
        results".
    iteration_parameters : dict or None
        Optional override dict; currently only supports overriding
        'min_ob_quality'. Exists for run_quality_sweep()'s threshold loop.

    Returns
    -------
    pandas.DataFrame
        The input `df` annotated with per-bar Trade_Status/Entry_Price/etc.
        columns, plus three items attached via df.attrs: 'trade_stats' (a
        summary dict), 'trades_df' (one row per closed trade, 27 fields),
        and 'touches_df' (one row per bar an active Order Block's price zone
        was touched, regardless of whether it triggered an entry).
    """
    if iteration_parameters is None:
        iteration_parameters = {}

    if "MACD" not in df.columns:
        df = compute_indicators(df)

    # Order Block detection is deterministic given (length, last close), so
    # it is cached across repeated calls on the same effective dataset --
    # this matters for run_quality_sweep(), which calls simulate_trades()
    # once per quality threshold on the same underlying candles.
    global _smc_detection_cache
    cache_key = (len(df), float(df["close"].iloc[-1]) if not df.empty else 0.0)
    if cache_key in _smc_detection_cache:
        order_blocks = _smc_detection_cache[cache_key]
    else:
        order_blocks = compute_smc(df)
        _smc_detection_cache[cache_key] = order_blocks

    for column_name in ["Trade_Status", "Active_Supply", "Active_Demand"]:
        df[column_name] = ""
    for column_name in ["Entry_Price", "Stop_Loss", "Take_Profit", "Exit_Price", "Running_PnL_%"]:
        df[column_name] = np.nan

    position = None
    entry_price = 0.0
    stop_loss_price = 0.0
    take_profit_price = 0.0
    entry_atr = 0.0
    peak_pnl_pct = 0.0
    entry_idx = 0
    kdj_state = None
    closed_trades = []
    ob_touch_events = []
    current_entry_ob = None
    current_tp_ob = None
    entry_tp_is_structural = False
    entry_tp_ob_bar = None
    entry_tp_ob_quality = None

    start_bar = SWING_STRUCTURE_LOOKBACK_BARS + 5

    for i in range(start_bar, len(df)):
        close = float(df.at[i, "close"])
        high = float(df.at[i, "high"])
        low = float(df.at[i, "low"])
        macd_hist_current = float(df.at[i, "MACD_hist"])
        macd_hist_prev_bar = float(df.at[i - 1, "MACD_hist"])
        macd_hist_two_bars_ago = float(df.at[i - 2, "MACD_hist"])
        kdj_k = float(df.at[i, "K"])
        kdj_d = float(df.at[i, "D"])
        kdj_j = float(df.at[i, "J"])
        kdj_k_prev_bar = float(df.at[i - 1, "K"])
        kdj_k_two_bars_ago = float(df.at[i - 2, "K"])
        atr_14 = float(df.at[i, "ATR"])
        atr_200 = float(df.at[i, "ATR_200"])
        # K acceleration: second difference of K over the last 3 bars. Used
        # as an entry filter window [1, 6] -- a single-bar K spike (> 6)
        # tends to reset immediately (treated as noise), while <= 0 means K
        # is not yet accelerating in the trade's favor.
        kdj_k_acceleration = (kdj_k - kdj_k_prev_bar) - (kdj_k_prev_bar - kdj_k_two_bars_ago)
        # Volatility-regime ratio: current ATR(14) vs. the longer-horizon
        # ATR(200) baseline. Values in [0.8, 1.0] ("dead zone") are filtered
        # out of entries -- see the v7 FILTER 3 comments below.
        atr_regime_ratio = atr_14 / atr_200 if atr_200 > 0 else 1.0

        effective_min_ob_quality = iteration_parameters.get(
            "min_ob_quality", DEFAULT_MIN_OB_QUALITY if min_ob_quality is None else int(min_ob_quality)
        )

        active_order_blocks_for_entry = [
            ob for ob in order_blocks
            if ob["created_at"] < i < ob["mitigated_at"]
            and i - ob["created_at"] <= MAX_ORDER_BLOCK_AGE_BARS
            and ob.get("quality", 0) >= effective_min_ob_quality
        ]
        active_order_blocks_for_tp = [
            ob for ob in order_blocks
            if ob["created_at"] < i < ob["mitigated_at"]
            and i - ob["created_at"] <= MAX_ORDER_BLOCK_AGE_BARS
        ]
        demand_obs = [ob for ob in active_order_blocks_for_entry if ob["type"] == "DEMAND"]
        supply_obs = [ob for ob in active_order_blocks_for_entry if ob["type"] == "SUPPLY"]

        # --- Capture OB touch events (diagnostic log, not used for entries) ---
        active_order_blocks_for_touch = [
            ob for ob in order_blocks
            if ob["created_at"] < i < ob["mitigated_at"]
            and i - ob["created_at"] <= MAX_ORDER_BLOCK_AGE_BARS
        ]
        for ob in active_order_blocks_for_touch:
            if max(low, ob["bottom"]) <= min(high, ob["top"]):
                bar_time = df.at[i, "time"] if "time" in df.columns else int(pd.to_datetime(df.at[i, "open_time"]).timestamp())
                ob_touch_events.append({
                    "ob_created_at": ob["created_at"], "ob_bar": ob["ob_bar"], "ob_type": ob["type"],
                    "ob_level": ob["level"], "ob_structure": ob["structure"], "ob_top": ob["top"],
                    "ob_bottom": ob["bottom"], "time": int(bar_time), "touch_price": close,
                    "macd": float(df.at[i, "MACD"]), "macd_signal": float(df.at[i, "MACD_signal"]),
                    "macd_hist": macd_hist_current, "k": kdj_k, "d": kdj_d, "j": kdj_j,
                    "k_accel": kdj_k_acceleration, "atr_14": atr_14, "atr_200": atr_200,
                })

        def nearest_zone(zones):
            if not zones:
                return None
            return min(zones, key=lambda ob: abs((ob["top"] + ob["bottom"]) / 2 - close))

        nearest_supply_ob = nearest_zone(supply_obs)
        nearest_demand_ob = nearest_zone(demand_obs)

        def format_ob_info(ob):
            if not ob:
                return ""
            bar_idx = ob.get("ob_bar", None)
            time_str = ""
            try:
                if bar_idx is not None and 0 <= bar_idx < len(df):
                    time_str = pd.to_datetime(df.at[int(bar_idx), "open_time"]).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                time_str = ""
            return f"{ob['bottom']:.4f} - {ob['top']:.4f} | bar {bar_idx} | {time_str}"

        if nearest_supply_ob:
            df.at[i, "Active_Supply"] = format_ob_info(nearest_supply_ob)
        if nearest_demand_ob:
            df.at[i, "Active_Demand"] = format_ob_info(nearest_demand_ob)

        if position is None:
            position, entry_price, stop_loss_price, take_profit_price, entry_atr, peak_pnl_pct, \
                entry_idx, kdj_state, current_entry_ob, current_tp_ob, entry_tp_is_structural, \
                entry_tp_ob_bar, entry_tp_ob_quality = _try_enter_long(
                    df, i, close, low, high, macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                    kdj_k, kdj_k_prev_bar, kdj_j, kdj_k_acceleration, atr_regime_ratio, atr_14,
                    demand_obs, active_order_blocks_for_tp,
                )
            if position is None:
                position, entry_price, stop_loss_price, take_profit_price, entry_atr, peak_pnl_pct, \
                    entry_idx, kdj_state, current_entry_ob, current_tp_ob, entry_tp_is_structural, \
                    entry_tp_ob_bar, entry_tp_ob_quality = _try_enter_short(
                        df, i, close, low, high, macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                        kdj_k, kdj_d, kdj_j, kdj_k_acceleration, atr_regime_ratio, atr_14,
                        supply_obs, active_order_blocks_for_tp,
                    )

        elif position == "LONG":
            pnl_pct = (close - entry_price) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)
            df.at[i, "Trade_Status"] = "RUNNING LONG"
            df.at[i, "Running_PnL_%"] = pnl_pct
            df.at[i, "Entry_Price"] = entry_price
            df.at[i, "Stop_Loss"] = stop_loss_price
            df.at[i, "Take_Profit"] = take_profit_price

            exit_reason, exit_pnl_pct, stop_loss_price, kdj_state = _check_long_exit_conditions(
                df, i, close, entry_price, stop_loss_price, take_profit_price, entry_atr,
                peak_pnl_pct, pnl_pct, entry_idx, kdj_state,
            )
            if exit_reason is not None:
                _record_closed_trade(
                    closed_trades, df, i, "LONG", entry_idx, entry_price, close, stop_loss_price,
                    take_profit_price, exit_pnl_pct, exit_reason, current_entry_ob, current_tp_ob,
                    entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality, kdj_state["period"],
                )
                position = None
                current_entry_ob = None
                current_tp_ob = None
                entry_tp_is_structural = False
                entry_tp_ob_bar = None
                entry_tp_ob_quality = None

        elif position == "SHORT":
            pnl_pct = (entry_price - close) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)
            df.at[i, "Trade_Status"] = "RUNNING SHORT"
            df.at[i, "Running_PnL_%"] = pnl_pct
            df.at[i, "Entry_Price"] = entry_price
            df.at[i, "Stop_Loss"] = stop_loss_price
            df.at[i, "Take_Profit"] = take_profit_price

            exit_reason, exit_pnl_pct, stop_loss_price, kdj_state = _check_short_exit_conditions(
                df, i, close, entry_price, stop_loss_price, take_profit_price, entry_atr,
                peak_pnl_pct, pnl_pct, entry_idx, kdj_state,
            )
            if exit_reason is not None:
                _record_closed_trade(
                    closed_trades, df, i, "SHORT", entry_idx, entry_price, close, stop_loss_price,
                    take_profit_price, exit_pnl_pct, exit_reason, current_entry_ob, current_tp_ob,
                    entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality, kdj_state["period"],
                )
                position = None
                current_entry_ob = None
                current_tp_ob = None
                entry_tp_is_structural = False
                entry_tp_ob_bar = None
                entry_tp_ob_quality = None

    trades_df = pd.DataFrame(closed_trades)
    if not trades_df.empty:
        total_trades = len(trades_df)
        total_return_pct = trades_df["pnl_pct"].sum()
        avg_return_pct = trades_df["pnl_pct"].mean()
        win_count = (trades_df["pnl_pct"] > 0).sum()
        trade_stats = {
            "Total Trades": total_trades,
            "Total Net Return (%)": total_return_pct,
            "Avg Return/Trade (%)": avg_return_pct,
            "Win Rate (%)": win_count / total_trades * 100,
        }
    else:
        trade_stats = {"Total Trades": 0, "Total Net Return (%)": 0.0,
                        "Avg Return/Trade (%)": 0.0, "Win Rate (%)": 0.0}

    df.attrs["trade_stats"] = trade_stats
    df.attrs["trades_df"] = trades_df
    df.attrs["touches_df"] = pd.DataFrame(ob_touch_events)
    return df


def run_quality_sweep(df, levels=(0, 1, 2, 3)):
    """
    Run simulate_trades() once per Order Block minimum-quality threshold and
    collect headline stats for each, for side-by-side comparison.

    Statistical/analytical question answered: "how sensitive is the
    strategy's performance to the OB quality gate?" -- not itself a formal
    test, but the trade pools it produces feed the q>=0 vs q>=1 comparison
    discussed in CLAUDE.md's locked results (the q>=1 significance-
    conclusion flip from the no-lookahead fix).

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data (compute_indicators() applied automatically inside
        simulate_trades() if needed).
    levels : iterable of int, default (0, 1, 2, 3)
        Minimum quality thresholds to sweep.

    Returns
    -------
    pandas.DataFrame
        One row per threshold: min_quality, Total Trades, Total Net Return
        (%), Avg Return/Trade (%), Win Rate (%).
    """
    sweep_rows = []
    for quality_threshold in levels:
        result_df = simulate_trades(df.copy(), min_ob_quality=quality_threshold)
        stats = result_df.attrs.get("trade_stats", {})
        sweep_rows.append({
            "min_quality": quality_threshold,
            "Total Trades": stats.get("Total Trades", 0),
            "Total Net Return (%)": stats.get("Total Net Return (%)", 0.0),
            "Avg Return/Trade (%)": stats.get("Avg Return/Trade (%)", 0.0),
            "Win Rate (%)": stats.get("Win Rate (%)", 0.0),
        })
    return pd.DataFrame(sweep_rows)


# ============================================================================
# SECTION 3B: LIVE DATA PULL + GOOGLE SHEETS EXPORT PLUMBING
# ============================================================================
# Consolidated from src/Binance backtest bot.py (now retired to
# legacy_pre_consolidation/, renamed "Binance backtest bot (legacy).py").
# Pure IO/formatting plumbing -- none of it computes strategy math, so it is
# outside CLAUDE.md's "no strategy logic changes" protection and was safe to
# relocate. Two deliberate, disclosed adjustments were made purely because
# this code now lives at the repo root instead of src/ (one directory level
# shallower) and because research_analysis.py promises to never touch the
# network on a bare import:
#   1. BASE_DIR's dirname() nesting was reduced by one level to match this
#      file's new location (SERVICE KEY/ still resolves to the same
#      repo-root folder as before).
#   2. The Binance Client() is now constructed lazily on first use
#      (_get_binance_client()) instead of at import time, so importing this
#      file never makes a network call even without API keys configured --
#      the original module-level `client = Client(...)` could raise before
#      any function was even called.
# Every formula/threshold inside get_candles()'s UTC+8 shift and the GSheet
# formatting functions is reproduced unchanged.

# Repo root -- this file lives at the repo root directly (unlike the retired
# src/Binance backtest bot.py, which needed one extra dirname() hop).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Keep real Binance keys in environment variables.
BINANCE_API_KEY_ENV = "BINANCE_API_KEY"
BINANCE_API_SECRET_ENV = "BINANCE_API_SECRET"

# Use environment variables in production; placeholder below is safe for upload.
GOOGLE_SERVICE_KEY_PATH = os.getenv(
    "GOOGLE_SERVICE_KEY_PATH",
    os.path.join(BASE_DIR, "SERVICE KEY", "your-service-account-key.json"),
)
GOOGLE_SHEET_ID = "1UXw_eTEVjV7lfwmVpLq9z2BWC8WShUFclD3xVkT4MdA"

_binance_client = None


def resolve_google_service_key_path():
    """
    Auto-discover a Google service-account JSON key under `SERVICE KEY/`.

    Statistical question answered: none -- IO plumbing for the (optional)
    Google Sheets export path.

    Prefers GOOGLE_SERVICE_KEY_PATH if it's set to a real (non-placeholder)
    file that exists; otherwise picks the most-recently-modified `*.json`
    key file under `SERVICE KEY/` whose filename doesn't contain "disabled"
    or "not working" -- this repo's convention for marking a dead key
    in-place rather than deleting it. "Newest file wins" matches how this
    repo rotates credentials (drop a new key in, no need to touch code).
    """
    configured = GOOGLE_SERVICE_KEY_PATH
    placeholder = configured.endswith("your-service-account-key.json")
    if not placeholder and os.path.isfile(configured):
        return configured

    candidates = [
        c for c in glob.glob(os.path.join(BASE_DIR, "SERVICE KEY", "*.json"))
        if "disabled" not in os.path.basename(c).lower()
        and "not working" not in os.path.basename(c).lower()
    ]
    if candidates:
        return max(candidates, key=os.path.getmtime)
    return configured


def _get_binance_client():
    """Lazily construct (and cache) the python-binance REST client, so that
    importing this module never touches the network -- only calling
    get_candles() or run_forward_oos_validation() etc. does."""
    global _binance_client
    if _binance_client is None:
        api_key = os.getenv(BINANCE_API_KEY_ENV)
        api_secret = os.getenv(BINANCE_API_SECRET_ENV)
        _binance_client = Client(api_key, api_secret)
    return _binance_client


def get_candles(symbol="BTCUSDT", interval=Client.KLINE_INTERVAL_4HOUR,
                 start_time=None, end_time=None):
    """
    Pull paginated OHLCV klines from the Binance REST API into a DataFrame.

    Statistical question answered: none -- raw data acquisition. This is
    the ONE function (besides the forward-OOS/backfill-audit live-pull
    functions in Section 5B) that touches the network; every other analysis
    in this file runs offline against artifacts/candles.csv.

    Parameters
    ----------
    symbol : str
    interval : str
        A `Client.KLINE_INTERVAL_*` constant.
    start_time, end_time : str or pandas.Timestamp, optional

    Returns
    -------
    pandas.DataFrame
        Columns: open_time (UTC+8-shifted, matching this project's
        historical candle-cache convention), open, high, low, close,
        volume, num_trades, taker_buy_base.
    """
    client = _get_binance_client()
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time)
    if isinstance(end_time, str):
        end_time = pd.to_datetime(end_time)

    start_ms = int(start_time.timestamp() * 1000) if start_time else 0
    end_ms = int(end_time.timestamp() * 1000) if end_time else None

    candles = []
    while True:
        batch = client.get_klines(
            symbol=symbol, interval=interval,
            startTime=start_ms, endTime=end_ms, limit=1000)
        if not batch:
            break
        candles.extend(batch)
        last_time = batch[-1][0]
        if end_ms and last_time >= end_ms:
            break
        start_ms = last_time + 1

    df = pd.DataFrame(candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"])
    df = df[["open_time", "open", "high", "low", "close", "volume",
             "num_trades", "taker_buy_base"]].copy()
    df["open_time"] = (pd.to_datetime(df["open_time"], unit="ms")
                        + pd.Timedelta(hours=8))
    for col in ["open", "high", "low", "close", "volume", "num_trades", "taker_buy_base"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)


# --- Google Sheets export: generic per-sheet helpers -----------------------

def _get_or_create_sheet(workbook, title, rows=50000, cols=30):
    try:
        ws = workbook.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = workbook.add_worksheet(title=title, rows=rows, cols=cols)
    ws.resize(rows=rows, cols=cols)
    return ws


def _format_df_for_export(df):
    """Curated-column formatting for the (legacy, no-longer-default)
    per-quality-threshold sheet export -- see push_all_thresholds_to_gsheet()."""
    columns_to_export = [
        "open_time", "open", "high", "low", "close",
        "MACD", "MACD_signal", "MACD_hist",
        "K", "D", "J",
        "ATR", "ATR_200",
        "Active_Supply", "Active_Demand",
        "Entry_Price", "Stop_Loss", "Take_Profit", "Exit_Price",
        "Trade_Status", "Running_PnL_%",
    ]
    df_copy = df[columns_to_export].copy()
    df_copy.rename(columns={
        "open_time": "Date/Time",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "ATR": "ATR (14)",
        "ATR_200": "ATR (200)",
        "Active_Supply": "Supply Zone",
        "Active_Demand": "Demand Zone",
        "Entry_Price": "Entry Price",
        "Stop_Loss": "Stop Loss",
        "Take_Profit": "Take Profit",
        "Exit_Price": "Exit Price",
        "Trade_Status": "Trade Status",
        "Running_PnL_%": "Running PnL %",
    }, inplace=True)

    df_copy["Date/Time"] = (pd.to_datetime(df_copy["Date/Time"], errors="coerce")
                             .dt.strftime("%Y-%m-%d %H:%M:%S"))
    for col in ["Entry Price", "Stop Loss", "Take Profit", "Exit Price"]:
        df_copy[col] = df_copy[col].apply(
            lambda x: f"{x:.4f}" if pd.notnull(x) else "")
    for col in ["ATR (14)", "ATR (200)"]:
        df_copy[col] = df_copy[col].apply(
            lambda x: f"{x:.4f}" if pd.notnull(x) else "")
    df_copy["Running PnL %"] = df_copy["Running PnL %"].apply(
        lambda x: f"{x:.4f}%" if pd.notnull(x) and isinstance(x, (float, int)) else "")
    df_copy = df_copy.astype(object).where(pd.notnull(df_copy), "")
    return df_copy


def _format_df_for_export_full(df):
    """Exports EVERY column present on the fully-simulated dataframe -- not
    the curated subset _format_df_for_export() selects. Column set is read
    from df.columns directly (not hardcoded), so nothing is silently
    dropped if compute_indicators()/simulate_trades() ever add a column.
    Used for the Candles gsheet tabs, where "as detailed as possible, don't
    hide any data" is the explicit requirement."""
    df_copy = df.copy()
    for col in df_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%d %H:%M:%S")
        elif pd.api.types.is_float_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].round(6)
    if "Running_PnL_%" in df_copy.columns:
        df_copy["Running_PnL_%"] = df_copy["Running_PnL_%"].apply(
            lambda x: f"{x:.4f}%" if pd.notnull(x) and isinstance(x, (float, int)) else "")
    df_copy = df_copy.rename(columns={"Trade_Status": "Trade Status", "Running_PnL_%": "Running PnL %"})
    df_copy = df_copy.astype(object).where(pd.notnull(df_copy), "")
    return df_copy


def _write_sheet(ws, df_copy):
    ws.clear()
    ws.update([df_copy.columns.values.tolist()] + df_copy.values.tolist())


def _apply_pnl_formatting(ws, df_copy):
    closed_kw = [
        "HIT STOP LOSS", "HIT TAKE PROFIT",
        "TRAILING EXIT (50% RETRACE)", "KDJ RESET EXIT", "ATR MOVE EXIT",
    ]
    pnl_col = df_copy.columns.get_loc("Running PnL %") + 1

    ranges = []
    for idx, (pnl, status) in enumerate(
            zip(df_copy["Running PnL %"], df_copy["Trade Status"]), start=2):
        if status in closed_kw and pnl not in ("", "nan%"):
            try:
                val = float(pnl.strip("%"))
                color = Color(0, 1, 0) if val > 0 else Color(1, 0, 0)
                ranges.append((f"{chr(64 + pnl_col)}{idx}",
                               CellFormat(backgroundColor=color)))
            except ValueError:
                pass
    if ranges:
        format_cell_ranges(ws, ranges)

    closed_pnls = []
    for pnl, status in zip(df_copy["Running PnL %"], df_copy["Trade Status"]):
        if status in closed_kw and pnl not in ("", "nan%"):
            try:
                closed_pnls.append(float(pnl.strip("%")))
            except ValueError:
                pass

    if closed_pnls:
        total = len(closed_pnls)
        tot_pnl = sum(closed_pnls)
        avg_pnl = tot_pnl / total
        wins = len([p for p in closed_pnls if p > 0])
        wr = wins / total * 100 if total > 0 else 0
        nr = len(df_copy) + 2
        cl = chr(64 + pnl_col)
        ws.update(values=[
            [f"Total Trades: {total}"],
            [f"Total Net Return: {tot_pnl:.4f}%"],
            [f"Avg Return/Trade: {avg_pnl:.4f}%"],
            [f"Win Rate: {wr:.4f}%"],
        ], range_name=f"{cl}{nr}:{cl}{nr + 3}")
        sc = Color(0, 1, 0) if tot_pnl > 0 else Color(1, 0, 0)
        format_cell_ranges(ws, [
            (f"{cl}{nr}:{cl}{nr + 3}", CellFormat(backgroundColor=sc))
        ])


def _write_summary_sheet(workbook, sweep_results):
    needed_rows = len(sweep_results) + 5
    needed_cols = 7
    ws = _get_or_create_sheet(workbook, "Summary — Quality Sweep",
                               rows=needed_rows, cols=needed_cols)
    ws.clear()

    header = [
        "Min OB Quality",
        "Total Trades",
        "Total Net Return (%)",
        "Avg Return / Trade (%)",
        "Win Rate (%)",
    ]
    rows = [header]
    for r in sweep_results:
        rows.append([
            str(r["quality"]),
            str(r["total_trades"]),
            f"{r['total_return']:.4f}",
            f"{r['avg_return']:.4f}",
            f"{r['win_rate']:.4f}",
        ])

    ws.update(rows)

    format_cell_ranges(ws, [
        ("A1:E1", CellFormat(
            textFormat=TextFormat(bold=True),
            backgroundColor=Color(0.18, 0.46, 0.71),
        ))
    ])

    for i, r in enumerate(sweep_results, start=2):
        color = Color(0.88, 0.95, 0.83) if r["total_return"] >= 0 else Color(0.98, 0.88, 0.88)
        format_cell_ranges(ws, [(f"A{i}:E{i}", CellFormat(backgroundColor=color))])

    print(f"  Summary sheet written ({len(sweep_results)} rows).")


def _authorize_gsheet_workbook():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    key_path = resolve_google_service_key_path()
    if key_path.endswith("your-service-account-key.json") or not os.path.isfile(key_path):
        raise ValueError(
            "Set GOOGLE_SERVICE_KEY_PATH (env var) or place a valid *.json key file in "
            "SERVICE KEY/."
        )
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is missing.")

    creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
    gc = gspread.authorize(creds)
    return gc.open_by_key(GOOGLE_SHEET_ID)


def push_all_thresholds_to_gsheet(raw_df, levels=None, precomputed_dfs=None):
    """Legacy per-quality-threshold sheet export ("Quality 0".."Quality 3" +
    a sweep-summary sheet). Superseded by push_trades_and_results_to_gsheet()
    (see CLAUDE.md's "Google Sheets pipeline" section) -- kept defined for
    reference but NOT called by --serve's default push path. Do not re-wire
    it back in without asking; it was deliberately superseded, not
    deprecated by accident."""
    if levels is None:
        levels = [0, 1, 2, 3]

    workbook = _authorize_gsheet_workbook()
    sweep_results = []

    for q in levels:
        sheet_title = f"Quality {q}"
        if precomputed_dfs and q in precomputed_dfs:
            print(f"\n[{sheet_title}] Using precomputed simulation...")
            sim_df = precomputed_dfs[q]
        else:
            print(f"\n[{sheet_title}] Running simulation...")
            sim_df = simulate_trades(raw_df.copy(), min_ob_quality=q)

        stats = sim_df.attrs.get("trade_stats", {})

        print(f"  Trades: {stats.get('Total Trades', 0)}  |  "
              f"Return: {stats.get('Total Net Return (%)', 0):.4f}%  |  "
              f"Win Rate: {stats.get('Win Rate (%)', 0):.4f}%")

        df_copy = _format_df_for_export(sim_df)
        needed_rows = len(df_copy) + 10
        needed_cols = len(df_copy.columns) + 2
        ws = _get_or_create_sheet(workbook, sheet_title, rows=needed_rows, cols=needed_cols)

        print(f"  Writing {len(df_copy)} rows to '{sheet_title}'...")
        _write_sheet(ws, df_copy)
        _apply_pnl_formatting(ws, df_copy)
        print(f"  '{sheet_title}' done.")

        sweep_results.append({
            "quality": q,
            "total_trades": int(stats.get("Total Trades", 0)),
            "total_return": float(stats.get("Total Net Return (%)", 0.0)),
            "avg_return": float(stats.get("Avg Return/Trade (%)", 0.0)),
            "win_rate": float(stats.get("Win Rate (%)", 0.0)),
        })

    print("\n[Summary] Writing quality sweep comparison sheet...")
    _write_summary_sheet(workbook, sweep_results)
    print("\nCheck GSHEET: All threshold sheets exported successfully.")
    return sweep_results


# --- Google Sheets export: benchmark-vs-passive -----------------------------
_BENCHMARK_SHEET_HEADER = ["Arm", "Total Return %", "Final Capital $", "Sharpe", "Sortino", "Max Drawdown %",
                           "% Time In-Market", "Starting Capital", "Window Start", "Window End"]


def _benchmark_row_to_sheet_row(r, window):
    return [
        r["arm"], f"{r['total_return_pct']:.4f}", f"{r['final_capital']:.2f}", f"{r['sharpe']:.4f}",
        f"{r['sortino']:.4f}", f"{r['max_drawdown_pct']:.4f}",
        f"{r['time_in_market_pct']:.4f}", r["starting_capital"],
        window["window_start"], window["window_end"],
    ]


def _write_benchmark_sheet(workbook, title, window, blocks):
    """blocks: list of (label, rows) pairs, each rows a list of per-arm dicts
    matching run_benchmark_vs_passive()'s row shape (arm, total_return_pct,
    final_capital, sharpe, sortino, max_drawdown_pct, time_in_market_pct,
    starting_capital)."""
    all_rows = [[f"Window: {window['window_start']} .. {window['window_end']}"], []]
    header_row_idxs = []
    data_rows = []
    for label, rows in blocks:
        all_rows.append([label])
        all_rows.append(_BENCHMARK_SHEET_HEADER)
        header_row_idxs.append(len(all_rows))
        for r in rows:
            all_rows.append(_benchmark_row_to_sheet_row(r, window))
            data_rows.append((len(all_rows), r))
        all_rows.append([])

    needed_rows = len(all_rows) + 5
    needed_cols = len(_BENCHMARK_SHEET_HEADER) + 2
    ws = _get_or_create_sheet(workbook, title, rows=needed_rows, cols=needed_cols)
    ws.clear()
    ws.update(all_rows)

    header_end_col = gspread.utils.rowcol_to_a1(1, len(_BENCHMARK_SHEET_HEADER)).rstrip("0123456789")
    format_cell_ranges(ws, [
        (f"A{i}:{header_end_col}{i}", CellFormat(
            textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
            backgroundColor=Color(0.18, 0.46, 0.71),
        )) for i in header_row_idxs
    ])
    return_col = _BENCHMARK_SHEET_HEADER.index("Total Return %") + 1
    capital_col = _BENCHMARK_SHEET_HEADER.index("Final Capital $") + 1
    ranges = []
    for row_idx, r in data_rows:
        color = Color(0.85, 0.95, 0.85) if r["total_return_pct"] >= 0 else Color(0.98, 0.88, 0.88)
        ranges.append((gspread.utils.rowcol_to_a1(row_idx, return_col), CellFormat(backgroundColor=color)))
        ranges.append((gspread.utils.rowcol_to_a1(row_idx, capital_col), CellFormat(backgroundColor=color)))
    if ranges:
        format_cell_ranges(ws, ranges)

    print(f"  '{title}' done.")


def push_benchmark_vs_passive_to_gsheet(benchmark_result):
    """benchmark_result: the dict run_benchmark_vs_passive() returns
    (top-level keys: starting_capital, fee_model, main_window,
    formulation_period_window)."""
    workbook = _authorize_gsheet_workbook()

    main_w = benchmark_result["main_window"]
    _write_benchmark_sheet(
        workbook, "Benchmark 2022-2026", main_w,
        [
            ("GROSS (no fees/slippage -- matches the locked +30.31% headline convention)", main_w["gross"]),
            ("FEE-ADJUSTED (strategy: round-trip drag/trade; DCA/B&H: one-sided buy markup)",
             main_w["fee_adjusted"]),
        ],
    )

    form_w = benchmark_result["formulation_period_window"]
    _write_benchmark_sheet(
        workbook, "Benchmark 2018-2022 (Formulation)", form_w,
        [("GROSS -- formulation period, NOT out-of-sample, NOT the 2026 forward-OOS test", form_w["gross"])],
    )

    print("\nCheck GSHEET: benchmark-vs-passive sheets exported successfully.")


# --- Google Sheets export: trades + results ---------------------------------
# Current, wired-in default (see CLAUDE.md "Google Sheets pipeline"). Writes
# the full per-trade log + results summary to four tabs (Trades/Results x
# 2022-2026 and 2018-2022) and actively deletes the old per-quality-threshold
# sheets on every push.
_TRADE_SHEET_COLUMNS = [
    "side", "entry_idx", "entry_time", "exit_idx", "exit_time",
    "entry", "exit", "stop_loss", "take_profit", "pnl_pct", "hold_bars", "exit_reason", "kdj_exit_window",
    "entry_ob_bar", "entry_ob_created_at", "entry_ob_type", "entry_ob_level", "entry_ob_quality",
    "entry_ob_quality_displacement", "entry_ob_quality_large_bar", "entry_ob_quality_fvg",
    "entry_ob_quality_liquidity_sweep", "entry_ob_quality_volume_expansion",
    "entry_ob_displacement_max_body_move", "entry_ob_displacement_threshold",
    "entry_ob_large_bar_range", "entry_ob_large_bar_threshold",
    "entry_ob_fvg_max_gap",
    "entry_ob_liquidity_sweep_ob_extreme", "entry_ob_liquidity_sweep_prior_10bar_extreme",
    "entry_ob_volume", "entry_ob_volume_avg_20bar", "entry_ob_volume_ratio", "entry_ob_body_ratio",
    "tp_is_structural", "tp_ob_bar", "tp_ob_created_at", "tp_ob_type", "tp_ob_level", "tp_ob_quality",
]

_OLD_QUALITY_SWEEP_SHEET_TITLES = [
    "Quality 0", "Quality 1", "Quality 2", "Quality 3", "Quality 4",
    "Summary — Quality Sweep",
]


def _delete_worksheet_if_exists(workbook, title):
    try:
        ws = workbook.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return False
    workbook.del_worksheet(ws)
    return True


def _clean_old_quality_sweep_sheets(workbook):
    removed = [t for t in _OLD_QUALITY_SWEEP_SHEET_TITLES if _delete_worksheet_if_exists(workbook, t)]
    if removed:
        print(f"  Removed old per-quality-threshold sheet(s): {', '.join(removed)}")


def _write_trades_sheet(workbook, title, trades):
    header = _TRADE_SHEET_COLUMNS
    rows = [header]
    for r in trades:
        rows.append([r.get(c, "") if r.get(c) is not None else "" for c in header])

    needed_rows = len(rows) + 5
    needed_cols = len(header) + 2
    ws = _get_or_create_sheet(workbook, title, rows=needed_rows, cols=needed_cols)
    ws.clear()
    ws.update(rows)

    header_end = gspread.utils.rowcol_to_a1(1, len(header))
    format_cell_ranges(ws, [
        (f"A1:{header_end}", CellFormat(
            textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
            backgroundColor=Color(0.18, 0.46, 0.71),
        ))
    ])
    pnl_col = header.index("pnl_pct") + 1
    ranges = []
    for i, r in enumerate(trades, start=2):
        pnl = r.get("pnl_pct")
        if pnl is not None:
            color = Color(0.85, 0.95, 0.85) if pnl > 0 else Color(0.98, 0.88, 0.88)
            ranges.append((gspread.utils.rowcol_to_a1(i, pnl_col), CellFormat(backgroundColor=color)))
    if ranges:
        format_cell_ranges(ws, ranges)

    print(f"  '{title}' done ({len(trades)} trades).")


def _write_results_sheet(workbook, title, window, results):
    header_row_idx = 3
    rows = [[f"Window: {window['window_start']} .. {window['window_end']}"], [], ["Metric", "Value"]]
    for k, v in results.items():
        rows.append([k, v])

    needed_rows = len(rows) + 5
    ws = _get_or_create_sheet(workbook, title, rows=needed_rows, cols=4)
    ws.clear()
    ws.update(rows)

    format_cell_ranges(ws, [
        (f"A{header_row_idx}:B{header_row_idx}", CellFormat(
            textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
            backgroundColor=Color(0.18, 0.46, 0.71),
        ))
    ])
    metric_names = list(results.keys())
    if "Total Net Return (%)" in metric_names:
        row_idx = header_row_idx + 1 + metric_names.index("Total Net Return (%)")
        val = results["Total Net Return (%)"]
        color = Color(0.85, 0.95, 0.85) if val >= 0 else Color(0.98, 0.88, 0.88)
        format_cell_ranges(ws, [(f"A{row_idx}:B{row_idx}", CellFormat(backgroundColor=color))])
    print(f"  '{title}' done.")


def push_trades_and_results_to_gsheet(export_result):
    """export_result: the dict build_trades_and_results_table() (Section 5B)
    returns (top-level keys: main_window, formulation_period_window, each
    with label/window_start/window_end/trades/results)."""
    workbook = _authorize_gsheet_workbook()
    _clean_old_quality_sweep_sheets(workbook)

    main_w = export_result["main_window"]
    _write_trades_sheet(workbook, "Trades 2022-2026", main_w["trades"])
    _write_results_sheet(workbook, "Results 2022-2026", main_w, main_w["results"])

    form_w = export_result["formulation_period_window"]
    _write_trades_sheet(workbook, "Trades 2018-2022", form_w["trades"])
    _write_results_sheet(workbook, "Results 2018-2022", form_w, form_w["results"])

    print("\nCheck GSHEET: trades + results sheets exported successfully.")


# --- Google Sheets export: candles ------------------------------------------
def push_candles_to_gsheet(candles_result):
    """candles_result: dict with top-level keys main_window,
    formulation_period_window, each {label, rows} -- rows already shaped by
    _format_df_for_export_full()."""
    workbook = _authorize_gsheet_workbook()

    for key, title in [("main_window", "Candles 2022-2026"), ("formulation_period_window", "Candles 2018-2022")]:
        df_copy = pd.DataFrame(candles_result[key]["rows"])
        needed_rows = len(df_copy) + 10
        needed_cols = len(df_copy.columns) + 2
        ws = _get_or_create_sheet(workbook, title, rows=needed_rows, cols=needed_cols)
        print(f"  Writing {len(df_copy)} rows to '{title}'...")
        _write_sheet(ws, df_copy)
        _apply_pnl_formatting(ws, df_copy)
        print(f"  '{title}' done.")

    print("\nCheck GSHEET: candle-level sheets exported successfully.")


# ============================================================================
# SECTION 4: ABLATION STUDY (THREE-ARM DESIGN)
# ============================================================================
#
# Ported from analysis/ablation_reconstruction.py. Reproduces the two
# indicators-only ablation arms cited in CLAUDE.md's locked results (Arm 2 /
# flat-ATR stop: 140 trades, 60.00% win rate, -14.63% return; Arm 3 /
# swing-pivot stop: 138 trades, 55.07%, -25.50%).
#
# IMPORTANT, DISCLOSED LIMITATION (preserved verbatim from the source file):
# the script that originally produced those exact per-trade pools was never
# committed to this repository. This is a FRESH, best-faith reconstruction
# from the *documented* ablation design (docs/ablation_study_indicators_only.md,
# docs/ablation_unconfounding_analysis.md), not a byte-for-byte recovery of
# the original uncommitted script -- and it is NOT guaranteed to reproduce
# the locked figures. Any divergence is reported explicitly by
# run_ablation_study() below, never silently reconciled with CLAUDE.md's
# locked numbers. A prior attempt at this same reconstruction (see
# scratch/02_benchmark_and_risk.py's own docstring) already diverged by
# >10 win-rate points from the published figures -- so a DIVERGE verdict
# here is an expected, already-known reconstruction-fidelity gap, not a
# new finding.
#
# Entry conditions (both arms) are the identical MACD/KDJ/ATR/k_accel/
# ATR-regime conditions used by the OB-gated strategy's LONG/SHORT entry
# gates (Section 3's _try_enter_long/_try_enter_short), with the sole
# change that the "price touching a valid Order Block zone" requirement is
# removed -- Order Block detection is irrelevant to an indicators-only
# configuration by design. Two stop-loss anchoring schemes are tested:
#   Arm 2 ("flat_atr"):    SL = close -/+ 1.5 * ATR(14)
#   Arm 3 ("swing_pivot"): SL = (5-bar low/high, prior bars only) -/+ 0.5 * ATR(14)
# Both arms keep rr_min=1.5 / sl_ratio_min=0.015 identical to the OB-gated
# strategy, and use a fixed 2R take-profit (no structural/OB-anchored TP --
# using one would reintroduce an OB dependency into a configuration meant
# to ablate OB away entirely). Post-entry exit logic is copied from
# simulate_trades(), including kdj_reset_init(..., ob_bar=None) -> a fixed
# default_period=9 fallback, which the engine already exposes as an
# explicit no-OB case.

ABLATION_SWING_PIVOT_LOOKBACK_BARS = 5
ABLATION_START_BAR = SWING_STRUCTURE_LOOKBACK_BARS + 5  # matches simulate_trades()'s warm-up


def ablation_entry_long_ok(macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                            kdj_k, kdj_k_prev_bar, kdj_j, kdj_k_acceleration, atr_regime_ratio):
    """
    Indicators-only LONG entry gate for the ablation arms -- identical to
    Section 3's OB-gated LONG entry filters, minus the Order Block price
    touch requirement.

    Statistical/analytical question answered: none -- entry rule logic.

    Returns
    -------
    bool
    """
    if not (macd_hist_current < 0 and macd_hist_current > macd_hist_prev_bar):
        return False
    if not (macd_hist_prev_bar > macd_hist_two_bars_ago):
        return False
    if not (kdj_k < KDJ_K_LONG_CAP and kdj_k > kdj_k_prev_bar and kdj_j < KDJ_J_LONG_CAP):
        return False
    if not (1 <= kdj_k_acceleration <= 6):
        return False
    if 0.8 <= atr_regime_ratio <= 1.0:
        return False
    return True


def ablation_entry_short_ok(macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                             kdj_k, kdj_d, kdj_j, kdj_k_acceleration, atr_regime_ratio):
    """
    Indicators-only SHORT entry gate for the ablation arms -- identical to
    Section 3's OB-gated SHORT entry filters, minus the Order Block price
    touch requirement.

    Statistical/analytical question answered: none -- entry rule logic.

    Returns
    -------
    bool
    """
    if not (macd_hist_current > 0 and macd_hist_current < macd_hist_prev_bar):
        return False
    if not (macd_hist_prev_bar < macd_hist_two_bars_ago):
        return False
    if not (kdj_k > 50 and kdj_j > kdj_k > kdj_d):
        return False
    if not (1 <= kdj_k_acceleration <= 6):
        return False
    if 0.8 <= atr_regime_ratio <= 1.0:
        return False
    if kdj_k < KDJ_K_SHORT_FLOOR:
        return False
    if kdj_j > KDJ_J_SHORT_CAP:
        return False
    return True


def run_ablation_arm(df, stop_mode):
    """
    Simulate one indicators-only ablation arm bar by bar.

    Statistical/analytical question answered: "how much of the OB-gated
    strategy's performance comes from the Order Block gate itself, versus
    the MACD/KDJ/ATR indicator conditions alone?" This produces the trade
    pool for one of the two arms (`stop_mode` selects which).

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with indicators already computed.
    stop_mode : str
        'flat_atr' (Arm 2) or 'swing_pivot' (Arm 3). Reuses this file's own
        kdj_reset_init/update/exit (Section 3), unmodified from the
        OB-gated engine, not reimplemented.

    Returns
    -------
    pandas.DataFrame
        One row per closed trade: side, entry_idx, exit_idx, entry, exit,
        pnl_pct, hold_bars, exit_reason.
    """
    position = None
    entry_price = stop_loss_price = take_profit_price = 0.0
    entry_atr = 0.0
    peak_pnl_pct = 0.0
    entry_idx = 0
    kdj_state = None
    closed_trades = []

    for i in range(ABLATION_START_BAR, len(df)):
        close = float(df.at[i, "close"])
        high = float(df.at[i, "high"])
        low = float(df.at[i, "low"])
        macd_hist_current = float(df.at[i, "MACD_hist"])
        macd_hist_prev_bar = float(df.at[i - 1, "MACD_hist"])
        macd_hist_two_bars_ago = float(df.at[i - 2, "MACD_hist"])
        kdj_k = float(df.at[i, "K"])
        kdj_d = float(df.at[i, "D"])
        kdj_j = float(df.at[i, "J"])
        kdj_k_prev_bar = float(df.at[i - 1, "K"])
        kdj_k_two_bars_ago = float(df.at[i - 2, "K"])
        atr_14 = float(df.at[i, "ATR"])
        atr_200 = float(df.at[i, "ATR_200"])
        kdj_k_acceleration = (kdj_k - kdj_k_prev_bar) - (kdj_k_prev_bar - kdj_k_two_bars_ago)
        atr_regime_ratio = atr_14 / atr_200 if atr_200 > 0 else 1.0

        if position is None:
            if ablation_entry_long_ok(macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                                       kdj_k, kdj_k_prev_bar, kdj_j, kdj_k_acceleration, atr_regime_ratio):
                if stop_mode == "flat_atr":
                    stop_loss_candidate = close - atr_14 * 1.5
                else:
                    window_low = df["low"].iloc[max(0, i - ABLATION_SWING_PIVOT_LOOKBACK_BARS):i]
                    pivot_low = float(window_low.min()) if len(window_low) else close - atr_14 * 1.5
                    stop_loss_candidate = pivot_low - atr_14 * 0.5
                risk = close - stop_loss_candidate
                if risk > 0 and risk / close >= MIN_STOP_LOSS_DISTANCE_RATIO:
                    take_profit_candidate = close + risk * 2.0
                    if (take_profit_candidate - close) / risk >= MIN_RISK_REWARD_RATIO:
                        position = "LONG"
                        entry_price, stop_loss_price, take_profit_price = close, stop_loss_candidate, take_profit_candidate
                        entry_atr, peak_pnl_pct, entry_idx = atr_14, 0.0, i
                        kdj_state = kdj_reset_init(df, i, ob_bar=None)

            if position is None and ablation_entry_short_ok(
                    macd_hist_current, macd_hist_prev_bar, macd_hist_two_bars_ago,
                    kdj_k, kdj_d, kdj_j, kdj_k_acceleration, atr_regime_ratio):
                if stop_mode == "flat_atr":
                    stop_loss_candidate = close + atr_14 * 1.5
                else:
                    window_high = df["high"].iloc[max(0, i - ABLATION_SWING_PIVOT_LOOKBACK_BARS):i]
                    pivot_high = float(window_high.max()) if len(window_high) else close + atr_14 * 1.5
                    stop_loss_candidate = pivot_high + atr_14 * 0.5
                risk = stop_loss_candidate - close
                if risk > 0 and risk / close >= MIN_STOP_LOSS_DISTANCE_RATIO:
                    take_profit_candidate = close - risk * 2.0
                    if (close - take_profit_candidate) / risk >= MIN_RISK_REWARD_RATIO:
                        position = "SHORT"
                        entry_price, stop_loss_price, take_profit_price = close, stop_loss_candidate, take_profit_candidate
                        entry_atr, peak_pnl_pct, entry_idx = atr_14, 0.0, i
                        kdj_state = kdj_reset_init(df, i, ob_bar=None)

        elif position == "LONG":
            pnl_pct = (close - entry_price) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)

            def record_exit(exit_reason, exit_pnl, _i=i):
                closed_trades.append({
                    "side": "LONG", "entry_idx": entry_idx, "exit_idx": _i,
                    "entry": entry_price, "exit": close, "pnl_pct": exit_pnl,
                    "hold_bars": _i - entry_idx, "exit_reason": exit_reason,
                })

            if peak_pnl_pct >= 1.5 and close <= entry_price * (1 + peak_pnl_pct * 0.5 / 100):
                record_exit("TRAILING EXIT (50% RETRACE)", pnl_pct)
                position = None
                continue

            kdj_state = kdj_reset_update(kdj_state, df, i, "LONG")
            if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, "LONG"):
                record_exit("KDJ RESET EXIT", pnl_pct)
                position = None
                continue

            if entry_atr > 0 and close >= entry_price + entry_atr * ATR_MULT_EXIT:
                record_exit("ATR MOVE EXIT", pnl_pct)
                position = None
                continue

            if close >= entry_price + entry_atr * ATR_MULT_BREAKEVEN:
                stop_loss_price = max(stop_loss_price, entry_price)

            if close <= stop_loss_price:
                record_exit("HIT STOP LOSS", (close - entry_price) / entry_price * 100)
                position = None
            elif close >= take_profit_price:
                record_exit("HIT TAKE PROFIT", (close - entry_price) / entry_price * 100)
                position = None

        elif position == "SHORT":
            pnl_pct = (entry_price - close) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)

            def record_exit(exit_reason, exit_pnl, _i=i):
                closed_trades.append({
                    "side": "SHORT", "entry_idx": entry_idx, "exit_idx": _i,
                    "entry": entry_price, "exit": close, "pnl_pct": exit_pnl,
                    "hold_bars": _i - entry_idx, "exit_reason": exit_reason,
                })

            if peak_pnl_pct >= 1.5 and close >= entry_price * (1 - peak_pnl_pct * 0.5 / 100):
                record_exit("TRAILING EXIT (50% RETRACE)", pnl_pct)
                position = None
                continue

            kdj_state = kdj_reset_update(kdj_state, df, i, "SHORT")
            if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, "SHORT"):
                record_exit("KDJ RESET EXIT", pnl_pct)
                position = None
                continue

            if entry_atr > 0 and close <= entry_price - entry_atr * ATR_MULT_EXIT:
                record_exit("ATR MOVE EXIT", pnl_pct)
                position = None
                continue

            if close <= entry_price - entry_atr * ATR_MULT_BREAKEVEN:
                stop_loss_price = min(stop_loss_price, entry_price)

            if close >= stop_loss_price:
                record_exit("HIT STOP LOSS", (entry_price - close) / entry_price * 100)
                position = None
            elif close <= take_profit_price:
                record_exit("HIT TAKE PROFIT", (entry_price - close) / entry_price * 100)
                position = None

    return pd.DataFrame(closed_trades)


def summarize_trade_pool(trades_df):
    """
    Compute n/wins/win_rate/total_return/avg_return/sd for a trade pool.

    Statistical/analytical question answered: none -- descriptive summary,
    shared by the ablation arms and (in spirit) every other trade-pool
    summary in Section 5.

    Parameters
    ----------
    trades_df : pandas.DataFrame
        Must contain a 'pnl_pct' column.

    Returns
    -------
    dict
        n, wins, win_rate (%), total_return (%), avg_return (%), sd (%, or
        None if n <= 1).
    """
    n = len(trades_df)
    if n == 0:
        return {"n": 0, "wins": 0, "win_rate": 0.0, "total_return": 0.0, "avg_return": 0.0, "sd": None}
    wins = int((trades_df["pnl_pct"] > 0).sum())
    return {
        "n": n, "wins": wins, "win_rate": wins / n * 100,
        "total_return": float(trades_df["pnl_pct"].sum()),
        "avg_return": float(trades_df["pnl_pct"].mean()),
        "sd": float(trades_df["pnl_pct"].std()) if n > 1 else None,
    }


def bootstrap_ablation_arm_vs_baseline(arm_pnl_values, baseline_n, baseline_win_rate, baseline_avg_return,
                                        bootstrap_resamples, seed):
    """
    Bootstrap-resample FROM one ablation arm's trade pool, at the baseline's
    own sample size, to ask: "if this arm's indicators-only entries were the
    true population, how often would a same-sized sample from it match or
    beat the OB-gated baseline's actual win rate / avg return?"

    Statistical/analytical question answered: a between-arms percentile
    bootstrap comparison -- distinct from Section 5's bootstrap_ci(), which
    resamples the baseline's OWN 27 trades to get a confidence interval on
    its own return (a within-arm design). Do not conflate the two: this
    function asks whether the ablation arm's return distribution could
    plausibly have produced the baseline's result; bootstrap_ci() asks how
    uncertain the baseline's own result is.

    Parameters
    ----------
    arm_pnl_values : numpy.ndarray
        The ablation arm's full per-trade pnl_pct values (n=140 or n=138).
    baseline_n : int
        Baseline sample size to resample at (27).
    baseline_win_rate, baseline_avg_return : float
        The OB-gated baseline's actual win rate (%) and avg return (%).
    bootstrap_resamples : int
        Number of bootstrap resamples (B).
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    dict
        b, seed, n, win_rate_percentiles (2.5/50/97.5), avg_return_percentiles
        (2.5/50/97.5), empirical_p_win_rate_ge_baseline,
        empirical_p_avg_return_ge_baseline.
    """
    rng = np.random.default_rng(seed)
    win_rate_samples = np.empty(bootstrap_resamples)
    avg_return_samples = np.empty(bootstrap_resamples)
    for k in range(bootstrap_resamples):
        resample = rng.choice(arm_pnl_values, size=baseline_n, replace=True)
        win_rate_samples[k] = (resample > 0).mean() * 100
        avg_return_samples[k] = resample.mean()

    return {
        "b": bootstrap_resamples, "seed": seed, "n": baseline_n,
        "win_rate_percentiles": {
            "p2_5": float(np.percentile(win_rate_samples, 2.5)),
            "p50": float(np.percentile(win_rate_samples, 50)),
            "p97_5": float(np.percentile(win_rate_samples, 97.5)),
        },
        "avg_return_percentiles": {
            "p2_5": float(np.percentile(avg_return_samples, 2.5)),
            "p50": float(np.percentile(avg_return_samples, 50)),
            "p97_5": float(np.percentile(avg_return_samples, 97.5)),
        },
        "empirical_p_win_rate_ge_baseline": float((win_rate_samples >= baseline_win_rate).mean()),
        "empirical_p_avg_return_ge_baseline": float((avg_return_samples >= baseline_avg_return).mean()),
    }


def run_ablation_study(df, bootstrap_resamples=2000, seed=42):
    """
    Run both ablation arms end to end: OB-gated baseline (for comparison),
    Arm 2 (flat-ATR stop), Arm 3 (swing-pivot stop), each with a
    bootstrap-vs-baseline comparison, and an explicit MATCH/DIVERGE check
    against CLAUDE.md's locked Ablation A/B figures.

    Statistical/analytical question answered: "does removing the Order
    Block gate (keeping only the MACD/KDJ/ATR indicator conditions) still
    produce a profitable strategy?" -- the paper's three-arm design
    contrasts the OB-gated baseline against these two OB-free variants to
    attribute performance to the OB gate specifically, not just the
    underlying indicators.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with indicators already computed.
    bootstrap_resamples : int, default 2000
        Matches the disclosed ablation-bootstrap methodology (distinct from
        Section 5's B=10,000 baseline-CI bootstrap).
    seed : int, default 42

    Returns
    -------
    dict
        {"baseline": {...}, "arms": {"flat_atr": {...}, "swing_pivot": {...}}}
    """
    baseline_sim = simulate_trades(df.copy(), min_ob_quality=0)
    baseline_trades = baseline_sim.attrs.get("trades_df", pd.DataFrame())
    baseline_summary = summarize_trade_pool(baseline_trades)
    assert baseline_summary["n"] == LOCKED_BASELINE_TRADE_COUNT, (
        f"expected {LOCKED_BASELINE_TRADE_COUNT} baseline trades, got {baseline_summary['n']}"
    )

    results = {"baseline": baseline_summary, "arms": {}}

    for stop_mode, label in (("flat_atr", "Arm 2 (flat-ATR stop)"), ("swing_pivot", "Arm 3 (swing-pivot stop)")):
        print(f"[ablation] Running indicators-only {label}...")
        arm_trades = run_ablation_arm(df, stop_mode)
        arm_summary = summarize_trade_pool(arm_trades)

        locked = LOCKED_ABLATION_ARMS[stop_mode]
        n_matches = arm_summary["n"] == locked["n"]
        win_rate_matches = abs(arm_summary["win_rate"] - locked["win_rate_pct"]) <= 1.0
        return_matches = abs(arm_summary["total_return"] - locked["total_return_pct"]) <= 1.0
        status = "MATCH" if (n_matches and win_rate_matches and return_matches) else "DIVERGE"

        print(f"  {label}: N={arm_summary['n']} win_rate={arm_summary['win_rate']:.2f}% "
              f"total_return={arm_summary['total_return']:+.2f}%  vs. locked "
              f"N={locked['n']} win_rate={locked['win_rate_pct']:.2f}% "
              f"total_return={locked['total_return_pct']:+.2f}%  status={status}")
        if status == "DIVERGE":
            print("  >>> Reconstruction does not match the locked figure. This is a known,")
            print("  >>> disclosed reconstruction-fidelity gap (see this section's docstring),")
            print("  >>> not evidence the locked figure is wrong -- reported as-is, never")
            print("  >>> silently reconciled. CLAUDE.md's locked numbers are not changed here.")

        bootstrap = None
        if arm_summary["n"] > 0:
            bootstrap = bootstrap_ablation_arm_vs_baseline(
                arm_trades["pnl_pct"].values, baseline_summary["n"], baseline_summary["win_rate"],
                baseline_summary["avg_return"], bootstrap_resamples, seed,
            )

        results["arms"][stop_mode] = {
            "label": label, "reconstructed": arm_summary, "locked": locked,
            "status_vs_locked": status, "bootstrap_vs_baseline": bootstrap,
        }

    return results


# ============================================================================
# SECTION 5: STATISTICAL TESTS
# ============================================================================
#
# Seven named test functions, each a thin, well-documented wrapper around a
# scipy.stats call. Verified formula-identical (same scipy function, same
# parameters) across every one of their call sites in the original
# analysis/*.py scripts (fee_slippage_analysis.py, oos_validation_analysis.py,
# paper_sync_report.py, export_trades_and_results.py, benchmark_dca_analysis.py,
# bootstrap_power_analysis.py) -- consolidating them here is deduplication,
# not a methodology change.
#
# spearman_correlation() is the one exception: no .py file in this
# repository previously computed Spearman's rho (see this file's module
# docstring). It is new code, added with the user's explicit approval,
# mirroring pearson_correlation()'s call pattern exactly.


def binomial_test(win_count, trade_count, null_win_probability=0.5):
    """
    One-sample binomial test: is the observed win rate significantly
    different from a fair-coin-flip null (50%)?

    Statistical question answered: "if trades were coin flips with a 50%
    win probability, how surprising is observing `win_count` wins out of
    `trade_count` trades?" Reported both one-sided (alternative='greater' --
    the directional hypothesis that the strategy beats chance, used as the
    paper's primary figure since the strategy's construction gives a
    directional prior) and two-sided (the more conservative test with no
    directional prior).

    Parameters
    ----------
    win_count : int
        Number of winning trades.
    trade_count : int
        Total number of trades.
    null_win_probability : float, default 0.5
        Null-hypothesis win probability.

    Returns
    -------
    dict
        p_one_sided, p_two_sided.
    """
    one_sided = scipy_stats.binomtest(win_count, trade_count, null_win_probability, alternative="greater")
    two_sided = scipy_stats.binomtest(win_count, trade_count, null_win_probability, alternative="two-sided")
    return {"p_one_sided": one_sided.pvalue, "p_two_sided": two_sided.pvalue}


def fisher_exact_test(group_true_wins, group_true_losses, group_false_wins, group_false_losses):
    """
    Fisher's exact test on a 2x2 win/loss contingency table, comparing two
    groups' win RATES (independent of return magnitude).

    Statistical question answered: "do trades whose entry Order Block had a
    given quality criterion TRUE win at a significantly different rate than
    trades where it was FALSE?" Used per-criterion across the 5 orthogonal
    OB quality criteria (displacement, large_bar, fvg, liquidity_sweep,
    volume_expansion). Fisher's exact (rather than a chi-square test) is
    used because several of the group sizes here are small (n as low as 4),
    where the chi-square approximation is unreliable.

    Parameters
    ----------
    group_true_wins, group_true_losses : int
        Win/loss counts where the criterion was True.
    group_false_wins, group_false_losses : int
        Win/loss counts where the criterion was False.

    Returns
    -------
    float
        p-value.
    """
    contingency_table = [[group_true_wins, group_true_losses], [group_false_wins, group_false_losses]]
    _, p_value = scipy_stats.fisher_exact(contingency_table)
    return p_value


def welch_t_test(group_true_returns, group_false_returns):
    """
    Welch's two-sample t-test on per-trade returns (pnl_pct), comparing two
    groups' MEAN returns (unlike fisher_exact_test(), which compares win
    rates only).

    Statistical question answered: "do trades whose entry Order Block had a
    given quality criterion TRUE earn a significantly different average
    return than trades where it was FALSE?"

    Why Welch's t-test (equal_var=False) rather than a standard pooled-
    variance t-test: the True/False subgroups for each criterion have
    different sample sizes AND no reason to assume equal variances (nothing
    about an OB quality criterion implies its two subgroups should have
    matched return volatility). Welch's test does not assume equal
    variances, making it the more defensible default here.

    Parameters
    ----------
    group_true_returns, group_false_returns : array-like
        Per-trade pnl_pct values for each subgroup.

    Returns
    -------
    dict
        t_statistic, p_value.
    """
    t_statistic, p_value = scipy_stats.ttest_ind(group_true_returns, group_false_returns, equal_var=False)
    return {"t_statistic": t_statistic, "p_value": p_value}


def bootstrap_resample(values, bootstrap_resamples, seed, resample_size=None):
    """
    Nonparametric percentile bootstrap: resample `values` with replacement
    `bootstrap_resamples` times, returning the resulting distributions of
    the resample total and resample mean.

    Statistical question answered: "how much sampling uncertainty surrounds
    this trade log's own total/average return?" Treats the realized trade
    outcomes as the population to resample from -- standard practice for a
    fixed trade log -- but does NOT capture uncertainty in which trades
    would have fired under a different history. Used both for the paper's
    canonical 95% CI on the baseline's own return (B=10,000, seed=42; see
    run_bootstrap_ci()) and, at a different B, for the ablation study's
    between-arms comparison (see bootstrap_ablation_arm_vs_baseline() in
    Section 4 -- deliberately kept as a separate function since it answers
    a different question, not collapsed into this one).

    Parameters
    ----------
    values : array-like
        The empirical distribution to resample from (e.g. trades['pnl_pct']).
    bootstrap_resamples : int
        Number of bootstrap resamples (B). B=10,000 is used for the paper's
        canonical CI -- large enough that percentile estimates are stable
        to the reported precision, while remaining fast enough to rerun on
        every commit as part of routine verification.
    seed : int
        RNG seed, for exact reproducibility (numpy Generator, not the
        legacy RandomState API).
    resample_size : int or None
        Size of each resample; defaults to len(values) (resample at the
        original sample's own size).

    Returns
    -------
    dict
        resample_totals, resample_means (both numpy arrays of length
        `bootstrap_resamples`).
    """
    values = np.asarray(values)
    n = resample_size if resample_size is not None else len(values)
    rng = np.random.default_rng(seed)
    resample_totals = np.empty(bootstrap_resamples)
    resample_means = np.empty(bootstrap_resamples)
    for k in range(bootstrap_resamples):
        sample = rng.choice(values, size=n, replace=True)
        resample_totals[k] = sample.sum()
        resample_means[k] = sample.mean()
    return {"resample_totals": resample_totals, "resample_means": resample_means}


def pearson_correlation(x_values, y_values):
    """
    Pearson correlation coefficient (linear association) between two
    equal-length numeric series.

    Statistical question answered: in this paper, "do trades with longer
    hold durations tend to realize larger (or smaller) returns?" (x=hold_bars,
    y=pnl_pct), and separately "does the strategy's per-trade return track
    BTC's own return over the identical holding window?" (see
    run_benchmark_vs_buy_and_hold() in this section). Pearson's r assumes a
    linear relationship and is sensitive to outliers -- see
    spearman_correlation() for the rank-based alternative.

    Parameters
    ----------
    x_values, y_values : array-like

    Returns
    -------
    dict
        r (correlation coefficient), p_value, n.
    """
    r, p_value = scipy_stats.pearsonr(x_values, y_values)
    return {"r": r, "p_value": p_value, "n": len(x_values)}


def spearman_correlation(x_values, y_values):
    """
    Spearman's rank correlation coefficient between two equal-length
    numeric series.

    Statistical question answered: same question as pearson_correlation()
    (does hold duration associate with return?), but on RANKS rather than
    raw values -- a nonparametric check for a monotonic (not necessarily
    linear) relationship, less sensitive to outliers than Pearson. Reported
    alongside Pearson in the paper as a robustness cross-check: if both
    agree in sign and significance, the association is not an artifact of a
    few extreme trades.

    NOTE ON PROVENANCE: unlike every other function in this section, this is
    NOT ported from an existing script -- no .py file in this repository
    previously computed Spearman's rho (see this file's module docstring).
    This is a new, minimal wrapper mirroring pearson_correlation()'s call
    pattern exactly, added with explicit user approval to fill that gap. It
    reproduces the already-published figures (rho=+0.4797, p=0.0113 for the
    27-trade baseline's hold_bars vs. pnl_pct) that were previously computed
    ad hoc and recorded only in markdown docs.

    Parameters
    ----------
    x_values, y_values : array-like

    Returns
    -------
    dict
        rho (Spearman correlation coefficient), p_value, n.
    """
    rho, p_value = scipy_stats.spearmanr(x_values, y_values)
    return {"rho": rho, "p_value": p_value, "n": len(x_values)}


def mde_power_analysis(group_true_returns, group_false_returns, alpha, power):
    """
    Minimum Detectable Effect (MDE) for a two-sample comparison, at a given
    significance level and target power, using the standard normal-
    approximation formula:
        MDE = (z_(alpha/2) + z_beta) * sqrt(SD_true^2/n_true + SD_false^2/n_false)

    Statistical question answered: "given the actual observed subgroup
    sizes and standard deviations, what is the smallest TRUE mean-return
    gap between these two subgroups that this sample size could reliably
    (80% of the time, at alpha=0.05) detect?" This reframes a
    non-significant Welch's-t result: if the observed difference is smaller
    than the MDE, the correct reading is "underpowered to rule out a gap up
    to roughly +/-MDE", not "no gap exists".

    Why a normal approximation to the Welch-t reference distribution is
    adequate here: it is standard practice for a post-hoc power/MDE sanity
    check at this scale, and here the subgroup sizes (n=4..23 across the 5
    OB quality criteria) are themselves the binding constraint on power --
    not the approximation error introduced by using a normal rather than a
    t reference distribution.

    Parameters
    ----------
    group_true_returns, group_false_returns : array-like
        Per-trade pnl_pct values for each subgroup.
    alpha : float
        Significance level (e.g. 0.05).
    power : float
        Target statistical power (e.g. 0.80).

    Returns
    -------
    dict
        n_true, sd_true, n_false, sd_false, observed_diff, mde,
        detectable (bool: is the observed difference >= MDE?).
    """
    z_alpha_2 = scipy_stats.norm.ppf(1 - alpha / 2)
    z_beta = scipy_stats.norm.ppf(power)

    n_true, n_false = len(group_true_returns), len(group_false_returns)
    sd_true = np.std(group_true_returns, ddof=1)
    sd_false = np.std(group_false_returns, ddof=1)
    observed_diff = np.mean(group_true_returns) - np.mean(group_false_returns)

    standard_error = np.sqrt(sd_true ** 2 / n_true + sd_false ** 2 / n_false)
    mde = (z_alpha_2 + z_beta) * standard_error
    detectable = abs(observed_diff) >= mde

    return {
        "n_true": n_true, "sd_true": sd_true, "n_false": n_false, "sd_false": sd_false,
        "observed_diff": observed_diff, "mde": mde, "detectable": bool(detectable),
    }


def max_drawdown_pct(equity_curve):
    """
    Maximum percentage drawdown of an equity curve (peak-to-trough decline
    relative to the running peak).

    Statistical/analytical question answered: none -- a standard risk
    metric, not a hypothesis test. Reported alongside Sharpe/Sortino for
    every equity curve in this section (strategy, buy-and-hold, DCA).

    Parameters
    ----------
    equity_curve : pandas.Series or numpy.ndarray

    Returns
    -------
    float
        Most negative percentage drawdown observed (e.g. -6.46 for -6.46%).
    """
    equity_curve = pd.Series(equity_curve)
    running_max = equity_curve.cummax()
    drawdown_pct = (equity_curve - running_max) / running_max * 100
    return drawdown_pct.min()


def sharpe_sortino_ratios(bar_returns, periods_per_year):
    """
    Annualized Sharpe and Sortino ratios from a series of per-period returns.

    Statistical/analytical question answered: none -- standard risk-adjusted
    return metrics. Sharpe penalizes total volatility; Sortino penalizes
    only downside volatility (returns below 0), which is arguably the more
    relevant risk measure for an asymmetric-payoff strategy like this one.

    Parameters
    ----------
    bar_returns : array-like
        Per-period simple returns (e.g. equity_curve.pct_change().dropna()).
    periods_per_year : float
        Annualization factor's period count (e.g. 6*365.25 for 4H bars,
        52 for weekly).

    Returns
    -------
    tuple of float
        (sharpe, sortino). NaN if the relevant volatility denominator is 0.
    """
    mean_return = np.mean(bar_returns)
    return_std = np.std(bar_returns, ddof=1)
    sharpe = (mean_return / return_std) * np.sqrt(periods_per_year) if return_std > 0 else float("nan")

    downside_returns = np.minimum(bar_returns, 0.0)
    downside_deviation = np.sqrt(np.mean(np.asarray(downside_returns) ** 2))
    sortino = (mean_return / downside_deviation) * np.sqrt(periods_per_year) if downside_deviation > 0 else float("nan")

    return sharpe, sortino


# ============================================================================
# SECTION 5B: APPLICATION-LEVEL ANALYSES
# ============================================================================
#
# Each function below applies Section 5's test primitives to a specific
# question raised in the paper. Ported from (one function per source file,
# noted in each docstring): analysis/benchmark_dca_analysis.py,
# analysis/fee_slippage_analysis.py, analysis/regime_breakdown_analysis.py,
# analysis/oos_validation_analysis.py, analysis/paper_sync_report.py,
# analysis/benchmark_vs_passive.py, analysis/export_trades_and_results.py.

OB_QUALITY_CRITERIA_COLUMNS = {
    "Displacement": "entry_ob_quality_displacement",
    "LargeBar": "entry_ob_quality_large_bar",
    "FVG": "entry_ob_quality_fvg",
    "LiqSweep": "entry_ob_quality_liquidity_sweep",
    "VolExpansion": "entry_ob_quality_volume_expansion",
}
PERIODS_PER_YEAR_4H_BARS = 6 * 365.25   # 4H bars/year, leap-year-averaged
PERIODS_PER_YEAR_WEEKLY = 52


def run_criteria_significance_tests(trades_df, pnl_column="pnl_pct"):
    """
    Run Fisher's exact test and Welch's t-test for each of the 5 orthogonal
    OB quality criteria, comparing the True-subgroup against the
    False-subgroup on win rate (Fisher) and mean return (Welch).

    Statistical question answered: "does any individual OB quality
    criterion predict trade outcome on its own?" -- ported from the
    identical per-criterion loop duplicated across
    analysis/fee_slippage_analysis.py, analysis/paper_sync_report.py, and
    scratch/fee_slippage_audit.py (verified formula-identical at every call
    site before consolidating here).

    Parameters
    ----------
    trades_df : pandas.DataFrame
        Must contain the 5 entry_ob_quality_* boolean columns and a return
        column (`pnl_column`, default 'pnl_pct' -- pass 'pnl_pct_adj' for a
        fee/slippage-adjusted scenario).

    Returns
    -------
    dict
        One entry per criterion name: true_n, true_wins, false_n,
        false_wins, fisher_p, welch_t, welch_p.
    """
    results = {}
    for name, column in OB_QUALITY_CRITERIA_COLUMNS.items():
        mask = trades_df[column].astype(bool)
        true_group = trades_df.loc[mask, pnl_column]
        false_group = trades_df.loc[~mask, pnl_column]
        true_wins = int((true_group > 0).sum())
        false_wins = int((false_group > 0).sum())
        fisher_p = fisher_exact_test(true_wins, len(true_group) - true_wins, false_wins, len(false_group) - false_wins)
        welch_result = welch_t_test(true_group, false_group)
        results[name] = {
            "true_n": len(true_group), "true_wins": true_wins,
            "false_n": len(false_group), "false_wins": false_wins,
            "fisher_p": fisher_p, "welch_t": welch_result["t_statistic"], "welch_p": welch_result["p_value"],
        }
    return results


def run_bootstrap_ci(trades_df, bootstrap_resamples=10000, seed=42):
    """
    Compute the paper's canonical 95% bootstrap confidence interval on the
    baseline trade log's own total and average return.

    Statistical question answered: "how much sampling uncertainty surrounds
    the reported +30.31% total return / +1.12% avg return figures?" This is
    the paper's headline bootstrap CI (B=10,000, seed=42) -- see
    bootstrap_resample() in Section 5 for the underlying mechanism and how
    this differs from the ablation study's between-arms bootstrap (Section 4).

    Parameters
    ----------
    trades_df : pandas.DataFrame
        Must contain a 'pnl_pct' column.
    bootstrap_resamples : int, default 10000
        B -- large enough for stable percentile estimates at this precision.
    seed : int, default 42

    Returns
    -------
    dict
        n, total_return_point_pct, total_return_ci_pct (2-tuple),
        avg_return_point_pct, avg_return_ci_pct (2-tuple),
        pct_resamples_total_le_zero, pct_resamples_avg_le_zero.
    """
    pnl_values = trades_df["pnl_pct"].values
    resamples = bootstrap_resample(pnl_values, bootstrap_resamples, seed)
    total_point = pnl_values.sum()
    mean_point = pnl_values.mean()
    total_ci = np.percentile(resamples["resample_totals"], [2.5, 97.5])
    mean_ci = np.percentile(resamples["resample_means"], [2.5, 97.5])
    return {
        "n": len(pnl_values), "b": bootstrap_resamples, "seed": seed,
        "total_return_point_pct": total_point, "total_return_ci_pct": total_ci.tolist(),
        "avg_return_point_pct": mean_point, "avg_return_ci_pct": mean_ci.tolist(),
        "pct_resamples_total_le_zero": (resamples["resample_totals"] <= 0).mean() * 100,
        "pct_resamples_avg_le_zero": (resamples["resample_means"] <= 0).mean() * 100,
    }


def run_mde_power_report(trades_df, alpha=0.05, power=0.80):
    """
    Run mde_power_analysis() for each of the 5 orthogonal OB quality
    criteria and collect the results into one report.

    Statistical question answered: "for each criterion, is this sample
    underpowered to detect its own observed effect size?" -- see
    mde_power_analysis() in Section 5.

    Parameters
    ----------
    trades_df : pandas.DataFrame
    alpha : float, default 0.05
    power : float, default 0.80

    Returns
    -------
    dict
        {"alpha":..., "power":..., "criteria": {name: mde_power_analysis()
        result, ...}}
    """
    per_criterion = {}
    for name, column in OB_QUALITY_CRITERIA_COLUMNS.items():
        mask = trades_df[column].astype(bool)
        per_criterion[name] = mde_power_analysis(
            trades_df.loc[mask, "pnl_pct"], trades_df.loc[~mask, "pnl_pct"], alpha, power
        )
    return {"alpha": alpha, "power": power, "criteria": per_criterion}


def run_benchmark_vs_buy_and_hold(df, trades_df):
    """
    Compare the OB-gated strategy against a same-window BTC buy-and-hold
    position on a 100-indexed basis: total return, time-in-market, max
    drawdown, Sharpe/Sortino, and the Pearson correlation between each
    trade's own return and BTC's return over that trade's holding window.

    Statistical/analytical question answered: "how does the strategy's
    risk-adjusted performance compare to passively holding BTC over the
    identical window, and does the strategy's return simply track BTC's own
    movement during each trade?" (a low/negative correlation would suggest
    the strategy captures something beyond simple directional beta).

    Ported from analysis/benchmark_dca_analysis.py's section_1_benchmark().
    The strategy's equity curve is event-driven (flat between trades,
    compounds only at each exit) -- valid because simulate_trades() never
    holds overlapping positions, so a simple sequential walk over exits is
    exact, not an approximation.

    Parameters
    ----------
    df : pandas.DataFrame
        Full candle series for the window (with 'close').
    trades_df : pandas.DataFrame
        The window's trade log (needs pnl_pct, hold_bars, entry_idx, exit_idx).

    Returns
    -------
    dict
        n_bars, strategy {...}, buy_and_hold {...}, correlation
        {pearson_r, n, p}.
    """
    n_bars = len(df)
    close = df["close"]

    buy_and_hold_total_return = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100
    buy_and_hold_equity = close / close.iloc[0] * 100
    buy_and_hold_bar_returns = buy_and_hold_equity.pct_change().dropna()
    buy_and_hold_exposure_bars = n_bars - 1
    buy_and_hold_return_per_bar = buy_and_hold_total_return / buy_and_hold_exposure_bars
    buy_and_hold_max_dd = max_drawdown_pct(buy_and_hold_equity)
    buy_and_hold_sharpe, buy_and_hold_sortino = sharpe_sortino_ratios(buy_and_hold_bar_returns, PERIODS_PER_YEAR_4H_BARS)

    total_net_return = trades_df["pnl_pct"].sum()
    hold_bars_sum = trades_df["hold_bars"].sum()
    strategy_time_in_market_pct = hold_bars_sum / n_bars * 100
    strategy_return_per_bar = total_net_return / hold_bars_sum

    equity_by_bar = np.full(n_bars, np.nan)
    equity_by_bar[0] = 100.0
    running_equity = 100.0
    exit_pnl_by_bar = dict(zip(trades_df.sort_values("exit_idx")["exit_idx"], trades_df.sort_values("exit_idx")["pnl_pct"]))
    for i in range(1, n_bars):
        if i in exit_pnl_by_bar:
            running_equity *= (1 + exit_pnl_by_bar[i] / 100)
        equity_by_bar[i] = running_equity
    strategy_equity = pd.Series(equity_by_bar)
    strategy_bar_returns = strategy_equity.pct_change().dropna()
    strategy_max_dd = max_drawdown_pct(strategy_equity)
    strategy_sharpe, strategy_sortino = sharpe_sortino_ratios(strategy_bar_returns, PERIODS_PER_YEAR_4H_BARS)

    btc_window_return = (
        close.iloc[trades_df["exit_idx"].values].values - close.iloc[trades_df["entry_idx"].values].values
    ) / close.iloc[trades_df["entry_idx"].values].values * 100
    correlation = pearson_correlation(trades_df["pnl_pct"].values, btc_window_return)

    return {
        "n_bars": n_bars,
        "strategy": {
            "total_return_pct": total_net_return, "time_in_market_pct": strategy_time_in_market_pct,
            "bars_of_exposure": int(hold_bars_sum), "return_per_bar_pct": strategy_return_per_bar,
            "max_drawdown_pct": strategy_max_dd, "sharpe": strategy_sharpe, "sortino": strategy_sortino,
        },
        "buy_and_hold": {
            "total_return_pct": buy_and_hold_total_return, "time_in_market_pct": 100.0,
            "bars_of_exposure": buy_and_hold_exposure_bars, "return_per_bar_pct": buy_and_hold_return_per_bar,
            "max_drawdown_pct": buy_and_hold_max_dd, "sharpe": buy_and_hold_sharpe, "sortino": buy_and_hold_sortino,
        },
        "correlation": {"pearson_r": correlation["r"], "n": correlation["n"], "p": correlation["p_value"]},
    }


def _iso_week_first_bars(df):
    """
    Bar index of the first bar of every ISO calendar week in `df`. Shared
    weekly-contribution-timing convention used by both the DCA-blend model
    below and run_benchmark_vs_passive()'s DCA arm -- kept as a single
    helper so the two cannot silently drift apart (the original two source
    files intentionally duplicated this in miniature for a reason explained
    in analysis/benchmark_vs_passive.py's docstring; here, with everything
    in one file, there is no more reason to duplicate it).
    """
    week_key = df["open_time"].dt.isocalendar().year.astype(str) + "-W" + df["open_time"].dt.isocalendar().week.astype(str)
    bars = df.groupby(week_key).apply(lambda g: g.index.min()).sort_values().values
    return np.array(sorted(set(int(x) for x in bars)))


def run_dca_blend_analysis(df, trades_df, contribution_amount=1.0, strategy_sleeve_fractions=(0.10, 0.20, 0.30)):
    """
    Model a "complementary sleeve" portfolio: a fixed amount of new capital
    arrives every ISO week; a 100%-BTC-DCA baseline is compared against
    portfolios that instead split each week's contribution between a
    BTC-DCA sub-sleeve and an independently-capitalized strategy sub-sleeve.

    Statistical/analytical question answered: "if an investor were already
    dollar-cost-averaging into BTC, does diverting a fraction of each
    contribution into this strategy improve risk-adjusted outcomes?" Not a
    hypothesis test -- a descriptive portfolio-construction comparison
    (Sharpe/Sortino/max-drawdown per split).

    Ported from analysis/benchmark_dca_analysis.py's section_2_dca_blend().
    Returns are computed net of each period's own contribution (so injected
    capital is not misread as investment return). Max drawdown is reported
    two ways: principal-inclusive (conventional DCA-calculator presentation)
    and as a peak-to-trough cumulative-P&L DOLLAR retracement -- a percentage
    drawdown on cumulative P&L is ill-defined early in the series (P&L can be
    ~0 or negative before enough capital has accumulated), so the dollar
    figure is used there instead.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with 'open_time' and 'close'.
    trades_df : pandas.DataFrame
        Trade log (needs exit_idx, pnl_pct).
    contribution_amount : float, default 1.0
        New capital contributed per ISO week (relative units by default).
    strategy_sleeve_fractions : tuple of float
        Fractions of each contribution diverted to the strategy sub-sleeve
        (default 90/10, 80/20, 70/30 splits).

    Returns
    -------
    dict
        contribution_amount, n_contribution_periods, splits (list of
        per-split dicts: split_label, strategy_sleeve_fraction, dca_only
        {...}, combined {...}).
    """
    n_bars = len(df)
    close = df["close"].values
    exit_pnl_by_bar = dict(zip(trades_df["exit_idx"].astype(int), trades_df["pnl_pct"].astype(float)))
    contribution_bars = _iso_week_first_bars(df)
    contribution_bar_set = set(contribution_bars.tolist())

    def run_split(strategy_sleeve_fraction, split_label):
        dca_only_units = 0.0
        btc_sub_sleeve_units = 0.0
        strategy_sleeve_cash = 0.0
        dca_only_value = np.empty(n_bars)
        combined_value = np.empty(n_bars)
        contribution_by_bar = np.zeros(n_bars)

        for i in range(n_bars):
            price = close[i]
            if i in contribution_bar_set:
                dca_only_units += contribution_amount / price
                btc_sub_sleeve_units += contribution_amount * (1.0 - strategy_sleeve_fraction) / price
                strategy_sleeve_cash += contribution_amount * strategy_sleeve_fraction
                contribution_by_bar[i] = contribution_amount
            if i in exit_pnl_by_bar:
                strategy_sleeve_cash *= (1.0 + exit_pnl_by_bar[i] / 100.0)
            dca_only_value[i] = dca_only_units * price
            combined_value[i] = btc_sub_sleeve_units * price + strategy_sleeve_cash

        dca_only_value_at_contributions = dca_only_value[contribution_bars]
        combined_value_at_contributions = combined_value[contribution_bars]
        contribution_at_contributions = contribution_by_bar[contribution_bars]

        def period_returns(value_series, contribution_series):
            returns = np.empty(len(value_series) - 1)
            for k in range(1, len(value_series)):
                returns[k - 1] = (value_series[k] - contribution_series[k]) / value_series[k - 1] - 1.0
            return returns

        dca_only_returns = period_returns(dca_only_value_at_contributions, contribution_at_contributions)
        combined_returns = period_returns(combined_value_at_contributions, contribution_at_contributions)

        def max_dd_principal_inclusive_pct(value_series):
            running_max = np.maximum.accumulate(value_series)
            return ((value_series - running_max) / running_max * 100).min()

        def max_pnl_retracement_dollars(pnl_series):
            running_max = np.maximum.accumulate(pnl_series)
            return (pnl_series - running_max).min()

        cumulative_contribution = np.cumsum(contribution_at_contributions)
        dca_only_pnl = dca_only_value_at_contributions - cumulative_contribution
        combined_pnl = combined_value_at_contributions - cumulative_contribution

        dca_only_sharpe, dca_only_sortino = sharpe_sortino_ratios(dca_only_returns, PERIODS_PER_YEAR_WEEKLY)
        combined_sharpe, combined_sortino = sharpe_sortino_ratios(combined_returns, PERIODS_PER_YEAR_WEEKLY)

        return {
            "split_label": split_label, "strategy_sleeve_fraction": strategy_sleeve_fraction,
            "dca_only": {
                "final_value": float(dca_only_value_at_contributions[-1]),
                "total_contributed": float(cumulative_contribution[-1]),
                "final_pnl": float(dca_only_pnl[-1]), "sharpe": dca_only_sharpe, "sortino": dca_only_sortino,
                "max_drawdown_principal_inclusive_pct": max_dd_principal_inclusive_pct(dca_only_value_at_contributions),
                "max_pnl_retracement_dollars": max_pnl_retracement_dollars(dca_only_pnl),
            },
            "combined": {
                "final_value": float(combined_value_at_contributions[-1]),
                "total_contributed": float(cumulative_contribution[-1]),
                "final_pnl": float(combined_pnl[-1]), "sharpe": combined_sharpe, "sortino": combined_sortino,
                "max_drawdown_principal_inclusive_pct": max_dd_principal_inclusive_pct(combined_value_at_contributions),
                "max_pnl_retracement_dollars": max_pnl_retracement_dollars(combined_pnl),
            },
        }

    splits = []
    for fraction in strategy_sleeve_fractions:
        label = f"{int(round((1 - fraction) * 100))}/{int(round(fraction * 100))}"
        splits.append(run_split(fraction, label))

    return {"contribution_amount": contribution_amount, "n_contribution_periods": len(contribution_bars), "splits": splits}


def run_fee_slippage_sensitivity(trades_df, taker_fee_bps=5.0, slippage_bps=5.0, include_legacy_sensitivity_band=True):
    """
    Re-derive the baseline's headline statistics under several transaction-
    cost assumptions, applied as a flat round-trip percentage drag on each
    trade's pnl_pct.

    Statistical/analytical question answered: "how sensitive are the
    reported win rate / total return / significance figures to reasonable
    fee and slippage assumptions?" -- the currently-reported headline
    figures are GROSS (no cost modeled anywhere in simulate_trades()); this
    answers whether the paper's significance conclusions survive a
    realistic cost adjustment.

    Ported from analysis/fee_slippage_analysis.py's run_scenario(), called
    once per scenario. PRIMARY scenario: 5bps/side taker fee (Binance
    USDT-M Futures standard tier, confirmed against Binance's published fee
    schedule) + 5bps/side slippage (a conservative estimate for BTC/USDT 4H
    bar-close execution), kept as a strictly separate line item from fees
    since it is not a published exchange number. A GROSS and a FEE-ONLY
    scenario are always included alongside PRIMARY; a legacy LOW/MID/HIGH
    sensitivity band (bundled fee+slippage guesses that predate the
    confirmed fee figure) is included by default for comparison.

    Parameters
    ----------
    trades_df : pandas.DataFrame
        Baseline trade log.
    taker_fee_bps, slippage_bps : float, default 5.0 each
        Per-side basis points; the round-trip PRIMARY drag is
        2*(taker_fee_bps + slippage_bps)*0.01 percent.
    include_legacy_sensitivity_band : bool, default True

    Returns
    -------
    list of dict
        One entry per scenario: label, drag_pct, total_return_pct,
        avg_return_pct, sd_return_pct, wins, n, win_rate_pct,
        binomial_p_one_sided, binomial_p_two_sided, flipped_trades (list),
        criteria (per-criterion Fisher/Welch, via
        run_criteria_significance_tests()).
    """
    fee_round_trip_pct = 2 * taker_fee_bps * 0.01
    slippage_round_trip_pct = 2 * slippage_bps * 0.01
    primary_round_trip_pct = fee_round_trip_pct + slippage_round_trip_pct

    scenarios = [
        ("GROSS (no fees, no slippage -- as currently reported)", 0.0),
        (f"FEE ONLY (confirmed {taker_fee_bps:.2f}bps/side taker, no slippage, round trip)", fee_round_trip_pct),
        (f"PRIMARY: FEE (confirmed) + CONSERVATIVE SLIPPAGE ({taker_fee_bps:.2f}+{slippage_bps:.2f}bps/side, round trip)",
         primary_round_trip_pct),
    ]
    if include_legacy_sensitivity_band:
        scenarios += [
            ("[sensitivity band, pre-confirmation] LOW  (4bps taker + 3bps slip, round trip)", 0.14),
            ("[sensitivity band, pre-confirmation] MID  (7bps taker + 5bps slip, round trip)", 0.24),
            ("[sensitivity band, pre-confirmation] HIGH (10bps taker + 10bps slip, round trip)", 0.40),
        ]

    results = []
    for label, drag_pct in scenarios:
        adjusted = trades_df.copy()
        adjusted["pnl_pct_adj"] = adjusted["pnl_pct"] - drag_pct

        wins = int((adjusted["pnl_pct_adj"] > 0).sum())
        n = len(adjusted)
        flipped = adjusted[(trades_df["pnl_pct"] > 0) & (adjusted["pnl_pct_adj"] <= 0)]
        binomial_result = binomial_test(wins, n)

        results.append({
            "label": label, "drag_pct": drag_pct,
            "total_return_pct": adjusted["pnl_pct_adj"].sum(), "avg_return_pct": adjusted["pnl_pct_adj"].mean(),
            "sd_return_pct": adjusted["pnl_pct_adj"].std(ddof=1), "wins": wins, "n": n,
            "win_rate_pct": wins / n * 100,
            "binomial_p_one_sided": binomial_result["p_one_sided"], "binomial_p_two_sided": binomial_result["p_two_sided"],
            "flipped_trades": [
                {"entry_idx": int(r["entry_idx"]), "gross_pnl_pct": r["pnl_pct"], "net_pnl_pct": r["pnl_pct_adj"]}
                for _, r in flipped.iterrows()
            ],
            "criteria": run_criteria_significance_tests(adjusted, pnl_column="pnl_pct_adj"),
        })
    return results


def run_regime_breakdown(df, trades_df, ath_seed=69000.0, bear_threshold_pct=-40.0, chop_threshold_pct=-12.0,
                          bear_year=2022, chop_year=2023):
    """
    Tag each baseline trade by the macro market regime active at its entry
    bar, using two independent methods, both reported (never collapsed to
    one, since they measure genuinely different things and disagree on a
    meaningful fraction of trades).

    Statistical/analytical question answered: "is the strategy's return
    concentrated in one type of market regime (e.g. only during a bull
    run), or does it perform across bear/chop/bull conditions?" Purely
    descriptive -- no formal hypothesis test.

    Ported from analysis/regime_breakdown_analysis.py. Two tagging methods:
      1. CALENDAR: 2022=bear, 2023=chop, 2024+ = bull, per the standard,
         widely-cited BTC cycle narrative for this exact window.
      2. DRAWDOWN-FROM-ATH: running all-time-high is seeded at $69,000
         (BTC's actual 2021-11-10 ATH, which predates this dataset's
         2022-01-01 start by seven weeks -- seeding from the dataset's own
         first bar would incorrectly read early-2022, already ~32% off the
         real ATH, as "at the high"). Thresholds (a judgment call, stated so
         they can be re-argued): BEAR = drawdown <= -40%, CHOP = -40% to
         -12%, BULL = drawdown > -12%.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with 'open_time' and 'close'.
    trades_df : pandas.DataFrame
        Baseline trade log (needs entry_idx, pnl_pct).
    ath_seed : float, default 69000.0
    bear_threshold_pct, chop_threshold_pct : float, defaults -40.0, -12.0
    bear_year, chop_year : int, defaults 2022, 2023

    Returns
    -------
    dict
        drawdown_method, calendar_method (each: {regime: {n, wins,
        win_rate_pct, total_pnl_pct, pct_of_total_return, avg_pnl_pct}}),
        method_agreement {agree, n, disagreements}.
    """
    running_ath = np.maximum.accumulate(np.concatenate([[ath_seed], df["close"].values]))[1:]
    drawdown_pct = (df["close"].values / running_ath - 1.0) * 100.0

    def drawdown_regime(dd):
        if dd <= bear_threshold_pct:
            return "BEAR"
        elif dd <= chop_threshold_pct:
            return "CHOP"
        return "BULL"

    def calendar_regime(timestamp):
        if timestamp.year == bear_year:
            return "BEAR"
        elif timestamp.year == chop_year:
            return "CHOP"
        return "BULL"

    dd_regime_by_bar = np.array([drawdown_regime(x) for x in drawdown_pct])
    cal_regime_by_bar = df["open_time"].apply(calendar_regime).values

    trades_df = trades_df.copy()
    trades_df["entry_dd_pct"] = drawdown_pct[trades_df["entry_idx"].values]
    trades_df["dd_regime"] = dd_regime_by_bar[trades_df["entry_idx"].values]
    trades_df["cal_regime"] = cal_regime_by_bar[trades_df["entry_idx"].values]

    def summarize_by_regime(group_col):
        total_pnl = trades_df["pnl_pct"].sum()
        regimes = {}
        for regime in ["BEAR", "CHOP", "BULL"]:
            group = trades_df[trades_df[group_col] == regime]
            if group.empty:
                regimes[regime] = None
                continue
            n = len(group)
            wins = int((group["pnl_pct"] > 0).sum())
            total = group["pnl_pct"].sum()
            regimes[regime] = {
                "n": n, "wins": wins, "win_rate_pct": wins / n * 100, "total_pnl_pct": total,
                "pct_of_total_return": total / total_pnl * 100, "avg_pnl_pct": group["pnl_pct"].mean(),
            }
        return regimes

    agree_count = int((trades_df["dd_regime"] == trades_df["cal_regime"]).sum())
    disagreements_df = trades_df[trades_df["dd_regime"] != trades_df["cal_regime"]]
    disagreements = [
        {"entry_idx": int(r["entry_idx"]), "dd_pct": r["entry_dd_pct"], "dd_regime": r["dd_regime"], "cal_regime": r["cal_regime"]}
        for _, r in disagreements_df.iterrows()
    ]

    return {
        "drawdown_method": summarize_by_regime("dd_regime"),
        "calendar_method": summarize_by_regime("cal_regime"),
        "method_agreement": {"agree": agree_count, "n": len(trades_df), "disagreements": disagreements},
    }


def run_forward_oos_validation(start_date="2022-01-01 00:00:00", oos_end_date="2026-07-31 23:59:59"):
    """
    Pull fresh BTC/USDT 4H candles live from Binance through a fixed,
    closed historical end date, confirm the locked 27-trade baseline
    reproduces byte-identically against the fresh pull, then report any
    trades entered after the locked window's end as genuinely
    out-of-sample (postdating every commit to the strategy code).

    Statistical/analytical question answered: "does the frozen rule set,
    tested against data it could not have been shaped against, still
    produce sensible-looking trades?" Not a formal significance test at
    this sample size (n is typically tiny) -- reported descriptively.

    DISCLOSED EXCEPTION TO THIS REPOSITORY'S OFFLINE-ONLY CONVENTION: this
    is the one function in this file that makes a live Binance API call.
    See run_full_analysis_pipeline()'s --include-oos-live flag (off by
    default) -- every other function in this file runs strictly offline.

    A fixed, closed --oos-end-date (rather than "through now") is used
    deliberately: Binance does not revise historical candles, so a closed
    range is safely re-runnable and reproduces the same numbers on a later
    run, unlike an open-ended "now" pull which would drift every run.

    Ported from analysis/oos_validation_analysis.py's section_1_forward_oos().

    Parameters
    ----------
    start_date : str, default "2022-01-01 00:00:00"
        Matches the locked baseline's start.
    oos_end_date : str, default "2026-07-31 23:59:59"
        Fixed historical end date for the live pull.

    Returns
    -------
    dict
        bars_pulled, integrity_check (bool), regression_check (bool),
        oos_trades (list), oos_summary (dict or None).
    """
    fresh_candles = get_candles(
        symbol="BTCUSDT", interval=Client.KLINE_INTERVAL_4HOUR,
        start_time=start_date, end_time=oos_end_date,
    )

    locked_candles = load_candles()
    n_locked = len(locked_candles)
    overlap = fresh_candles.iloc[:n_locked].reset_index(drop=True)
    comparison_columns = ["open_time", "open", "high", "low", "close", "volume"]
    integrity_check = overlap[comparison_columns].reset_index(drop=True)["open_time"].equals(
        locked_candles[comparison_columns].reset_index(drop=True)["open_time"]
    ) and np.allclose(
        overlap[["open", "high", "low", "close", "volume"]].values,
        locked_candles[["open", "high", "low", "close", "volume"]].values, atol=1e-8,
    )

    df = compute_indicators(fresh_candles.copy())
    sim = simulate_trades(df.copy(), min_ob_quality=0)
    trades = sim.attrs.get("trades_df").copy()

    original_trades = trades[trades["entry_idx"] < n_locked]
    new_trades = trades[trades["entry_idx"] >= n_locked]
    regression_check = (len(original_trades) == LOCKED_BASELINE_TRADE_COUNT) and np.isclose(
        original_trades["pnl_pct"].sum(), LOCKED_BASELINE_TOTAL_RETURN_PCT, atol=1e-2,
    )

    oos_trade_list = []
    oos_summary = None
    if not new_trades.empty:
        for _, row in new_trades.iterrows():
            oos_trade_list.append({
                "side": row["side"], "entry_time": fresh_candles.iloc[int(row["entry_idx"])]["open_time"],
                "exit_time": fresh_candles.iloc[int(row["exit_idx"])]["open_time"],
                "pnl_pct": row["pnl_pct"], "exit_reason": row["exit_reason"],
            })
        wins = int((new_trades["pnl_pct"] > 0).sum())
        binomial_result = binomial_test(wins, len(new_trades))
        oos_summary = {
            "n": len(new_trades), "wins": wins, "win_rate_pct": wins / len(new_trades) * 100,
            "total_pnl_pct": new_trades["pnl_pct"].sum(), "avg_pnl_pct": new_trades["pnl_pct"].mean(),
            "binomial_p_one_sided": binomial_result["p_one_sided"],
        }

    return {
        "start_date": start_date, "oos_end_date": oos_end_date, "bars_pulled": len(fresh_candles),
        "integrity_check": bool(integrity_check), "regression_check": bool(regression_check),
        "oos_trades": oos_trade_list, "oos_summary": oos_summary,
    }


def run_paper_sync_check(df):
    """
    Recompute every checkable headline figure fresh from data+code, then
    cross-check each against this file's own LOCKED_* constants (Section 1
    -- sourced from CLAUDE.md's "Locked results" section).

    Statistical/analytical question answered: none directly -- this is a
    correctness/reproducibility check, not a hypothesis test. It answers
    "does the code, run today, still produce the numbers the paper cites?"

    Ported from analysis/paper_sync_report.py, SIMPLIFIED: the original
    script regex-parses CLAUDE.md's raw text at runtime so it stays
    self-updating as CLAUDE.md's wording changes. This consolidated version
    instead compares against the LOCKED_* constants already declared in
    Section 1 -- the same comparison, the same tolerances, the same
    MISMATCH-is-a-correctness-finding posture (never silently reconciled),
    just without re-scraping an external markdown file at runtime, which
    is clearer for a reader of this file but means this function will NOT
    automatically track future wording changes to CLAUDE.md the way the
    original script does. If CLAUDE.md's locked figures are ever revised,
    Section 1's LOCKED_* constants must be updated by hand to match.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data with indicators already computed.

    Returns
    -------
    dict
        checks (list of {metric, locked, live, status}), any_mismatch (bool).
    """
    order_blocks = compute_smc(df)
    total_obs = len(order_blocks)
    fvg_true_count = sum(1 for ob in order_blocks if ob.get("quality_fvg"))
    fvg_true_pct = fvg_true_count / total_obs * 100 if total_obs else None

    baseline_sim = simulate_trades(df.copy(), min_ob_quality=0)
    baseline_trades = baseline_sim.attrs.get("trades_df", pd.DataFrame())
    baseline_stats = baseline_sim.attrs.get("trade_stats", {})
    baseline_wins = int((baseline_trades["pnl_pct"] > 0).sum())
    baseline_binomial = binomial_test(baseline_wins, len(baseline_trades))
    baseline_sd = float(baseline_trades["pnl_pct"].std())

    def check(metric, locked_value, live_value, tolerance=None):
        if tolerance is not None:
            status = "MATCH" if abs(float(locked_value) - float(live_value)) <= tolerance else "MISMATCH"
        else:
            status = "MATCH" if locked_value == live_value else "MISMATCH"
        return {"metric": metric, "locked": locked_value, "live": live_value, "status": status}

    checks = [
        check("Baseline (q>=0) trades", LOCKED_BASELINE_TRADE_COUNT, baseline_stats["Total Trades"]),
        check("Baseline win rate (%)", LOCKED_BASELINE_WIN_RATE_PCT, baseline_stats["Win Rate (%)"], tolerance=0.01),
        check("Baseline total net return (%)", LOCKED_BASELINE_TOTAL_RETURN_PCT, baseline_stats["Total Net Return (%)"], tolerance=0.01),
        check("Baseline avg return/trade (%)", LOCKED_BASELINE_AVG_RETURN_PCT, baseline_stats["Avg Return/Trade (%)"], tolerance=0.01),
        check("Baseline SD (%)", LOCKED_BASELINE_RETURN_SD_PCT, baseline_sd, tolerance=0.01),
        check("Baseline p (one-sided)", 0.026, baseline_binomial["p_one_sided"], tolerance=0.001),
        check("Total detected Order Blocks", 761, total_obs),
        check("FVG-true count", 253, fvg_true_count),
        check("FVG-true (%)", 33.2, fvg_true_pct, tolerance=0.05),
    ]
    any_mismatch = any(c["status"] == "MISMATCH" for c in checks)
    return {"checks": checks, "any_mismatch": any_mismatch}


# --- CLAUDE.md prose cross-check + markdown report --------------------------
# Unlike run_paper_sync_check() above (which compares against this file's own
# LOCKED_* constants), this section regex-parses CLAUDE.md's actual prose at
# runtime, so it also catches CLAUDE.md wording drift, not just code drift --
# a capability run_paper_sync_check() explicitly does not have (see its
# docstring). Ported near-verbatim from analysis/paper_sync_report.py (now
# retired to legacy_pre_consolidation/), since this is the one analysis/*.py
# script called routinely by the export/--serve pipeline (Section 7), not an
# occasional manual audit tool. Writes artifacts/paper_sync_report.md.

CLAUDE_MD_PATH = os.path.join(BASE_DIR, "CLAUDE.md")
PAPER_SYNC_REPORT_DEFAULT_OUT_PATH = os.path.join(BASE_DIR, "artifacts", "paper_sync_report.md")

_PAPER_SYNC_CRITERIA_COLUMNS = {
    "Displacement": "entry_ob_quality_displacement",
    "LargeBar": "entry_ob_quality_large_bar",
    "FVG": "entry_ob_quality_fvg",
    "LiqSweep": "entry_ob_quality_liquidity_sweep",
    "VolExpansion": "entry_ob_quality_volume_expansion",
}
_PAPER_SYNC_OB_QUALITY_FIELDS = {
    "Displacement": "quality_displacement",
    "LargeBar": "quality_large_bar",
    "FVG": "quality_fvg",
    "LiqSweep": "quality_liquidity_sweep",
    "VolExpansion": "quality_volume_expansion",
}


def _paper_sync_threshold_sweep(df):
    """Full q0-q5 sweep with binomial tests at every threshold (not just the
    q>=0 baseline run_paper_sync_check() checks)."""
    rows = []
    for q in range(6):
        sim_df = simulate_trades(df.copy(), min_ob_quality=q)
        trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
        n = len(trades_df)
        if n == 0:
            rows.append({"q": q, "n": 0})
            continue
        wins = int((trades_df["pnl_pct"] > 0).sum())
        binomial_result = binomial_test(wins, n)
        rows.append({
            "q": q, "n": n, "wins": wins, "losses": n - wins,
            "win_rate": wins / n * 100, "total_return": float(trades_df["pnl_pct"].sum()),
            "avg_return": float(trades_df["pnl_pct"].mean()),
            "sd": float(trades_df["pnl_pct"].std()) if n > 1 else float("nan"),
            "p_one_sided": binomial_result["p_one_sided"], "p_two_sided": binomial_result["p_two_sided"],
        })
    return rows


def _paper_sync_ob_population(order_blocks):
    total = len(order_blocks)
    counts = {name: sum(1 for ob in order_blocks if ob.get(field))
              for name, field in _PAPER_SYNC_OB_QUALITY_FIELDS.items()}
    quality_distribution = {q: 0 for q in range(6)}
    for ob in order_blocks:
        quality_distribution[int(ob.get("quality", 0))] += 1
    return {"total": total, "criteria_true_counts": counts, "quality_distribution": quality_distribution}


def _paper_sync_criteria_tests(trades_df):
    results = {}
    for name, col in _PAPER_SYNC_CRITERIA_COLUMNS.items():
        true_pnl = trades_df.loc[trades_df[col] == True, "pnl_pct"]
        false_pnl = trades_df.loc[trades_df[col] == False, "pnl_pct"]
        true_n, false_n = len(true_pnl), len(false_pnl)
        true_wins, false_wins = int((true_pnl > 0).sum()), int((false_pnl > 0).sum())
        fisher_p = fisher_exact_test(
            true_wins, true_n - true_wins, false_wins, false_n - false_wins,
        ) if true_n and false_n else float("nan")
        welch_result = welch_t_test(true_pnl.tolist(), false_pnl.tolist()) if true_n > 1 and false_n > 1 else None
        results[name] = {
            "true_n": true_n, "true_wins": true_wins,
            "false_n": false_n, "false_wins": false_wins,
            "fisher_p": fisher_p,
            "welch_t": welch_result["t_statistic"] if welch_result else float("nan"),
            "welch_p": welch_result["p_value"] if welch_result else float("nan"),
        }
    return results


def _parse_claude_md_locked_results():
    """Regex-parse CLAUDE.md's "Locked results" prose into a dict of live-
    comparable values. Returns (locked_dict, raw_text)."""
    with open(CLAUDE_MD_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    locked = {}
    checks = [
        ("baseline_trades", r"Baseline \(min_ob_quality=0\):\s*(\d+)\s*trades", int),
        ("baseline_win_rate", r"(\d+\.\d+)%\s*win rate", float),
        ("baseline_total_return", r"\+(\d+\.\d+)%\s*total net\s*\n?\s*return", float),
        ("baseline_avg_return", r"\+(\d+\.\d+)%\s*avg return/trade", float),
        ("baseline_sd", r"SD\s*(\d+\.\d+)%", float),
        ("baseline_p_one_sided", r"One-sided binomial p\s*=\s*(\d+\.\d+)", float),
        ("baseline_p_two_sided", r"two-sided\s*(\d+\.\d+)\)\s*for the q>=0 baseline", float),
        ("total_obs", r"(\d+)\s*detected Order Blocks", int),
        ("fvg_true_count", r"FVG criterion true for\s*(\d+)\s*\(", int),
        ("fvg_true_pct", r"FVG criterion true for\s*\d+\s*\((\d+\.\d+)%\)", float),
        ("bar_count", r"(\d[\d,]*)\s*bars \(1,461 days", lambda s: int(s.replace(",", ""))),
    ]
    for key, pattern, cast in checks:
        m = re.search(pattern, raw_text)
        locked[key] = cast(m.group(1)) if m else None

    qdist_m = re.search(
        r"OB quality distribution \(post-fix.*?\):\s*"
        r"q0=(\d+), q1=(\d+),\s*\n?\s*q2=(\d+), q3=(\d+), q4=(\d+), q5=(\d+)",
        raw_text,
    )
    locked["quality_distribution"] = (
        {i: int(qdist_m.group(i + 1)) for i in range(6)} if qdist_m else None
    )

    ablation_a_m = re.search(
        r"Ablation A \(indicators-only, entry-ATR stop\):\s*(\d+) trades,\s*(\d+\.\d+)%,\s*(-?\d+\.\d+)%", raw_text)
    ablation_b_m = re.search(
        r"Ablation B \(indicators-only, swing-pivot stop\):\s*(\d+) trades,\s*(\d+\.\d+)%,\s*(-?\d+\.\d+)%", raw_text)
    locked["ablation_a"] = (
        {"n": int(ablation_a_m.group(1)), "win_rate": float(ablation_a_m.group(2)),
         "total_return": float(ablation_a_m.group(3))} if ablation_a_m else None
    )
    locked["ablation_b"] = (
        {"n": int(ablation_b_m.group(1)), "win_rate": float(ablation_b_m.group(2)),
         "total_return": float(ablation_b_m.group(3))} if ablation_b_m else None
    )
    return locked, raw_text


class _PaperSyncCheck:
    """One locked-vs-live row in the paper-sync report table."""

    def __init__(self, metric, locked_val, live_val, fmt=None, tol=None):
        self.metric = metric
        self.locked_val = locked_val
        self.live_val = live_val
        self.fmt = fmt or (lambda v: str(v))
        self.tol = tol

    @property
    def status(self):
        if self.locked_val is None:
            return "NO-PARSE"
        if self.live_val is None:
            return "NO-DATA"
        if self.tol is not None:
            ok = abs(float(self.locked_val) - float(self.live_val)) <= self.tol
        else:
            ok = self.locked_val == self.live_val
        return "MATCH" if ok else "MISMATCH"

    def row(self):
        locked_s = self.fmt(self.locked_val) if self.locked_val is not None else "(not found in CLAUDE.md)"
        live_s = self.fmt(self.live_val) if self.live_val is not None else "(not computed)"
        mark = {"MATCH": "MATCH", "MISMATCH": "MISMATCH -- STOP", "NO-PARSE": "NO-PARSE",
                "NO-DATA": "NO-DATA"}[self.status]
        return f"| {self.metric} | {locked_s} | {live_s} | {mark} |"


def generate_paper_sync_report(out_path=PAPER_SYNC_REPORT_DEFAULT_OUT_PATH, verbose=True):
    """
    Recompute every checkable headline figure fresh from data+code, cross-
    check each against a live regex-parse of CLAUDE.md's own "Locked
    results" prose, write the markdown report to out_path, and return
    (report_text, mismatches, checks).

    Statistical/analytical question answered: none directly -- a
    reproducibility/correctness check, same posture as run_paper_sync_check()
    but comparing against CLAUDE.md's actual current wording (catches prose
    drift too) instead of this file's own LOCKED_* constants. Never edits
    CLAUDE.md or "corrects" a mismatch itself -- a MISMATCH is a correctness
    finding for a human to review, per CLAUDE.md's own rule on newly found
    bugs.

    Parameters
    ----------
    out_path : str
    verbose : bool

    Returns
    -------
    (report_text: str, mismatches: list, checks: list)
    """
    generated_at = datetime.now(timezone.utc).isoformat()

    def log(msg):
        if verbose:
            print(msg)

    log("[paper_sync_report] Loading candles...")
    raw_df = load_candles()
    bar_count = len(raw_df)

    log("[paper_sync_report] Computing indicators and Order Blocks...")
    base_df = compute_indicators(raw_df.copy())
    order_blocks = compute_smc(base_df)
    ob_population = _paper_sync_ob_population(order_blocks)

    log("[paper_sync_report] Running q0-q5 threshold sweep...")
    sweep_rows = _paper_sync_threshold_sweep(base_df)

    log("[paper_sync_report] Running per-criterion Fisher/Welch tests on the q>=0 baseline...")
    q0_sim = simulate_trades(base_df.copy(), min_ob_quality=0)
    q0_trades = q0_sim.attrs.get("trades_df", pd.DataFrame())
    criteria_tests = _paper_sync_criteria_tests(q0_trades)

    log("[paper_sync_report] Parsing CLAUDE.md locked results...")
    locked, _ = _parse_claude_md_locked_results()

    q0 = next(r for r in sweep_rows if r["q"] == 0)
    checks = [
        _PaperSyncCheck("Bar count", locked.get("bar_count"), bar_count),
        _PaperSyncCheck("Baseline (q>=0) trades", locked.get("baseline_trades"), q0.get("n")),
        _PaperSyncCheck("Baseline win rate (%)", locked.get("baseline_win_rate"), q0.get("win_rate"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01),
        _PaperSyncCheck("Baseline total net return (%)", locked.get("baseline_total_return"), q0.get("total_return"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01),
        _PaperSyncCheck("Baseline avg return/trade (%)", locked.get("baseline_avg_return"), q0.get("avg_return"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01),
        _PaperSyncCheck("Baseline SD (%)", locked.get("baseline_sd"), q0.get("sd"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01),
        _PaperSyncCheck("Baseline p (one-sided)", locked.get("baseline_p_one_sided"), q0.get("p_one_sided"),
                         fmt=lambda v: f"{v:.3f}", tol=0.001),
        _PaperSyncCheck("Total detected Order Blocks", locked.get("total_obs"), ob_population["total"]),
        _PaperSyncCheck("FVG-true count", locked.get("fvg_true_count"), ob_population["criteria_true_counts"]["FVG"]),
    ]
    fvg_pct_live = (ob_population["criteria_true_counts"]["FVG"] / ob_population["total"] * 100) if ob_population["total"] else None
    checks.append(_PaperSyncCheck("FVG-true (%)", locked.get("fvg_true_pct"), fvg_pct_live,
                                   fmt=lambda v: f"{v:.1f}", tol=0.05))
    qdist_locked = locked.get("quality_distribution") or {}
    for q in range(6):
        checks.append(_PaperSyncCheck(f"OB quality distribution q{q}", qdist_locked.get(q),
                                       ob_population["quality_distribution"][q]))

    welch_ps_all5 = [v["welch_p"] for v in criteria_tests.values()]
    welch_range_all5 = (min(welch_ps_all5), max(welch_ps_all5)) if welch_ps_all5 else (None, None)

    lines = [
        "# Paper/codebase sync report", "",
        f"Generated: {generated_at}", "",
        "Recomputed live from `artifacts/candles.csv` and this file's own strategy-engine "
        "functions, then cross-checked against the figures parsed out of `CLAUDE.md`'s "
        "\"Locked results\" section. A MISMATCH row is a correctness finding, not something "
        "this script resolves automatically -- see `CLAUDE.md`'s rule on newly found bugs.",
        "", "## Cross-check summary", "",
        "| Metric | Locked (CLAUDE.md) | Live (this run) | Status |",
        "|---|---|---|---|",
    ]
    lines.extend(c.row() for c in checks)
    lines.append("")

    lines.append("## Full q0-q5 threshold sweep (live)")
    lines.append("")
    lines.append("| q | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (one-sided) | p (two-sided) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in sweep_rows:
        if r.get("n", 0) == 0:
            lines.append(f"| {r['q']} | 0 | - | - | - | - | - | - | - | - |")
            continue
        sd_s = f"{r['sd']:.2f}" if not np.isnan(r["sd"]) else "n/a (n=1)"
        lines.append(
            f"| {r['q']} | {r['n']} | {r['wins']} | {r['losses']} | {r['win_rate']:.2f}% | "
            f"{r['total_return']:+.2f}% | {r['avg_return']:+.4f}% | {sd_s} | "
            f"{r['p_one_sided']:.4f} | {r['p_two_sided']:.4f} |"
        )
    lines.append("")

    lines.append("## Per-criterion Fisher's exact + Welch's t-test (live, q>=0 baseline)")
    lines.append("")
    lines.append("| Criterion | True n (wins) | False n (wins) | Fisher p | Welch t | Welch p |")
    lines.append("|---|---|---|---|---|---|")
    for name in _PAPER_SYNC_CRITERIA_COLUMNS:
        r = criteria_tests[name]
        lines.append(
            f"| {name} | {r['true_n']} ({r['true_wins']}) | {r['false_n']} ({r['false_wins']}) | "
            f"{r['fisher_p']:.4f} | {r['welch_t']:+.4f} | {r['welch_p']:.4f} |"
        )
    lines.append("")
    if welch_range_all5[0] is not None:
        lines.append(
            f"Welch p-value range across all 5 criteria: "
            f"**{welch_range_all5[0]:.4f}-{welch_range_all5[1]:.4f}**."
        )
    lines.append("")

    lines.append("## Ablation A/B -- passthrough from CLAUDE.md, UNVERIFIED this run")
    lines.append("")
    lines.append(
        "No function in this file reproduces these figures from current code -- the "
        "originating script was never committed. Printed here only as cited from "
        "`CLAUDE.md`, not independently recomputed."
    )
    lines.append("")
    a, b = locked.get("ablation_a"), locked.get("ablation_b")
    lines.append("| Configuration | N | Win rate | Total return |")
    lines.append("|---|---|---|---|")
    if a:
        lines.append(f"| Indicators-only (entry-ATR stop) | {a['n']} | {a['win_rate']:.2f}% | {a['total_return']:+.2f}% |")
    if b:
        lines.append(f"| Indicators-only (swing-pivot stop) | {b['n']} | {b['win_rate']:.2f}% | {b['total_return']:+.2f}% |")
    lines.append("")

    report_text = "\n".join(lines)
    mismatches = [c for c in checks if c.status == "MISMATCH"]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    log(f"[paper_sync_report] Wrote {out_path}")

    no_parse = [c for c in checks if c.status == "NO-PARSE"]
    if no_parse and verbose:
        print("[paper_sync_report] WARNING: could not parse the following figures out of "
              "CLAUDE.md (regex no longer matches its current wording):")
        for c in no_parse:
            print(f"  - {c.metric}")

    if mismatches and verbose:
        print("\n" + "=" * 70)
        print("[paper_sync_report] STOP: live-recomputed figures disagree with "
              "CLAUDE.md's locked results.")
        print("This is a correctness finding, not something to silently reconcile.")
        print("=" * 70)
        for c in mismatches:
            print(f"  - {c.metric}: locked={c.locked_val!r} live={c.live_val!r}")
    elif verbose:
        print("[paper_sync_report] All parsed CLAUDE.md figures match live recomputation.")

    return report_text, mismatches, checks


FORMULATION_PERIOD_PREFIX_BARS = 8750  # artifacts/candles_extended_manifest.json: segment_bar_counts.prefix_pre_2022
MAIN_WINDOW_LABEL = "locked baseline window"
FORMULATION_WINDOW_LABEL = "formulation period -- NOT out-of-sample, NOT the 2026 forward-OOS test"


def load_formulation_period_window():
    """
    Load the 2018-01-01 .. 2022-01-01 "formulation period" window from the
    committed extended-history JSON snapshot -- the period the strategy's
    rule STRUCTURE was originally tuned against, explicitly NOT
    out-of-sample and NOT the same window as run_forward_oos_validation().

    Statistical/analytical question answered: none -- data loading. Ported
    from analysis/benchmark_vs_passive.py's load_formulation_window().

    Returns
    -------
    pandas.DataFrame
        Candle data for the formulation-period window, columns matching
        load_candles().
    """
    with open(ARTIFACTS_CANDLES_EXTENDED_JSON, encoding="utf-8") as f:
        records = json.load(f)
    prefix = pd.DataFrame(records[:FORMULATION_PERIOD_PREFIX_BARS])
    prefix["open_time"] = pd.to_datetime(prefix["open_time"])
    last_open_time = str(prefix["open_time"].iloc[-1])
    assert last_open_time == "2022-01-01 04:00:00", (
        f"expected the formulation-period slice to end at 2022-01-01 04:00:00 (one bar "
        f"before the locked window starts), got {last_open_time} -- "
        f"artifacts/candles_extended.json's segment boundaries may have changed."
    )
    return prefix


def reconcile_formulation_window_trades(trades_df, published_json_path="artifacts/oos_validation_analysis.json"):
    """
    Cross-check the formulation-period trade set computed in THIS file
    against the already-published figures in
    artifacts/oos_validation_analysis.json (produced by
    run_forward_oos_validation()'s Section 2 equivalent in the original
    analysis/oos_validation_analysis.py script), since two independently
    written code paths loading the same window should agree exactly.

    Statistical/analytical question answered: none -- a cross-implementation
    consistency check, not a hypothesis test.

    Parameters
    ----------
    trades_df : pandas.DataFrame
        This file's own formulation-period trade log.
    published_json_path : str
        Path to the previously-generated comparison artifact.

    Returns
    -------
    bool or None
        True (match), False (diverge), or None (no published figure found
        to check against -- never silently assumed to match).
    """
    if not os.path.isfile(published_json_path):
        return None
    with open(published_json_path, encoding="utf-8") as f:
        published = json.load(f)["section_2_backfill_audit"]["pre_window_not_oos"]

    n = len(trades_df)
    wins = int((trades_df["pnl_pct"] > 0).sum())
    binomial_result = binomial_test(wins, n) if n else {"p_one_sided": float("nan")}
    live_fields = {
        "n": n, "wins": wins, "win_rate_pct": (wins / n * 100) if n else float("nan"),
        "total_pnl_pct": trades_df["pnl_pct"].sum(), "avg_pnl_pct": trades_df["pnl_pct"].mean(),
        "binomial_p_one_sided": binomial_result["p_one_sided"],
    }
    all_match = True
    for name, live_value in live_fields.items():
        published_value = published.get(name)
        if published_value is None:
            continue
        all_match = all_match and abs(live_value - published_value) < 1e-6
    return all_match


# Confirmed transaction-cost constants, matching run_fee_slippage_sensitivity()'s
# PRIMARY scenario defaults exactly (5bps/side taker + 5bps/side slippage).
BENCHMARK_ROUND_TRIP_DRAG_PCT = 0.20  # strategy arm: round-trip, per trade
BENCHMARK_ONE_SIDE_DRAG_PCT = 0.10    # DCA/buy-and-hold arms: one-sided buy markup only


def _run_strategy_dollar_arm(df, trades_df, starting_capital, drag_pct=0.0):
    """
    Build a dollar-denominated strategy equity curve: starting_capital sits
    idle between trades, compounding only at each exit by that trade's
    (optionally drag-adjusted) pnl_pct.

    Statistical/analytical question answered: none -- equity-curve
    construction for run_benchmark_vs_passive(). Ported from
    analysis/benchmark_vs_passive.py's strategy_arm().
    """
    n_bars = len(df)
    adjusted_trades = trades_df.copy()
    if drag_pct:
        adjusted_trades["pnl_pct"] = adjusted_trades["pnl_pct"] - drag_pct

    total_return_pct = adjusted_trades["pnl_pct"].sum()
    hold_bars_sum = adjusted_trades["hold_bars"].sum()
    time_in_market_pct = hold_bars_sum / n_bars * 100

    equity = np.full(n_bars, np.nan)
    equity[0] = starting_capital
    running_equity = starting_capital
    exit_pnl_by_bar = dict(zip(adjusted_trades["exit_idx"].astype(int), adjusted_trades["pnl_pct"]))
    for i in range(1, n_bars):
        if i in exit_pnl_by_bar:
            running_equity *= (1 + exit_pnl_by_bar[i] / 100)
        equity[i] = running_equity
    equity = pd.Series(equity)
    bar_returns = equity.pct_change().dropna()
    sharpe, sortino = sharpe_sortino_ratios(bar_returns, PERIODS_PER_YEAR_4H_BARS)

    return {
        "arm": "OB-gated strategy", "total_return_pct": total_return_pct,
        # final_capital is the REAL final value of the compounded, sequential
        # equity curve -- NOT back-derived from total_return_pct. The two can
        # differ very slightly since total_return_pct is a simple sum of
        # pnl_pct (matching the locked headline convention) while the equity
        # curve compounds multiplicatively; shown separately, not reconciled.
        "final_capital": float(equity.iloc[-1]), "sharpe": sharpe, "sortino": sortino,
        "max_drawdown_pct": max_drawdown_pct(equity), "time_in_market_pct": time_in_market_pct,
        "starting_capital": starting_capital,
    }


def _run_dca_dollar_arm(df, starting_capital, drag_pct=0.0):
    """
    Build a dollar-denominated weekly-DCA-into-BTC equity curve:
    starting_capital split evenly across every ISO week, bought at that
    week's first-bar CLOSE price.

    Ported from analysis/benchmark_vs_passive.py's dca_arm().
    """
    n_bars = len(df)
    close = df["close"].values
    contribution_bars = _iso_week_first_bars(df)
    n_weeks = len(contribution_bars)
    contribution = starting_capital / n_weeks
    contribution_bar_set = set(contribution_bars.tolist())

    units = 0.0
    value = np.empty(n_bars)
    contribution_by_bar = np.zeros(n_bars)
    for i in range(n_bars):
        price = close[i]
        if i in contribution_bar_set:
            buy_price = price * (1 + drag_pct / 100)  # one-sided fee+slippage markup
            units += contribution / buy_price
            contribution_by_bar[i] = contribution
        value[i] = units * price

    value_at_contributions = value[contribution_bars]
    contribution_at_contributions = contribution_by_bar[contribution_bars]
    period_returns = np.empty(len(value_at_contributions) - 1)
    for k in range(1, len(value_at_contributions)):
        period_returns[k - 1] = (value_at_contributions[k] - contribution_at_contributions[k]) / value_at_contributions[k - 1] - 1.0
    sharpe, sortino = sharpe_sortino_ratios(period_returns, PERIODS_PER_YEAR_WEEKLY)

    total_contributed = float(np.cumsum(contribution_at_contributions)[-1])
    final_value = float(value_at_contributions[-1])
    return {
        "arm": "Weekly DCA into BTC", "total_return_pct": (final_value - total_contributed) / total_contributed * 100,
        "final_capital": final_value, "sharpe": sharpe, "sortino": sortino,
        "max_drawdown_pct": max_drawdown_pct(pd.Series(value_at_contributions)), "time_in_market_pct": 100.0,
        "starting_capital": starting_capital, "n_contributions": int(n_weeks), "contribution_per_week": contribution,
    }


def _run_lump_sum_dollar_arm(df, starting_capital, drag_pct=0.0):
    """
    Build a dollar-denominated lump-sum buy-and-hold equity curve:
    starting_capital deployed entirely at the window's first bar's OPEN
    price, held to the window's last bar's close.

    Ported from analysis/benchmark_vs_passive.py's lump_sum_arm().
    """
    entry_price = df["open"].iloc[0] * (1 + drag_pct / 100)  # one-sided fee+slippage markup
    units = starting_capital / entry_price
    equity = units * df["close"]
    total_return_pct = (equity.iloc[-1] - starting_capital) / starting_capital * 100
    sharpe, sortino = sharpe_sortino_ratios(equity.pct_change().dropna(), PERIODS_PER_YEAR_4H_BARS)
    return {
        "arm": "Lump-sum buy-and-hold", "total_return_pct": total_return_pct,
        "final_capital": float(equity.iloc[-1]), "sharpe": sharpe, "sortino": sortino,
        "max_drawdown_pct": max_drawdown_pct(equity), "time_in_market_pct": 100.0,
        "starting_capital": starting_capital,
    }


def run_benchmark_vs_passive(df_main, trades_main, df_formulation, trades_formulation, starting_capital=10000.0):
    """
    Head-to-head, dollar-denominated benchmark: OB-gated strategy vs. weekly
    DCA into BTC vs. lump-sum buy-and-hold, same starting capital per arm,
    computed for two windows (the locked 2022-2026 baseline, and the
    2018-2022 formulation period).

    Statistical/analytical question answered: "in real dollar terms, how
    does the strategy's terminal value compare to two standard passive BTC
    exposure strategies, over both the locked evaluation window and the
    period the rules were originally formulated against?" Purely
    descriptive/comparative, not a hypothesis test.

    Ported from analysis/benchmark_vs_passive.py. GROSS vs. FEE-ADJUSTED:
    the locked +30.31% headline is GROSS (no fee/slippage modeled anywhere
    in simulate_trades()), so the PRIMARY tables here are gross for a true
    apples-to-apples comparison against that published figure. A separate
    fee-adjusted table (main window only) applies
    BENCHMARK_ROUND_TRIP_DRAG_PCT (0.20%, matching
    run_fee_slippage_sensitivity()'s confirmed PRIMARY scenario) to the
    strategy arm, and BENCHMARK_ONE_SIDE_DRAG_PCT (0.10%, one-sided --
    these arms are held, not round-tripped, within the window) to the DCA
    and lump-sum arms.

    Parameters
    ----------
    df_main, trades_main : the locked 2022-2026 window's candles/trades.
    df_formulation, trades_formulation : the 2018-2022 formulation window's
        candles/trades (see load_formulation_period_window()).
    starting_capital : float, default 10000.0
        Total capital per arm, per window -- a clean round number, not tied
        to any real position-sizing model (the strategy's own trades are
        pure percentage returns).

    Returns
    -------
    dict
        main_window {gross: [3 arms], fee_adjusted: [3 arms]},
        formulation_period_window {gross: [3 arms]}.
    """
    main_gross = [
        _run_strategy_dollar_arm(df_main, trades_main, starting_capital),
        _run_dca_dollar_arm(df_main, starting_capital),
        _run_lump_sum_dollar_arm(df_main, starting_capital),
    ]
    main_fee_adjusted = [
        _run_strategy_dollar_arm(df_main, trades_main, starting_capital, drag_pct=BENCHMARK_ROUND_TRIP_DRAG_PCT),
        _run_dca_dollar_arm(df_main, starting_capital, drag_pct=BENCHMARK_ONE_SIDE_DRAG_PCT),
        _run_lump_sum_dollar_arm(df_main, starting_capital, drag_pct=BENCHMARK_ONE_SIDE_DRAG_PCT),
    ]
    formulation_gross = [
        _run_strategy_dollar_arm(df_formulation, trades_formulation, starting_capital),
        _run_dca_dollar_arm(df_formulation, starting_capital),
        _run_lump_sum_dollar_arm(df_formulation, starting_capital),
    ]

    return {
        "starting_capital": starting_capital,
        "main_window": {
            "label": MAIN_WINDOW_LABEL, "window_start": str(df_main["open_time"].iloc[0]),
            "window_end": str(df_main["open_time"].iloc[-1]), "gross": main_gross, "fee_adjusted": main_fee_adjusted,
        },
        "formulation_period_window": {
            "label": FORMULATION_WINDOW_LABEL, "window_start": str(df_formulation["open_time"].iloc[0]),
            "window_end": str(df_formulation["open_time"].iloc[-1]), "gross": formulation_gross,
        },
    }


def build_trades_and_results_table(df, trades_df):
    """
    Assemble the full per-trade table (sorted by entry_idx, with resolved
    entry_time/exit_time) and the extended results summary (adds
    Wins/Losses/SD/binomial p to the base trade_stats dict) for one window.

    Statistical/analytical question answered: none directly for the trades
    table (a data product); results_table extends the base summary with
    binomial_test() -- the same one-sample test as elsewhere in this file,
    applied here for a complete standalone summary of any given window.

    Ported from analysis/export_trades_and_results.py's trades_table() and
    results_table(). NOTE: the original script also includes an extensive
    read-only diagnostic cross-check (compute_ob_criteria_diagnostics() /
    verify_ob_criteria_diagnostics()) that reimplements each OB quality
    criterion's underlying NUMERIC values from raw price/volume data and
    diffs the resulting booleans against the ones already computed in
    compute_smc(), as a second independent check that compute_smc()'s
    criteria are internally consistent. That ~150-line diagnostic
    recomputation is OMITTED here as out of scope for a file focused on the
    paper's statistical methodology -- it duplicates compute_smc()'s own
    logic for engineering-verification purposes rather than adding a new
    analytical result. See analysis/export_trades_and_results.py directly
    if that cross-check is needed.

    Parameters
    ----------
    df : pandas.DataFrame
        Candle data for the window (needs 'open_time').
    trades_df : pandas.DataFrame
        Trade log for the window.

    Returns
    -------
    tuple of (pandas.DataFrame, dict)
        (trades_table, results_summary). results_summary keys: Total
        Trades, Wins, Losses, Win Rate (%), Total Net Return (%), Avg
        Return/Trade (%), SD (Return/Trade %), Binomial p (one-sided),
        Binomial p (two-sided).
    """
    trades_table = trades_df.sort_values("entry_idx").reset_index(drop=True).copy()
    trades_table["entry_time"] = df.loc[trades_table["entry_idx"].astype(int), "open_time"].values
    trades_table["exit_time"] = df.loc[trades_table["exit_idx"].astype(int), "open_time"].values

    n = len(trades_df)
    wins = int((trades_df["pnl_pct"] > 0).sum())
    binomial_result = binomial_test(wins, n) if n else {"p_one_sided": float("nan"), "p_two_sided": float("nan")}
    results_summary = {
        "Total Trades": n, "Wins": wins, "Losses": n - wins,
        "Win Rate (%)": (wins / n * 100) if n else float("nan"),
        "Total Net Return (%)": trades_df["pnl_pct"].sum(), "Avg Return/Trade (%)": trades_df["pnl_pct"].mean(),
        "SD (Return/Trade %)": trades_df["pnl_pct"].std(ddof=1) if n > 1 else float("nan"),
        "Binomial p (one-sided)": binomial_result["p_one_sided"], "Binomial p (two-sided)": binomial_result["p_two_sided"],
    }
    return trades_table, results_summary


# ============================================================================
# SECTION 6: DASHBOARD ARTIFACT EXPORT + DATABASE PERSISTENCE
# ============================================================================
# Consolidated from export_gui_data.py (now retired to
# legacy_pre_consolidation/). Computes the same JSON/CSV artifact files and
# SQL database rows dashboard-v2 and the Section 7 HTTP server depend on --
# same file paths, same schema, same column sets -- so dashboard-v2's
# frontend code needs zero changes. Two simplifications versus the original,
# both disclosed:
#   1. `db_manager.X` calls become direct calls to Section 1B's Candle/
#      OrderBlock/OBTouch/Trade/init_db/get_session/clear_db -- same
#      schema, no behavior change, just no more separate-module indirection.
#   2. The three Google Sheets pushes and the four statistical-artifact
#      JSON files were previously computed by shelling out to analysis/*.py
#      scripts as subprocesses and round-tripping through a JSON file. They
#      are now computed in-process by calling this file's own Section 4/5B
#      functions directly (run_benchmark_vs_passive(), build_trades_and_
#      results_table(), run_bootstrap_ci(), etc.) -- same figures, no
#      subprocess/file round-trip. Every push remains non-fatal: a failure
#      in one is reported and skipped, never aborts the rest.

SCHEMA_VERSION = "1.0.0"
DEFAULT_ARTIFACT_LEVELS = [0, 1, 2, 3]


def to_native(value):
    """
    Convert a single numpy/pandas scalar to its native Python equivalent,
    passing through everything else (including strings/dicts) unchanged.

    Statistical question answered: none -- serialization utility. Distinct
    from json_safe() (Section 1): json_safe() stringifies anything it
    doesn't recognize (safe as a json.dump default=), while to_native() is
    used per-cell while building a plain Python dict of trade/candle
    records, where an unrecognized type should pass through untouched, not
    become a string.
    """
    if pd.isna(value):
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def normalize_records(records):
    """Apply to_native() to every value in a list of dict records (e.g. from
    DataFrame.to_dict(orient="records"))."""
    return [{key: to_native(value) for key, value in row.items()} for row in records]


def hash_payload(payload):
    """SHA-256 of a canonical (sorted-keys, no whitespace) JSON encoding of
    `payload` -- used by build_verification_report() so a reader can confirm
    two independently-generated exports produced byte-identical data
    without diffing the full payload."""
    canonical = json.dumps(payload, sort_keys=True, default=json_safe, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_artifact_manifest(symbol, timeframe, start, end, levels, candle_count):
    """Top-level manifest.json content: run parameters + candle count.
    Read directly by dashboard-v2 (GET /artifacts/manifest.json)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": timeframe,
        "start_time": start,
        "end_time": end,
        "levels": levels,
        "candle_count": candle_count,
    }


def build_verification_report(manifest, candles, runs_by_threshold):
    """
    Build verification_report.json: source-data sanity checks (symbol/
    timeframe match, candle presence, date range) plus SHA-256 hashes of the
    OHLC series, indicator series, and each quality-threshold's Order-Block/
    trade/stats payload -- so a reader (or a future run) can confirm
    deterministic reproduction without re-diffing the full data.

    Statistical question answered: none -- data-integrity/reproducibility
    check, not an analysis.
    """
    ohlc_payload = [
        {"time": c["time"], "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"]}
        for c in candles
    ]
    indicator_payload = [
        {"time": c["time"], "MACD": c["MACD"], "MACD_signal": c["MACD_signal"], "MACD_hist": c["MACD_hist"],
         "K": c["K"], "D": c["D"], "J": c["J"], "ATR": c["ATR"], "ATR_200": c["ATR_200"]}
        for c in candles
    ]

    run_hashes = {}
    for level, run in runs_by_threshold.items():
        run_hashes[str(level)] = {
            "orderblocks_hash": hash_payload(run["obs"]),
            "trades_hash": hash_payload(run["trades"]),
            "stats_hash": hash_payload(run["stats"]),
        }

    return {
        "status": "pass",
        "notes": [
            "TradingView alignment target: BTCUSDT Binance 4H candles.",
            "Cross-source TradingView API pull is not used; this report validates deterministic "
            "Binance snapshot + recalculation consistency.",
        ],
        "source_checks": {
            "symbol_match": manifest["symbol"] == "BTCUSDT",
            "timeframe_match": manifest["timeframe"] == "4h",
            "has_candles": len(candles) > 0,
            "first_candle_utc": datetime.fromtimestamp(candles[0]["time"], timezone.utc).isoformat() if candles else None,
            "last_candle_utc": datetime.fromtimestamp(candles[-1]["time"], timezone.utc).isoformat() if candles else None,
        },
        "snapshot_hashes": {
            "ohlc_hash": hash_payload(ohlc_payload),
            "indicator_hash": hash_payload(indicator_payload),
        },
        "recalculation_hashes_by_threshold": run_hashes,
    }


def export_dashboard_artifacts(symbol="BTCUSDT", timeframe="4h", start="2022-01-01 00:00:00",
                                end="2026-01-01 00:00:00", levels=None, default_view_quality=1,
                                output_dir="artifacts", db_url=None, export_gsheet=False):
    """
    Full dashboard-artifact export: pull (or load cached) candles, compute
    indicators, run simulate_trades() at every requested min_ob_quality
    threshold, write every JSON/CSV artifact dashboard-v2 and Section 7's
    HTTP server read, and persist candles/Order-Blocks/touches/trades to the
    SQL database. Optionally also pushes to Google Sheets.

    Statistical question answered: none directly -- this is the export/
    persistence step; simulate_trades() (Section 3) does the actual
    backtesting.

    Ported from export_gui_data.py's export_artifacts(), flattened from an
    argparse Namespace into explicit parameters to match this file's style.

    Parameters
    ----------
    symbol, timeframe : str
    start, end : str
        Passed to get_candles() if a live pull is attempted.
    levels : list of int, optional
        min_ob_quality thresholds to simulate. Defaults to [0, 1, 2, 3].
    default_view_quality : int, default 1
        Which threshold's Trade_Status populates candles.json's default view.
    output_dir : str, default "artifacts"
    db_url : str, optional
        Defaults to get_db_url() (Section 1B).
    export_gsheet : bool, default False
        Also push to Google Sheets via push_all_gsheet_exports().

    Returns
    -------
    (manifest: dict, threshold_runs: list, verification_report: dict)
    """
    if levels is None:
        levels = list(DEFAULT_ARTIFACT_LEVELS)
    interval_map = {"4h": Client.KLINE_INTERVAL_4HOUR}
    if timeframe not in interval_map:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    print("Fetching candles...")
    try:
        base_df = get_candles(symbol=symbol, interval=interval_map[timeframe], start_time=start, end_time=end)
    except Exception as e:
        print(f"Warning: Failed to fetch candles from API ({e}). Attempting to load from local cache...")
        cache_path = os.path.join(output_dir, "candles.csv")
        if os.path.isfile(cache_path):
            base_df = pd.read_csv(cache_path)
            base_df["open_time"] = pd.to_datetime(base_df["open_time"])
        else:
            raise FileNotFoundError(f"No local candles cache found at {cache_path} and API connection failed.")

    print("Computing indicators...")
    base_df = compute_indicators(base_df)
    base_df["time"] = base_df["open_time"].apply(lambda x: int(x.timestamp()))

    candle_cols = ["time", "open_time", "open", "high", "low", "close", "volume",
                   "MACD", "MACD_signal", "MACD_hist", "K", "D", "J", "ATR", "ATR_200", "Trade_Status"]

    runs_by_threshold = {}
    threshold_runs = []
    sim_dfs = {}
    for level in levels:
        print(f"Running simulation for min_ob_quality={level}...")
        sim_df = simulate_trades(base_df.copy(), min_ob_quality=level)
        sim_dfs[level] = sim_df
        stats = sim_df.attrs.get("trade_stats", {})
        trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
        obs = compute_smc(sim_df)
        trades = normalize_records(trades_df.to_dict(orient="records")) if not trades_df.empty else []
        obs = normalize_records(obs)
        stats = {k: to_native(v) for k, v in stats.items()}

        runs_by_threshold[level] = {"obs": obs, "trades": trades, "stats": stats}
        threshold_runs.append({
            "min_quality": level, "trade_stats": stats,
            "trade_count": len(trades), "orderblock_count": len(obs),
        })

    if default_view_quality in sim_dfs:
        base_df["Trade_Status"] = sim_dfs[default_view_quality]["Trade_Status"]
    else:
        base_df["Trade_Status"] = ""
    base_df["Trade_Status"] = base_df["Trade_Status"].fillna("")

    candles = normalize_records(base_df[candle_cols].to_dict(orient="records"))

    manifest = build_artifact_manifest(symbol, timeframe, start, end, levels, len(candles))
    verification_report = build_verification_report(manifest, candles, runs_by_threshold)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=json_safe)
    with open(os.path.join(output_dir, "candles.json"), "w", encoding="utf-8") as f:
        json.dump(candles, f, indent=2, default=json_safe)
    with open(os.path.join(output_dir, "threshold_runs.json"), "w", encoding="utf-8") as f:
        json.dump(threshold_runs, f, indent=2, default=json_safe)
    with open(os.path.join(output_dir, "runs_by_threshold.json"), "w", encoding="utf-8") as f:
        json.dump(runs_by_threshold, f, indent=2, default=json_safe)
    with open(os.path.join(output_dir, "verification_report.json"), "w", encoding="utf-8") as f:
        json.dump(verification_report, f, indent=2, default=json_safe)

    candles_df = pd.DataFrame(candles)
    candles_df.to_csv(os.path.join(output_dir, "candles.csv"), index=False)
    pd.DataFrame(threshold_runs).to_csv(os.path.join(output_dir, "threshold_runs.csv"), index=False)
    default_run = runs_by_threshold.get(default_view_quality, runs_by_threshold[levels[0]])
    pd.DataFrame(default_run["trades"]).to_csv(os.path.join(output_dir, "trades_default_view.csv"), index=False)
    pd.DataFrame(default_run["obs"]).to_csv(os.path.join(output_dir, "orderblocks_default_view.csv"), index=False)

    # --- Database export -----------------------------------------------
    print("Connecting to SQL database...")
    resolved_db_url = db_url if db_url else get_db_url()
    try:
        engine = init_db(resolved_db_url)
        clear_db(engine)  # Fresh run, clear old values
        session = get_session(engine)

        print("Saving candles to database...")
        candles_to_save = []
        for _, row in base_df.iterrows():
            candles_to_save.append(Candle(
                time=int(row["time"]), symbol=symbol, interval=timeframe,
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                close=float(row["close"]), volume=float(row["volume"]),
                macd=float(row["MACD"]) if pd.notnull(row["MACD"]) else None,
                macd_signal=float(row["MACD_signal"]) if pd.notnull(row["MACD_signal"]) else None,
                macd_hist=float(row["MACD_hist"]) if pd.notnull(row["MACD_hist"]) else None,
                k=float(row["K"]) if pd.notnull(row["K"]) else None,
                d=float(row["D"]) if pd.notnull(row["D"]) else None,
                j=float(row["J"]) if pd.notnull(row["J"]) else None,
                atr_14=float(row["ATR"]) if pd.notnull(row["ATR"]) else None,
                atr_200=float(row["ATR_200"]) if pd.notnull(row["ATR_200"]) else None,
                volume_ma_ratio=float(row["volume_ma_ratio"]) if pd.notnull(row.get("volume_ma_ratio")) else None,
                taker_buy_ratio=float(row["taker_buy_ratio"]) if pd.notnull(row.get("taker_buy_ratio")) else None,
                body_wick_ratio=float(row["body_wick_ratio"]) if pd.notnull(row.get("body_wick_ratio")) else None,
                time_hour=int(row["time_hour"]) if pd.notnull(row.get("time_hour")) else None,
                time_day_of_week=int(row["time_day_of_week"]) if pd.notnull(row.get("time_day_of_week")) else None,
            ))
        session.bulk_save_objects(candles_to_save)
        session.commit()

        print("Saving order blocks to database...")
        first_level = levels[0]
        obs_raw = compute_smc(sim_dfs[first_level])

        ob_lookup = {}
        for ob in obs_raw:
            ob_model = OrderBlock(
                symbol=symbol, interval=timeframe, type=ob["type"],
                top=float(ob["top"]), bottom=float(ob["bottom"]),
                created_at=int(ob["created_at"]), ob_bar=int(ob["ob_bar"]),
                level=ob["level"], structure=ob["structure"],
                mitigated_at=int(ob["mitigated_at"]) if (pd.notnull(ob.get("mitigated_at")) and ob["mitigated_at"] < len(base_df)) else None,
                quality=int(ob["quality"]),
                quality_displacement=bool(ob.get("quality_displacement", False)),
                quality_large_bar=bool(ob.get("quality_large_bar", False)),
                quality_fvg=bool(ob.get("quality_fvg", False)),
                quality_liquidity_sweep=bool(ob.get("quality_liquidity_sweep", False)),
                quality_volume_expansion=bool(ob.get("quality_volume_expansion", False)),
            )
            session.add(ob_model)
            session.flush()  # Flush to generate ob_id
            ob_lookup[(ob["created_at"], ob["ob_bar"], ob["type"], ob["level"])] = ob_model.ob_id
        session.commit()

        print("Saving OB touch events to database...")
        touches_df = sim_dfs[first_level].attrs.get("touches_df", pd.DataFrame())
        if not touches_df.empty:
            touches_to_save = []
            for _, touch in touches_df.iterrows():
                ob_key = (int(touch["ob_created_at"]), int(touch["ob_bar"]), touch["ob_type"], touch["ob_level"])
                ob_id = ob_lookup.get(ob_key)
                if ob_id is None:
                    continue
                touches_to_save.append(OBTouch(
                    ob_id=ob_id, time=int(touch["time"]), touch_price=float(touch["touch_price"]),
                    macd=float(touch["macd"]) if pd.notnull(touch["macd"]) else None,
                    macd_signal=float(touch["macd_signal"]) if pd.notnull(touch["macd_signal"]) else None,
                    macd_hist=float(touch["macd_hist"]) if pd.notnull(touch["macd_hist"]) else None,
                    k=float(touch["k"]) if pd.notnull(touch["k"]) else None,
                    d=float(touch["d"]) if pd.notnull(touch["d"]) else None,
                    j=float(touch["j"]) if pd.notnull(touch["j"]) else None,
                    k_accel=float(touch["k_accel"]) if pd.notnull(touch["k_accel"]) else None,
                    atr_14=float(touch["atr_14"]) if pd.notnull(touch["atr_14"]) else None,
                    atr_200=float(touch["atr_200"]) if pd.notnull(touch["atr_200"]) else None,
                ))
            session.bulk_save_objects(touches_to_save)
            session.commit()

        print("Saving trades to database...")
        trades_to_save = []
        for level in levels:
            trades_df = sim_dfs[level].attrs.get("trades_df", pd.DataFrame())
            if trades_df.empty:
                continue
            for _, tr in trades_df.iterrows():
                entry_key = (int(tr["entry_ob_created_at"]), int(tr["entry_ob_bar"]), tr["entry_ob_type"], tr["entry_ob_level"])
                entry_ob_id = ob_lookup.get(entry_key)
                if entry_ob_id is None:
                    continue
                tp_ob_id = None
                if tr.get("tp_is_structural") and pd.notnull(tr.get("tp_ob_created_at")):
                    tp_key = (int(tr["tp_ob_created_at"]), int(tr["tp_ob_bar"]), tr["tp_ob_type"], tr["tp_ob_level"])
                    tp_ob_id = ob_lookup.get(tp_key)
                trades_to_save.append(Trade(
                    symbol=symbol, interval=timeframe, side=tr["side"], min_ob_quality=int(level),
                    entry_time=int(base_df.loc[int(tr["entry_idx"]), "time"]),
                    exit_time=int(base_df.loc[int(tr["exit_idx"]), "time"]),
                    entry_price=float(tr["entry"]), exit_price=float(tr["exit"]),
                    stop_loss=float(tr["stop_loss"]), take_profit=float(tr["take_profit"]),
                    pnl_pct=float(tr["pnl_pct"]), hold_bars=int(tr["hold_bars"]), exit_reason=tr["exit_reason"],
                    entry_ob_id=entry_ob_id, tp_ob_id=tp_ob_id,
                ))
        if trades_to_save:
            session.bulk_save_objects(trades_to_save)
            session.commit()

        print("Database save completed successfully.")
    except Exception as e:
        import traceback
        print(f"Warning: Failed to save results to database ({e})")
        traceback.print_exc()

    if export_gsheet:
        print("Exporting to Google Sheets (optional mode)...")
        push_all_gsheet_exports(output_dir)

    return manifest, threshold_runs, verification_report


def push_all_gsheet_exports(output_dir="artifacts"):
    """
    Compute and push all three Google Sheets exports (candles, trades+
    results, benchmark-vs-passive) in-process, using this file's own
    Section 3B push_*_to_gsheet() writers and Section 4/5B analysis
    functions directly -- no subprocess, no intermediate JSON file, unlike
    the export_gui_data.py pipeline this replaces (which shelled out to
    analysis/*.py scripts and read their --json-out files back in). Each
    push is independent and non-fatal: a failure in one is reported and
    skipped, never aborts the others.
    """
    df_main = compute_indicators(load_candles())
    df_formulation = compute_indicators(load_formulation_period_window())
    sim_main = simulate_trades(df_main.copy(), min_ob_quality=0)
    sim_form = simulate_trades(df_formulation.copy(), min_ob_quality=0)
    trades_main = sim_main.attrs["trades_df"]
    trades_form = sim_form.attrs["trades_df"]

    try:
        candles_result = {
            "main_window": {"label": MAIN_WINDOW_LABEL,
                             "rows": _format_df_for_export_full(sim_main).to_dict(orient="records")},
            "formulation_period_window": {"label": FORMULATION_WINDOW_LABEL,
                                           "rows": _format_df_for_export_full(sim_form).to_dict(orient="records")},
        }
        push_candles_to_gsheet(candles_result)
    except Exception as e:
        print(f"\n[WARNING] Skipping candle-level gsheet push: {e}")

    try:
        main_trades_table, main_results = build_trades_and_results_table(df_main, trades_main)
        form_trades_table, form_results = build_trades_and_results_table(df_formulation, trades_form)
        export_result = {
            "main_window": {
                "label": MAIN_WINDOW_LABEL, "window_start": str(df_main["open_time"].iloc[0]),
                "window_end": str(df_main["open_time"].iloc[-1]),
                "trades": main_trades_table.to_dict(orient="records"), "results": main_results,
            },
            "formulation_period_window": {
                "label": FORMULATION_WINDOW_LABEL, "window_start": str(df_formulation["open_time"].iloc[0]),
                "window_end": str(df_formulation["open_time"].iloc[-1]),
                "trades": form_trades_table.to_dict(orient="records"), "results": form_results,
            },
        }
        push_trades_and_results_to_gsheet(export_result)
    except Exception as e:
        print(f"\n[WARNING] Skipping trades+results gsheet push: {e}")

    try:
        benchmark_result = run_benchmark_vs_passive(df_main, trades_main, df_formulation, trades_form)
        push_benchmark_vs_passive_to_gsheet(benchmark_result)
    except Exception as e:
        print(f"\n[WARNING] Skipping benchmark-vs-passive gsheet push: {e}")


def write_statistical_artifacts(df, baseline_trades, output_dir="artifacts"):
    """
    Write the same JSON artifacts export_gui_data.py's run_statistical_
    artifacts() previously produced by shelling out to bootstrap_power_
    analysis.py / fee_slippage_analysis.py / ablation_reconstruction.py /
    benchmark_vs_passive.py -- computed in-process here instead, calling
    this file's own Section 4/5B functions directly.

    Parameters
    ----------
    df : pandas.DataFrame
        Main-window candles with indicators already computed.
    baseline_trades : pandas.DataFrame
        The q>=0 baseline trade log for `df`.
    output_dir : str, default "artifacts"
    """
    write_json_results(
        {"bootstrap_ci": run_bootstrap_ci(baseline_trades), "mde_power": run_mde_power_report(baseline_trades)},
        os.path.join(output_dir, "bootstrap_power_analysis.json"),
    )
    write_json_results(
        run_fee_slippage_sensitivity(baseline_trades),
        os.path.join(output_dir, "fee_slippage_analysis.json"),
    )
    write_json_results(
        run_ablation_study(df),
        os.path.join(output_dir, "ablation_reconstruction.json"),
    )
    df_formulation = compute_indicators(load_formulation_period_window())
    sim_form = simulate_trades(df_formulation.copy(), min_ob_quality=0)
    write_json_results(
        run_benchmark_vs_passive(df, baseline_trades, df_formulation, sim_form.attrs["trades_df"]),
        os.path.join(output_dir, "benchmark_vs_passive.json"),
    )


# ============================================================================
# SECTION 7: HTTP SERVER / FRONTEND ENDPOINTS
# ============================================================================
# Consolidated from export_gui_data.py's main() (now retired to
# legacy_pre_consolidation/). Same port (8765), same route table, same
# static-file mapping for dashboard-v2/dist/ under /dashboard/ and
# artifacts/*.json under /artifacts/ -- dashboard-v2's existing
# src/api/client.ts needs ZERO changes to talk to this server instead of
# the retired one. `db_manager.X` calls become direct calls to Section 1B's
# ORM classes/session helpers.

DASHBOARD_DIST_DIR = os.path.join("dashboard-v2", "dist")


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dashboard-v2's built static assets under /dashboard/, every
    artifacts/*.json|csv file as a plain static file (Python's built-in
    static-file serving, unchanged), and the dynamic /api/* routes below."""

    def log_message(self, format, *args):
        pass

    def translate_path(self, path):
        parsed_path = urlparse(path).path
        if parsed_path in ("/dashboard", "/dashboard/"):
            return os.path.join(os.getcwd(), DASHBOARD_DIST_DIR, "index.html")
        if parsed_path.startswith("/dashboard/"):
            rel = parsed_path[len("/dashboard/"):]
            candidate = os.path.join(os.getcwd(), DASHBOARD_DIST_DIR, rel)
            if os.path.isfile(candidate):
                return candidate
            # Bare/unknown sub-path under /dashboard/ -- this app has no
            # client-side routing (tabs are React state, not URL paths), so
            # falling back to index.html here is the standard, harmless SPA
            # convention rather than a 404 on a hard reload.
            return os.path.join(os.getcwd(), DASHBOARD_DIST_DIR, "index.html")
        return super().translate_path(path)

    def do_GET(self):
        if self.path == "/api/iterations":
            self.handle_get_iterations()
        elif self.path == "/api/get_theme":
            self.handle_get_theme()
        elif self.path.startswith("/api/trades"):
            self.handle_get_trades()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/push_gsheet":
            self.handle_push_gsheet()
        elif self.path == "/api/save_theme":
            self.handle_save_theme()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_get_trades(self):
        """GET /api/trades[?min_ob_quality=N] -- live DB-backed route (not a
        static file): joins Trade to OrderBlock for the quality-criteria
        booleans dashboard-v2's Stats tab needs."""
        try:
            query_params = parse_qs(urlparse(self.path).query)
            min_ob_quality_str = query_params.get("min_ob_quality", [None])[0]
            min_ob_quality = None
            if min_ob_quality_str is not None:
                try:
                    min_ob_quality = int(min_ob_quality_str)
                except ValueError:
                    pass

            engine = init_db()
            session = get_session(engine)
            query = session.query(
                Trade, OrderBlock.quality, OrderBlock.quality_displacement, OrderBlock.quality_large_bar,
                OrderBlock.quality_fvg, OrderBlock.quality_liquidity_sweep, OrderBlock.quality_volume_expansion,
            ).join(OrderBlock, Trade.entry_ob_id == OrderBlock.ob_id)
            if min_ob_quality is not None:
                query = query.filter(Trade.min_ob_quality == min_ob_quality)
            results = query.all()

            trades_data = []
            for trade, quality, disp, lb, fvg, liq, vol in results:
                trades_data.append({
                    "trade_id": trade.trade_id, "side": trade.side, "min_ob_quality": trade.min_ob_quality,
                    "entry_time": trade.entry_time, "exit_time": trade.exit_time,
                    "entry_price": trade.entry_price, "exit_price": trade.exit_price,
                    "stop_loss": trade.stop_loss, "take_profit": trade.take_profit,
                    "pnl_pct": trade.pnl_pct, "hold_bars": trade.hold_bars, "exit_reason": trade.exit_reason,
                    "entry_ob_id": trade.entry_ob_id, "tp_ob_id": trade.tp_ob_id,
                    "quality_score": quality,
                    "quality_displacement": bool(disp) if disp is not None else False,
                    "quality_large_bar": bool(lb) if lb is not None else False,
                    "quality_fvg": bool(fvg) if fvg is not None else False,
                    "quality_liquidity_sweep": bool(liq) if liq is not None else False,
                    "quality_volume_expansion": bool(vol) if vol is not None else False,
                })
            session.close()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(trades_data, default=json_safe).encode("utf-8"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Database error: {e}")

    def handle_get_iterations(self):
        """GET /api/iterations -- synthesizes a single 'Heuristic Base'
        pseudo-iteration record from the DB's trades, for a dashboard UI
        panel that predates this project dropping its ML-iteration feature
        (see CLAUDE.md's db_manager note: the MLIteration table itself was
        already removed; this route just no longer has real iterations to
        report, so it fabricates one static baseline entry)."""
        try:
            engine = init_db()
            session = get_session(engine)
            trades = []
            try:
                trades = session.query(Trade).all()
            except Exception as e:
                print(f"Warning: failed to query trades table: {e}")

            base_metrics = {}
            for q in [0, 1, 2, 3]:
                q_trades = [t for t in trades if t.min_ob_quality == q]
                count = len(q_trades)
                pnl = sum(t.pnl_pct for t in q_trades)
                win_count = sum(1 for t in q_trades if t.pnl_pct > 0)
                wr = (win_count / count * 100) if count > 0 else 0.0
                base_metrics[f"q{q}"] = {
                    "base_trades": count, "base_pnl": pnl, "base_wr": wr,
                    "tuned_trades": count, "tuned_pnl": pnl, "tuned_wr": wr,
                }

            base_iter = {
                "iteration_id": 0, "label": "Heuristic Base (No ML)", "created_at": 1782016399,
                "model_type": "Heuristic Base",
                "parameters": {
                    "sl_ratio_min": MIN_STOP_LOSS_DISTANCE_RATIO, "kdj_j_long_cap": KDJ_J_LONG_CAP,
                    "kdj_k_long_cap": KDJ_K_LONG_CAP, "kdj_k_short_floor": KDJ_K_SHORT_FLOOR,
                    "kdj_j_short_cap": KDJ_J_SHORT_CAP, "atr_mult_exit": ATR_MULT_EXIT,
                    "atr_mult_be": ATR_MULT_BREAKEVEN, "rr_min": MIN_RISK_REWARD_RATIO,
                    "classifier_threshold": 0.5,
                },
                "metrics": base_metrics,
                "pattern_diff": {
                    "tuned_parameters": {
                        "sl_ratio_min": MIN_STOP_LOSS_DISTANCE_RATIO, "kdj_j_long_cap": KDJ_J_LONG_CAP,
                        "kdj_k_long_cap": KDJ_K_LONG_CAP, "kdj_k_short_floor": KDJ_K_SHORT_FLOOR,
                        "kdj_j_short_cap": KDJ_J_SHORT_CAP, "atr_mult_exit": ATR_MULT_EXIT,
                        "atr_mult_be": ATR_MULT_BREAKEVEN, "rr_min": MIN_RISK_REWARD_RATIO,
                    },
                    "pnl_improvement_pct": 0.0, "reweighted_failures_count": 0,
                },
            }
            session.close()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([base_iter]).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Database error: {e}")

    def handle_get_theme(self):
        try:
            theme_path = "chart_theme.json"
            if os.path.isfile(theme_path):
                with open(theme_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {
                    "pageTheme": "light",
                    "dataColors": {
                        "candleUp": "#26a69a", "candleDown": "#ef5350", "candleWick": "#475569",
                        "demand": "#0d9488", "supply": "#ea580c", "macd": "#1d4ed8", "macdSignal": "#f97316",
                        "macdHist": "#10b981", "kdjK": "#0d9488", "kdjD": "#3b82f6", "kdjJ": "#ec4899",
                        "atr14": "#8b5cf6", "atr200": "#6b7280",
                    },
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Error getting theme: {e}")

    def handle_save_theme(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            with open("chart_theme.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Error saving theme: {e}")

    def handle_push_gsheet(self):
        try:
            print("[Dashboard Server] Exporting to Google Sheets...")
            push_all_gsheet_exports("artifacts")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "Success", "message": "Google Sheets updated."}).encode("utf-8"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Google Sheets Sync failed: {e}")


def run_dashboard_server(host=None, port=8765, open_browser=True):
    """
    Start the dashboard HTTP server (Section 7) on a background thread and
    block, printing the URL and opening a browser tab unless suppressed.

    Parameters
    ----------
    host : str, optional
        Defaults to the DASHBOARD_HOST env var, or "127.0.0.1" (loopback-
        only, so a native run isn't reachable from the LAN). The Dockerfile
        sets DASHBOARD_HOST=0.0.0.0 -- a container's loopback interface is
        not what `docker run -p` forwards host traffic to.
    port : int, default 8765
    open_browser : bool, default True
    """
    if host is None:
        host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")

    print(f"\n[Dashboard] Starting local web server on http://{host}:{port} ...")

    def serve():
        with ThreadingHTTPServer((host, port), DashboardRequestHandler) as httpd:
            httpd.serve_forever()

    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()

    dashboard_index = os.path.join(DASHBOARD_DIST_DIR, "index.html")
    if not os.path.isfile(dashboard_index):
        print(
            f"\n[ERROR] {dashboard_index} not found -- the dashboard hasn't been built.\n"
            f"  Run: cd dashboard-v2 && npm run build\n"
            f"  The API server is still running on http://{host}:{port}/ for debugging, "
            f"but no browser window will open."
        )
    elif not open_browser:
        print(f"[Dashboard] Server ready at http://{host}:{port}/dashboard/ (browser suppressed)")
    else:
        url = f"http://{host}:{port}/dashboard/"
        print(f"[Dashboard] Opening dashboard in browser: {url}")
        webbrowser.open(url)

    print("\nPress Ctrl+C to stop the server and exit.")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nExiting.")


# ============================================================================
# SECTION 8: MAIN EXECUTION BLOCK
# ============================================================================

def run_full_analysis_pipeline(include_oos_live=False, bootstrap_resamples=10000, seed=42, json_out=None):
    """
    Run the entire research pipeline end to end: load data, run the OB-gated
    baseline backtest, run the three-arm ablation study, then run every
    statistical analysis in Section 5/5b against the baseline trade log, and
    print a summary of every headline figure.

    Offline by default: every step here runs against the committed
    artifacts/candles.csv and artifacts/candles_extended.json snapshots. The
    one disclosed exception -- run_forward_oos_validation()'s live Binance
    pull -- only runs if `include_oos_live=True` (CLI: --include-oos-live).

    Parameters
    ----------
    include_oos_live : bool, default False
        Whether to run the live-network forward-OOS validation section.
    bootstrap_resamples : int, default 10000
        B for the canonical baseline bootstrap CI.
    seed : int, default 42
    json_out : str or None
        Optional path to write every section's results as one JSON file.

    Returns
    -------
    dict
        Every section's results, keyed by section name.
    """
    results = {}

    print("=" * 100)
    print("  research_analysis.py -- full pipeline run")
    print("=" * 100)

    print("\n[1/10] Loading candles and computing indicators...")
    df = load_candles()
    df = compute_indicators(df)

    print("[2/10] Running OB-gated baseline backtest (min_ob_quality=0)...")
    baseline_sim = simulate_trades(df.copy(), min_ob_quality=0)
    baseline_trades = baseline_sim.attrs["trades_df"]
    baseline_stats = baseline_sim.attrs["trade_stats"]
    assert baseline_stats["Total Trades"] == LOCKED_BASELINE_TRADE_COUNT, (
        f"Baseline trade count changed: expected {LOCKED_BASELINE_TRADE_COUNT}, "
        f"got {baseline_stats['Total Trades']}. This is a correctness finding -- stop and report it."
    )
    report_stat(
        "Baseline OB-gated backtest (min_ob_quality=0)",
        inputs={"min_ob_quality": 0, "n_bars": len(df)},
        outputs={
            "total_trades": baseline_stats["Total Trades"],
            "win_rate_pct": baseline_stats["Win Rate (%)"],
            "total_net_return_pct": baseline_stats["Total Net Return (%)"],
            "avg_return_per_trade_pct": baseline_stats["Avg Return/Trade (%)"],
            "sd_return_pct": baseline_trades["pnl_pct"].std(),
        },
    )
    results["baseline"] = baseline_stats

    print("[3/10] Running the three-arm ablation study...")
    results["ablation"] = run_ablation_study(df, bootstrap_resamples=2000, seed=seed)

    print("[4/10] Running core statistical tests on the baseline...")
    baseline_wins = int((baseline_trades["pnl_pct"] > 0).sum())
    binomial_result = binomial_test(baseline_wins, len(baseline_trades))
    report_stat(
        "Binomial test (q>=0 baseline win rate vs. 50% null)",
        inputs={"win_count": baseline_wins, "trade_count": len(baseline_trades), "null_win_probability": 0.5},
        outputs={"p_one_sided": binomial_result["p_one_sided"], "p_two_sided": binomial_result["p_two_sided"]},
    )
    criteria_significance = run_criteria_significance_tests(baseline_trades)
    for name, r in criteria_significance.items():
        report_stat(
            f"Per-criterion significance: {name}",
            inputs={"criterion": name, "true_n": r["true_n"], "true_wins": r["true_wins"],
                    "false_n": r["false_n"], "false_wins": r["false_wins"]},
            outputs={"fisher_p": r["fisher_p"], "welch_t": r["welch_t"], "welch_p": r["welch_p"]},
        )
    bootstrap_ci = run_bootstrap_ci(baseline_trades, bootstrap_resamples, seed)
    report_stat(
        "Bootstrap 95% CI on baseline total/avg return",
        inputs={"n_trades": len(baseline_trades), "bootstrap_resamples": bootstrap_resamples, "seed": seed},
        outputs={
            "total_return_ci_low_pct": bootstrap_ci["total_return_ci_pct"][0],
            "total_return_ci_high_pct": bootstrap_ci["total_return_ci_pct"][1],
            "avg_return_ci_low_pct": bootstrap_ci["avg_return_ci_pct"][0],
            "avg_return_ci_high_pct": bootstrap_ci["avg_return_ci_pct"][1],
        },
    )
    mde_report = run_mde_power_report(baseline_trades)
    pearson_result = pearson_correlation(baseline_trades["hold_bars"].values, baseline_trades["pnl_pct"].values)
    spearman_result = spearman_correlation(baseline_trades["hold_bars"].values, baseline_trades["pnl_pct"].values)
    report_stat(
        "hold_bars vs. pnl_pct correlation (baseline trades)",
        inputs={"n_trades": len(baseline_trades)},
        outputs={
            "pearson_r": pearson_result["r"], "pearson_p_value": pearson_result["p_value"],
            "spearman_rho": spearman_result["rho"], "spearman_p_value": spearman_result["p_value"],
        },
    )
    results["statistical_tests"] = {
        "binomial": binomial_result, "criteria_significance": criteria_significance,
        "bootstrap_ci": bootstrap_ci, "mde_power": mde_report,
        "hold_bars_vs_pnl_correlation": {"pearson": pearson_result, "spearman": spearman_result},
    }

    print("[5/10] Running benchmark vs. buy-and-hold...")
    benchmark_vs_bh = run_benchmark_vs_buy_and_hold(df, baseline_trades)
    report_stat(
        "Strategy vs. buy-and-hold benchmark",
        inputs={"n_trades": len(baseline_trades), "n_bars": len(df)},
        outputs={
            **{f"strategy_{k}": v for k, v in benchmark_vs_bh["strategy"].items()},
            **{f"buy_and_hold_{k}": v for k, v in benchmark_vs_bh["buy_and_hold"].items()},
            **{f"correlation_{k}": v for k, v in benchmark_vs_bh["correlation"].items()},
        },
    )
    results["benchmark_vs_buy_and_hold"] = benchmark_vs_bh

    print("[6/10] Running DCA-blend complementary-sleeve analysis...")
    results["dca_blend"] = run_dca_blend_analysis(df, baseline_trades)

    print("[7/10] Running fee/slippage sensitivity scenarios...")
    fee_slippage_scenarios = run_fee_slippage_sensitivity(baseline_trades)
    for scenario in fee_slippage_scenarios:
        report_stat(
            f"Fee/slippage scenario: {scenario['label']}",
            inputs={"n_trades": len(baseline_trades)},
            outputs={"total_return_pct": scenario["total_return_pct"], "win_rate_pct": scenario["win_rate_pct"]},
        )
    results["fee_slippage_sensitivity"] = fee_slippage_scenarios

    print("[8/10] Running macro-regime breakdown...")
    results["regime_breakdown"] = run_regime_breakdown(df, baseline_trades)

    print("[9/10] Running paper/codebase sync check...")
    sync_check = run_paper_sync_check(df)
    if sync_check["any_mismatch"]:
        print("  >>> MISMATCH found -- a live-recomputed figure disagrees with a locked constant.")
        print("  >>> This is a correctness finding to report, not to silently reconcile.")
        for c in sync_check["checks"]:
            if c["status"] == "MISMATCH":
                print(f"      {c['metric']}: locked={c['locked']!r} live={c['live']!r}")
    else:
        print("  All checked figures match this file's LOCKED_* constants.")
    results["paper_sync_check"] = sync_check

    print("[10/10] Running benchmark-vs-passive (strategy vs. DCA vs. lump-sum, both windows)...")
    formulation_df = compute_indicators(load_formulation_period_window())
    formulation_sim = simulate_trades(formulation_df.copy(), min_ob_quality=0)
    formulation_trades = formulation_sim.attrs["trades_df"]
    reconciliation = reconcile_formulation_window_trades(formulation_trades)
    print(f"  Formulation-period reconciliation vs. published figures: "
          f"{'MATCH' if reconciliation else ('DIVERGE' if reconciliation is False else 'SKIPPED (no published artifact found)')}")
    benchmark_vs_passive = run_benchmark_vs_passive(df, baseline_trades, formulation_df, formulation_trades)
    for window_key, window_label in (("main_window", "main window"), ("formulation_period_window", "formulation window")):
        for arm in benchmark_vs_passive[window_key]["gross"]:
            report_stat(
                f"Benchmark-vs-passive, GROSS, {window_label}: {arm['arm']}",
                inputs={"starting_capital": arm["starting_capital"]},
                outputs={"total_return_pct": arm["total_return_pct"], "final_capital": arm["final_capital"],
                         "sharpe": arm["sharpe"], "sortino": arm["sortino"],
                         "max_drawdown_pct": arm["max_drawdown_pct"], "time_in_market_pct": arm["time_in_market_pct"]},
            )
    results["benchmark_vs_passive"] = benchmark_vs_passive
    results["formulation_window_reconciliation"] = reconciliation

    main_trades_table, main_results_summary = build_trades_and_results_table(df, baseline_trades)
    formulation_trades_table, formulation_results_summary = build_trades_and_results_table(formulation_df, formulation_trades)
    results["trades_and_results"] = {
        "main_window": {"trades": main_trades_table, "results": main_results_summary},
        "formulation_period_window": {"trades": formulation_trades_table, "results": formulation_results_summary},
    }

    if include_oos_live:
        print("\n[bonus] Running forward out-of-sample validation (LIVE Binance pull)...")
        oos_result = run_forward_oos_validation()
        print(f"  Integrity check: {'PASS' if oos_result['integrity_check'] else 'FAIL'}  "
              f"Regression check: {'PASS' if oos_result['regression_check'] else 'FAIL'}  "
              f"OOS trades: {len(oos_result['oos_trades'])}")
        results["forward_oos_validation"] = oos_result
    else:
        print("\n[bonus] Skipping forward OOS validation (live Binance pull) -- pass --include-oos-live to run it.")

    print("\n" + "=" * 100)
    print("  Pipeline complete.")
    print("=" * 100)

    if json_out:
        write_json_results(results, json_out)

    return results


def run_serve_mode(cli_args):
    """
    `--serve` entrypoint: the single-file equivalent of what
    Run_All.py + export_gui_data.py previously did as separate processes.
    Exports dashboard artifacts + database rows
    (Section 6), regenerates the paper-sync report and statistical-artifact
    JSON files, optionally pushes to Google Sheets, then starts the HTTP
    server (Section 7) dashboard-v2 talks to -- all from this one file, one
    process.
    """
    print("Loading candles and running the dashboard export pipeline...")
    manifest, threshold_runs, verification_report = export_dashboard_artifacts(
        symbol=cli_args.symbol, timeframe=cli_args.timeframe, start=cli_args.start, end=cli_args.end,
        levels=cli_args.levels, default_view_quality=cli_args.default_view_quality,
        output_dir=cli_args.output_dir, db_url=cli_args.db_url, export_gsheet=cli_args.export_gsheet,
    )
    print("\n=== Export Complete ===")
    print(f"Symbol/Timeframe: {manifest['symbol']} {manifest['timeframe']}")
    print(f"Candles: {manifest['candle_count']}")
    print(f"Thresholds: {', '.join(str(x['min_quality']) for x in threshold_runs)}")
    print(f"Verification: {verification_report['status']}")
    print(f"Artifacts directory: {cli_args.output_dir}")

    print("\nRegenerating paper/codebase sync report...")
    try:
        _, mismatches, _ = generate_paper_sync_report(
            out_path=os.path.join(cli_args.output_dir, "paper_sync_report.md"))
        if mismatches:
            print(f"\n[WARNING] paper_sync_report.md found {len(mismatches)} mismatch(es) "
                  f"against CLAUDE.md's locked results.")
    except Exception as e:
        print(f"\n[WARNING] Skipping paper_sync_report.md: failed to generate ({e}).")

    print("\nRegenerating statistical-artifact JSON files...")
    try:
        df = compute_indicators(load_candles())
        baseline_sim = simulate_trades(df.copy(), min_ob_quality=0)
        write_statistical_artifacts(df, baseline_sim.attrs["trades_df"], output_dir=cli_args.output_dir)
    except Exception as e:
        print(f"\n[WARNING] Skipping statistical-artifact JSON files: {e}")

    if cli_args.no_server:
        print("\nSkipping local dashboard web server (--no-server was set).")
        return

    run_dashboard_server(port=8765, open_browser=not cli_args.no_browser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="research_analysis.py -- single-file backtest engine, statistics pipeline, "
                     "database manager, and dashboard HTTP server for the ISEF paper's research codebase.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--serve", action="store_true",
                         help="Export dashboard artifacts + database rows, then start the dashboard HTTP "
                              "server (what Run_All.py/export_gui_data.py used to do). Without "
                              "this flag, runs the offline statistics pipeline only (default behavior).")
    # --- Statistics-pipeline flags (default mode) ---------------------------
    parser.add_argument("--include-oos-live", action="store_true",
                         help="Also run the forward out-of-sample validation, which makes a live Binance API "
                              "call (the one disclosed exception to this file's offline-by-default design). "
                              "Off by default.")
    parser.add_argument("--bootstrap-n", type=int, default=10000,
                         help="Number of bootstrap resamples for the canonical baseline CI (default: 10,000).")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for all bootstrap resampling (default: 42).")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write every section's results as one JSON file.")
    # --- --serve-mode flags (mirror export_gui_data.py's former CLI) --------
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--start", default="2022-01-01 00:00:00")
    parser.add_argument("--end", default="2026-01-01 00:00:00")
    parser.add_argument("--levels", default="0,1,2,3", help="Comma-separated min OB quality levels.")
    parser.add_argument("--default-view-quality", type=int, default=1)
    parser.add_argument("--output-dir", default="artifacts")
    parser.add_argument("--export-gsheet", action="store_true")
    parser.add_argument("--db-url", default=None, help="SQLAlchemy database URL connection string.")
    parser.add_argument("--no-server", action="store_true", help="Skip launching the local dashboard web server.")
    parser.add_argument("--no-browser", action="store_true",
                         help="Start the server but don't auto-open a browser tab (used by dashboard-v2's "
                              "`npm run dev`).")
    cli_args = parser.parse_args()
    cli_args.levels = [int(x.strip()) for x in cli_args.levels.split(",") if x.strip()] or DEFAULT_ARTIFACT_LEVELS
    if cli_args.default_view_quality not in cli_args.levels:
        cli_args.default_view_quality = cli_args.levels[0]

    if cli_args.serve:
        run_serve_mode(cli_args)
    else:
        run_full_analysis_pipeline(
            include_oos_live=cli_args.include_oos_live,
            bootstrap_resamples=cli_args.bootstrap_n,
            seed=cli_args.seed,
            json_out=cli_args.json_out,
        )
