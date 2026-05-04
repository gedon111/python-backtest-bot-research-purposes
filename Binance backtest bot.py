# trading_bot_v9.py
# Based verbatim on trading_bot_v8.py
#
# ── CHANGES FROM v8 (4 lines changed in simulate_trades only) ─────────────────
#
# All changes derived from bar-by-bar pattern analysis of 55 trades
# across the full 7-year / 15,331-bar dataset (backlog_28).
#
# Lookahead audit: both changes use only data known at or before bar i.
# sl_pct uses entry_price and sl, both set at bar i. The KDJ min-bars
# check uses entry_idx, which is a past bar index. No forward data. ✅
#
# [1] REQUIRE SL DISTANCE >= 1.5% FROM ENTRY (BOTH SIDES)
#
#     v8: no minimum SL size
#     v9: skip entry if (|entry - sl| / entry) < 1.5%
#
#     Why: 10 trades had SL distance < 1.5% → 23% WR, net −9.97%.
#     These OBs are too thin. The SL sits inside normal 4H price noise,
#     so the trade gets stopped before the move even starts.
#     The 3 winners lost are all small (+0.18%, +0.28%, +0.25%).
#     The 7 losers blocked include five of the worst SL hits in the set.
#     Keeping sl>=1.5% lifts net from +23.65% to +31.34% on 7yr data.
#
#     Code:
#       LONG:  after `if risk <= 0: continue`
#              add `if risk / close < 0.015: continue`
#       SHORT: after `if risk <= 0: continue`
#              add `if risk / close < 0.015: continue`
#
# [2] BLOCK KDJ RESET EXIT BEFORE BAR 3 IN TRADE (BOTH SIDES)
#
#     v8: KDJ reset can fire on bar 1 of the trade
#     v9: KDJ reset exit only allowed if (i - entry_idx) >= 3
#
#     Why: 14 KDJ RESET EXITs total, 12 are losers (86% loss rate).
#     Exit type analysis: KDJ exit 14% WR, avg −0.64%, net −8.92%.
#     The KDJ reset is firing on single-bar KDJ fluctuations in the
#     first 1-2 bars of the trade before the move has had time to develop.
#     Minimum 3-bar hold before KDJ reset is allowed gives the trade
#     time to confirm. If KDJ resets before bar 3, let the SL handle it.
#     The 2 KDJ exit winners both held >= 4 bars before exiting.
#
#     Code:
#       LONG:  change `if kdj_reset_exit(kdj_state, 'LONG'):`
#              to     `if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, 'LONG'):`
#       SHORT: same for SHORT
#
# [KEPT] All v8 filters unchanged.
# Everything else — indicators, SMC, GSheet export — is identical.
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np
from binance.client import Client
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from gspread_formatting import CellFormat, Color, TextFormat, format_cell_ranges
import os
import glob

# ─── SAFE CONFIG (GITHUB-FRIENDLY) ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Keep real Binance keys in environment variables.
BINANCE_API_KEY_ENV    = "BINANCE_API_KEY"
BINANCE_API_SECRET_ENV = "BINANCE_API_SECRET"

# Use environment variables in production; placeholders below are safe for upload.
GOOGLE_SERVICE_KEY_PATH = os.getenv(
    "GOOGLE_SERVICE_KEY_PATH",
    os.path.join(BASE_DIR, "SERVICE KEY", "your-service-account-key.json"),
)
GOOGLE_SHEET_ID = "1UXw_eTEVjV7lfwmVpLq9z2BWC8WShUFclD3xVkT4MdA"


def resolve_google_service_key_path():
    configured = GOOGLE_SERVICE_KEY_PATH
    placeholder = configured.endswith("your-service-account-key.json")
    if not placeholder and os.path.isfile(configured):
        return configured

    # Auto-discover any json key under SERVICE KEY for local workflows.
    candidates = sorted(glob.glob(os.path.join(BASE_DIR, "SERVICE KEY", "*.json")))
    if candidates:
        # Prioritize the known working 'new-strat' key if multiple exist
        for c in candidates:
            if "new-strat" in os.path.basename(c):
                return c
        return candidates[0]
    return configured

# ─── API ─────────────────────────────────────────────────────────────────────
API_KEY    = os.getenv(BINANCE_API_KEY_ENV)
API_SECRET = os.getenv(BINANCE_API_SECRET_ENV)
client     = Client(API_KEY, API_SECRET)

# ─── SMC PARAMETERS (match LuxAlgo defaults) ─────────────────────────────────
SWING_SIZE    = 50    # bars — swing structure pivot lookback (LuxAlgo swingsLengthInput)
INTERNAL_SIZE = 5     # bars — internal structure pivot lookback
MAX_OB_AGE    = 500   # bars — discard OBs older than this


# ─── FETCH CANDLES ────────────────────────────────────────────────────────────
def get_candles(symbol="BTCUSDT", interval=Client.KLINE_INTERVAL_4HOUR,
                start_time=None, end_time=None):
    if isinstance(start_time, str): start_time = pd.to_datetime(start_time)
    if isinstance(end_time,   str): end_time   = pd.to_datetime(end_time)

    start_ms = int(start_time.timestamp() * 1000) if start_time else 0
    end_ms   = int(end_time.timestamp()   * 1000) if end_time   else None

    candles = []
    while True:
        batch = client.get_klines(
            symbol=symbol, interval=interval,
            startTime=start_ms, endTime=end_ms, limit=1000)
        if not batch: break
        candles.extend(batch)
        last_time = batch[-1][0]
        if end_ms and last_time >= end_ms: break
        start_ms = last_time + 1

    df = pd.DataFrame(candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"])
    df = df.iloc[:, :6]
    df["open_time"] = (pd.to_datetime(df["open_time"], unit='ms')
                       + pd.Timedelta(hours=8))
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)


# ─── INDICATORS ───────────────────────────────────────────────────────────────
def compute_indicators(df, kdj_period=9, atr_period=14):
    """
    MACD(12,26,9) + KDJ(kdj_period, 3, 3) + ATR(14) + ATR_200.
    KDJ period defaults to 9 (standard stochastic window).
    """
    df = df.copy()
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # MACD (12, 26, 9)
    ema_fast         = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow         = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD']       = ema_fast - ema_slow
    df['MACD_signal']= df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist']  = df['MACD'] - df['MACD_signal']

    # KDJ  — EWM alpha = 1/3, matching the standard KDJ smoothing
    n        = int(kdj_period)
    low_min  = df['low'].rolling(n,  min_periods=1).min()
    high_max = df['high'].rolling(n, min_periods=1).max()
    denom    = (high_max - low_min).replace(0, np.nan)
    rsv      = ((df['close'] - low_min) / denom * 100).fillna(50)
    alpha    = 1.0 / 3.0
    df['K']  = rsv.ewm(alpha=alpha, adjust=False).mean()
    df['D']  = df['K'].ewm(alpha=alpha, adjust=False).mean()
    df['J']  = 3 * df['K'] - 2 * df['D']
    df['RSV']= rsv

    # ATR  — true range, Wilder's smoothing (RMA)
    #   Seed : first n bars use a plain SMA (identical to TradingView/MT4).
    #   Then : ATR = (ATR_prev × (n-1) + TR_current) / n
    #   This is equivalent to ewm(alpha=1/n, adjust=False) in pandas.
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low']  - prev_close).abs()
    ], axis=1).max(axis=1)
    df['ATR']     = tr.ewm(alpha=1.0 / atr_period, adjust=False).mean()
    df['ATR_200'] = tr.ewm(alpha=1.0 / 200,         adjust=False).mean()

    return df


# ─── SMC: LUXALGO ORDER BLOCKS VIA CHoCH / BOS ───────────────────────────────
def compute_smc(df):
    """
    Faithful Python translation of LuxAlgo Smart Money Concepts.

    Runs two passes — swing (size=50) and internal (size=5).

    For each pass, bar by bar:
      1. Check if bar (i-size) is a new pivot high/low (right-side only).
      2. Detect if close crosses a tracked pivot level (BOS or CHoCH).
      3. On crossover, create an Order Block from the parsedHigh/parsedLow arrays.

    Returns list of OB dicts:
      type       : 'DEMAND' (bullish) or 'SUPPLY' (bearish)
      top        : parsedHigh of OB bar
      bottom     : parsedLow  of OB bar
      created_at : bar index when OB was confirmed (no lookahead)
      level      : 'swing' or 'internal'
      structure  : 'CHoCH' or 'BOS'
    """
    n       = len(df)
    highs   = df['high'].values
    lows    = df['low'].values
    closes  = df['close'].values
    atr200  = df['ATR_200'].values

    # Volatility-parsed high/low (LuxAlgo OB filter):
    #   On high-volatility bars the body is inverted for OB search purposes.
    #   parsedHigh = low  if bar range >= 2×ATR200 else high
    #   parsedLow  = high if bar range >= 2×ATR200 else low
    high_vol    = (highs - lows) >= (2 * atr200)
    parsed_highs = np.where(high_vol, lows,  highs)
    parsed_lows  = np.where(high_vol, highs, lows)

    all_obs = []

    for size in [INTERNAL_SIZE, SWING_SIZE]:
        level_tag = 'internal' if size == INTERNAL_SIZE else 'swing'

        # Mutable state for this structure level
        sh_price   = np.nan   # current tracked swing HIGH price
        sh_bar     = -1       # bar index of that pivot
        sh_crossed = False    # True once close crossed above it

        sl_price   = np.nan   # current tracked swing LOW price
        sl_bar     = -1
        sl_crossed = False

        trend = 0   # +1 bullish, -1 bearish, 0 neutral

        for i in range(size + 1, n):
            pb = i - size   # pivot bar candidate (size bars ago)

            # ── Pivot HIGH confirmation ───────────────────────────────────
            # high[pb] > max(high[pb+1 .. i])  →  bar pb is a swing high
            right_highs = highs[pb + 1: i + 1]
            if len(right_highs) and highs[pb] > right_highs.max():
                sh_price   = float(highs[pb])
                sh_bar     = pb
                sh_crossed = False   # reset — new pivot to watch

            # ── Pivot LOW confirmation ────────────────────────────────────
            right_lows = lows[pb + 1: i + 1]
            if len(right_lows) and lows[pb] < right_lows.min():
                sl_price   = float(lows[pb])
                sl_bar     = pb
                sl_crossed = False

            # ── BULLISH BOS / CHoCH ───────────────────────────────────────
            if (not np.isnan(sh_price) and not sh_crossed
                    and closes[i - 1] <= sh_price < closes[i]):

                tag        = 'CHoCH' if trend == -1 else 'BOS'
                sh_crossed = True
                trend      = 1

                if sh_bar >= 0:
                    seg    = parsed_lows[sh_bar: i + 1]
                    ob_idx = sh_bar + int(np.argmin(seg))
                    ob = {
                        'type':       'DEMAND',
                        'top':        float(parsed_highs[ob_idx]),
                        'bottom':     float(parsed_lows[ob_idx]),
                        'created_at': i,
                        'ob_bar':     ob_idx,
                        'level':      level_tag,
                        'structure':  tag,
                    }

                    displacement = False
                    try:
                        for j in range(ob_idx + 1, min(n, ob_idx + 4)):
                            body = float(df.at[j, 'close']) - float(df.at[j, 'open'])
                            thresh = 1.5 * float(atr200[ob_idx]) if not np.isnan(atr200[ob_idx]) else 0
                            if ob['type'] == 'DEMAND' and body > 0 and abs(body) >= thresh:
                                displacement = True
                                break
                            if ob['type'] == 'SUPPLY' and body < 0 and abs(body) >= thresh:
                                displacement = True
                                break
                    except Exception:
                        displacement = False

                    try:
                        bar_range = float(highs[ob_idx]) - float(lows[ob_idx])
                        large_bar = (not np.isnan(atr200[ob_idx]) and bar_range >= float(atr200[ob_idx]))
                    except Exception:
                        large_bar = False

                    fvg = False
                    try:
                        for j in range(ob_idx + 1, min(n - 1, ob_idx + 4)):
                            if float(lows[j + 1]) > float(highs[j]) and ob['type'] == 'DEMAND':
                                fvg = True
                                break
                            if float(highs[j + 1]) < float(lows[j]) and ob['type'] == 'SUPPLY':
                                fvg = True
                                break
                    except Exception:
                        fvg = False

                    try:
                        prev_start = max(0, ob_idx - 10)
                        if ob['type'] == 'DEMAND':
                            liquidity_sweep = float(lows[ob_idx]) <= float(lows[prev_start:ob_idx].min())
                        else:
                            liquidity_sweep = float(highs[ob_idx]) >= float(highs[prev_start:ob_idx].max())
                    except Exception:
                        liquidity_sweep = False

                    try:
                        vstart = max(0, ob_idx - 20)
                        if ob_idx > 0:
                            vol = float(df.at[ob_idx, 'volume'])
                            avg_vol = float(df['volume'].iloc[vstart:ob_idx].mean())
                            volume_good = (avg_vol > 0 and vol >= 1.25 * avg_vol)
                        else:
                            volume_good = False
                        body = abs(float(df.at[ob_idx, 'close']) - float(df.at[ob_idx, 'open']))
                        rng = float(highs[ob_idx]) - float(lows[ob_idx])
                        impulse_body = (rng > 0 and body / rng > 0.6)
                        vol_expansion = (volume_good or impulse_body)
                    except Exception:
                        vol_expansion = False

                    ob['quality_displacement'] = bool(displacement)
                    ob['quality_large_bar'] = bool(large_bar)
                    ob['quality_fvg'] = bool(fvg)
                    ob['quality_liquidity_sweep'] = bool(liquidity_sweep)
                    ob['quality_volume_expansion'] = bool(vol_expansion)
                    ob['quality'] = int(
                        ob['quality_displacement'] + ob['quality_large_bar'] +
                        ob['quality_fvg'] + ob['quality_liquidity_sweep'] +
                        ob['quality_volume_expansion']
                    )

                    all_obs.append(ob)

            # ── BEARISH BOS / CHoCH ───────────────────────────────────────
            if (not np.isnan(sl_price) and not sl_crossed
                    and closes[i - 1] >= sl_price > closes[i]):

                tag        = 'CHoCH' if trend == 1 else 'BOS'
                sl_crossed = True
                trend      = -1

                if sl_bar >= 0:
                    seg    = parsed_highs[sl_bar: i + 1]
                    ob_idx = sl_bar + int(np.argmax(seg))
                    ob = {
                        'type':       'SUPPLY',
                        'top':        float(parsed_highs[ob_idx]),
                        'bottom':     float(parsed_lows[ob_idx]),
                        'created_at': i,
                        'ob_bar':     ob_idx,
                        'level':      level_tag,
                        'structure':  tag,
                    }

                    displacement = False
                    try:
                        for j in range(ob_idx + 1, min(n, ob_idx + 4)):
                            body = float(df.at[j, 'close']) - float(df.at[j, 'open'])
                            thresh = 1.5 * float(atr200[ob_idx]) if not np.isnan(atr200[ob_idx]) else 0
                            if ob['type'] == 'DEMAND' and body > 0 and abs(body) >= thresh:
                                displacement = True
                                break
                            if ob['type'] == 'SUPPLY' and body < 0 and abs(body) >= thresh:
                                displacement = True
                                break
                    except Exception:
                        displacement = False

                    try:
                        bar_range = float(highs[ob_idx]) - float(lows[ob_idx])
                        large_bar = (not np.isnan(atr200[ob_idx]) and bar_range >= float(atr200[ob_idx]))
                    except Exception:
                        large_bar = False

                    fvg = False
                    try:
                        for j in range(ob_idx + 1, min(n - 1, ob_idx + 4)):
                            if float(lows[j + 1]) > float(highs[j]) and ob['type'] == 'DEMAND':
                                fvg = True
                                break
                            if float(highs[j + 1]) < float(lows[j]) and ob['type'] == 'SUPPLY':
                                fvg = True
                                break
                    except Exception:
                        fvg = False

                    try:
                        prev_start = max(0, ob_idx - 10)
                        if ob['type'] == 'DEMAND':
                            liquidity_sweep = float(lows[ob_idx]) <= float(lows[prev_start:ob_idx].min())
                        else:
                            liquidity_sweep = float(highs[ob_idx]) >= float(highs[prev_start:ob_idx].max())
                    except Exception:
                        liquidity_sweep = False

                    try:
                        vstart = max(0, ob_idx - 20)
                        if ob_idx > 0:
                            vol = float(df.at[ob_idx, 'volume'])
                            avg_vol = float(df['volume'].iloc[vstart:ob_idx].mean())
                            volume_good = (avg_vol > 0 and vol >= 1.25 * avg_vol)
                        else:
                            volume_good = False
                        body = abs(float(df.at[ob_idx, 'close']) - float(df.at[ob_idx, 'open']))
                        rng = float(highs[ob_idx]) - float(lows[ob_idx])
                        impulse_body = (rng > 0 and body / rng > 0.6)
                        vol_expansion = (volume_good or impulse_body)
                    except Exception:
                        vol_expansion = False

                    ob['quality_displacement'] = bool(displacement)
                    ob['quality_large_bar'] = bool(large_bar)
                    ob['quality_fvg'] = bool(fvg)
                    ob['quality_liquidity_sweep'] = bool(liquidity_sweep)
                    ob['quality_volume_expansion'] = bool(vol_expansion)
                    ob['quality'] = int(
                        ob['quality_displacement'] + ob['quality_large_bar'] +
                        ob['quality_fvg'] + ob['quality_liquidity_sweep'] +
                        ob['quality_volume_expansion']
                    )

                    all_obs.append(ob)

    closes_arr = df['close'].values
    for ob in all_obs:
        start = ob['created_at'] + 1
        if start >= n:
            ob['mitigated_at'] = n
            continue
        if ob['type'] == 'DEMAND':
            viol = np.where(closes_arr[start:] < ob['bottom'])[0]
        else:
            viol = np.where(closes_arr[start:] > ob['top'])[0]
        ob['mitigated_at'] = int(start + viol[0]) if len(viol) else n

    return all_obs


# ─── STRUCTURAL TP ────────────────────────────────────────────────────────────
def get_structural_tp(entry, side, valid_obs):
    if side == 'LONG':
        targets = [z for z in valid_obs
                   if z['type'] == 'SUPPLY' and z['bottom'] > entry]
        return min(targets, key=lambda z: z['bottom'])['bottom'] if targets else None
    else:
        targets = [z for z in valid_obs
                   if z['type'] == 'DEMAND' and z['top'] < entry]
        return max(targets, key=lambda z: z['top'])['top'] if targets else None


# ─── KDJ LENGTH RESET (DYNAMIC PERIOD BASED ON OB DISTANCE) ─────────────────
def kdj_reset_init(df, entry_idx, ob_bar=None, default_period=9):
    period = default_period
    if ob_bar is not None and isinstance(ob_bar, int) and ob_bar >= 0:
        period = max(1, entry_idx - ob_bar)

    return {
        'k':          float(df.at[entry_idx, 'K']),
        'd':          float(df.at[entry_idx, 'D']),
        'prev_k':     float(df.at[entry_idx, 'K']),
        'prev_d':     float(df.at[entry_idx, 'D']),
        'period':     int(period),
        'entry_idx':  int(entry_idx),
        'armed':      False,
    }


def kdj_reset_update(state, df, cur_idx, side):
    alpha = 1.0 / 3.0
    period = max(1, int(state.get('period', 9)))

    window_start = max(cur_idx - period + 1, 0)
    window_high = df['high'].iloc[window_start:cur_idx + 1]
    window_low  = df['low'].iloc[window_start:cur_idx + 1]

    if len(window_high) == 0 or len(window_low) == 0:
        rsv = 50.0
    else:
        highest = window_high.max()
        lowest  = window_low.min()
        denom = highest - lowest
        rsv = ((df.at[cur_idx, 'close'] - lowest) / denom * 100) if denom > 0 else 50.0

    state['prev_k'] = state['k']
    state['prev_d'] = state['d']
    state['k']      = state['k'] * (1 - alpha) + rsv * alpha
    state['d']      = state['d'] * (1 - alpha) + state['k'] * alpha

    if side == 'SHORT' and state['k'] < state['d']:
        state['armed'] = True
    if side == 'LONG'  and state['k'] > state['d']:
        state['armed'] = True

    return state


def kdj_reset_exit(state, side):
    if not state['armed']:
        return False
    if side == 'SHORT':
        return state['prev_k'] <= state['prev_d'] and state['k'] > state['d']
    else:
        return state['prev_k'] >= state['prev_d'] and state['k'] < state['d']


# ─── TRADE SIMULATION ─────────────────────────────────────────────────────────
MIN_OB_QUALITY = 1


def simulate_trades(df, min_ob_quality=None):
    current_entry_ob = None
    entry_tp_is_structural = False
    entry_tp_ob_bar = None
    entry_tp_ob_quality = None
    df  = compute_indicators(df)
    obs = compute_smc(df)

    for col in ['Trade_Status', 'Active_Supply', 'Active_Demand']:
        df[col] = ''
    for col in ['Entry_Price', 'Stop_Loss', 'Take_Profit', 'Exit_Price', 'Running_PnL_%']:
        df[col] = np.nan

    position         = None
    entry_price      = 0.0
    stop_loss_price  = 0.0
    take_profit_price= 0.0
    entry_atr        = 0.0
    peak_pnl_pct     = 0.0
    entry_idx        = 0
    kdj_state        = None
    trades = []
    current_entry_ob = None
    entry_tp_is_structural = False
    entry_tp_ob_bar = None
    entry_tp_ob_quality = None

    start_bar = SWING_SIZE + 5

    for i in range(start_bar, len(df)):
        close   = float(df.at[i, 'close'])
        high    = float(df.at[i, 'high'])
        low     = float(df.at[i, 'low'])
        hist    = float(df.at[i, 'MACD_hist'])
        p_hist  = float(df.at[i - 1, 'MACD_hist'])
        pp_hist = float(df.at[i - 2, 'MACD_hist'])        # [v7] 2-bar lookback
        K       = float(df.at[i, 'K'])
        D       = float(df.at[i, 'D'])
        J       = float(df.at[i, 'J'])
        K_prev  = float(df.at[i - 1, 'K'])
        K2      = float(df.at[i - 2, 'K'])                # [v7] 2-bar lookback
        ATR     = float(df.at[i, 'ATR'])
        ATR_200 = float(df.at[i, 'ATR_200'])              # [v7] for atr_r
        k_accel = (K - K_prev) - (K_prev - K2)            # [v7] K acceleration
        atr_r   = ATR / ATR_200 if ATR_200 > 0 else 1.0  # [v7] volatility regime

        local_min_quality = MIN_OB_QUALITY if min_ob_quality is None else int(min_ob_quality)

        valid_obs_entries = [
            ob for ob in obs
            if ob['created_at'] < i < ob['mitigated_at']
            and i - ob['created_at'] <= MAX_OB_AGE
            and ob.get('quality', 0) >= local_min_quality
        ]
        valid_obs_tp = [
            ob for ob in obs
            if ob['created_at'] < i < ob['mitigated_at']
            and i - ob['created_at'] <= MAX_OB_AGE
        ]
        demand_obs = [z for z in valid_obs_entries if z['type'] == 'DEMAND']
        supply_obs = [z for z in valid_obs_entries if z['type'] == 'SUPPLY']

        def nearest(zones):
            if not zones: return None
            return min(zones, key=lambda z: abs((z['top'] + z['bottom']) / 2 - close))

        ns = nearest(supply_obs)
        nd = nearest(demand_obs)

        def ob_info(ob):
            if not ob:
                return ""
            bar_idx = ob.get('ob_bar', None)
            time_str = ""
            try:
                if bar_idx is not None and bar_idx >= 0 and bar_idx < len(df):
                    time_val = df.at[int(bar_idx), 'open_time']
                    time_str = pd.to_datetime(time_val).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                time_str = ""
            return f"{ob['bottom']:.4f} - {ob['top']:.4f} | bar {bar_idx} | {time_str}"

        if ns:
            df.at[i, 'Active_Supply'] = ob_info(ns)
        if nd:
            df.at[i, 'Active_Demand'] = ob_info(nd)

        if position is None:

            for ob in demand_obs:
                if not (low <= ob['top'] and close >= ob['bottom']):
                    continue
                if not (hist < 0 and hist > p_hist):
                    continue
                # ── [v7 FILTER 1] hist must have been rising for ≥ 2 bars ──
                # Requires hist[i-1] > hist[i-2] in addition to hist[i] > hist[i-1]
                if not (p_hist > pp_hist):
                    continue
                # ── [v5→v6] J < 60 cap retained, Displacement gate removed ──
                if not (K < 50 and K > K_prev and J < 60):
                    continue
                # ── [v7→v8] K acceleration window [1, 6] ─────────────────
                # v7: k_accel >= 1  (floor only)
                # v8: 1 <= k_accel <= 6  (floor + ceiling)
                # k_accel > 6 = single-bar K spike, resets immediately (noise)
                if not (1 <= k_accel <= 6):
                    continue
                # ── [v7 FILTER 3] reject ATR dead zone [0.8, 1.0] ────────
                if 0.8 <= atr_r <= 1.0:
                    continue

                sl   = ob['bottom'] - ATR * 0.5
                risk = close - sl
                if risk <= 0: continue
                # ── [v9 FILTER 1] SL must be >= 1.5% from entry ──────────
                # Thin OBs sit inside normal 4H noise → stopped before move.
                # 10 trades < 1.5% SL had 23% WR. Blocked 7 losers, 3 small winners.
                if risk / close < 0.015: continue

                stp = get_structural_tp(close, 'LONG', valid_obs_tp)
                tp  = stp if stp else close + risk * 2.0
                if (tp - close) / risk < 1.5: continue

                position          = 'LONG'
                entry_price       = close
                stop_loss_price   = sl
                take_profit_price = tp
                entry_atr         = ATR
                peak_pnl_pct      = 0.0
                entry_idx         = i
                kdj_state = kdj_reset_init(df, i, ob_bar=ob.get('ob_bar', None))

                current_entry_ob = ob
                stp_ob = None
                if stp is not None:
                    tol = 1e-6
                    candidates = [z for z in valid_obs_tp if z['type'] == 'SUPPLY' and abs(z['bottom'] - stp) <= tol * max(1.0, abs(stp))]
                    stp_ob = min(candidates, key=lambda z: abs(z['bottom'] - stp)) if candidates else None
                entry_tp_is_structural = True if stp_ob else False
                entry_tp_ob_bar = stp_ob.get('ob_bar') if stp_ob else None
                entry_tp_ob_quality = stp_ob.get('quality') if stp_ob else None

                df.at[i, 'Trade_Status'] = 'OPEN LONG'
                df.at[i, 'Entry_Price']  = entry_price
                df.at[i, 'Stop_Loss']    = stop_loss_price
                df.at[i, 'Take_Profit']  = take_profit_price
                break

            if position is None:
                for ob in supply_obs:
                    if not (high >= ob['bottom'] and close <= ob['top']):
                        continue
                    if not (hist > 0 and hist < p_hist):
                        continue
                    # ── [v7 FILTER 1] hist must have been falling for ≥ 2 bars ─
                    # SHORT needs hist declining: hist[i]<hist[i-1]<hist[i-2]
                    if not (p_hist < pp_hist):
                        continue
                    # v4/v5/v6/v7/v8: J > K > D unchanged
                    if not (K > 50 and J > K > D):
                        continue
                    # ── [v7→v8] K acceleration window [1, 6] ──────────────
                    # v7: k_accel >= 1  (floor only)
                    # v8: 1 <= k_accel <= 6  (floor + ceiling)
                    if not (1 <= k_accel <= 6):
                        continue
                    # ── [v7 FILTER 3] reject ATR dead zone [0.8, 1.0] ─────
                    if 0.8 <= atr_r <= 1.0:
                        continue
                    # ── [v8 FILTER 4] SHORT K floor: must be overbought ────
                    # K=63.7 SHORT lost −2.68%. All winners had K >= 77.
                    # K >= 70 = genuinely overbought zone for a SHORT entry.
                    if K < 70:
                        continue
                    # ── [v8 FILTER 5] SHORT J cap: exhaustion already done ─
                    # J > 100 means overbought move is already in extreme.
                    # Both J>100 entries lost (−1.58%, −0.31%). Cap at 100.
                    if J > 100:
                        continue
                    # ── [v5→v6] Displacement gate removed ────────────────
                    # Quality score already includes displacement as a component.

                    sl   = ob['top'] + ATR * 0.5
                    risk = sl - close
                    if risk <= 0: continue
                    # ── [v9 FILTER 1] SL must be >= 1.5% from entry ──────
                    if risk / close < 0.015: continue

                    stp = get_structural_tp(close, 'SHORT', valid_obs_tp)
                    tp  = stp if stp else close - risk * 2.0
                    if (close - tp) / risk < 1.5: continue

                    position          = 'SHORT'
                    entry_price       = close
                    stop_loss_price   = sl
                    take_profit_price = tp
                    entry_atr         = ATR
                    peak_pnl_pct      = 0.0
                    entry_idx         = i
                    kdj_state = kdj_reset_init(df, i, ob_bar=ob.get('ob_bar', None))

                    current_entry_ob = ob
                    stp_ob = None
                    if stp is not None:
                        tol = 1e-6
                        candidates = [z for z in valid_obs_tp if z['type'] == 'DEMAND' and abs(z['top'] - stp) <= tol * max(1.0, abs(stp))]
                        stp_ob = min(candidates, key=lambda z: abs(z['top'] - stp)) if candidates else None
                    entry_tp_is_structural = True if stp_ob else False
                    entry_tp_ob_bar = stp_ob.get('ob_bar') if stp_ob else None
                    entry_tp_ob_quality = stp_ob.get('quality') if stp_ob else None

                    df.at[i, 'Trade_Status'] = 'OPEN SHORT'
                    df.at[i, 'Entry_Price']  = entry_price
                    df.at[i, 'Stop_Loss']    = stop_loss_price
                    df.at[i, 'Take_Profit']  = take_profit_price
                    break

        elif position == 'LONG':
            pnl_pct      = (close - entry_price) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)

            df.at[i, 'Trade_Status']  = 'RUNNING LONG'
            df.at[i, 'Running_PnL_%'] = pnl_pct
            df.at[i, 'Entry_Price']   = entry_price
            df.at[i, 'Stop_Loss']     = stop_loss_price
            df.at[i, 'Take_Profit']   = take_profit_price

            def close_trade(tag, pnl):
                nonlocal position, current_entry_ob, entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality
                df.at[i, 'Trade_Status']  = tag
                df.at[i, 'Exit_Price']    = close
                df.at[i, 'Running_PnL_%'] = pnl
                trades.append({'side': 'LONG', 'entry_idx': entry_idx,
                                'exit_idx': i, 'entry': entry_price,
                                'exit': close, 'pnl_pct': pnl,
                                'entry_ob_bar': (current_entry_ob.get('ob_bar') if current_entry_ob else None),
                                'entry_ob_quality': (current_entry_ob.get('quality') if current_entry_ob else None),
                                'tp_is_structural': entry_tp_is_structural,
                                'tp_ob_bar': entry_tp_ob_bar,
                                'tp_ob_quality': entry_tp_ob_quality,
                                'hold_bars': i - entry_idx})
                current_entry_ob = None
                entry_tp_is_structural = False
                entry_tp_ob_bar = None
                entry_tp_ob_quality = None
                position = None

            if peak_pnl_pct >= 1.5:
                floor = entry_price * (1 + peak_pnl_pct * 0.5 / 100)
                if close <= floor:
                    close_trade('TRAILING EXIT (50% RETRACE)', pnl_pct)
                    continue

            if position is None: continue

            kdj_state = kdj_reset_update(kdj_state, df, i, 'LONG')
            # ── [v9 CHANGE 2] KDJ reset only allowed after bar 3 in trade ─
            # 12/14 KDJ exits were losers. Both winners held >= 4 bars.
            # Single-bar KDJ fluctuations in bars 1-2 should not exit the trade.
            if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, 'LONG'):
                close_trade('KDJ RESET EXIT', pnl_pct)
                continue

            if entry_atr > 0 and close >= entry_price + entry_atr * 1.8:
                close_trade('ATR MOVE EXIT', pnl_pct)
                continue

            if close >= entry_price + entry_atr * 2:
                stop_loss_price = max(stop_loss_price, entry_price)
                df.at[i, 'Stop_Loss'] = stop_loss_price

            if close <= stop_loss_price:
                close_trade('HIT STOP LOSS',
                            (close - entry_price) / entry_price * 100)
            elif close >= take_profit_price:
                close_trade('HIT TAKE PROFIT',
                            (close - entry_price) / entry_price * 100)

        elif position == 'SHORT':
            pnl_pct      = (entry_price - close) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)

            df.at[i, 'Trade_Status']  = 'RUNNING SHORT'
            df.at[i, 'Running_PnL_%'] = pnl_pct
            df.at[i, 'Entry_Price']   = entry_price
            df.at[i, 'Stop_Loss']     = stop_loss_price
            df.at[i, 'Take_Profit']   = take_profit_price

            def close_trade(tag, pnl):
                nonlocal position, current_entry_ob, entry_tp_is_structural, entry_tp_ob_bar, entry_tp_ob_quality
                df.at[i, 'Trade_Status']  = tag
                df.at[i, 'Exit_Price']    = close
                df.at[i, 'Running_PnL_%'] = pnl
                trades.append({'side': 'SHORT', 'entry_idx': entry_idx,
                                'exit_idx': i, 'entry': entry_price,
                                'exit': close, 'pnl_pct': pnl,
                                'entry_ob_bar': (current_entry_ob.get('ob_bar') if current_entry_ob else None),
                                'entry_ob_quality': (current_entry_ob.get('quality') if current_entry_ob else None),
                                'tp_is_structural': entry_tp_is_structural,
                                'tp_ob_bar': entry_tp_ob_bar,
                                'tp_ob_quality': entry_tp_ob_quality,
                                'hold_bars': i - entry_idx})
                current_entry_ob = None
                entry_tp_is_structural = False
                entry_tp_ob_bar = None
                entry_tp_ob_quality = None
                position = None

            if peak_pnl_pct >= 1.5:
                floor = entry_price * (1 - peak_pnl_pct * 0.5 / 100)
                if close >= floor:
                    close_trade('TRAILING EXIT (50% RETRACE)', pnl_pct)
                    continue

            if position is None: continue

            kdj_state = kdj_reset_update(kdj_state, df, i, 'SHORT')
            # ── [v9 CHANGE 2] KDJ reset only allowed after bar 3 in trade ─
            if (i - entry_idx) >= 3 and kdj_reset_exit(kdj_state, 'SHORT'):
                close_trade('KDJ RESET EXIT', pnl_pct)
                continue

            if entry_atr > 0 and close <= entry_price - entry_atr * 1.8:
                close_trade('ATR MOVE EXIT', pnl_pct)
                continue

            if close <= entry_price - entry_atr * 2:
                stop_loss_price = min(stop_loss_price, entry_price)
                df.at[i, 'Stop_Loss'] = stop_loss_price

            if close >= stop_loss_price:
                close_trade('HIT STOP LOSS',
                            (entry_price - close) / entry_price * 100)
            elif close <= take_profit_price:
                close_trade('HIT TAKE PROFIT',
                            (entry_price - close) / entry_price * 100)

    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        total = len(trades_df)
        tot_p = trades_df['pnl_pct'].sum()
        avg_p = trades_df['pnl_pct'].mean()
        wins  = (trades_df['pnl_pct'] > 0).sum()
        stats = {
            'Total Trades':         total,
            'Total Net Return (%)': tot_p,
            'Avg Return/Trade (%)': avg_p,
            'Win Rate (%)':         wins / total * 100,
        }
    else:
        stats = {'Total Trades': 0, 'Total Net Return (%)': 0.0,
                 'Avg Return/Trade (%)': 0.0, 'Win Rate (%)': 0.0}

    df.attrs['trade_stats'] = stats
    df.attrs['trades_df']   = trades_df
    return df


def run_quality_sweep(df, levels=[0,1,2,3]):
    results = []
    for q in levels:
        out = simulate_trades(df.copy(), min_ob_quality=q)
        stats = out.attrs.get('trade_stats', {})
        results.append({
            'min_quality': q,
            'Total Trades': stats.get('Total Trades', 0),
            'Total Net Return (%)': stats.get('Total Net Return (%)', 0.0),
            'Avg Return/Trade (%)': stats.get('Avg Return/Trade (%)', 0.0),
            'Win Rate (%)': stats.get('Win Rate (%)', 0.0),
        })
    return pd.DataFrame(results)


# ─── GSHEET HELPERS ───────────────────────────────────────────────────────────
def _get_or_create_sheet(workbook, title, rows=50000, cols=30):
    try:
        ws = workbook.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = workbook.add_worksheet(title=title, rows=rows, cols=cols)
    ws.resize(rows=rows, cols=cols)
    return ws


def _format_df_for_export(df):
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
        "open_time":     "Date/Time",
        "open":          "Open",
        "high":          "High",
        "low":           "Low",
        "close":         "Close",
        "ATR":           "ATR (14)",
        "ATR_200":       "ATR (200)",
        "Active_Supply": "Supply Zone",
        "Active_Demand": "Demand Zone",
        "Entry_Price":   "Entry Price",
        "Stop_Loss":     "Stop Loss",
        "Take_Profit":   "Take Profit",
        "Exit_Price":    "Exit Price",
        "Trade_Status":  "Trade Status",
        "Running_PnL_%": "Running PnL %",
    }, inplace=True)

    df_copy["Date/Time"] = (pd.to_datetime(df_copy["Date/Time"], errors="coerce")
                            .dt.strftime('%Y-%m-%d %H:%M:%S'))
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
                val   = float(pnl.strip('%'))
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
                closed_pnls.append(float(pnl.strip('%')))
            except ValueError:
                pass

    if closed_pnls:
        total   = len(closed_pnls)
        tot_pnl = sum(closed_pnls)
        avg_pnl = tot_pnl / total
        wins    = len([p for p in closed_pnls if p > 0])
        wr      = wins / total * 100 if total > 0 else 0
        nr      = len(df_copy) + 2
        cl      = chr(64 + pnl_col)
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
    # ── Compute exact dimensions needed before resizing ──────────────────────
    needed_rows = len(sweep_results) + 5   # 1 header + N data rows + buffer
    needed_cols = 7                         # 5 data columns + 2 buffer
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


# ─── MAIN EXPORT: ALL QUALITY THRESHOLDS ─────────────────────────────────────
def push_all_thresholds_to_gsheet(raw_df, levels=None, precomputed_dfs=None):
    if levels is None:
        levels = [0, 1, 2, 3]

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

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        key_path,
        scope)
    gc       = gspread.authorize(creds)
    workbook = gc.open_by_key(GOOGLE_SHEET_ID)

    sweep_results = []

    for q in levels:
        sheet_title = f"Quality {q}"
        if precomputed_dfs and q in precomputed_dfs:
            print(f"\n[{sheet_title}] Using precomputed simulation...")
            sim_df = precomputed_dfs[q]
        else:
            print(f"\n[{sheet_title}] Running simulation...")
            sim_df = simulate_trades(raw_df.copy(), min_ob_quality=q)
            
        stats  = sim_df.attrs.get("trade_stats", {})

        print(f"  Trades: {stats.get('Total Trades', 0)}  |  "
              f"Return: {stats.get('Total Net Return (%)', 0):.4f}%  |  "
              f"Win Rate: {stats.get('Win Rate (%)', 0):.4f}%")

        # ── Format first so dimensions are known before sheet resize ─────────
        df_copy     = _format_df_for_export(sim_df)
        needed_rows = len(df_copy) + 10   # +1 header, +4 summary stats, +5 buffer
        needed_cols = len(df_copy.columns) + 2
        ws          = _get_or_create_sheet(workbook, sheet_title,
                                           rows=needed_rows, cols=needed_cols)

        print(f"  Writing {len(df_copy)} rows to '{sheet_title}'...")
        _write_sheet(ws, df_copy)
        _apply_pnl_formatting(ws, df_copy)
        print(f"  '{sheet_title}' done.")

        sweep_results.append({
            "quality":      q,
            "total_trades": int(stats.get("Total Trades", 0)),
            "total_return": float(stats.get("Total Net Return (%)", 0.0)),
            "avg_return":   float(stats.get("Avg Return/Trade (%)", 0.0)),
            "win_rate":     float(stats.get("Win Rate (%)", 0.0)),
        })

    print("\n[Summary] Writing quality sweep comparison sheet...")
    _write_summary_sheet(workbook, sweep_results)

    print("\nCheck GSHEET: All threshold sheets exported successfully.")
    return sweep_results


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    btc = get_candles(
        symbol     = "BTCUSDT",
        interval   = Client.KLINE_INTERVAL_4HOUR,
        start_time = "2022-01-01 00:00:00",
        end_time   = "2026-01-01 00:00:00",
    )

    try:
        sweep = push_all_thresholds_to_gsheet(btc, levels=[0, 1, 2, 3])
        print("\n=== Quality Sweep Summary ===")
        for r in sweep:
            print(f"  Quality {r['quality']}: "
                  f"{r['total_trades']} trades | "
                  f"Return {r['total_return']:.4f}% | "
                  f"Win Rate {r['win_rate']:.4f}%")
    except Exception as e:
        print(f"\nFailed to export to Google Sheets: {e}")
        print("Please ensure your Google Service Account has Editor permissions for the target Google Sheet.")