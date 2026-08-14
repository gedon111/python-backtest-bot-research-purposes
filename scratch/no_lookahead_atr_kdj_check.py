"""
No-lookahead verification for compute_indicators() — ATR(14), ATR_200, and
static KDJ(9,3,3). Part of the CLAUDE.md-mandated final no-lookahead
enforcement step (isolated task, run alone, per project rule).

Method (gold-standard causality test, not just source inspection): for a
sample of bar indices i spanning the dataset (including all rolling-window
boundaries: 9, 14, 26, 200), truncate the raw candle dataframe to df[:i+1]
and recompute compute_indicators() from scratch on the truncated frame. If
ATR/ATR_200/K/D/J at the truncated frame's LAST row differ at all from the
value at row i in the full-dataset computation, that row's value depended on
data after bar i — i.e., a lookahead violation. Exact equality (not just
"close") is required and asserted.

This complements (does not replace) the source-level fact, confirmed via
grep across the whole file, that no .rolling(...) call uses center=True and
no .shift() call uses a negative offset — the only two ways pandas rolling/
ewm could become forward-looking. rolling()/ewm(adjust=False) are causal by
construction when neither of those is present; this script empirically
confirms that construction holds for the actual columns used.
"""
import os
import importlib.util
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bot_path = os.path.join(BASE_DIR, "research_analysis.py")
CANDLES_CACHE_PATH = os.path.join(BASE_DIR, "artifacts", "candles.csv")

spec = importlib.util.spec_from_file_location("bot_lookahead", bot_path)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

CHECK_COLS = ["ATR", "ATR_200", "K", "D", "J"]


def main():
    df_raw = pd.read_csv(CANDLES_CACHE_PATH)
    df_raw["open_time"] = pd.to_datetime(df_raw["open_time"])
    n = len(df_raw)
    print(f"Loaded {n} bars.")

    print("Computing full-dataset indicators (reference)...")
    full = bot.compute_indicators(df_raw.copy())

    # Sample indices: window boundaries (9, 14, 26, 200) +/- a few bars,
    # plus evenly spaced points across the whole series, plus the very
    # first and last usable bars.
    boundary_points = []
    for w in (9, 14, 26, 200):
        boundary_points += [w - 1, w, w + 1, w + 2]
    spaced_points = list(np.linspace(210, n - 1, 20).astype(int))
    sample_idx = sorted(set(
        [p for p in boundary_points if 0 <= p < n] + spaced_points + [n - 1]
    ))
    print(f"Testing {len(sample_idx)} sample bar indices: {sample_idx}")

    failures = []
    for i in sample_idx:
        truncated = bot.compute_indicators(df_raw.iloc[:i + 1].copy())
        last_row = truncated.iloc[-1]
        full_row = full.iloc[i]
        for col in CHECK_COLS:
            v_trunc = float(last_row[col])
            v_full = float(full_row[col])
            if not (np.isnan(v_trunc) and np.isnan(v_full)) and v_trunc != v_full:
                failures.append({
                    "bar_index": i,
                    "column": col,
                    "truncated_value": v_trunc,
                    "full_dataset_value": v_full,
                    "diff": v_trunc - v_full,
                })

    print("\n--- Result ---")
    if failures:
        print(f"FAIL: {len(failures)} lookahead violations found.")
        for f in failures:
            print(f"  bar_index={f['bar_index']} column={f['column']} "
                  f"truncated={f['truncated_value']} full={f['full_dataset_value']} "
                  f"diff={f['diff']}")
    else:
        print(f"PASS: all {len(sample_idx)} sampled bars x {len(CHECK_COLS)} columns "
              f"({len(sample_idx) * len(CHECK_COLS)} checks) match exactly between "
              f"truncated and full-dataset computation. ATR(14), ATR_200, and static "
              f"KDJ(9,3,3) are confirmed causal at every sampled bar.")


if __name__ == "__main__":
    main()
