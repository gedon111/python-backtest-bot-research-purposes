"""
Additive analysis only — no changes to entry logic, OB detection, static
KDJ(9,3,3), or locked baseline results.

Question: does the OB-relative dynamic exit window
(period = entry_idx - ob_bar, set in kdj_reset_init) contribute measurable
value over a fixed exit window?

Method: monkeypatch bot.kdj_reset_init at runtime (the on-disk file is never
modified) so that state['period'] is a constant instead of entry_idx - ob_bar,
for the two invocation sites in simulate_trades (LONG/SHORT entry). Everything
else — entry gating, OB detection, static KDJ(9,3,3), stop/TP/RR rules — is
untouched, since kdj_reset_init's seed values (k, d, prev_k, prev_d) and the
caller's entry logic do not depend on `period`; only kdj_reset_update /
kdj_reset_exit (post-entry exit-signal recursion) read it.

Configs tested, all otherwise identical to baseline (min_ob_quality=0).
Pre-specified grid: conventional default, 25th/50th/75th percentile of the
actual observed w distribution across the 27 baseline trades, and the
observed max. Every point is reported regardless of outcome — no selection
of a "best" constant, no feedback into the live default. This characterizes
sensitivity of an already-fixed design choice; it is not a retuning pass.

  - baseline:         period = entry_idx - ob_bar  (current code, unmodified)
  - fixed_period_9:    period = 9    (conventional KDJ default)
  - fixed_period_p25:  period = 25th percentile of observed w (computed below)
  - fixed_period_74:   period = 74   (median observed w in baseline, see
                                       CLAUDE.md "KDJ architecture" note)
  - fixed_period_p75:  period = 75th percentile of observed w (computed below)
  - fixed_period_439:  period = 439  (observed max w in baseline)

Percentiles are computed at runtime from w = entry_idx - entry_ob_bar over
the 27 baseline trades (numpy default linear interpolation), then rounded
to the nearest integer (banker's rounding) since kdj_reset_init casts
period to int. p25 -> 38.0 -> 38; p75 -> 113.5 -> 114 (observed at script
authorship time; recomputed fresh on every run, not hardcoded).

Output: scratch/kdj_exit_window_counterfactual_results.json
Does not touch scratch/fixtures/. Run scratch/regression.py afterward to
confirm the baseline is unaffected by this script (it monkeypatches its own
in-process copy of the bot module only).
"""
import os
import sys
import json
import importlib.util
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bot_path = os.path.join(BASE_DIR, "research_analysis.py")
CANDLES_CACHE_PATH = os.path.join(BASE_DIR, "artifacts", "candles.csv")
OUT_PATH = os.path.join(BASE_DIR, "scratch", "kdj_exit_window_counterfactual_results.json")


def load_fresh_bot_module():
    """Fresh module instance per run so monkeypatches never leak across configs."""
    spec = importlib.util.spec_from_file_location("bot_cf", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fixed_period_init(orig_init, fixed_period):
    """Same seeding behavior as the real kdj_reset_init; only `period` differs."""
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


def run_config(label, fixed_period, df_template):
    mod = load_fresh_bot_module()
    if fixed_period is not None:
        orig_init = mod.kdj_reset_init
        mod.kdj_reset_init = make_fixed_period_init(orig_init, fixed_period)

    df = df_template.copy()
    sim_df = mod.simulate_trades(df, min_ob_quality=0)
    stats = sim_df.attrs.get("trade_stats", {})
    trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())

    exit_reason_counts = (
        trades_df["exit_reason"].value_counts().to_dict()
        if not trades_df.empty and "exit_reason" in trades_df.columns
        else {}
    )

    entries = sorted(
        (int(r["entry_idx"]), r["side"]) for _, r in trades_df.iterrows()
    ) if not trades_df.empty else []

    return {
        "label": label,
        "fixed_period": fixed_period,
        "trade_count": int(stats.get("Total Trades", len(trades_df))),
        "win_rate_pct": stats.get("Win Rate (%)"),
        "total_net_return_pct": stats.get("Total Net Return (%)"),
        "avg_return_per_trade_pct": stats.get("Avg Return/Trade (%)"),
        "sd_return_pct": float(trades_df["pnl_pct"].std()) if not trades_df.empty else None,
        "exit_reason_distribution": exit_reason_counts,
        "entries": entries,  # (entry_idx, side) pairs, for sanity-check alignment
    }


def main():
    print("Loading candles...")
    df_raw = pd.read_csv(CANDLES_CACHE_PATH)
    df_raw["open_time"] = pd.to_datetime(df_raw["open_time"])

    bot0 = load_fresh_bot_module()
    print("Computing static indicators (shared across all configs)...")
    df_template = bot0.compute_indicators(df_raw)

    # Observed w distribution over the 27 baseline trades, from the
    # unmodified baseline config itself (w = entry_idx - entry_ob_bar).
    sim_df_probe = bot0.simulate_trades(df_template.copy(), min_ob_quality=0)
    trades_df_probe = sim_df_probe.attrs.get("trades_df", pd.DataFrame())
    ws = sorted(
        int(r["entry_idx"]) - int(r["entry_ob_bar"])
        for _, r in trades_df_probe.iterrows()
    )
    p25 = int(round(float(np.percentile(ws, 25))))
    p75 = int(round(float(np.percentile(ws, 75))))
    w_max = max(ws)
    print(f"\nObserved w distribution (n={len(ws)}): min={min(ws)} p25={np.percentile(ws, 25)} "
          f"median={np.percentile(ws, 50)} p75={np.percentile(ws, 75)} max={w_max}")
    print(f"Grid periods derived: p25={p25} (rounded), p75={p75} (rounded)")

    configs = [
        ("baseline", None),
        ("fixed_period_9", 9),
        ("fixed_period_p25", p25),
        ("fixed_period_74", 74),
        ("fixed_period_p75", p75),
        ("fixed_period_439", w_max),
    ]

    results = {}
    for label, fixed_period in configs:
        print(f"Running config: {label} ...")
        results[label] = run_config(label, fixed_period, df_template)

    # ── Sanity check: entries (entry_idx, side) must be IDENTICAL across all
    # configs, since period only governs post-entry exit timing. ──
    baseline_entries = results["baseline"]["entries"]
    sanity = {"identical_entries": True, "details": []}
    for label in ("fixed_period_9", "fixed_period_p25", "fixed_period_74", "fixed_period_p75", "fixed_period_439"):
        cf_entries = results[label]["entries"]
        if cf_entries != baseline_entries:
            sanity["identical_entries"] = False
            missing = [e for e in baseline_entries if e not in cf_entries]
            extra = [e for e in cf_entries if e not in baseline_entries]
            sanity["details"].append({
                "config": label,
                "baseline_count": len(baseline_entries),
                "config_count": len(cf_entries),
                "missing_in_config": missing,
                "extra_in_config": extra,
            })

    print("\n--- Sanity check: entry identity across configs ---")
    print(f"Baseline entries (entry_idx, side), n={len(baseline_entries)}:")
    print(baseline_entries)
    if sanity["identical_entries"]:
        print("PASS: all fixed-period configs (9, p25, 74, p75, 439) have IDENTICAL entries to baseline.")
    else:
        print("FAIL: entry sets diverge across configs — see 'sanity' block in output JSON.")
        for d in sanity["details"]:
            print(f"  {d['config']}: baseline_count={d['baseline_count']} config_count={d['config_count']}")
            print(f"    missing_in_config: {d['missing_in_config']}")
            print(f"    extra_in_config:   {d['extra_in_config']}")

    print("\n--- Results summary ---")
    for label, _ in configs:
        r = results[label]
        print(f"\n[{label}] (fixed_period={r['fixed_period']})")
        print(f"  Trades:            {r['trade_count']}")
        print(f"  Win Rate:          {r['win_rate_pct']}")
        print(f"  Total Net Return:  {r['total_net_return_pct']}")
        print(f"  Avg Return/Trade:  {r['avg_return_per_trade_pct']}")
        print(f"  SD Return/Trade:   {r['sd_return_pct']}")
        print(f"  Exit reasons:      {r['exit_reason_distribution']}")

    output = {
        "description": (
            "Additive counterfactual: fixed exit-window period vs. baseline "
            "OB-relative dynamic period (entry_idx - ob_bar) in kdj_reset_init. "
            "Entry logic, OB detection, static KDJ(9,3,3), and stop/TP/RR rules "
            "are untouched; only the post-entry exit-signal window is varied. "
            "No changes made to Binance backtest bot.py; kdj_reset_init was "
            "monkeypatched at runtime on an in-memory module copy per config."
        ),
        "observed_w_distribution": {
            "n": len(ws),
            "sorted_w": ws,
            "min": min(ws),
            "p25": float(np.percentile(ws, 25)),
            "median": float(np.percentile(ws, 50)),
            "p75": float(np.percentile(ws, 75)),
            "max": w_max,
            "p25_rounded_for_grid": p25,
            "p75_rounded_for_grid": p75,
        },
        "grid": [label for label, _ in configs],
        "sanity_check": sanity,
        "configs": results,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nWrote results to {OUT_PATH}")


if __name__ == "__main__":
    main()
