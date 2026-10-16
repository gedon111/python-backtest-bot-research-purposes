"""
Ablation reconstruction: indicators-only entry, no Order Block gate.

CLAUDE.md's locked results cite two indicators-only ablation configurations
(Ablation A: 140 trades, 60.00% win rate, -14.63% total return; Ablation B:
138 trades, 55.07%, -25.50%) and a bootstrap-resampling comparison against
those pools (p=0.0020 both arms for avg return). Per STUDY_REFERENCE.md
Sec.6.4/Sec.7, the script that originally produced those per-trade pools was
never committed to this repository, and a prior reconstruction attempt on
record there already diverged by >10 win-rate points from the published
figures. This script is a FRESH, best-faith reconstruction from the
*documented* ablation design (docs/ablation_study_indicators_only.md,
docs/ablation_unconfounding_analysis.md) -- not a byte-for-byte recovery of
the original uncommitted script -- and is not guaranteed to reproduce the
locked figures. Any divergence is reported explicitly at the end of main(),
never silently reconciled with CLAUDE.md's locked numbers.

Read-only, additive: loads artifacts/candles.csv, reuses
compute_indicators()/kdj_reset_init()/kdj_reset_update()/kdj_reset_exit()
from src/Binance backtest bot.py UNMODIFIED. Does not call compute_smc() or
simulate_trades() for the ablation arms themselves (Order Block detection is
irrelevant to an indicators-only configuration by design), and never writes
to backtest_results.db or mutates any locked artifact.

Entry conditions (both arms) are the identical MACD/KDJ/ATR/k_accel/ATR-
regime conditions used by simulate_trades()'s OB-gated LONG/SHORT entry
blocks (src/Binance backtest bot.py, simulate_trades(), lines ~744-874),
evaluated on every bar with the sole change that the "price touching a valid
Order Block zone" requirement is removed. Two stop-loss anchoring schemes
are tested, per the two docs above:

  Arm 2 ("flat-ATR", docs/ablation_study_indicators_only.md):
      SL = close -/+ 1.5 * ATR(14)   ["Entry Volatility Offset"]
  Arm 3 ("swing-pivot", docs/ablation_unconfounding_analysis.md):
      SL = (5-bar low/high, prior bars only) -/+ 0.5 * ATR(14)
      ["5-Bar Internal Pivot Extreme"]

Both arms keep rr_min=1.5 / sl_ratio_min=0.015 identical to the OB-gated
strategy, and use a fixed 2R take-profit (no structural/OB-anchored TP --
using one would reintroduce an OB dependency into a configuration meant to
ablate OB away entirely). Post-entry exit logic (trailing stop / KDJ-reset /
ATR-move / breakeven / hard SL-TP) is copied verbatim from simulate_trades(),
including kdj_reset_init(..., ob_bar=None) -> default_period=9, which the
strategy code already exposes as an explicit no-OB fallback.

Usage (run from repo root):
    python analysis/ablation_reconstruction.py
    python analysis/ablation_reconstruction.py --json-out artifacts/ablation_reconstruction.json
    python analysis/ablation_reconstruction.py --bootstrap-n 5000 --seed 7
"""
import argparse
import importlib.util

import numpy as np
import pandas as pd

from _json_utils import write_json

SL_RATIO_MIN = 0.015
KDJ_J_LONG_CAP = 60.0
KDJ_K_LONG_CAP = 50.0
KDJ_K_SHORT_FLOOR = 70.0
KDJ_J_SHORT_CAP = 100.0
ATR_MULT_EXIT = 1.8
ATR_MULT_BE = 2.0
RR_MIN = 1.5
SWING_LOOKBACK = 5
START_BAR = 55  # matches simulate_trades()'s SWING_SIZE(50) + 5 warm-up

LOCKED = {
    "flat_atr": {"n": 140, "win_rate": 60.00, "total_return": -14.63},
    "swing_pivot": {"n": 138, "win_rate": 55.07, "total_return": -25.50},
}


def load_bot():
    spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def load_candles():
    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    return df


def entry_long_ok(hist, p_hist, pp_hist, K, K_prev, J, k_accel, atr_r):
    if not (hist < 0 and hist > p_hist):
        return False
    if not (p_hist > pp_hist):
        return False
    if not (K < KDJ_K_LONG_CAP and K > K_prev and J < KDJ_J_LONG_CAP):
        return False
    if not (1 <= k_accel <= 6):
        return False
    if 0.8 <= atr_r <= 1.0:
        return False
    return True


def entry_short_ok(hist, p_hist, pp_hist, K, D, J, k_accel, atr_r):
    if not (hist > 0 and hist < p_hist):
        return False
    if not (p_hist < pp_hist):
        return False
    if not (K > 50 and J > K > D):
        return False
    if not (1 <= k_accel <= 6):
        return False
    if 0.8 <= atr_r <= 1.0:
        return False
    if K < KDJ_K_SHORT_FLOOR:
        return False
    if J > KDJ_J_SHORT_CAP:
        return False
    return True


def run_ablation_arm(bot, df, stop_mode: str) -> pd.DataFrame:
    """stop_mode: 'flat_atr' or 'swing_pivot'."""
    position = None
    entry_price = entry_atr = stop_loss_price = take_profit_price = 0.0
    peak_pnl_pct = 0.0
    entry_idx = 0
    kdj_state = None
    trades = []

    for i in range(START_BAR, len(df)):
        close = float(df.at[i, "close"])
        high = float(df.at[i, "high"])
        low = float(df.at[i, "low"])
        hist = float(df.at[i, "MACD_hist"])
        p_hist = float(df.at[i - 1, "MACD_hist"])
        pp_hist = float(df.at[i - 2, "MACD_hist"])
        K = float(df.at[i, "K"])
        D = float(df.at[i, "D"])
        J = float(df.at[i, "J"])
        K_prev = float(df.at[i - 1, "K"])
        K2 = float(df.at[i - 2, "K"])
        ATR = float(df.at[i, "ATR"])
        ATR_200 = float(df.at[i, "ATR_200"])
        k_accel = (K - K_prev) - (K_prev - K2)
        atr_r = ATR / ATR_200 if ATR_200 > 0 else 1.0

        if position is None:
            if entry_long_ok(hist, p_hist, pp_hist, K, K_prev, J, k_accel, atr_r):
                if stop_mode == "flat_atr":
                    sl = close - ATR * 1.5
                else:
                    window_low = df["low"].iloc[max(0, i - SWING_LOOKBACK):i]
                    pivot_low = float(window_low.min()) if len(window_low) else close - ATR * 1.5
                    sl = pivot_low - ATR * 0.5
                risk = close - sl
                if risk > 0 and risk / close >= SL_RATIO_MIN:
                    tp = close + risk * 2.0
                    if (tp - close) / risk >= RR_MIN:
                        position = "LONG"
                        entry_price, stop_loss_price, take_profit_price = close, sl, tp
                        entry_atr, peak_pnl_pct, entry_idx = ATR, 0.0, i
                        kdj_state = bot.kdj_reset_init(df, i, ob_bar=None)

            if position is None and entry_short_ok(hist, p_hist, pp_hist, K, D, J, k_accel, atr_r):
                if stop_mode == "flat_atr":
                    sl = close + ATR * 1.5
                else:
                    window_high = df["high"].iloc[max(0, i - SWING_LOOKBACK):i]
                    pivot_high = float(window_high.max()) if len(window_high) else close + ATR * 1.5
                    sl = pivot_high + ATR * 0.5
                risk = sl - close
                if risk > 0 and risk / close >= SL_RATIO_MIN:
                    tp = close - risk * 2.0
                    if (close - tp) / risk >= RR_MIN:
                        position = "SHORT"
                        entry_price, stop_loss_price, take_profit_price = close, sl, tp
                        entry_atr, peak_pnl_pct, entry_idx = ATR, 0.0, i
                        kdj_state = bot.kdj_reset_init(df, i, ob_bar=None)

        elif position == "LONG":
            pnl_pct = (close - entry_price) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)

            def close_trade(tag, pnl, _i=i):
                trades.append({
                    "side": "LONG", "entry_idx": entry_idx, "exit_idx": _i,
                    "entry": entry_price, "exit": close, "pnl_pct": pnl,
                    "hold_bars": _i - entry_idx, "exit_reason": tag,
                })

            if peak_pnl_pct >= 1.5 and close <= entry_price * (1 + peak_pnl_pct * 0.5 / 100):
                close_trade("TRAILING EXIT (50% RETRACE)", pnl_pct)
                position = None
                continue

            kdj_state = bot.kdj_reset_update(kdj_state, df, i, "LONG")
            if (i - entry_idx) >= 3 and bot.kdj_reset_exit(kdj_state, "LONG"):
                close_trade("KDJ RESET EXIT", pnl_pct)
                position = None
                continue

            if entry_atr > 0 and close >= entry_price + entry_atr * ATR_MULT_EXIT:
                close_trade("ATR MOVE EXIT", pnl_pct)
                position = None
                continue

            if close >= entry_price + entry_atr * ATR_MULT_BE:
                stop_loss_price = max(stop_loss_price, entry_price)

            if close <= stop_loss_price:
                close_trade("HIT STOP LOSS", (close - entry_price) / entry_price * 100)
                position = None
            elif close >= take_profit_price:
                close_trade("HIT TAKE PROFIT", (close - entry_price) / entry_price * 100)
                position = None

        elif position == "SHORT":
            pnl_pct = (entry_price - close) / entry_price * 100
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)

            def close_trade(tag, pnl, _i=i):
                trades.append({
                    "side": "SHORT", "entry_idx": entry_idx, "exit_idx": _i,
                    "entry": entry_price, "exit": close, "pnl_pct": pnl,
                    "hold_bars": _i - entry_idx, "exit_reason": tag,
                })

            if peak_pnl_pct >= 1.5 and close >= entry_price * (1 - peak_pnl_pct * 0.5 / 100):
                close_trade("TRAILING EXIT (50% RETRACE)", pnl_pct)
                position = None
                continue

            kdj_state = bot.kdj_reset_update(kdj_state, df, i, "SHORT")
            if (i - entry_idx) >= 3 and bot.kdj_reset_exit(kdj_state, "SHORT"):
                close_trade("KDJ RESET EXIT", pnl_pct)
                position = None
                continue

            if entry_atr > 0 and close <= entry_price - entry_atr * ATR_MULT_EXIT:
                close_trade("ATR MOVE EXIT", pnl_pct)
                position = None
                continue

            if close <= entry_price - entry_atr * ATR_MULT_BE:
                stop_loss_price = min(stop_loss_price, entry_price)

            if close >= stop_loss_price:
                close_trade("HIT STOP LOSS", (entry_price - close) / entry_price * 100)
                position = None
            elif close <= take_profit_price:
                close_trade("HIT TAKE PROFIT", (entry_price - close) / entry_price * 100)
                position = None

    return pd.DataFrame(trades)


def summarize(trades_df: pd.DataFrame) -> dict:
    n = len(trades_df)
    if n == 0:
        return {"n": 0, "wins": 0, "win_rate": 0.0, "total_return": 0.0, "avg_return": 0.0, "sd": None}
    wins = int((trades_df["pnl_pct"] > 0).sum())
    return {
        "n": n, "wins": wins, "win_rate": wins / n * 100,
        "total_return": float(trades_df["pnl_pct"].sum()),
        "avg_return": float(trades_df["pnl_pct"].mean()),
        "sd": float(trades_df["pnl_pct"].std()) if n > 1 else None,
    }


def bootstrap_vs_baseline(arm_pnl: np.ndarray, baseline_n: int, baseline_win_rate: float,
                           baseline_avg_return: float, b: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    wr_samples = np.empty(b)
    avg_samples = np.empty(b)
    for k in range(b):
        sample = rng.choice(arm_pnl, size=baseline_n, replace=True)
        wr_samples[k] = (sample > 0).mean() * 100
        avg_samples[k] = sample.mean()

    return {
        "b": b, "seed": seed, "n": baseline_n,
        "win_rate_percentiles": {
            "p2_5": float(np.percentile(wr_samples, 2.5)),
            "p50": float(np.percentile(wr_samples, 50)),
            "p97_5": float(np.percentile(wr_samples, 97.5)),
        },
        "avg_return_percentiles": {
            "p2_5": float(np.percentile(avg_samples, 2.5)),
            "p50": float(np.percentile(avg_samples, 50)),
            "p97_5": float(np.percentile(avg_samples, 97.5)),
        },
        "empirical_p_win_rate_ge_baseline": float((wr_samples >= baseline_win_rate).mean()),
        "empirical_p_avg_return_ge_baseline": float((avg_samples >= baseline_avg_return).mean()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bootstrap-n", type=int, default=2000, help="Bootstrap resamples (default: 2000, matching the disclosed methodology)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json-out", default=None, help="Optional path to write results as JSON")
    args = parser.parse_args()

    print("[ablation_reconstruction] Loading candles and strategy module...")
    bot = load_bot()
    raw_df = load_candles()
    df = bot.compute_indicators(raw_df.copy())

    print("[ablation_reconstruction] Running OB-gated baseline (min_ob_quality=0) for comparison...")
    base_sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
    base_trades = base_sim.attrs.get("trades_df", pd.DataFrame())
    baseline = summarize(base_trades)
    assert baseline["n"] == 27, f"expected 27 baseline trades, got {baseline['n']}"

    results = {"baseline": baseline, "arms": {}}

    for stop_mode, label in (("flat_atr", "Arm 2 (flat-ATR stop)"), ("swing_pivot", "Arm 3 (swing-pivot stop)")):
        print(f"[ablation_reconstruction] Running indicators-only {label}...")
        arm_trades = run_ablation_arm(bot, df, stop_mode)
        arm_summary = summarize(arm_trades)

        print("=" * 100)
        print(f"  {label} -- RECONSTRUCTED THIS SESSION")
        print("=" * 100)
        print(f"  N={arm_summary['n']}  win_rate={arm_summary['win_rate']:.2f}%  "
              f"total_return={arm_summary['total_return']:+.2f}%  avg_return={arm_summary['avg_return']:+.4f}%  "
              f"sd={arm_summary['sd']:.4f}%" if arm_summary["n"] > 1 else
              f"  N={arm_summary['n']}")

        locked = LOCKED[stop_mode]
        n_match = arm_summary["n"] == locked["n"]
        wr_match = abs(arm_summary["win_rate"] - locked["win_rate"]) <= 1.0
        ret_match = abs(arm_summary["total_return"] - locked["total_return"]) <= 1.0
        status = "MATCH" if (n_match and wr_match and ret_match) else "DIVERGE"

        print(f"  Locked (CLAUDE.md, disclosed, unverified until now): "
              f"N={locked['n']} win_rate={locked['win_rate']:.2f}% total_return={locked['total_return']:+.2f}%")
        print(f"  Status vs. locked figure: {status}")
        if status == "DIVERGE":
            print("  >>> This reconstruction DOES NOT match the locked figure. Per CLAUDE.md's rule on")
            print("  >>> newly found discrepancies, this is reported as-is, not reconciled or silently")
            print("  >>> adjusted. CLAUDE.md's locked numbers are NOT changed by this script.")
        print()

        bootstrap = None
        if arm_summary["n"] > 0:
            bootstrap = bootstrap_vs_baseline(
                arm_trades["pnl_pct"].values, baseline["n"], baseline["win_rate"], baseline["avg_return"],
                args.bootstrap_n, args.seed,
            )
            print(f"  Bootstrap (B={args.bootstrap_n}, n={baseline['n']}, resampled from this arm's {arm_summary['n']}-trade pool):")
            print(f"    Win rate percentiles:   2.5%={bootstrap['win_rate_percentiles']['p2_5']:.2f}%  "
                  f"50%={bootstrap['win_rate_percentiles']['p50']:.2f}%  97.5%={bootstrap['win_rate_percentiles']['p97_5']:.2f}%")
            print(f"    Avg return percentiles: 2.5%={bootstrap['avg_return_percentiles']['p2_5']:+.2f}%  "
                  f"50%={bootstrap['avg_return_percentiles']['p50']:+.2f}%  97.5%={bootstrap['avg_return_percentiles']['p97_5']:+.2f}%")
            print(f"    Empirical p (win rate >= baseline {baseline['win_rate']:.2f}%):   {bootstrap['empirical_p_win_rate_ge_baseline']:.4f}")
            print(f"    Empirical p (avg return >= baseline {baseline['avg_return']:+.4f}%): {bootstrap['empirical_p_avg_return_ge_baseline']:.4f}")
            print()

        results["arms"][stop_mode] = {
            "label": label, "reconstructed": arm_summary, "locked": locked,
            "status_vs_locked": status, "bootstrap_vs_baseline": bootstrap,
        }

    if args.json_out:
        write_json(results, args.json_out)

    any_diverge = any(a["status_vs_locked"] == "DIVERGE" for a in results["arms"].values())
    if any_diverge:
        print("=" * 100)
        print("[ablation_reconstruction] SUMMARY: at least one arm diverges from CLAUDE.md's locked")
        print("Ablation A/B figures. This is a reconstruction-fidelity finding, not evidence the locked")
        print("figures are wrong -- the original generating script/trade data was never committed, so")
        print("neither this script's output nor the locked figures can currently be cross-verified")
        print("against each other's exact per-trade basis. Report to the user for review; do not edit")
        print("CLAUDE.md or the paper's Ablation section based on this script's numbers alone.")
        print("=" * 100)


if __name__ == "__main__":
    main()
