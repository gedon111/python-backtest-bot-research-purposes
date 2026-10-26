"""
EXPERIMENTAL -- ONE-TIME pull of BTCUSDT 1h candles (2018-01-01 UTC -> last
closed hour) from Binance's public klines endpoint, written to
experimental/data/btcusdt_1h.csv plus a manifest.

This is the only network access in the experimental study, run once with
the user's explicit approval (2026-10-26). Everything downstream reads the
committed CSV offline. The script refuses to overwrite an existing CSV.

It deliberately prints and records only counts, date ranges, gaps and the
overlap cross-check against the committed 4h series -- no prices or
returns from the holdout (open_time >= 2026-08-08 00:00 UTC).

Cross-check: 1h bars are aggregated to 4h (open=first, high=max, low=min,
close=last, volume=sum) and compared with artifacts/candles_extended.json
over their full overlap. That file's OHLCV is the paper's data source.
Its open_time (and `time`) labels are UTC+8-shifted by design -- see
get_candles() in research_analysis.py, "UTC+8-shifted, matching this
project's historical candle-cache convention" -- so they are shifted back
by 8h before comparing. This file's own open_time is true UTC.

`--recheck` rebuilds the manifest from the committed CSV without any
network access (endpoint and pull time are carried over).
"""

import hashlib
import json
import os
import sys
import time
import urllib.request

import pandas as pd

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "btcusdt_1h.csv")
MANIFEST_PATH = os.path.join(DATA_DIR, "btcusdt_1h_manifest.json")
EXTENDED_4H_PATH = os.path.join(BASE_DIR, "artifacts", "candles_extended.json")

ENDPOINTS = ["https://api.binance.com/api/v3/klines", "https://data-api.binance.vision/api/v3/klines"]
START_MS = int(pd.Timestamp("2018-01-01 00:00:00", tz="UTC").timestamp() * 1000)
HOUR_MS = 3_600_000
HOLDOUT_START = pd.Timestamp("2026-08-08 00:00:00")


def fetch(endpoint, start_ms):
    url = f"{endpoint}?symbol=BTCUSDT&interval=1h&limit=1000&startTime={start_ms}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def pull():
    pulled_at_ms = int(time.time() * 1000)
    last_err = None
    for endpoint in ENDPOINTS:
        rows, start = [], START_MS
        try:
            while True:
                batch = fetch(endpoint, start)
                if not batch:
                    break
                rows.extend(batch)
                start = batch[-1][0] + HOUR_MS
                if start > pulled_at_ms or len(batch) < 1000:
                    break
                time.sleep(0.25)
            return endpoint, pulled_at_ms, rows
        except Exception as exc:  # try the mirror
            last_err = exc
            print(f"[pull] {endpoint} failed: {exc!r}")
    raise RuntimeError(f"all endpoints failed: {last_err!r}")


def main():
    if "--recheck" in sys.argv:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            old = json.load(f)
        endpoint = old["endpoint"]
        pulled_at_ms = int(pd.Timestamp(old["pulled_at_utc"]).timestamp() * 1000)
        df = pd.read_csv(CSV_PATH)
        df["open_ms"] = df["time"].astype("int64") * 1000
    else:
        if os.path.exists(CSV_PATH):
            print(f"Refusing: {os.path.relpath(CSV_PATH, BASE_DIR)} already exists (one-time pull).")
            sys.exit(1)
        endpoint, pulled_at_ms, rows = pull()
        # Keep only fully closed bars (close_time < pull time), de-duplicated.
        rows = [r for r in rows if r[6] < pulled_at_ms]
        df = pd.DataFrame(rows, columns=["open_ms", "open", "high", "low", "close", "volume", "close_ms", "quote_volume",
                                         "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"])
        df = df.drop_duplicates("open_ms").sort_values("open_ms").reset_index(drop=True)
        for c in ["open", "high", "low", "close", "volume", "taker_buy_base"]:
            df[c] = df[c].astype(float)
        df["time"] = (df["open_ms"] // 1000).astype(int)
        df["open_time"] = pd.to_datetime(df["open_ms"], unit="ms")          # true UTC, naive
        out = df[["time", "open_time", "open", "high", "low", "close", "volume", "num_trades", "taker_buy_base"]].copy()
        out["open_time"] = out["open_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(DATA_DIR, exist_ok=True)
        out.to_csv(CSV_PATH, index=False, lineterminator="\n")
    with open(CSV_PATH, "rb") as f:
        csv_sha = hashlib.sha256(f.read()).hexdigest()

    # Gaps (missing hours), reported, not filled.
    step = df["open_ms"].diff().iloc[1:]
    gap_rows = df.iloc[1:][step != HOUR_MS]
    gaps = [{"after": str(pd.to_datetime(int(df.at[k - 1, "open_ms"]), unit="ms")),
             "next": str(pd.to_datetime(int(df.at[k, "open_ms"]), unit="ms")),
             "missing_hours": int((df.at[k, "open_ms"] - df.at[k - 1, "open_ms"]) // HOUR_MS - 1)}
            for k in gap_rows.index]

    # Cross-check against the committed 4h series over the overlap.
    with open(EXTENDED_4H_PATH, encoding="utf-8") as f:
        four = pd.DataFrame(json.load(f))[["open_time", "open", "high", "low", "close", "volume"]]
    four["open_time"] = pd.to_datetime(four["open_time"]) - pd.Timedelta(hours=8)   # UTC+8 labels -> UTC
    h = df.assign(ts=pd.to_datetime(df["open_ms"], unit="ms"))
    h = h[h["ts"] < HOLDOUT_START]
    h["bucket"] = h["ts"].dt.floor("4h")
    agg = h.groupby("bucket").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                  close=("close", "last"), volume=("volume", "sum"), n_hours=("open", "size"))
    merged = four.merge(agg, left_on="open_time", right_index=True, how="left", suffixes=("_4h", "_1h"))
    missing_in_1h = merged["open_1h"].isna()
    both = merged[~missing_in_1h]
    price_cols = ["open", "high", "low", "close"]
    price_match = (both[[f"{c}_4h" for c in price_cols]].to_numpy() == both[[f"{c}_1h" for c in price_cols]].to_numpy()).all(axis=1)
    vol_rel = (both["volume_4h"] - both["volume_1h"]).abs() / both["volume_4h"].clip(lower=1e-12)
    mismatch = both[~price_match | (vol_rel > 1e-6)]
    cross_check = {
        "four_hour_bars_compared": int(len(both)),
        "four_hour_bars_missing_from_1h": int(missing_in_1h.sum()),
        "ohlc_exact_and_volume_within_1e-6": int(len(both) - len(mismatch)),
        "mismatching_bars": int(len(mismatch)),
        "mismatching_bars_with_incomplete_hours": int((mismatch["n_hours"] < 4).sum()),
        "first_mismatches": [
            {"open_time": str(r.open_time), "n_hours": int(r.n_hours),
             "ohlc_match": bool((r.open_4h, r.high_4h, r.low_4h, r.close_4h) == (r.open_1h, r.high_1h, r.low_1h, r.close_1h))}
            for r in mismatch.head(20).itertuples()
        ],
    }

    ts = pd.to_datetime(df["open_ms"], unit="ms")
    manifest = {
        "pulled_at_utc": str(pd.to_datetime(pulled_at_ms, unit="ms")),
        "endpoint": endpoint, "symbol": "BTCUSDT", "interval": "1h", "time_convention": "open_time and time are true UTC (artifacts/ 4h files are UTC+8-labelled by design)",
        "csv_sha256": csv_sha, "total_bars": int(len(df)),
        "first_open_time": str(ts.iloc[0]), "last_open_time": str(ts.iloc[-1]),
        "segment_bar_counts": {
            "2018_2021": int((ts < pd.Timestamp("2022-01-01")).sum()),
            "2022_2025": int(((ts >= pd.Timestamp("2022-01-01")) & (ts < pd.Timestamp("2026-01-01"))).sum()),
            "2026_01_01_to_2026_08_07_seen_at_4h": int(((ts >= pd.Timestamp("2026-01-01")) & (ts < HOLDOUT_START)).sum()),
            "holdout_from_2026_08_08": int((ts >= HOLDOUT_START).sum()),
        },
        "gaps": gaps, "gap_count": len(gaps), "missing_hours_total": int(sum(g["missing_hours"] for g in gaps)),
        "cross_check_vs_candles_extended_4h": cross_check,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps({k: v for k, v in manifest.items() if k != "gaps"}, indent=2))


if __name__ == "__main__":
    main()
