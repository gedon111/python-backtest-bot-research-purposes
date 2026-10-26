"""
EXPERIMENTAL -- ML meta-labeling study on branch `experimental`.

Not part of the paper. Not imported by research_analysis.py, the dashboard,
or the regression harness. See experimental/PREREGISTRATION.md for the
fixed design (written and committed before any 2022+ evaluation) and
experimental/RESULTS.md for the outcome.

Question: the locked rule set takes 27 trades in 2022-2026. If the rules'
indicator gates are relaxed into FEATURES, and a model trained only on
2018-2021 decides which Order Block touches to take, does that selection
hold up on 2022-2025 (and once, on the Jan-Aug 2026 lockbox)?

The strategy engine is loaded dynamically from research_analysis.py (same
pattern as scratch/regression.py) and is NEVER modified. Entry geometry and
every exit rule are the engine's own functions; this file only decides
WHICH candidate entries are taken.

Phases (run in order; each writes experimental/results/<phase>.json):
  parity   hard gate: the single-trade simulator + rule policy must
           reproduce the locked 27 trades exactly on artifacts/candles.csv,
           and features must be truncation-invariant.
  select   2018-2021 only. Purged walk-forward CV model selection.
  freeze   refit the chosen config on all 2018-2021 data, hash it.
  oos      2022-2025, run once after the freeze commit.
  lockbox  Jan-Aug 2026, one shot (--i-understand-this-is-one-shot).
"""

import argparse
import hashlib
import importlib.util
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
RESULTS_DIR = os.path.join(EXPERIMENT_DIR, "results")

_spec = importlib.util.spec_from_file_location("bot", os.path.join(BASE_DIR, "research_analysis.py"))
bot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bot)

EXTENDED_JSON_PATH = os.path.join(BASE_DIR, bot.ARTIFACTS_CANDLES_EXTENDED_JSON)
CANDLES_CSV_PATH = os.path.join(BASE_DIR, bot.ARTIFACTS_CANDLES_CSV)

# Segment boundaries of artifacts/candles_extended.json, by bar index
# (candles_extended_manifest.json: segment_bar_counts).
PREFIX_END = bot.FORMULATION_PERIOD_PREFIX_BARS          # 8750 -> bars < 2022-01-01 08:00
OOS_END = PREFIX_END + 8767                              # 17517 -> bars < 2026-01-01 12:00
FIRST_OOS_OPEN_TIME = pd.Timestamp("2022-01-01 08:00:00")
FIRST_LOCKBOX_OPEN_TIME = pd.Timestamp("2026-01-01 12:00:00")

LOCKBOX_MARKER_PATH = os.path.join(RESULTS_DIR, "LOCKBOX_USED.marker")
FEE_ROUND_TRIP_PCT = bot.BENCHMARK_ROUND_TRIP_DRAG_PCT   # 0.20, the paper's primary fee scenario
MASTER_SEED = 20260101

# The four bar-level indicator gates of the locked entry rule, as named in
# the pre-registration. OB touch + risk geometry are NOT gates here: they
# define what a candidate is.
GATES = ("macd", "kdj", "kacc", "atr")


# ============================================================================
# DATA
# ============================================================================

def load_extended_series(n_bars, phase):
    """
    First `n_bars` bars of the extended 2018-2026 series. The `select` and
    `freeze` phases may only see the 2018-2021 prefix; asking for more raises
    (the date guard), and the returned frame is re-checked by timestamp.
    """
    if phase in ("select", "freeze") and n_bars > PREFIX_END:
        raise PermissionError(f"date guard: phase '{phase}' may not read bars at/after index {PREFIX_END} (2022+)")
    if phase == "oos" and n_bars > OOS_END:
        raise PermissionError(f"date guard: phase 'oos' may not read lockbox bars (index >= {OOS_END})")
    with open(EXTENDED_JSON_PATH, encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records[:n_bars])[["time", "open_time", "open", "high", "low", "close", "volume"]]
    df["open_time"] = pd.to_datetime(df["open_time"])
    if phase in ("select", "freeze"):
        assert df["open_time"].max() < FIRST_OOS_OPEN_TIME, "date guard: 2022+ bar leaked into a 2018-2021 phase"
    if phase == "oos":
        assert df["open_time"].max() < FIRST_LOCKBOX_OPEN_TIME, "date guard: lockbox bar leaked into the oos phase"
    df = bot.compute_indicators(df)
    obs = bot.compute_smc(df)
    return df, obs


def load_locked_baseline_series():
    """artifacts/candles.csv, loaded exactly as scratch/regression.py does."""
    df = pd.read_csv(CANDLES_CSV_PATH)
    df["open_time"] = pd.to_datetime(df["open_time"])
    df = bot.compute_indicators(df)
    obs = bot.compute_smc(df)
    return df, obs


# ============================================================================
# CANDIDATES
# ============================================================================

def _bar_gates(hist, hist1, hist2, k, k1, d, j, kacc, atr_ratio):
    """The locked entry rule's bar-level gates, per side, from the same constants."""
    long_gates = {
        "macd": hist < 0 and hist > hist1 and hist1 > hist2,
        "kdj": k < bot.KDJ_K_LONG_CAP and k > k1 and j < bot.KDJ_J_LONG_CAP,
        "kacc": 1 <= kacc <= 6,
        "atr": not (0.8 <= atr_ratio <= 1.0),
    }
    short_gates = {
        "macd": hist > 0 and hist < hist1 and hist1 < hist2,
        "kdj": (k > 50 and j > k > d) and not (k < bot.KDJ_K_SHORT_FLOOR) and not (j > bot.KDJ_J_SHORT_CAP),
        "kacc": 1 <= kacc <= 6,
        "atr": not (0.8 <= atr_ratio <= 1.0),
    }
    return long_gates, short_gates


def build_candidates(df, obs, i_start, i_end, feature_offset=0):
    """
    Every (bar, Order Block) pair in [i_start, i_end) where price touches an
    active OB the way the entry rule defines a touch AND the engine's risk
    geometry is valid (SL >= MIN_STOP_LOSS_DISTANCE_RATIO, R:R >=
    MIN_RISK_REWARD_RATIO). Indicator gates are recorded (`gate_*`, always
    at the candidate's own bar i), not applied.

    Ordering within a bar follows simulate_trades(): every DEMAND OB in
    compute_smc() list order (LONG), then every SUPPLY OB (SHORT).

    `feature_offset` exists only for the lookahead test: the bar-level
    indicator features (f_*, f_g_*) are read at bar i + feature_offset while
    the candidate itself, its geometry and its rule gates stay at bar i.
    Production runs use 0.
    """
    close_arr = df["close"].to_numpy(float)
    high_arr = df["high"].to_numpy(float)
    low_arr = df["low"].to_numpy(float)
    hist_arr = df["MACD_hist"].to_numpy(float)
    k_arr, d_arr, j_arr = (df[c].to_numpy(float) for c in ("K", "D", "J"))
    atr_arr = df["ATR"].to_numpy(float)
    atr200_arr = df["ATR_200"].to_numpy(float)
    log_vol = np.log(df["volume"].to_numpy(float) + 1e-12)
    vol_mean = pd.Series(log_vol).rolling(30).mean().to_numpy()
    vol_std = pd.Series(log_vol).rolling(30).std(ddof=1).to_numpy()

    def bar_level(b):
        """Rule gates + oriented indicator features at bar b, per side."""
        close = float(close_arr[b])
        hist, hist1, hist2 = float(hist_arr[b]), float(hist_arr[b - 1]), float(hist_arr[b - 2])
        k, k1, k2 = float(k_arr[b]), float(k_arr[b - 1]), float(k_arr[b - 2])
        d, j = float(d_arr[b]), float(j_arr[b])
        atr_14, atr_200 = float(atr_arr[b]), float(atr200_arr[b])
        kacc = (k - k1) - (k1 - k2)
        atr_ratio = atr_14 / atr_200 if atr_200 > 0 else 1.0
        long_gates, short_gates = _bar_gates(hist, hist1, hist2, k, k1, d, j, kacc, atr_ratio)
        atr_safe = atr_14 if atr_14 > 0 else np.nan
        out = {}
        for side, s, gates in (("LONG", 1.0, long_gates), ("SHORT", -1.0, short_gates)):
            out[side] = {
                "gates": gates,
                "features": {
                    **{f"f_g_{g}": float(gates[g]) for g in GATES},
                    "f_macd_hist_atr": s * hist / atr_safe,
                    "f_macd_d1_atr": s * (hist - hist1) / atr_safe,
                    "f_macd_d2_atr": s * (hist1 - hist2) / atr_safe,
                    "f_k": k if s > 0 else 100.0 - k,
                    "f_d": d if s > 0 else 100.0 - d,
                    "f_j": j if s > 0 else 100.0 - j,
                    "f_k_d1": s * (k - k1),
                    "f_kacc": kacc,
                    "f_atr_ratio": atr_ratio,
                    "f_atr_pct": atr_14 / close,
                    "f_ret_6": s * np.log(close / close_arr[b - 6]),
                    "f_ret_30": s * np.log(close / close_arr[b - 30]),
                    "f_vol_z": (log_vol[b] - vol_mean[b]) / vol_std[b] if vol_std[b] > 0 else 0.0,
                },
            }
        return out

    index_by_identity = {id(ob): idx for idx, ob in enumerate(obs)}
    rows = []
    start_bar = max(bot.SWING_STRUCTURE_LOOKBACK_BARS + 5, i_start, 32)
    stop_bar = min(i_end, len(df) - max(feature_offset, 0))
    for i in range(start_bar, stop_bar):
        close, high, low = float(close_arr[i]), float(high_arr[i]), float(low_arr[i])
        atr_14 = float(atr_arr[i])

        active = [
            ob for ob in obs
            if ob["created_at"] < i < ob["mitigated_at"]
            and i - ob["created_at"] <= bot.MAX_ORDER_BLOCK_AGE_BARS
            and ob.get("quality", 0) >= 0
        ]
        if not active:
            continue
        rule_bar = bar_level(i)
        feature_bar = rule_bar if feature_offset == 0 else bar_level(i + feature_offset)
        order_in_bar = 0
        for side in ("LONG", "SHORT"):
            ob_type = "DEMAND" if side == "LONG" else "SUPPLY"
            for ob in (o for o in active if o["type"] == ob_type):
                if side == "LONG":
                    if not (low <= ob["top"] and close >= ob["bottom"]):
                        continue
                    stop_loss = ob["bottom"] - atr_14 * 0.5
                    risk = close - stop_loss
                else:
                    if not (high >= ob["bottom"] and close <= ob["top"]):
                        continue
                    stop_loss = ob["top"] + atr_14 * 0.5
                    risk = stop_loss - close
                if risk <= 0 or risk / close < bot.MIN_STOP_LOSS_DISTANCE_RATIO:
                    continue
                structural_tp = bot.get_structural_tp(close, side, active)
                if side == "LONG":
                    take_profit = structural_tp if structural_tp else close + risk * 2.0
                    reward = take_profit - close
                else:
                    take_profit = structural_tp if structural_tp else close - risk * 2.0
                    reward = close - take_profit
                if reward / risk < bot.MIN_RISK_REWARD_RATIO:
                    continue

                s = 1.0 if side == "LONG" else -1.0
                atr_safe = atr_14 if atr_14 > 0 else np.nan
                rows.append({
                    # identity / trade setup
                    "i": i, "order_in_bar": order_in_bar, "side": side,
                    "ob_id": f"{ob['type']}:{ob['level']}:{ob['ob_bar']}:{ob['created_at']}",
                    "ob_index": index_by_identity[id(ob)],
                    "entry": close, "stop_loss": stop_loss, "take_profit": take_profit, "entry_atr": atr_14,
                    "open_time": str(df.at[i, "open_time"]),
                    # the locked rule's gates, at bar i
                    **{f"gate_{g}": bool(rule_bar[side]["gates"][g]) for g in GATES},
                    # bar-level features (oriented so LONG semantics hold for both sides)
                    **feature_bar[side]["features"],
                    # Order Block features
                    "f_ob_quality": float(ob.get("quality", 0)),
                    "f_q_displacement": float(bool(ob.get("quality_displacement"))),
                    "f_q_large_bar": float(bool(ob.get("quality_large_bar"))),
                    "f_q_fvg": float(bool(ob.get("quality_fvg"))),
                    "f_q_liquidity_sweep": float(bool(ob.get("quality_liquidity_sweep"))),
                    "f_q_volume_expansion": float(bool(ob.get("quality_volume_expansion"))),
                    "f_ob_age": float(i - ob["created_at"]),
                    "f_ob_width_atr": (ob["top"] - ob["bottom"]) / atr_safe,
                    "f_ob_penetration_atr": ((close - ob["bottom"]) if s > 0 else (ob["top"] - close)) / atr_safe,
                    "f_ob_swing_level": float(ob["level"] == "swing"),
                    "f_sl_pct": risk / close,
                    "f_rr": reward / risk,
                    "f_tp_structural": float(bool(structural_tp)),
                    "f_side_long": float(s > 0),
                })
                order_in_bar += 1
    return pd.DataFrame(rows)


# Feature groups, one row each in every ablation table (PREREGISTRATION.md).
FEATURE_GROUPS = {
    "MACD_hist_gate": ["f_macd_hist_atr", "f_macd_d1_atr", "f_macd_d2_atr", "f_g_macd"],
    "KDJ_gate": ["f_k", "f_d", "f_j", "f_k_d1", "f_g_kdj"],
    "K_acceleration": ["f_kacc", "f_g_kacc"],
    "ATR_regime": ["f_atr_ratio", "f_atr_pct", "f_g_atr"],
    "OB_quality": ["f_ob_quality", "f_q_displacement", "f_q_large_bar", "f_q_fvg",
                   "f_q_liquidity_sweep", "f_q_volume_expansion"],
    "OB_geometry": ["f_ob_age", "f_ob_width_atr", "f_ob_penetration_atr", "f_ob_swing_level",
                    "f_sl_pct", "f_rr", "f_tp_structural"],
    "Price_volume_context": ["f_ret_6", "f_ret_30", "f_vol_z", "f_side_long"],
}
FEATURE_COLUMNS = [c for cols in FEATURE_GROUPS.values() for c in cols]


def feature_matrix(cands, columns=None):
    columns = FEATURE_COLUMNS if columns is None else columns
    return cands[columns].astype(float).to_numpy()


# ============================================================================
# SINGLE-TRADE SIMULATOR (engine exit rules, unchanged)
# ============================================================================

def _exit_work_frame(df):
    work = df.copy()
    for column_name in ["Trade_Status"]:
        work[column_name] = ""
    for column_name in ["Entry_Price", "Stop_Loss", "Take_Profit", "Exit_Price", "Running_PnL_%"]:
        work[column_name] = np.nan
    return work


def simulate_one(work, obs, cand, end_bar):
    """
    Run the engine's own exit helpers bar by bar from a candidate entry, the
    way simulate_trades()'s position branches do. Returns (exit_idx, pnl_pct,
    exit_reason), or (None, None, None) if still open at `end_bar`.
    """
    i, side = int(cand["i"]), cand["side"]
    entry, stop_loss, take_profit, entry_atr = cand["entry"], cand["stop_loss"], cand["take_profit"], cand["entry_atr"]
    ob = obs[int(cand["ob_index"])]
    kdj_state = bot.kdj_reset_init(work, i, ob_bar=ob.get("ob_bar", None))
    check = bot._check_long_exit_conditions if side == "LONG" else bot._check_short_exit_conditions
    peak_pnl_pct = 0.0
    for bar in range(i + 1, end_bar):
        close = float(work.at[bar, "close"])
        pnl_pct = (close - entry) / entry * 100 if side == "LONG" else (entry - close) / entry * 100
        peak_pnl_pct = max(peak_pnl_pct, pnl_pct)
        exit_reason, exit_pnl_pct, stop_loss, kdj_state = check(
            work, bar, close, entry, stop_loss, take_profit, entry_atr, peak_pnl_pct, pnl_pct, i, kdj_state,
        )
        if exit_reason is not None:
            return bar, exit_pnl_pct, exit_reason
    return None, None, None


def label_candidates(df, obs, cands, end_bar):
    work = _exit_work_frame(df)
    outcomes = [simulate_one(work, obs, row, end_bar) for _, row in cands.iterrows()]
    cands = cands.copy()
    cands["exit_idx"] = [o[0] for o in outcomes]
    cands["pnl_pct"] = [o[1] for o in outcomes]
    cands["exit_reason"] = [o[2] for o in outcomes]
    cands["resolved"] = cands["exit_idx"].notna()
    cands["label"] = (cands["pnl_pct"] > 0).astype(int)
    return cands


# ============================================================================
# SEQUENTIAL ONE-POSITION POLICY
# ============================================================================

def run_sequential(cands, take):
    """
    One position at a time, exactly as simulate_trades(): at the first bar
    with no open position, take the first candidate (in engine order) whose
    `take` flag is set. The exit bar is still a position bar, so the next
    entry can come no earlier than exit_idx + 1. A taken candidate that never
    resolves holds the position to the end of the series.
    """
    take = np.asarray(take, dtype=bool)
    next_free_bar = -1
    taken_rows = []
    for pos, (i, resolved, exit_idx) in enumerate(zip(cands["i"].to_numpy(), cands["resolved"].to_numpy(),
                                                       cands["exit_idx"].to_numpy())):
        if i < next_free_bar or not take[pos]:
            continue
        if not resolved:
            break
        taken_rows.append(pos)
        next_free_bar = int(exit_idx) + 1
    return cands.iloc[taken_rows].reset_index(drop=True)


def rule_mask(cands, gates=GATES):
    """The locked rule with only `gates` switched on (all four = A0)."""
    mask = np.ones(len(cands), dtype=bool)
    for g in gates:
        mask &= cands[f"gate_{g}"].to_numpy(bool)
    return mask


# ============================================================================
# PHASE: PARITY (hard gate)
# ============================================================================

def _save(name, payload):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_json_default)
    print(f"[saved] {os.path.relpath(path, BASE_DIR)}")
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def phase_parity():
    df, obs = load_locked_baseline_series()
    locked = bot.simulate_trades(df.copy(), min_ob_quality=0).attrs["trades_df"]
    assert len(locked) == bot.LOCKED_BASELINE_TRADE_COUNT, f"engine gave {len(locked)} trades, expected 27"

    cands = build_candidates(df, obs, 0, len(df))
    cands = label_candidates(df, obs, cands, len(df))
    ours = run_sequential(cands, rule_mask(cands))

    report = {"locked_trades": len(locked), "reproduced_trades": len(ours), "mismatches": []}
    for k in range(max(len(locked), len(ours))):
        a = locked.iloc[k] if k < len(locked) else None
        b = ours.iloc[k] if k < len(ours) else None
        same = (a is not None and b is not None
                and int(a["entry_idx"]) == int(b["i"]) and int(a["exit_idx"]) == int(b["exit_idx"])
                and a["side"] == b["side"] and a["exit_reason"] == b["exit_reason"]
                and float(a["pnl_pct"]) == float(b["pnl_pct"]) and float(a["entry"]) == float(b["entry"])
                and float(a["take_profit"]) == float(b["take_profit"]))
        if not same:
            report["mismatches"].append({
                "k": k,
                "locked": None if a is None else {c: a[c] for c in ("side", "entry_idx", "exit_idx", "pnl_pct", "exit_reason")},
                "ours": None if b is None else {"side": b["side"], "entry_idx": b["i"], "exit_idx": b["exit_idx"],
                                                "pnl_pct": b["pnl_pct"], "exit_reason": b["exit_reason"]},
            })
    report["parity_exact"] = not report["mismatches"]
    report["candidates_on_locked_window"] = len(cands)
    report["rule_passing_candidates_on_locked_window"] = int(rule_mask(cands).sum())

    # Truncation invariance: candidates/features for bars before a cut must
    # not change when later bars are appended (lookahead test (b)).
    report["truncation_checks"] = []
    rng = np.random.default_rng(MASTER_SEED)
    full_df, full_obs = load_extended_series(PREFIX_END, "select")
    full_c = build_candidates(full_df, full_obs, 0, PREFIX_END)
    for cut in sorted(rng.integers(2000, PREFIX_END - 500, size=3).tolist()):
        cut_df, cut_obs = load_extended_series(cut, "select")
        cut_c = build_candidates(cut_df, cut_obs, 0, cut)
        ref = full_c[full_c["i"] < cut].reset_index(drop=True)
        cols = ["i", "side", "ob_id", "entry", "stop_loss", "take_profit"] + [f"gate_{g}" for g in GATES] + FEATURE_COLUMNS
        identical = len(ref) == len(cut_c) and ref[cols].equals(cut_c[cols])
        report["truncation_checks"].append({"cut_bar": cut, "candidates_before_cut": len(ref), "identical": bool(identical)})
    report["truncation_invariant"] = all(c["identical"] for c in report["truncation_checks"])

    # Date guard unit check.
    try:
        load_extended_series(PREFIX_END + 1, "select")
        report["date_guard_raises"] = False
    except PermissionError:
        report["date_guard_raises"] = True

    _save("parity", report)
    print(json.dumps({k: v for k, v in report.items() if k != "mismatches"}, indent=2, default=_json_default))
    if report["mismatches"]:
        print("PARITY FAILED -- first mismatches:", json.dumps(report["mismatches"][:3], indent=2, default=_json_default))
    ok = report["parity_exact"] and report["truncation_invariant"] and report["date_guard_raises"]
    print("PARITY GATE:", "PASS" if ok else "FAIL")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", required=True, choices=["parity", "select", "freeze", "oos", "lockbox"])
    parser.add_argument("--i-understand-this-is-one-shot", action="store_true")
    args = parser.parse_args()
    t0 = time.time()
    ok = {"parity": phase_parity}[args.phase]()
    print(f"[{args.phase}] done in {time.time() - t0:.0f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
