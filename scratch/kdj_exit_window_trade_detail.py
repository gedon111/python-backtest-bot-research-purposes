"""
Read-only, additive. Does not modify entry logic, OB detection, static
KDJ(9,3,3), locked baseline results, or kdj_exit_window_counterfactual.py's
existing configs/output — this is a separate script reusing the same
runtime-monkeypatch technique (fresh in-memory bot module per config,
kdj_reset_init's `period` fixed to a constant; nothing else touched).

Purpose: scratch/kdj_exit_window_counterfactual_results.json only has
aggregate stats + (entry_idx, side) pairs, not per-trade pnl_pct/win-loss.
This script reruns the same grid and dumps full per-trade detail so two
questions can be answered:

  1. For fixed_period_p25 (38), fixed_period_74, fixed_period_p75 (114) —
     all reporting 19/27 wins — is it the SAME 19 trades winning each time,
     or do individual trades flip while the count nets out equal?
  2. Across the full grid (9, p25=38, 74, p75=114, 439), what does
     entry_idx=359 (known top winner) and entry_idx=2624 (known top loser)
     do to pnl_pct, and how much of the ~5.5pt total-return spread across
     the grid do these two trades alone account for?

Output: scratch/kdj_exit_window_trade_detail_results.json
"""
import os
import json
import importlib.util
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bot_path = os.path.join(BASE_DIR, "src", "Binance backtest bot.py")
CANDLES_CACHE_PATH = os.path.join(BASE_DIR, "artifacts", "candles.csv")
OUT_PATH = os.path.join(BASE_DIR, "scratch", "kdj_exit_window_trade_detail_results.json")


def load_fresh_bot_module():
    spec = importlib.util.spec_from_file_location("bot_detail", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fixed_period_init(fixed_period):
    def patched(df, entry_idx, ob_bar=None, default_period=9):
        return {
            'k':          float(df.at[entry_idx, 'K']),
            'd':          float(df.at[entry_idx, 'D']),
            'prev_k':     float(df.at[entry_idx, 'K']),
            'prev_d':     float(df.at[entry_idx, 'D']),
            'period':     int(fixed_period),
            'entry_idx':  int(entry_idx),
            'armed':      False,
        }
    return patched


def run_config_trades(fixed_period, df_template):
    mod = load_fresh_bot_module()
    if fixed_period is not None:
        mod.kdj_reset_init = make_fixed_period_init(fixed_period)
    sim_df = mod.simulate_trades(df_template.copy(), min_ob_quality=0)
    trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
    out = {}
    for _, r in trades_df.iterrows():
        out[int(r["entry_idx"])] = {
            "side": r["side"],
            "pnl_pct": float(r["pnl_pct"]),
            "win": bool(float(r["pnl_pct"]) > 0),
            "exit_reason": r["exit_reason"],
        }
    return out


def main():
    df_raw = pd.read_csv(CANDLES_CACHE_PATH)
    df_raw["open_time"] = pd.to_datetime(df_raw["open_time"])
    bot0 = load_fresh_bot_module()
    df_template = bot0.compute_indicators(df_raw)

    grid = [
        ("baseline", None),
        ("fixed_period_9", 9),
        ("fixed_period_p25", 38),
        ("fixed_period_74", 74),
        ("fixed_period_p75", 114),
        ("fixed_period_439", 439),
    ]

    per_config = {}
    for label, period in grid:
        print(f"Running {label} (period={period})...")
        per_config[label] = run_config_trades(period, df_template)

    baseline_entries = sorted(per_config["baseline"].keys())

    # ── Q1: trade-level win/loss identity across p25/74/p75 (+ baseline) ──
    q1_configs = ["baseline", "fixed_period_p25", "fixed_period_74", "fixed_period_p75"]
    q1_table = []
    for eidx in baseline_entries:
        row = {"entry_idx": eidx, "side": per_config["baseline"][eidx]["side"]}
        for label in q1_configs:
            row[label] = "WIN" if per_config[label][eidx]["win"] else "LOSS"
        q1_table.append(row)

    win_sets = {label: {e for e in baseline_entries if per_config[label][e]["win"]} for label in q1_configs}
    q1_identical = win_sets["fixed_period_p25"] == win_sets["fixed_period_74"] == win_sets["fixed_period_p75"]
    q1_diffs = {}
    labels3 = ["fixed_period_p25", "fixed_period_74", "fixed_period_p75"]
    for i in range(len(labels3)):
        for j in range(i + 1, len(labels3)):
            a, b = labels3[i], labels3[j]
            sym_diff = win_sets[a] ^ win_sets[b]
            if sym_diff:
                q1_diffs[f"{a}_vs_{b}"] = sorted(sym_diff)

    # ── Q2: entry_idx=359 and 2624 across full grid ──
    watch_ids = [359, 2624]
    q2_table = []
    for label, period in grid:
        row = {"config": label, "period": period}
        for wid in watch_ids:
            if wid in per_config[label]:
                row[f"pnl_{wid}"] = per_config[label][wid]["pnl_pct"]
                row[f"exit_reason_{wid}"] = per_config[label][wid]["exit_reason"]
            else:
                row[f"pnl_{wid}"] = None
                row[f"exit_reason_{wid}"] = None
        row["total_net_return_pct"] = sum(t["pnl_pct"] for t in per_config[label].values())
        q2_table.append(row)

    total_returns = {r["config"]: r["total_net_return_pct"] for r in q2_table}
    grid_labels_no_baseline = ["fixed_period_9", "fixed_period_p25", "fixed_period_74", "fixed_period_p75", "fixed_period_439"]
    spread_total = max(total_returns[l] for l in grid_labels_no_baseline) - min(total_returns[l] for l in grid_labels_no_baseline)

    pnl_359_by_cfg = {r["config"]: r["pnl_359"] for r in q2_table}
    pnl_2624_by_cfg = {r["config"]: r["pnl_2624"] for r in q2_table}
    spread_359 = max(pnl_359_by_cfg[l] for l in grid_labels_no_baseline) - min(pnl_359_by_cfg[l] for l in grid_labels_no_baseline)
    spread_2624 = max(pnl_2624_by_cfg[l] for l in grid_labels_no_baseline) - min(pnl_2624_by_cfg[l] for l in grid_labels_no_baseline)

    print("\n--- Q1: win/loss identity table (baseline, p25=38, 74, p75=114) ---")
    for row in q1_table:
        print(row)
    print(f"\nIdentical winner set across p25/74/p75? {q1_identical}")
    if not q1_identical:
        print("Pairwise symmetric differences (trades that flip):")
        for k, v in q1_diffs.items():
            print(f"  {k}: {v}")

    print("\n--- Q2: entry_idx=359 / 2624 across full grid ---")
    for row in q2_table:
        print(row)
    print(f"\nTotal-return spread across grid (excl. baseline): {spread_total:.4f} pts")
    print(f"PnL spread at entry_idx=359 alone: {spread_359:.4f} pts")
    print(f"PnL spread at entry_idx=2624 alone: {spread_2624:.4f} pts")
    print(f"Combined |spread_359| + |spread_2624| vs total spread: "
          f"{abs(spread_359) + abs(spread_2624):.4f} vs {spread_total:.4f}")

    output = {
        "q1_win_loss_table": q1_table,
        "q1_identical_across_p25_74_p75": q1_identical,
        "q1_flips": q1_diffs,
        "q2_watch_trades_table": q2_table,
        "q2_total_return_by_config": total_returns,
        "q2_spread_total_return_pts": spread_total,
        "q2_spread_pnl_359_pts": spread_359,
        "q2_spread_pnl_2624_pts": spread_2624,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
