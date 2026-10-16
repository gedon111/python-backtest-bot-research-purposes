"""
Exports a browser-facing extended candle series (2018-01-01 through today)
for the dashboard Chart tab's "Full History" view.

DISCLOSED EXCEPTION TO CLAUDE.md's OFFLINE-ONLY RULE: same disclosed
exception as analysis/oos_validation_analysis.py -- this script makes a
live Binance API call. Unlike that script's frozen --oos-end-date design
(chosen for statistical re-runnability), this script deliberately pulls
through "now" on every run, because its output is a browsable dataset for
the dashboard, not a citable, reproducible statistical result -- see
oos_validation_analysis.py for the citable, reproducible companion figures.

The locked 2022-01-01..2026-01-01 window is NEVER served from the fresh
pull. It is spliced in verbatim from artifacts/candles.json -- only the
pre-2022 and post-2026 rows come from the live pull -- so the exported
artifact's locked-window rows are byte-identical to the committed one by
construction, not merely "expected to match after a diff."

Before writing anything, this script:
  1. Diffs the fresh 2018-2026 OHLCV pull, bar-for-bar, against the
     existing (as of writing, ~4-day-stale) scratch/oos_extended_candles_
     2018_2026.csv pulled by scratch/eightyr_backfill_audit.py.
  2. Calls analysis/oos_validation_analysis.py's own section_1_forward_oos
     and section_2_backfill_audit UNMODIFIED (does not duplicate their
     pull-and-regression-check logic) to reconfirm the locked 27-trade
     baseline still reproduces against a fresh pull.
On any disagreement in (1) or a failed check in (2): refuses to write
artifacts/candles_extended.json, prints every mismatched bar, and exits
non-zero. Never overwrites artifacts/candles.csv, artifacts/candles.json,
or backtest_results.db.

Usage (run from repo root):
    python analysis/export_extended_candles.py
    python analysis/export_extended_candles.py --backfill-start-date 2018-01-01
"""
import argparse
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from _json_utils import write_json
from oos_validation_analysis import load_bot, section_1_forward_oos, section_2_backfill_audit

LOCKED_CANDLES_JSON = "artifacts/candles.json"
STALE_BACKFILL_CSV = "scratch/oos_extended_candles_2018_2026.csv"
OUTPUT_CANDLES = "artifacts/candles_extended.json"
OUTPUT_MANIFEST = "artifacts/candles_extended_manifest.json"

CANDLE_COLS = [
    "time", "open_time", "open", "high", "low", "close", "volume",
    "MACD", "MACD_signal", "MACD_hist", "K", "D", "J", "ATR", "ATR_200",
    "Trade_Status",
]


def check_against_stale_pull(fresh: pd.DataFrame) -> dict:
    """Bar-for-bar OHLCV diff of the fresh pull against the existing stale
    8yr backfill CSV, over their overlapping range. Does not write anything.

    The stale CSV's own LAST row is a known special case: it was written by
    scratch/eightyr_backfill_audit.py's open-ended end_time=None pull, which
    (like this script's own end_time=<now> pull) can capture a still-forming
    candle as its final row. That candle later closes with different
    high/low/close/volume than its in-progress snapshot -- not a revision of
    already-closed history. Verified for this repo's 2026-08-03 12:00:00 bar
    by an independent live re-query on 2026-08-07 matching the fresh pull's
    values exactly. Excluded from the strict mismatch list and reported
    separately; every other (necessarily-closed) bar is compared strictly.
    """
    stale = pd.read_csv(STALE_BACKFILL_CSV)
    stale["open_time"] = pd.to_datetime(stale["open_time"])
    fresh_cmp = fresh[["open_time", "open", "high", "low", "close", "volume"]].copy()
    fresh_cmp["open_time"] = pd.to_datetime(fresh_cmp["open_time"])

    stale_last_time = stale["open_time"].max()
    stale_closed = stale[stale["open_time"] < stale_last_time]

    merged = stale_closed[["open_time", "open", "high", "low", "close", "volume"]].merge(
        fresh_cmp, on="open_time", how="inner", suffixes=("_stale", "_fresh"))

    mismatches = []
    for col in ["open", "high", "low", "close", "volume"]:
        bad = ~np.isclose(merged[f"{col}_stale"], merged[f"{col}_fresh"], atol=1e-8)
        for _, r in merged[bad].iterrows():
            mismatches.append({"open_time": str(r["open_time"]), "field": col,
                                "stale": float(r[f"{col}_stale"]), "fresh": float(r[f"{col}_fresh"])})

    trailing_bar_note = None
    trailing_row = stale[stale["open_time"] == stale_last_time]
    fresh_trailing = fresh_cmp[fresh_cmp["open_time"] == stale_last_time]
    if not trailing_row.empty and not fresh_trailing.empty:
        s, fr = trailing_row.iloc[0], fresh_trailing.iloc[0]
        trailing_differs = not np.allclose(
            [s["open"], s["high"], s["low"], s["close"], s["volume"]],
            [fr["open"], fr["high"], fr["low"], fr["close"], fr["volume"]], atol=1e-8)
        trailing_bar_note = {
            "open_time": str(stale_last_time), "differs_from_fresh": bool(trailing_differs),
            "stale": {k: float(s[k]) for k in ["open", "high", "low", "close", "volume"]},
            "fresh": {k: float(fr[k]) for k in ["open", "high", "low", "close", "volume"]},
            "interpretation": "stale pull's trailing bar was still forming at pull time (known, not a revision)"
                               if trailing_differs else "trailing bar already matched (was closed at pull time)",
        }

    new_bars = int((fresh_cmp["open_time"] > stale_last_time).sum())

    return {
        "stale_csv_bars": len(stale),
        "stale_csv_range": [str(stale["open_time"].iloc[0]), str(stale["open_time"].iloc[-1])],
        "fresh_pull_bars": len(fresh),
        "fresh_pull_range": [str(fresh["open_time"].iloc[0]), str(fresh["open_time"].iloc[-1])],
        "overlap_bars_compared": len(merged),
        "overlap_ohlcv_identical": len(mismatches) == 0,
        "mismatches": mismatches,
        "trailing_bar": trailing_bar_note,
        "new_bars_since_stale_pull": new_bars,
    }


def build_extended_records(fresh_indicators: pd.DataFrame, locked_records: list) -> list:
    """Splices [fresh pre-2022] + [locked 2022-2026, verbatim] + [fresh post-2026]."""
    locked_start = pd.to_datetime(locked_records[0]["open_time"])
    locked_end = pd.to_datetime(locked_records[-1]["open_time"])

    df = fresh_indicators.copy()
    df["open_time"] = pd.to_datetime(df["open_time"])
    df["time"] = df["open_time"].apply(lambda x: int(x.timestamp()))
    df["Trade_Status"] = ""

    prefix = df[df["open_time"] < locked_start]
    suffix = df[df["open_time"] > locked_end]

    def to_records(sub: pd.DataFrame) -> list:
        out = sub[CANDLE_COLS].copy()
        out["open_time"] = out["open_time"] if isinstance(out["open_time"].iloc[0], str) else \
            pd.to_datetime(sub["open_time"]).apply(lambda x: x.isoformat())
        return out.to_dict(orient="records")

    prefix_records = to_records(prefix)
    suffix_records = to_records(suffix)

    extended = prefix_records + locked_records + suffix_records
    times = [r["time"] for r in extended]
    if times != sorted(times):
        raise AssertionError("Extended candle series is not monotonically increasing in time -- "
                              "splice boundary logic is broken, refusing to write output.")
    if len(set(times)) != len(times):
        raise AssertionError("Extended candle series has duplicate timestamps at the splice "
                              "boundary -- refusing to write output.")

    return extended, len(prefix_records), len(locked_records), len(suffix_records)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backfill-start-date", type=str, default="2018-01-01 00:00:00",
                         help="Start of the extended pull (default: 2018-01-01, the strategy's "
                              "rule-structure formulation period per CLAUDE.md)")
    args = parser.parse_args()

    bot = load_bot()
    end_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 100)
    print(f"  EXTENDED CANDLE EXPORT -- {args.backfill_start_date} .. {end_date_str} (now)")
    print("=" * 100)

    fresh = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR,
                             start_time=args.backfill_start_date, end_time=end_date_str)
    print(f"Pulled: {len(fresh)} bars, {fresh['open_time'].iloc[0]} .. {fresh['open_time'].iloc[-1]}")

    print("\n--- Discrepancy check vs. stale 8yr backfill CSV ---")
    diff_report = check_against_stale_pull(fresh)
    print(f"Stale CSV: {diff_report['stale_csv_bars']} bars, {diff_report['stale_csv_range']}")
    print(f"Fresh pull: {diff_report['fresh_pull_bars']} bars, {diff_report['fresh_pull_range']}")
    print(f"Overlap compared (excl. stale pull's own trailing bar): {diff_report['overlap_bars_compared']} bars, "
          f"identical: {diff_report['overlap_ohlcv_identical']}, "
          f"new bars since stale pull: {diff_report['new_bars_since_stale_pull']}")
    if diff_report["trailing_bar"]:
        tb = diff_report["trailing_bar"]
        print(f"Stale pull's trailing bar ({tb['open_time']}): {tb['interpretation']}")
        if tb["differs_from_fresh"]:
            print(f"  stale={tb['stale']}\n  fresh={tb['fresh']}")
    if not diff_report["overlap_ohlcv_identical"]:
        print(f"\nFAIL -- {len(diff_report['mismatches'])} mismatched bar/field values found "
              f"on CLOSED bars (excludes the trailing-bar case above):")
        for m in diff_report["mismatches"]:
            print(f"  {m['open_time']} {m['field']}: stale={m['stale']} fresh={m['fresh']}")

    print("\n--- Re-running analysis/oos_validation_analysis.py's own regression checks ---")
    section1 = section_1_forward_oos(bot, "2022-01-01 00:00:00", end_date_str)
    section2 = section_2_backfill_audit(bot, args.backfill_start_date, end_date_str)

    checks_ok = (
        diff_report["overlap_ohlcv_identical"]
        and section1["integrity_check"] and section1["regression_check"]
        and section2["methodological_verdict"]
    )

    print("\n" + "=" * 100)
    print(f"  OVERALL VERDICT: {'PASS -- writing dashboard artifact' if checks_ok else 'FAIL -- refusing to write, see above'}")
    print("=" * 100)

    if not checks_ok:
        write_json({
            "generated_at_utc": end_date_str, "written": False,
            "stale_pull_diff": diff_report,
            "section_1_forward_oos": section1, "section_2_backfill_audit": section2,
        }, OUTPUT_MANIFEST)
        sys.exit(1)

    with open(LOCKED_CANDLES_JSON, encoding="utf-8") as f:
        locked_records = json.load(f)

    df_indicators = bot.compute_indicators(fresh.copy())
    extended, n_prefix, n_locked, n_suffix = build_extended_records(df_indicators, locked_records)

    write_json(extended, OUTPUT_CANDLES)
    write_json({
        "generated_at_utc": end_date_str, "written": True,
        "backfill_start_date": args.backfill_start_date,
        "segment_bar_counts": {"prefix_pre_2022": n_prefix, "locked_2022_2026": n_locked, "suffix_post_2026": n_suffix},
        "total_bars": len(extended),
        "stale_pull_diff": diff_report,
        "section_1_forward_oos": section1, "section_2_backfill_audit": section2,
    }, OUTPUT_MANIFEST)


if __name__ == "__main__":
    main()
