"""
EXPERIMENTAL -- offline estimate of perpetual-futures funding paid or received
over each of the paper's 27 baseline trades (2022-2026, 4h), from the
committed experimental/data/btcusdt_funding.csv (see pull_funding_rates.py).

Added 2026-10-28 for the regional paper revision (item 3). It does not
change any trade, rule or headline figure: funding is reported as a separate
cost line next to the paper's 0.20% round-trip cost.

Timing convention. A trade enters at the CLOSE of its entry bar and exits at
the CLOSE of its exit bar (simulate_trades()). Orders placed at a bar close
fill just after it, so a position opened at close T does not hold at T, and a
position closed at close T' still holds at T'. A funding settlement at time s
is therefore charged when entry_close < s <= exit_close (primary). The
inclusive interval entry_close <= s <= exit_close is reported as a check.

Cost per settlement, in percent of the trade's entry notional at 1x:
    side_sign * rate * (close_at_s / entry_price) * 100
side_sign = +1 for a long (pays when rate > 0), -1 for a short (receives when
rate > 0). close_at_s is the close of the 4h bar that ends at s, so the
notional follows price. A positive number is a cost to the trade.

4h open_time labels are UTC+8 (get_candles()); a bar's close in true UTC is
open_time - 8h + 4h.

Output: experimental/results_funding/funding.json
"""

import hashlib
import json
import os
import sys

import pandas as pd

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
sys.path.insert(0, BASE_DIR)

import research_analysis as ra  # noqa: E402

FUNDING_CSV = os.path.join(EXPERIMENT_DIR, "data", "btcusdt_funding.csv")
OUT_DIR = os.path.join(EXPERIMENT_DIR, "results_funding")
OUT_PATH = os.path.join(OUT_DIR, "funding.json")
EIGHT_HOURS_MS = 8 * 3_600_000


def bar_close_utc(df):
    return df["open_time"] - pd.Timedelta(hours=8) + pd.Timedelta(hours=4)


def funding_per_trade(df, trades, funding, inclusive_entry=False):
    close_utc = bar_close_utc(df)
    close_by_time = pd.Series(df["close"].values, index=close_utc.values)
    rows = []
    for t in trades.sort_values("entry_idx").itertuples():
        entry_close = close_utc.iloc[int(t.entry_idx)]
        exit_close = close_utc.iloc[int(t.exit_idx)]
        lower = funding["settle"] >= entry_close if inclusive_entry else funding["settle"] > entry_close
        held = funding[lower & (funding["settle"] <= exit_close)]
        side = str(t.side).upper()
        assert side in ("LONG", "SHORT"), side
        sign = 1.0 if side == "LONG" else -1.0
        cost_pct = float((sign * held["fundingRate"] * held["settle"].map(close_by_time) / t.entry * 100).sum())
        rows.append({
            "entry_idx": int(t.entry_idx), "side": side, "settlements": int(len(held)),
            "funding_cost_pct": cost_pct, "pnl_pct_gross": float(t.pnl_pct),
        })
    return rows


def main():
    with open(FUNDING_CSV, "rb") as f:
        funding_sha = hashlib.sha256(f.read()).hexdigest()
    funding = pd.read_csv(FUNDING_CSV)
    # Snap the few-ms settlement jitter onto the 8h grid the bars close on.
    funding["settle"] = pd.to_datetime((funding["fundingTime"] / EIGHT_HOURS_MS).round().astype("int64") * EIGHT_HOURS_MS, unit="ms")

    df = ra.compute_indicators(ra.load_candles())
    trades = ra.simulate_trades(df.copy(), min_ob_quality=0).attrs["trades_df"]
    assert len(trades) == ra.LOCKED_BASELINE_TRADE_COUNT

    primary = funding_per_trade(df, trades, funding)
    inclusive = funding_per_trade(df, trades, funding, inclusive_entry=True)
    for r in primary:
        r["pnl_pct_net_cost_and_funding"] = r["pnl_pct_gross"] - ra.BENCHMARK_ROUND_TRIP_DRAG_PCT - r["funding_cost_pct"]

    total_funding = sum(r["funding_cost_pct"] for r in primary)
    gross_total = sum(r["pnl_pct_gross"] for r in primary)
    net_cost_total = gross_total - ra.BENCHMARK_ROUND_TRIP_DRAG_PCT * len(primary)
    net_all = [r["pnl_pct_net_cost_and_funding"] for r in primary]
    wins_net_all = sum(1 for x in net_all if x > 0)
    binom = ra.binomial_test(wins_net_all, len(net_all))
    payload = {
        "funding_csv_sha256": funding_sha,
        "convention": "charged when entry_close < settlement <= exit_close; cost = side_sign*rate*close_s/entry*100",
        "n_trades": len(primary),
        "total_settlements": int(sum(r["settlements"] for r in primary)),
        "trades_with_no_settlement": int(sum(1 for r in primary if r["settlements"] == 0)),
        "total_funding_cost_pct": total_funding,
        "mean_funding_cost_pct_per_trade": total_funding / len(primary),
        "max_abs_funding_cost_pct_one_trade": max(abs(r["funding_cost_pct"]) for r in primary),
        "long_funding_cost_pct": sum(r["funding_cost_pct"] for r in primary if r["side"] == "LONG"),
        "short_funding_cost_pct": sum(r["funding_cost_pct"] for r in primary if r["side"] == "SHORT"),
        "total_return_gross_pct": gross_total,
        "total_return_net_0_20_pct": net_cost_total,
        "total_return_net_0_20_and_funding_pct": net_cost_total - total_funding,
        "wins_net_0_20_and_funding": wins_net_all,
        "binomial_p_one_sided_net_0_20_and_funding": binom["p_one_sided"],
        "check_inclusive_entry_total_funding_cost_pct": sum(r["funding_cost_pct"] for r in inclusive),
        "per_trade": primary,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=ra.json_safe)
    print(json.dumps({k: v for k, v in payload.items() if k != "per_trade"}, indent=2, default=ra.json_safe))


if __name__ == "__main__":
    main()
