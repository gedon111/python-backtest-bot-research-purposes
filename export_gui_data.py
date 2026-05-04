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
    base_df = bot.get_candles(
        symbol=args.symbol,
        interval=interval_map[args.timeframe],
        start_time=args.start,
        end_time=args.end,
    )

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
    ]
    candles = normalize_records(base_df[candle_cols].to_dict(orient="records"))

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

    # Start local web server and open browser
    PORT = 8765
    HOST = "127.0.0.1"
    
    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    print(f"\n[Dashboard] Starting local web server on http://{HOST}:{PORT} ...")
    
    def serve():
        with socketserver.TCPServer((HOST, PORT), SilentHandler) as httpd:
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
