"""
EXPERIMENTAL -- stop-loss realism sensitivity for the paper's 27 baseline 4h
trades (2022-2026). The close-only baseline stays the paper's result; this is
a sensitivity row beside it.

Added 2026-10-28 for bitcoin (7) (review item M11). No rule, threshold or
trade selection changes: the SAME 27 entries are replayed, each with its own
stop_loss price from simulate_trades(). The stop never moves during a trade
(the 2.0x ATR breakeven ratchet cannot fire, because the 1.8x ATR move exit
returns first), so the entry stop is the stop on every bar.

Rule. On every bar after entry, up to and including the trade's original
exit bar, the stop is checked against the bar's low (long) or high (short)
BEFORE any close-based exit on that bar (stop-first, the conservative order).
If touched, the trade exits on that bar at the stop price, or at the bar's
open when the bar opens already past the stop (a gap). Otherwise the trade
keeps its published close-based exit. Trades that a shorter hold would have
let the engine take are NOT added: the trade set is held fixed at 27.

Output: experimental/results/stop_intrabar.json
"""

import json
import os
import sys

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
sys.path.insert(0, BASE_DIR)

import research_analysis as ra  # noqa: E402

OUT_PATH = os.path.join(EXPERIMENT_DIR, "results", "stop_intrabar.json")
COST_PCT = ra.BENCHMARK_ROUND_TRIP_DRAG_PCT  # 0.20


def replay(df, t):
    sign = 1.0 if str(t.side).upper() == "LONG" else -1.0
    stop = float(t.stop_loss)
    for j in range(int(t.entry_idx) + 1, int(t.exit_idx) + 1):
        if sign > 0 and df["low"].iat[j] <= stop:
            fill = min(df["open"].iat[j], stop)
        elif sign < 0 and df["high"].iat[j] >= stop:
            fill = max(df["open"].iat[j], stop)
        else:
            continue
        return {"exit_idx": j, "exit": float(fill), "pnl_pct": sign * (fill / t.entry - 1) * 100,
                "gap_fill": bool(fill != stop), "changed": True}
    return {"exit_idx": int(t.exit_idx), "exit": float(t.exit), "pnl_pct": float(t.pnl_pct),
            "gap_fill": False, "changed": False}


def summary(pnl, cost):
    adj = [p - cost for p in pnl]
    wins = sum(p > 0 for p in adj)
    return {"wins": wins, "win_rate_pct": wins / len(adj) * 100, "total_pct": sum(adj),
            "mean_pct": sum(adj) / len(adj), **ra.binomial_test(wins, len(adj))}


def main():
    df = ra.compute_indicators(ra.load_candles())
    trades = ra.simulate_trades(df.copy(), min_ob_quality=0).attrs["trades_df"]
    assert len(trades) == 27
    rows = []
    for t in trades.sort_values("entry_idx").itertuples():
        r = replay(df, t)
        rows.append({"entry_idx": int(t.entry_idx), "side": str(t.side).upper(),
                     "stop_distance_pct": abs(t.stop_loss / t.entry - 1) * 100,
                     "baseline_exit_reason": t.exit_reason, "baseline_pnl_pct": float(t.pnl_pct),
                     "intrabar_exit_idx": r["exit_idx"], "intrabar_pnl_pct": r["pnl_pct"],
                     "changed": r["changed"], "gap_fill": r["gap_fill"]})
    base = [r["baseline_pnl_pct"] for r in rows]
    intra = [r["intrabar_pnl_pct"] for r in rows]
    out = {
        "n": len(rows), "cost_pct": COST_PCT,
        "trades_changed": sum(r["changed"] for r in rows),
        "winners_turned_losers_gross": sum(b > 0 >= i for b, i in zip(base, intra)),
        "losers_cut_smaller_gross": sum(b <= 0 and i > b for b, i in zip(base, intra)),
        "close_only_baseline": {"gross": summary(base, 0.0), "net": summary(base, COST_PCT)},
        "intrabar_stop": {"gross": summary(intra, 0.0), "net": summary(intra, COST_PCT)},
        "changed_trades": [r for r in rows if r["changed"]],
        "trades": rows,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=ra.json_safe)
    print(json.dumps({k: v for k, v in out.items() if k != "trades"}, indent=1, default=ra.json_safe))


if __name__ == "__main__":
    main()
