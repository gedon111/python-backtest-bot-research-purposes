"""
Offline driver for export_gui_data.py's artifact-regeneration pipeline.

export_gui_data.export_artifacts() tries a LIVE Binance API call
(bot.get_candles) first and only falls back to the local artifacts/candles.csv
cache on failure. Per CLAUDE.md ("All scratch scripts run offline from
artifacts/candles.csv. No live API calls"), this driver forces that fallback
deterministically -- by making bot.get_candles raise immediately -- instead
of depending on network behavior. This does not change export_gui_data.py;
it patches the already-loaded bot module instance before calling the
pipeline's own existing exception handler, which already knows how to load
from cache.

Runs with the same default args export_gui_data.py's CLI would use
(symbol=BTCUSDT, timeframe=4h, start=2022-01-01, end=2026-01-01,
levels=[0,1,2,3], default_view_quality=1, output_dir=artifacts), minus the
local dashboard web server (not invoked here at all).
"""
import argparse
import sys

sys.path.insert(0, ".")
import export_gui_data as egd


def main():
    bot = egd.load_bot_module()

    def _no_live_call(*args, **kwargs):
        raise RuntimeError("Live API calls disabled for this offline regeneration run.")
    bot.get_candles = _no_live_call

    args = argparse.Namespace(
        symbol="BTCUSDT",
        timeframe="4h",
        start="2022-01-01 00:00:00",
        end="2026-01-01 00:00:00",
        levels=[0, 1, 2, 3],
        default_view_quality=1,
        output_dir="artifacts",
        export_gsheet=False,
        db_url=None,
        no_server=True,
    )

    manifest, threshold_runs, verification_report = egd.export_artifacts(bot, args)
    print("\n=== Export Complete (offline) ===")
    print(f"Symbol/Timeframe: {manifest['symbol']} {manifest['timeframe']}")
    print(f"Candles: {manifest['candle_count']}")
    print(f"Thresholds: {', '.join([str(x['min_quality']) for x in threshold_runs])}")
    print(f"Verification: {verification_report['status']}")
    print(f"Artifacts directory: {args.output_dir}")


if __name__ == "__main__":
    main()
