import os

filepath = "Binance backtest bot.py"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

# Normalize CRLF to LF for reliable matching, then write out properly
original_crlf = ("\r\n" in code)
code = code.replace("\r\n", "\n")

# 1. get_candles replacement
target_1 = """    df = pd.DataFrame(candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"])
    df = df.iloc[:, :6]
    df["open_time"] = (pd.to_datetime(df["open_time"], unit='ms')
                       + pd.Timedelta(hours=8))
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)"""

rep_1 = """    df = pd.DataFrame(candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"])
    df = df[["open_time", "open", "high", "low", "close", "volume", "num_trades", "taker_buy_base"]].copy()
    df["open_time"] = (pd.to_datetime(df["open_time"], unit='ms')
                       + pd.Timedelta(hours=8))
    for col in ["open", "high", "low", "close", "volume", "num_trades", "taker_buy_base"]:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)"""

target_1 = target_1.replace("\r\n", "\n")
rep_1 = rep_1.replace("\r\n", "\n")

if target_1 in code:
    code = code.replace(target_1, rep_1)
    print("Patch 1 applied!")
else:
    print("Patch 1 not found!")

# 2. compute_indicators replacement
target_2 = """    df['ATR']     = tr.rolling(atr_period, min_periods=1).mean()
    df['ATR_200'] = tr.rolling(200,         min_periods=1).mean()

    return df"""

rep_2 = """    df['ATR']     = tr.rolling(atr_period, min_periods=1).mean()
    df['ATR_200'] = tr.rolling(200,         min_periods=1).mean()

    # Safeguard for missing columns in cached files
    if 'num_trades' not in df.columns:
        df['num_trades'] = 0.0
    if 'taker_buy_base' not in df.columns:
        df['taker_buy_base'] = df['volume'] * 0.5

    # ML Feature calculations
    vol_ma = df['volume'].rolling(20, min_periods=1).mean()
    df['volume_ma_ratio'] = np.where(vol_ma > 0, df['volume'] / vol_ma, 1.0)
    df['taker_buy_ratio'] = np.where(df['volume'] > 0, df['taker_buy_base'] / df['volume'], 0.5)
    
    body = (df['close'] - df['open']).abs()
    rng = df['high'] - df['low']
    df['body_wick_ratio'] = np.where(rng > 0, body / rng, 0.0)
    
    open_time_dt = pd.to_datetime(df['open_time'])
    df['time_hour'] = open_time_dt.dt.hour
    df['time_day_of_week'] = open_time_dt.dt.dayofweek

    return df"""

target_2 = target_2.replace("\r\n", "\n")
rep_2 = rep_2.replace("\r\n", "\n")

if target_2 in code:
    code = code.replace(target_2, rep_2)
    print("Patch 2 applied!")
else:
    print("Patch 2 not found!")

# 3. simulate_trades signature and overrides setup
target_3 = """def simulate_trades(df, min_ob_quality=None):
    current_entry_ob = None
    current_tp_ob = None
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
    touches = []
    current_entry_ob = None
    current_tp_ob = None
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

        local_min_quality = MIN_OB_QUALITY if min_ob_quality is None else int(min_ob_quality)"""

rep_3 = """def simulate_trades(df, min_ob_quality=None, iteration_parameters=None):
    if iteration_parameters is None:
        iteration_parameters = {}
    
    sl_ratio_min = iteration_parameters.get('sl_ratio_min', 0.015)
    kdj_j_long_cap = iteration_parameters.get('kdj_j_long_cap', 60.0)
    kdj_k_long_cap = iteration_parameters.get('kdj_k_long_cap', 50.0)
    kdj_k_short_floor = iteration_parameters.get('kdj_k_short_floor', 70.0)
    kdj_j_short_cap = iteration_parameters.get('kdj_j_short_cap', 100.0)
    atr_mult_exit = iteration_parameters.get('atr_mult_exit', 1.8)
    atr_mult_be = iteration_parameters.get('atr_mult_be', 2.0)
    rr_min = iteration_parameters.get('rr_min', 1.5)

    current_entry_ob = None
    current_tp_ob = None
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
    touches = []
    current_entry_ob = None
    current_tp_ob = None
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

        local_min_quality = iteration_parameters.get('min_ob_quality', MIN_OB_QUALITY if min_ob_quality is None else int(min_ob_quality))"""

target_3 = target_3.replace("\r\n", "\n")
rep_3 = rep_3.replace("\r\n", "\n")

if target_3 in code:
    code = code.replace(target_3, rep_3)
    print("Patch 3 applied!")
else:
    print("Patch 3 not found!")

# 4. LONG entry logic
target_4 = """                # ── [v5→v6] J < 60 cap retained, Displacement gate removed ──
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
                if (tp - close) / risk < 1.5: continue"""

rep_4 = """                # ── [v5→v6] J < 60 cap retained, Displacement gate removed ──
                if not (K < kdj_k_long_cap and K > K_prev and J < kdj_j_long_cap):
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
                if risk / close < sl_ratio_min: continue

                stp = get_structural_tp(close, 'LONG', valid_obs_tp)
                tp  = stp if stp else close + risk * 2.0
                if (tp - close) / risk < rr_min: continue

                # ML Classifier filter
                classifier = iteration_parameters.get('classifier_model')
                if classifier is not None:
                    features = [
                        float(df.at[i, 'MACD']), float(df.at[i, 'MACD_signal']), float(df.at[i, 'MACD_hist']),
                        float(df.at[i, 'K']), float(df.at[i, 'D']), float(df.at[i, 'J']),
                        float(df.at[i, 'ATR']), float(df.at[i, 'ATR_200']),
                        float(df.at[i, 'volume_ma_ratio']), float(df.at[i, 'taker_buy_ratio']),
                        float(df.at[i, 'body_wick_ratio']), float(df.at[i, 'time_hour']),
                        float(df.at[i, 'time_day_of_week']), float(ob['quality'])
                    ]
                    prob = classifier.predict_proba([features])[0][1]
                    threshold = iteration_parameters.get('classifier_threshold', 0.5)
                    if prob < threshold:
                        continue"""

target_4 = target_4.replace("\r\n", "\n")
rep_4 = rep_4.replace("\r\n", "\n")

if target_4 in code:
    code = code.replace(target_4, rep_4)
    print("Patch 4 applied!")
else:
    print("Patch 4 not found!")

# 5. SHORT entry logic
target_5 = """                    # v4/v5/v6/v7/v8: J > K > D unchanged
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
                    if (close - tp) / risk < 1.5: continue"""

rep_5 = """                    # v4/v5/v6/v7/v8: J > K > D unchanged
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
                    if K < kdj_k_short_floor:
                        continue
                    # ── [v8 FILTER 5] SHORT J cap: exhaustion already done ─
                    # J > 100 means overbought move is already in extreme.
                    # Both J>100 entries lost (−1.58%, −0.31%). Cap at 100.
                    if J > kdj_j_short_cap:
                        continue
                    # ── [v5→v6] Displacement gate removed ────────────────
                    # Quality score already includes displacement as a component.

                    sl   = ob['top'] + ATR * 0.5
                    risk = sl - close
                    if risk <= 0: continue
                    # ── [v9 FILTER 1] SL must be >= 1.5% from entry ──────
                    if risk / close < sl_ratio_min: continue

                    stp = get_structural_tp(close, 'SHORT', valid_obs_tp)
                    tp  = stp if stp else close - risk * 2.0
                    if (close - tp) / risk < rr_min: continue

                    # ML Classifier filter
                    classifier = iteration_parameters.get('classifier_model')
                    if classifier is not None:
                        features = [
                            float(df.at[i, 'MACD']), float(df.at[i, 'MACD_signal']), float(df.at[i, 'MACD_hist']),
                            float(df.at[i, 'K']), float(df.at[i, 'D']), float(df.at[i, 'J']),
                            float(df.at[i, 'ATR']), float(df.at[i, 'ATR_200']),
                            float(df.at[i, 'volume_ma_ratio']), float(df.at[i, 'taker_buy_ratio']),
                            float(df.at[i, 'body_wick_ratio']), float(df.at[i, 'time_hour']),
                            float(df.at[i, 'time_day_of_week']), float(ob['quality'])
                        ]
                        prob = classifier.predict_proba([features])[0][1]
                        threshold = iteration_parameters.get('classifier_threshold', 0.5)
                        if prob < threshold:
                            continue"""

target_5 = target_5.replace("\r\n", "\n")
rep_5 = rep_5.replace("\r\n", "\n")

if target_5 in code:
    code = code.replace(target_5, rep_5)
    print("Patch 5 applied!")
else:
    print("Patch 5 not found!")

# 6. Exit conditions overrides (LONG & SHORT)
target_6 = """            if entry_atr > 0 and close >= entry_price + entry_atr * 1.8:
                close_trade('ATR MOVE EXIT', pnl_pct)
                continue

            if close >= entry_price + entry_atr * 2:
                stop_loss_price = max(stop_loss_price, entry_price)
                df.at[i, 'Stop_Loss'] = stop_loss_price"""

rep_6 = """            if entry_atr > 0 and close >= entry_price + entry_atr * atr_mult_exit:
                close_trade('ATR MOVE EXIT', pnl_pct)
                continue

            if close >= entry_price + entry_atr * atr_mult_be:
                stop_loss_price = max(stop_loss_price, entry_price)
                df.at[i, 'Stop_Loss'] = stop_loss_price"""

target_6 = target_6.replace("\r\n", "\n")
rep_6 = rep_6.replace("\r\n", "\n")

if target_6 in code:
    code = code.replace(target_6, rep_6)
    print("Patch 6 applied!")
else:
    print("Patch 6 not found!")

target_7 = """            if entry_atr > 0 and close <= entry_price - entry_atr * 1.8:
                close_trade('ATR MOVE EXIT', pnl_pct)
                continue

            if close <= entry_price - entry_atr * 2:
                stop_loss_price = min(stop_loss_price, entry_price)
                df.at[i, 'Stop_Loss'] = stop_loss_price"""

rep_7 = """            if entry_atr > 0 and close <= entry_price - entry_atr * atr_mult_exit:
                close_trade('ATR MOVE EXIT', pnl_pct)
                continue

            if close <= entry_price - entry_atr * atr_mult_be:
                stop_loss_price = min(stop_loss_price, entry_price)
                df.at[i, 'Stop_Loss'] = stop_loss_price"""

target_7 = target_7.replace("\r\n", "\n")
rep_7 = rep_7.replace("\r\n", "\n")

if target_7 in code:
    code = code.replace(target_7, rep_7)
    print("Patch 7 applied!")
else:
    print("Patch 7 not found!")

# Restore line endings
if original_crlf:
    code = code.replace("\n", "\r\n")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)
print("Successfully saved changes to Binance backtest bot.py!")
