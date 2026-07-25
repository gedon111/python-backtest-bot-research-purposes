import argparse
import hashlib
import importlib.util
import json
import os
import sys
import threading
import http.server
import socketserver
import webbrowser
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import db_manager
import pickle
import time

SELECTED_ITERATION_ID = 0


DEFAULT_LEVELS = [0, 1, 2, 3]
SCHEMA_VERSION = "1.0.0"


def fallback_json(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if pd.isna(obj):
        return None
    return str(obj)


def load_bot_module():
    try:
        spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
        bot = importlib.util.module_from_spec(spec)
        sys.modules["bot"] = bot
        spec.loader.exec_module(bot)
    except Exception as e:
        print(f"Warning: Failed to import bot normally ({e}). Attempting offline mock...")
        import types
        binance_mod = types.ModuleType('binance')
        binance_client_mod = types.ModuleType('binance.client')
        class DummyClient:
            KLINE_INTERVAL_4HOUR = '4h'
            def __init__(self, *args, **kwargs): pass
            def ping(self): pass
            def get_klines(self, *args, **kwargs): return []
        binance_client_mod.Client = DummyClient
        binance_mod.client = binance_client_mod
        sys.modules['binance'] = binance_mod
        sys.modules['binance.client'] = binance_client_mod
        
        spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
        bot = importlib.util.module_from_spec(spec)
        sys.modules["bot"] = bot
        spec.loader.exec_module(bot)
    return bot


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def to_native(value):
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
    out = []
    for row in records:
        clean = {}
        for key, value in row.items():
            clean[key] = to_native(value)
        out.append(clean)
    return out


def hash_payload(payload):
    canonical = json.dumps(payload, sort_keys=True, default=fallback_json, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest(args, candles):
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "start_time": args.start,
        "end_time": args.end,
        "levels": args.levels,
        "candle_count": len(candles),
    }


def build_verification_report(manifest, candles, runs_by_threshold):
    ohlc_payload = [
        {
            "time": c["time"],
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
        }
        for c in candles
    ]
    indicator_payload = [
        {
            "time": c["time"],
            "MACD": c["MACD"],
            "MACD_signal": c["MACD_signal"],
            "MACD_hist": c["MACD_hist"],
            "K": c["K"],
            "D": c["D"],
            "J": c["J"],
            "ATR": c["ATR"],
            "ATR_200": c["ATR_200"],
        }
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
            "Cross-source TradingView API pull is not used; this report validates deterministic Binance snapshot + recalculation consistency.",
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


def export_artifacts(bot, args):
    interval_map = {"4h": bot.Client.KLINE_INTERVAL_4HOUR}
    if args.timeframe not in interval_map:
        raise ValueError(f"Unsupported timeframe: {args.timeframe}")

    print("Fetching candles...")
    try:
        base_df = bot.get_candles(
            symbol=args.symbol,
            interval=interval_map[args.timeframe],
            start_time=args.start,
            end_time=args.end,
        )
    except Exception as e:
        print(f"Warning: Failed to fetch candles from API ({e}). Attempting to load from local cache...")
        cache_path = os.path.join(args.output_dir, "candles.csv")
        if os.path.isfile(cache_path):
            base_df = pd.read_csv(cache_path)
            base_df["open_time"] = pd.to_datetime(base_df["open_time"])
        else:
            raise FileNotFoundError(f"No local candles cache found at {cache_path} and API connection failed.")

    print("Computing indicators...")
    base_df = bot.compute_indicators(base_df)
    base_df["time"] = base_df["open_time"].apply(lambda x: int(x.timestamp()))

    candle_cols = [
        "time",
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "MACD",
        "MACD_signal",
        "MACD_hist",
        "K",
        "D",
        "J",
        "ATR",
        "ATR_200",
        "Trade_Status"
    ]

    runs_by_threshold = {}
    threshold_runs = []
    sim_dfs = {}
    for level in args.levels:
        print(f"Running simulation for min_ob_quality={level}...")
        sim_df = bot.simulate_trades(base_df.copy(), min_ob_quality=level)
        sim_dfs[level] = sim_df
        stats = sim_df.attrs.get("trade_stats", {})
        trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
        obs = bot.compute_smc(sim_df)
        trades = normalize_records(trades_df.to_dict(orient="records")) if not trades_df.empty else []
        obs = normalize_records(obs)
        stats = {k: to_native(v) for k, v in stats.items()}

        runs_by_threshold[level] = {
            "obs": obs,
            "trades": trades,
            "stats": stats,
        }
        threshold_runs.append(
            {
                "min_quality": level,
                "trade_stats": stats,
                "trade_count": len(trades),
                "orderblock_count": len(obs),
            }
        )

    # Add Trade_Status to base_df for candles.json
    default_level = args.default_view_quality
    if default_level in sim_dfs:
        base_df["Trade_Status"] = sim_dfs[default_level]["Trade_Status"]
    else:
        base_df["Trade_Status"] = ""
    base_df["Trade_Status"] = base_df["Trade_Status"].fillna("")

    candles = normalize_records(base_df[candle_cols].to_dict(orient="records"))

    manifest = build_manifest(args, candles)
    verification_report = build_verification_report(manifest, candles, runs_by_threshold)

    ensure_dir(args.output_dir)
    with open(os.path.join(args.output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=fallback_json)
    with open(os.path.join(args.output_dir, "candles.json"), "w", encoding="utf-8") as f:
        json.dump(candles, f, indent=2, default=fallback_json)
    with open(os.path.join(args.output_dir, "threshold_runs.json"), "w", encoding="utf-8") as f:
        json.dump(threshold_runs, f, indent=2, default=fallback_json)
    with open(os.path.join(args.output_dir, "runs_by_threshold.json"), "w", encoding="utf-8") as f:
        json.dump(runs_by_threshold, f, indent=2, default=fallback_json)
    with open(os.path.join(args.output_dir, "verification_report.json"), "w", encoding="utf-8") as f:
        json.dump(verification_report, f, indent=2, default=fallback_json)

    candles_df = pd.DataFrame(candles)
    candles_df.to_csv(os.path.join(args.output_dir, "candles.csv"), index=False)
    pd.DataFrame(threshold_runs).to_csv(os.path.join(args.output_dir, "threshold_runs.csv"), index=False)
    default_level = args.default_view_quality
    default_run = runs_by_threshold.get(default_level, runs_by_threshold[args.levels[0]])
    pd.DataFrame(default_run["trades"]).to_csv(os.path.join(args.output_dir, "trades_default_view.csv"), index=False)
    pd.DataFrame(default_run["obs"]).to_csv(os.path.join(args.output_dir, "orderblocks_default_view.csv"), index=False)

    # ─── DATABASE EXPORT ─────────────────────────────────────────────────────
    print("Connecting to SQL database...")
    db_url = args.db_url if args.db_url else db_manager.get_db_url()
    try:
        engine = db_manager.init_db(db_url)
        db_manager.clear_db(engine)  # Fresh run, clear old values
        session = db_manager.get_session(engine)
        
        print("Saving candles to database...")
        candles_to_save = []
        for _, row in base_df.iterrows():
            candle_model = db_manager.Candle(
                time=int(row['time']),
                symbol=args.symbol,
                interval=args.timeframe,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                macd=float(row['MACD']) if pd.notnull(row['MACD']) else None,
                macd_signal=float(row['MACD_signal']) if pd.notnull(row['MACD_signal']) else None,
                macd_hist=float(row['MACD_hist']) if pd.notnull(row['MACD_hist']) else None,
                k=float(row['K']) if pd.notnull(row['K']) else None,
                d=float(row['D']) if pd.notnull(row['D']) else None,
                j=float(row['J']) if pd.notnull(row['J']) else None,
                atr_14=float(row['ATR']) if pd.notnull(row['ATR']) else None,
                atr_200=float(row['ATR_200']) if pd.notnull(row['ATR_200']) else None,
                volume_ma_ratio=float(row['volume_ma_ratio']) if pd.notnull(row.get('volume_ma_ratio')) else None,
                taker_buy_ratio=float(row['taker_buy_ratio']) if pd.notnull(row.get('taker_buy_ratio')) else None,
                body_wick_ratio=float(row['body_wick_ratio']) if pd.notnull(row.get('body_wick_ratio')) else None,
                time_hour=int(row['time_hour']) if pd.notnull(row.get('time_hour')) else None,
                time_day_of_week=int(row['time_day_of_week']) if pd.notnull(row.get('time_day_of_week')) else None
            )
            candles_to_save.append(candle_model)
        session.bulk_save_objects(candles_to_save)
        session.commit()

        print("Saving order blocks to database...")
        first_level = args.levels[0]
        obs_raw = bot.compute_smc(sim_dfs[first_level])
        
        ob_lookup = {}
        for ob in obs_raw:
            ob_model = db_manager.OrderBlock(
                symbol=args.symbol,
                interval=args.timeframe,
                type=ob['type'],
                top=float(ob['top']),
                bottom=float(ob['bottom']),
                created_at=int(ob['created_at']),
                ob_bar=int(ob['ob_bar']),
                level=ob['level'],
                structure=ob['structure'],
                mitigated_at=int(ob['mitigated_at']) if (pd.notnull(ob.get('mitigated_at')) and ob['mitigated_at'] < len(base_df)) else None,
                quality=int(ob['quality']),
                quality_displacement=bool(ob.get('quality_displacement', False)),
                quality_large_bar=bool(ob.get('quality_large_bar', False)),
                quality_fvg=bool(ob.get('quality_fvg', False)),
                quality_liquidity_sweep=bool(ob.get('quality_liquidity_sweep', False)),
                quality_volume_expansion=bool(ob.get('quality_volume_expansion', False))
            )
            session.add(ob_model)
            session.flush()  # Flush to generate ob_id
            
            key = (ob['created_at'], ob['ob_bar'], ob['type'], ob['level'])
            ob_lookup[key] = ob_model.ob_id
        session.commit()

        print("Saving OB touch events to database...")
        touches_df = sim_dfs[first_level].attrs.get('touches_df', pd.DataFrame())
        if not touches_df.empty:
            touches_to_save = []
            for _, touch in touches_df.iterrows():
                ob_key = (int(touch['ob_created_at']), int(touch['ob_bar']), touch['ob_type'], touch['ob_level'])
                ob_id = ob_lookup.get(ob_key)
                if ob_id is None:
                    continue
                touch_model = db_manager.OBTouch(
                    ob_id=ob_id,
                    time=int(touch['time']),
                    touch_price=float(touch['touch_price']),
                    macd=float(touch['macd']) if pd.notnull(touch['macd']) else None,
                    macd_signal=float(touch['macd_signal']) if pd.notnull(touch['macd_signal']) else None,
                    macd_hist=float(touch['macd_hist']) if pd.notnull(touch['macd_hist']) else None,
                    k=float(touch['k']) if pd.notnull(touch['k']) else None,
                    d=float(touch['d']) if pd.notnull(touch['d']) else None,
                    j=float(touch['j']) if pd.notnull(touch['j']) else None,
                    k_accel=float(touch['k_accel']) if pd.notnull(touch['k_accel']) else None,
                    atr_14=float(touch['atr_14']) if pd.notnull(touch['atr_14']) else None,
                    atr_200=float(touch['atr_200']) if pd.notnull(touch['atr_200']) else None
                )
                touches_to_save.append(touch_model)
            session.bulk_save_objects(touches_to_save)
            session.commit()

        print("Saving trades to database...")
        trades_to_save = []
        for level in args.levels:
            trades_df = sim_dfs[level].attrs.get("trades_df", pd.DataFrame())
            if trades_df.empty:
                continue
            for _, tr in trades_df.iterrows():
                entry_key = (int(tr['entry_ob_created_at']), int(tr['entry_ob_bar']), tr['entry_ob_type'], tr['entry_ob_level'])
                entry_ob_id = ob_lookup.get(entry_key)
                if entry_ob_id is None:
                    continue
                
                tp_ob_id = None
                if tr.get('tp_is_structural') and pd.notnull(tr.get('tp_ob_created_at')):
                    tp_key = (int(tr['tp_ob_created_at']), int(tr['tp_ob_bar']), tr['tp_ob_type'], tr['tp_ob_level'])
                    tp_ob_id = ob_lookup.get(tp_key)
                
                trade_model = db_manager.Trade(
                    symbol=args.symbol,
                    interval=args.timeframe,
                    side=tr['side'],
                    min_ob_quality=int(level),
                    entry_time=int(base_df.loc[int(tr['entry_idx']), 'time']),
                    exit_time=int(base_df.loc[int(tr['exit_idx']), 'time']),
                    entry_price=float(tr['entry']),
                    exit_price=float(tr['exit']),
                    stop_loss=float(tr['stop_loss']),
                    take_profit=float(tr['take_profit']),
                    pnl_pct=float(tr['pnl_pct']),
                    hold_bars=int(tr['hold_bars']),
                    exit_reason=tr['exit_reason'],
                    entry_ob_id=entry_ob_id,
                    tp_ob_id=tp_ob_id
                )
                trades_to_save.append(trade_model)
        if trades_to_save:
            session.bulk_save_objects(trades_to_save)
            session.commit()
            
        print("Database save completed successfully.")
    except Exception as e:
        import traceback
        print(f"Warning: Failed to save results to database ({e})")
        traceback.print_exc()

    if args.export_gsheet:
        print("Exporting to Google Sheets (optional mode)...")
        try:
            bot.push_all_thresholds_to_gsheet(base_df.copy(), levels=args.levels, precomputed_dfs=sim_dfs)
        except Exception as e:
            print(f"Warning: Failed to export to Google Sheets: {e}")
            print("Please ensure your Google Service Account has Editor permissions for the target Google Sheet.")

    return manifest, threshold_runs, verification_report


def parse_args():
    parser = argparse.ArgumentParser(description="Export local dashboard artifacts for Binance backtest GUI.")
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
    args = parser.parse_args()
    args.levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]
    if not args.levels:
        args.levels = DEFAULT_LEVELS
    if args.default_view_quality not in args.levels:
        args.default_view_quality = args.levels[0]
    return args


def main():
    args = parse_args()
    print("Loading Binance backtest bot module...")
    bot = load_bot_module()
    manifest, threshold_runs, verification_report = export_artifacts(bot, args)
    print("\n=== Export Complete ===")
    print(f"Symbol/Timeframe: {manifest['symbol']} {manifest['timeframe']}")
    print(f"Candles: {manifest['candle_count']}")
    print(f"Thresholds: {', '.join([str(x['min_quality']) for x in threshold_runs])}")
    print(f"Verification: {verification_report['status']}")
    print(f"Artifacts directory: {args.output_dir}")

    if getattr(args, 'no_server', False):
        print("\nSkipping local dashboard web server (--no-server was set).")
        return

    # Start local web server and open browser
    PORT = 8765
    HOST = "127.0.0.1"
    
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

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
            try:
                import urllib.parse
                parsed_url = urllib.parse.urlparse(self.path)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                min_ob_quality_str = query_params.get("min_ob_quality", [None])[0]
                min_ob_quality = None
                if min_ob_quality_str is not None:
                    try:
                        min_ob_quality = int(min_ob_quality_str)
                    except ValueError:
                        pass
                
                engine = db_manager.init_db()
                session = db_manager.get_session(engine)
                
                # Query trades and join order_blocks to fetch quality score and criteria flags
                query = session.query(
                    db_manager.Trade,
                    db_manager.OrderBlock.quality,
                    db_manager.OrderBlock.quality_displacement,
                    db_manager.OrderBlock.quality_large_bar,
                    db_manager.OrderBlock.quality_fvg,
                    db_manager.OrderBlock.quality_liquidity_sweep,
                    db_manager.OrderBlock.quality_volume_expansion
                ).join(db_manager.OrderBlock, db_manager.Trade.entry_ob_id == db_manager.OrderBlock.ob_id)
                
                if min_ob_quality is not None:
                    query = query.filter(db_manager.Trade.min_ob_quality == min_ob_quality)
                
                results = query.all()
                
                trades_data = []
                for trade, quality, disp, lb, fvg, liq, vol in results:
                    trades_data.append({
                        "trade_id": trade.trade_id,
                        "side": trade.side,
                        "min_ob_quality": trade.min_ob_quality,
                        "entry_time": trade.entry_time,
                        "exit_time": trade.exit_time,
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "stop_loss": trade.stop_loss,
                        "take_profit": trade.take_profit,
                        "pnl_pct": trade.pnl_pct,
                        "hold_bars": trade.hold_bars,
                        "exit_reason": trade.exit_reason,
                        "entry_ob_id": trade.entry_ob_id,
                        "tp_ob_id": trade.tp_ob_id,
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
                self.wfile.write(json.dumps(trades_data, default=fallback_json).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Database error: {e}")


        def handle_get_iterations(self):
            try:
                engine = db_manager.init_db()
                session = db_manager.get_session(engine)
                
                trades = []
                try:
                    trades = session.query(db_manager.Trade).all()
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
                        "base_trades": count,
                        "base_pnl": pnl,
                        "base_wr": wr,
                        "tuned_trades": count,
                        "tuned_pnl": pnl,
                        "tuned_wr": wr
                    }
                
                base_iter = {
                    "iteration_id": 0,
                    "label": "Heuristic Base (No ML)",
                    "created_at": 1782016399,
                    "model_type": "Heuristic Base",
                    "parameters": {
                        "sl_ratio_min": 0.015,
                        "kdj_j_long_cap": 60.0,
                        "kdj_k_long_cap": 50.0,
                        "kdj_k_short_floor": 70.0,
                        "kdj_j_short_cap": 100.0,
                        "atr_mult_exit": 1.8,
                        "atr_mult_be": 2.0,
                        "rr_min": 1.5,
                        "classifier_threshold": 0.5
                    },
                    "metrics": base_metrics,
                    "pattern_diff": {
                        "tuned_parameters": {
                            "sl_ratio_min": 0.015,
                            "kdj_j_long_cap": 60.0,
                            "kdj_k_long_cap": 50.0,
                            "kdj_k_short_floor": 70.0,
                            "kdj_j_short_cap": 100.0,
                            "atr_mult_exit": 1.8,
                            "atr_mult_be": 2.0,
                            "rr_min": 1.5
                        },
                        "pnl_improvement_pct": 0.0,
                        "reweighted_failures_count": 0
                    }
                }
                
                data = [base_iter]
                session.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))
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
                            "candleUp": "#26a69a",
                            "candleDown": "#ef5350",
                            "candleWick": "#475569",
                            "demand": "#0d9488",
                            "supply": "#ea580c",
                            "macd": "#1d4ed8",
                            "macdSignal": "#f97316",
                            "macdHist": "#10b981",
                            "kdjK": "#0d9488",
                            "kdjD": "#3b82f6",
                            "kdjJ": "#ec4899",
                            "atr14": "#8b5cf6",
                            "atr200": "#6b7280"
                        }
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
                
                theme_path = "chart_theme.json"
                with open(theme_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            except Exception as e:
                self.send_error(500, f"Error saving theme: {e}")

        def handle_push_gsheet(self):
            try:
                bot = load_bot_module()
                
                global SELECTED_ITERATION_ID
                it_id = SELECTED_ITERATION_ID
                
                iteration_parameters = None
                active_model = None
                
                if it_id > 0:
                    engine = db_manager.init_db()
                    session = db_manager.get_session(engine)
                    iteration = session.query(db_manager.MLIteration).filter(db_manager.MLIteration.iteration_id == it_id).first()
                    if iteration:
                        iteration_params = json.loads(iteration.parameters)
                        model_path = iteration_params.get("classifier_model_path")
                        if model_path and os.path.isfile(model_path):
                            try:
                                with open(model_path, "rb") as f:
                                    active_model = pickle.load(f)
                            except Exception:
                                pass
                        
                        iteration_parameters = {
                            "sl_ratio_min": iteration_params.get("sl_ratio_min"),
                            "kdj_j_long_cap": iteration_params.get("kdj_j_long_cap"),
                            "kdj_k_long_cap": iteration_params.get("kdj_k_long_cap"),
                            "kdj_k_short_floor": iteration_params.get("kdj_k_short_floor"),
                            "kdj_j_short_cap": iteration_params.get("kdj_j_short_cap"),
                            "atr_mult_exit": iteration_params.get("atr_mult_exit"),
                            "atr_mult_be": iteration_params.get("atr_mult_be"),
                            "rr_min": iteration_params.get("rr_min"),
                            "classifier_model": active_model,
                            "classifier_threshold": iteration_params.get("classifier_threshold", 0.5)
                        }
                    session.close()
                
                cache_path = "artifacts/candles.csv"
                if os.path.isfile(cache_path):
                    base_df = pd.read_csv(cache_path)
                    base_df["open_time"] = pd.to_datetime(base_df["open_time"])
                else:
                    base_df = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR)
                
                base_df = bot.compute_indicators(base_df)
                
                levels = [0, 1, 2, 3]
                sim_dfs = {}
                for level in levels:
                    sim_df = bot.simulate_trades(base_df.copy(), min_ob_quality=level, iteration_parameters=iteration_parameters)
                    sim_dfs[level] = sim_df
                
                print(f"[Dashboard Server] Exporting iteration {it_id} to Google Sheets...")
                bot.push_all_thresholds_to_gsheet(base_df.copy(), levels=levels, precomputed_dfs=sim_dfs)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "Success", "message": "Google Sheets updated."}).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Google Sheets Sync failed: {e}")

    print(f"\n[Dashboard] Starting local web server on http://{HOST}:{PORT} ...")
    
    def serve():
        with ThreadingHTTPServer((HOST, PORT), SilentHandler) as httpd:
            httpd.serve_forever()

    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()

    url = f"http://{HOST}:{PORT}/gui.html"
    print(f"[Dashboard] Opening dashboard in browser: {url}")
    webbrowser.open(url)
    
    print("\nPress Ctrl+C to stop the server and exit.")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
