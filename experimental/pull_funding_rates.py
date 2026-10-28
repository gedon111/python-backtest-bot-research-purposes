"""
EXPERIMENTAL -- ONE-TIME pull of BTCUSDT USDT-M perpetual funding-rate
history (monthly files 2021-12 -> 2026-01) from Binance's public data
mirror, data.binance.vision, written to experimental/data/btcusdt_funding.csv
plus a manifest. fapi.binance.com/fapi/v1/fundingRate refused the
connection from this machine (WinError 10054), so the mirror's monthly
archives are used instead; each zip is checked against the sha256 in its
published .CHECKSUM file before it is read.

Run once with the user's explicit approval (2026-10-28, regional paper
revision item 3). Everything downstream (experimental/funding_cost.py) reads
the committed CSV offline. The script refuses to overwrite an existing CSV;
`--recheck` rebuilds the manifest from the committed CSV with no network.

Funding is settled every 8 hours (00:00, 08:00, 16:00 UTC). A positive rate
means longs pay shorts; a negative rate means shorts pay longs.
"""

import hashlib
import io
import json
import os
import sys
import time
import urllib.request
import zipfile

import pandas as pd

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "btcusdt_funding.csv")
MANIFEST_PATH = os.path.join(DATA_DIR, "btcusdt_funding_manifest.json")

MIRROR = "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT"
MONTHS = [str(m)[:7] for m in pd.period_range("2021-12", "2026-01", freq="M")]
EIGHT_HOURS_MS = 8 * 3_600_000


def _get(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def pull():
    pulled_at_ms = int(time.time() * 1000)
    frames, checksums = [], {}
    for month in MONTHS:
        name = f"BTCUSDT-fundingRate-{month}.zip"
        blob = _get(f"{MIRROR}/{name}")
        expected = _get(f"{MIRROR}/{name}.CHECKSUM").decode().split()[0]
        actual = hashlib.sha256(blob).hexdigest()
        if actual != expected:
            raise RuntimeError(f"{name}: sha256 {actual} != published {expected}")
        checksums[name] = actual
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            frames.append(pd.read_csv(z.open(z.namelist()[0])))
        time.sleep(0.1)
    raw = pd.concat(frames, ignore_index=True)
    return pulled_at_ms, raw, checksums


def main():
    if "--recheck" in sys.argv:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            old = json.load(f)
        pulled_at_utc, checksums = old["pulled_at_utc"], old["zip_sha256"]
        df = pd.read_csv(CSV_PATH)
    else:
        if os.path.exists(CSV_PATH):
            print(f"Refusing: {os.path.relpath(CSV_PATH, BASE_DIR)} already exists (one-time pull).")
            sys.exit(1)
        pulled_at_ms, raw, checksums = pull()
        pulled_at_utc = str(pd.to_datetime(pulled_at_ms, unit="ms"))
        df = pd.DataFrame({"fundingTime": raw["calc_time"].astype("int64"),
                           "fundingRate": raw["last_funding_rate"].astype(float),
                           "interval_hours": raw["funding_interval_hours"].astype(int)})
        df = df.drop_duplicates("fundingTime").sort_values("fundingTime").reset_index(drop=True)
        df["funding_time_utc"] = pd.to_datetime(df["fundingTime"], unit="ms").dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(CSV_PATH, index=False, lineterminator="\n")
    with open(CSV_PATH, "rb") as f:
        csv_sha = hashlib.sha256(f.read()).hexdigest()

    # Settlement times are nominally on the 8h grid but carry a few ms of
    # jitter; gaps are measured on the grid-rounded time.
    grid = (df["fundingTime"] / EIGHT_HOURS_MS).round().astype("int64")
    step = grid.diff().iloc[1:]
    manifest = {
        "pulled_at_utc": pulled_at_utc, "source": MIRROR, "zip_sha256": checksums, "symbol": "BTCUSDT",
        "time_convention": "fundingTime is true UTC milliseconds",
        "csv_sha256": csv_sha, "rows": int(len(df)),
        "first_funding_time_utc": str(pd.to_datetime(df["fundingTime"].iloc[0], unit="ms")),
        "last_funding_time_utc": str(pd.to_datetime(df["fundingTime"].iloc[-1], unit="ms")),
        "off_grid_steps": int((step != 1).sum()),
        "rate_min": float(df["fundingRate"].min()), "rate_max": float(df["fundingRate"].max()),
        "rate_mean": float(df["fundingRate"].mean()),
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
