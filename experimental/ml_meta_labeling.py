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
  report   regenerate experimental/RESULTS.md from results/*.json.
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


# ============================================================================
# MODELS (PREREGISTRATION.md section 5)
# ============================================================================

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import log_loss  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

MODEL_GRID = (
    [("logreg", {"C": c}) for c in (0.001, 0.01, 0.1, 1.0, 10.0)]
    + [("random_forest", {"max_depth": md, "min_samples_leaf": msl}) for md in (3, 5, None) for msl in (20, 50)]
    + [("hist_gbm", {"learning_rate": lr, "max_depth": md}) for lr in (0.03, 0.1) for md in (2, 3, 4)]
)
THRESHOLD_GRID = tuple(round(0.40 + 0.05 * k, 2) for k in range(7))   # 0.40 .. 0.70
MIN_POOLED_TRADES_FOR_THRESHOLD = 30
DEFAULT_THRESHOLD = 0.50
CV_BLOCKS = 5
EMBARGO_BARS = 30           # = longest 2018-2021 hold
N_NULL_RETRAINS = 200
N_RANDOM_FILTER_SEEDS = 1000
R1_BOOTSTRAP = 1000
R2_WINDOWS = 50
R2_WINDOW_BARS = 2190       # 12 months of 4h bars
ABLATION_BOOTSTRAP = 2000
PERMUTATION_REPEATS = 30


def make_model(family, params, seed=MASTER_SEED):
    if family == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=params["C"], max_iter=5000))
    if family == "random_forest":
        return RandomForestClassifier(n_estimators=500, max_features="sqrt", max_depth=params["max_depth"],
                                      min_samples_leaf=params["min_samples_leaf"], random_state=seed, n_jobs=-1)
    if family == "hist_gbm":
        return HistGradientBoostingClassifier(max_iter=200, min_samples_leaf=40, l2_regularization=1.0,
                                              learning_rate=params["learning_rate"], max_depth=params["max_depth"],
                                              early_stopping=False, random_state=seed)
    raise ValueError(family)


def fit_predict(family, params, train, test, columns=None, labels=None, seed=MASTER_SEED):
    model = make_model(family, params, seed)
    y = train["label"].to_numpy() if labels is None else labels
    model.fit(feature_matrix(train, columns), y)
    return model, model.predict_proba(feature_matrix(test, columns))[:, 1]


def cv_folds(cands):
    """
    Walk-forward purged/embargoed/OB-grouped folds over resolved 2018-2021
    candidates. Blocks are cut at bar boundaries so no bar is split.
    Yields (fold_number, train_frame, test_frame).
    """
    bars = cands["i"].to_numpy()
    cut_positions = [int(round(len(cands) * k / CV_BLOCKS)) for k in range(CV_BLOCKS + 1)]
    edges = [int(bars[0])] + [int(bars[p]) for p in cut_positions[1:-1]] + [int(bars[-1]) + 1]
    for k in range(1, CV_BLOCKS):
        test_start, test_end = edges[k], edges[k + 1]
        test = cands[(cands["i"] >= test_start) & (cands["i"] < test_end)]
        test_obs = set(test["ob_id"])
        train = cands[
            (cands["i"] < test_start)
            & (cands["exit_idx"] < test_start)                       # purge
            & (cands["i"] < test_start - EMBARGO_BARS)                # embargo
            & (~cands["ob_id"].isin(test_obs))                        # OB grouping
        ]
        yield k + 1, train, test


def _fold_trades(test, p, threshold):
    return run_sequential(test.reset_index(drop=True), p >= threshold)


def pick_threshold(oof):
    """oof: list of (test_frame, p) per fold. Highest pooled mean pnl/trade with >= 30 trades."""
    table = []
    for t in THRESHOLD_GRID:
        pooled = pd.concat([_fold_trades(test, p, t) for test, p in oof], ignore_index=True)
        n = len(pooled)
        table.append({"threshold": t, "pooled_trades": n,
                      "mean_pnl_pct": float(pooled["pnl_pct"].mean()) if n else None})
    qualifying = [r for r in table if r["pooled_trades"] >= MIN_POOLED_TRADES_FOR_THRESHOLD]
    if not qualifying:
        return DEFAULT_THRESHOLD, table
    best = max(qualifying, key=lambda r: (r["mean_pnl_pct"], -r["threshold"]))
    return best["threshold"], table


def cv_score(cands, family, params):
    fold_rows, oof = [], []
    for fold, train, test in cv_folds(cands):
        _, p = fit_predict(family, params, train, test)
        fold_rows.append({"fold": fold, "n_train": len(train), "n_test": len(test),
                          "log_loss": float(log_loss(test["label"], p, labels=[0, 1])),
                          "base_rate_test": float(test["label"].mean())})
        oof.append((test, p))
    return float(np.mean([r["log_loss"] for r in fold_rows])), fold_rows, oof


def _prefix_candidates(feature_offset=0):
    df, obs = load_extended_series(PREFIX_END, "select")
    cands = build_candidates(df, obs, 0, PREFIX_END, feature_offset=feature_offset)
    cands = label_candidates(df, obs, cands, PREFIX_END)
    return df, obs, cands


# ============================================================================
# PHASE: SELECT
# ============================================================================

def phase_select():
    df, obs, all_cands = _prefix_candidates()
    cands = all_cands[all_cands["resolved"]].reset_index(drop=True)
    minority = float(min(cands["label"].mean(), 1 - cands["label"].mean()))
    go = len(cands) >= 150 and minority >= 0.20
    report = {"phase": "select", "window": "2018-01-01 .. 2021-12-31 (bars [0, 8750))",
              "go_no_go": {"resolved_candidates": len(cands), "unresolved_dropped": int((~all_cands["resolved"]).sum()),
                           "distinct_obs": int(cands["ob_id"].nunique()), "minority_share": minority, "go": go}}
    if not go:
        _save("select", report)
        print("NO-GO -- stopping before model selection.")
        return False
    assert not np.isnan(feature_matrix(cands)).any(), "NaN in training features"

    grid_rows = []
    for family, params in MODEL_GRID:
        score, folds, _ = cv_score(cands, family, params)
        grid_rows.append({"family": family, "params": params, "mean_cv_log_loss": score, "folds": folds})
        print(f"  {family:14s} {str(params):45s} log-loss {score:.5f}")
    best = min(range(len(grid_rows)), key=lambda k: (grid_rows[k]["mean_cv_log_loss"], k))
    family, params = grid_rows[best]["family"], grid_rows[best]["params"]
    _, _, oof = cv_score(cands, family, params)
    threshold, threshold_table = pick_threshold(oof)

    # Reference point: log-loss of predicting each fold's training base rate.
    base_rate_ll = []
    for _, train, test in cv_folds(cands):
        p0 = np.full(len(test), train["label"].mean())
        base_rate_ll.append(float(log_loss(test["label"], p0, labels=[0, 1])))

    # Lookahead test (a): lagged and lead bar-level features, chosen config.
    shift_rows = {}
    for offset in (-1, 1):
        _, _, shifted = _prefix_candidates(feature_offset=offset)
        shifted = shifted[shifted["resolved"]].reset_index(drop=True)
        merged = cands[["i", "ob_id", "side"]].merge(shifted, on=["i", "ob_id", "side"], how="inner")
        score, _, _ = cv_score(merged, family, params)
        ref = cands.merge(shifted[["i", "ob_id", "side"]], on=["i", "ob_id", "side"], how="inner")
        ref_score, _, _ = cv_score(ref, family, params)
        shift_rows["lag_minus_1" if offset < 0 else "lead_plus_1"] = {
            "n": len(merged), "cv_log_loss_shifted": score, "cv_log_loss_unshifted_same_rows": ref_score}

    report.update({
        "model_grid": grid_rows,
        "chosen": {"family": family, "params": params, "mean_cv_log_loss": grid_rows[best]["mean_cv_log_loss"],
                   "grid_index": best},
        "base_rate_mean_cv_log_loss": float(np.mean(base_rate_ll)),
        "threshold": threshold, "threshold_table": threshold_table,
        "lookahead_shift_test": shift_rows,
    })
    _save("select", report)
    print(f"CHOSEN: {family} {params}  cv log-loss {grid_rows[best]['mean_cv_log_loss']:.5f} "
          f"(base-rate {np.mean(base_rate_ll):.5f})  threshold {threshold}")
    return True


# ============================================================================
# PHASE: FREEZE
# ============================================================================

FROZEN_MODEL_PATH = os.path.join(RESULTS_DIR, "frozen_model.pkl")


def phase_freeze():
    with open(os.path.join(RESULTS_DIR, "select.json"), encoding="utf-8") as f:
        select = json.load(f)
    family, params, threshold = select["chosen"]["family"], select["chosen"]["params"], select["threshold"]
    _, _, cands = _prefix_candidates()
    cands = cands[cands["resolved"]].reset_index(drop=True)
    model = make_model(family, params)
    model.fit(feature_matrix(cands), cands["label"].to_numpy())
    p_train = model.predict_proba(feature_matrix(cands))[:, 1]
    blob = pickle.dumps(model, protocol=4)
    with open(FROZEN_MODEL_PATH, "wb") as f:
        f.write(blob)
    import sklearn
    frozen = {
        "family": family, "params": params, "threshold": threshold, "feature_columns": FEATURE_COLUMNS,
        "feature_groups": FEATURE_GROUPS, "n_train": len(cands), "train_base_rate": float(cands["label"].mean()),
        "train_take_rate_at_threshold": float((p_train >= threshold).mean()),
        "model_sha256": hashlib.sha256(blob).hexdigest(), "sklearn_version": sklearn.__version__,
        "seed": MASTER_SEED,
    }
    _save("frozen_model", frozen)
    print(f"FROZEN {family} {params} t={threshold} sha256={frozen['model_sha256'][:16]}...")
    return True


def load_frozen():
    with open(os.path.join(RESULTS_DIR, "frozen_model.json"), encoding="utf-8") as f:
        frozen = json.load(f)
    with open(FROZEN_MODEL_PATH, "rb") as f:
        blob = f.read()
    if hashlib.sha256(blob).hexdigest() != frozen["model_sha256"]:
        raise RuntimeError("frozen model hash mismatch -- refusing to evaluate")
    assert frozen["feature_columns"] == FEATURE_COLUMNS, "feature list changed since freeze"
    return frozen, pickle.loads(blob)


# ============================================================================
# EVALUATION HELPERS
# ============================================================================

def summarize(trades, window_df, window_start):
    n = len(trades)
    out = {"n": n}
    if n == 0:
        return {**out, "wins": 0, "win_rate_pct": None, "mean_pnl_pct": None, "total_pnl_pct": 0.0, "sd_pnl_pct": None,
                "mean_net_pnl_pct": None, "total_net_pnl_pct": 0.0}
    pnl = trades["pnl_pct"].to_numpy(float)
    wins = int((pnl > 0).sum())
    out.update({
        "wins": wins, "win_rate_pct": wins / n * 100, "mean_pnl_pct": float(pnl.mean()),
        "total_pnl_pct": float(pnl.sum()), "sd_pnl_pct": float(pnl.std(ddof=1)) if n > 1 else None,
        "mean_net_pnl_pct": float(pnl.mean() - FEE_ROUND_TRIP_PCT), "total_net_pnl_pct": float((pnl - FEE_ROUND_TRIP_PCT).sum()),
        "binomial_p_one_sided": float(bot.binomial_test(wins, n)["p_one_sided"]),
        "longs": int((trades["side"] == "LONG").sum()), "shorts": int((trades["side"] == "SHORT").sum()),
    })
    rel = pd.DataFrame({"exit_idx": trades["exit_idx"].astype(int) - window_start,
                        "hold_bars": trades["exit_idx"].astype(int) - trades["i"].astype(int),
                        "pnl_pct": pnl})
    for label, drag in (("gross", 0.0), ("net", FEE_ROUND_TRIP_PCT)):
        dollar = bot._run_strategy_dollar_arm(window_df, rel, 10000.0, drag_pct=drag)
        out[f"dollar_{label}"] = {k: dollar[k] for k in ("final_capital", "sharpe", "max_drawdown_pct", "time_in_market_pct")}
    return out


def stationary_block_bootstrap(values, resamples, seed):
    values = np.asarray(values, float)
    n = len(values)
    if n == 0:
        return None
    block = max(1, int(round(n ** (1 / 3))))
    rng = np.random.default_rng(seed)
    means, totals = np.empty(resamples), np.empty(resamples)
    for b in range(resamples):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(n)
        for t in range(1, n):
            idx[t] = rng.integers(n) if rng.random() < 1.0 / block else (idx[t - 1] + 1) % n
        sample = values[idx]
        means[b], totals[b] = sample.mean(), sample.sum()
    return {"expected_block_length": block, "resamples": resamples,
            "mean_ci95": [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))],
            "total_ci95": [float(np.percentile(totals, 2.5)), float(np.percentile(totals, 97.5))],
            "p_total_le_0": float((totals <= 0).mean())}


def diff_of_means_bootstrap(a, b, resamples, seed):
    """Independent percentile bootstrap of mean(a) - mean(b); two-sided p."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return {"diff": None, "ci95": None, "p_two_sided": None}
    rng = np.random.default_rng(seed)
    diffs = np.array([rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(resamples)])
    p = min(1.0, 2 * min((diffs <= 0).mean(), (diffs >= 0).mean()))
    return {"diff": float(a.mean() - b.mean()), "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "p_two_sided": float(p)}


def holm(rows, key="p_two_sided", out_key="p_holm"):
    tested = [(r[key], k) for k, r in enumerate(rows) if r.get(key) is not None]
    tested.sort()
    m, running = len(tested), 0.0
    for rank, (p, k) in enumerate(tested):
        running = max(running, min(1.0, (m - rank) * p))
        rows[k][out_key] = running
    return rows


RULE_ABLATION_ARMS = (
    [(f"B-LOO minus {g}", tuple(x for x in GATES if x != g), False) for g in GATES]
    + [(f"B-ONLY {g}", (g,), False) for g in GATES]
    + [("B+Q quality>=1", GATES, True)]
)


def rule_ablation(cands, window_df, window_start, seed):
    """Section 10 rule-side arms vs A0 on one window."""
    a0 = run_sequential(cands, rule_mask(cands))
    check = run_sequential(cands, rule_mask(cands, GATES))
    rows = []
    for k, (name, gates, quality_filter) in enumerate(RULE_ABLATION_ARMS):
        mask = rule_mask(cands, gates)
        if quality_filter:
            mask &= cands["f_ob_quality"].to_numpy() >= bot.DEFAULT_MIN_OB_QUALITY
        trades = run_sequential(cands, mask)
        row = {"arm": name, "gates_on": list(gates), **summarize(trades, window_df, window_start)}
        row.update({f"vs_A0_{k2}": v for k2, v in diff_of_means_bootstrap(
            trades["pnl_pct"], a0["pnl_pct"], ABLATION_BOOTSTRAP, seed + k).items()})
        rows.append(row)
    holm(rows, key="vs_A0_p_two_sided", out_key="vs_A0_p_holm")
    return {"A0": summarize(a0, window_df, window_start),
            "all_gates_on_equals_A0": bool(check[["i", "exit_idx", "pnl_pct"]].equals(a0[["i", "exit_idx", "pnl_pct"]])),
            "arms": rows}


def _window_frame(df, start, end):
    return df.iloc[start:end].reset_index(drop=True)


def _trades_csv(name, trades):
    cols = ["open_time", "i", "exit_idx", "side", "entry", "stop_loss", "take_profit", "pnl_pct", "exit_reason", "ob_id"]
    if "p" in trades.columns:
        cols.append("p")
    trades[cols].to_csv(os.path.join(RESULTS_DIR, f"{name}.csv"), index=False)


# ============================================================================
# PHASE: OOS (2022-2025, once, after the freeze commit)
# ============================================================================

def phase_oos():
    frozen, model = load_frozen()
    family, params, threshold = frozen["family"], frozen["params"], frozen["threshold"]
    _, _, train = _prefix_candidates()
    train = train[train["resolved"]].reset_index(drop=True)

    df, obs = load_extended_series(OOS_END, "oos")
    cands = build_candidates(df, obs, PREFIX_END, OOS_END)
    cands = label_candidates(df, obs, cands, OOS_END)
    assert not np.isnan(feature_matrix(cands)).any(), "NaN in OOS features"
    cands["p"] = model.predict_proba(feature_matrix(cands))[:, 1]
    resolved = cands[cands["resolved"]]
    window_df = _window_frame(df, PREFIX_END, OOS_END)
    rng_seed = MASTER_SEED + 1

    take_a2 = cands["p"].to_numpy() >= threshold
    arms_trades = {
        "A0_rules": run_sequential(cands, rule_mask(cands)),
        "A1_all": run_sequential(cands, np.ones(len(cands), bool)),
        "A2_ml": run_sequential(cands, take_a2),
        "A3_ml_on_rules": run_sequential(cands, rule_mask(cands) & take_a2),
    }
    arms = {name: summarize(t, window_df, PREFIX_END) for name, t in arms_trades.items()}
    for name, t in arms_trades.items():
        _trades_csv(f"oos_trades_{name}", t)
    cands.to_csv(os.path.join(RESULTS_DIR, "oos_candidates.csv"), index=False)

    # A4: random filter at A2's candidate take-rate.
    q = float(take_a2.mean())
    rng = np.random.default_rng(rng_seed)
    a4_means, a4_totals, a4_n = [], [], []
    for _ in range(N_RANDOM_FILTER_SEEDS):
        t = run_sequential(cands, rng.random(len(cands)) < q)
        a4_n.append(len(t))
        a4_means.append(float(t["pnl_pct"].mean()) if len(t) else 0.0)
        a4_totals.append(float(t["pnl_pct"].sum()))
    a2_mean = arms["A2_ml"]["mean_pnl_pct"] or 0.0
    a2_total = arms["A2_ml"]["total_pnl_pct"]
    arms["A4_random"] = {
        "take_rate_q": q, "seeds": N_RANDOM_FILTER_SEEDS, "mean_n": float(np.mean(a4_n)),
        "mean_pnl_pct_median": float(np.median(a4_means)),
        "mean_pnl_pct_ci95": [float(np.percentile(a4_means, 2.5)), float(np.percentile(a4_means, 97.5))],
        "total_pnl_pct_median": float(np.median(a4_totals)),
        "share_seeds_mean_ge_A2": float(np.mean(np.array(a4_means) >= a2_mean)),
        "share_seeds_total_ge_A2": float(np.mean(np.array(a4_totals) >= a2_total)),
    }

    # A5: shuffled-label null (primary endpoint).
    target_rate = frozen["train_take_rate_at_threshold"]
    rng = np.random.default_rng(rng_seed + 1)
    null_means, null_n = [], []
    y = train["label"].to_numpy()
    for r in range(N_NULL_RETRAINS):
        y_perm = rng.permutation(y)
        null_model = make_model(family, params, seed=MASTER_SEED + 1000 + r)
        null_model.fit(feature_matrix(train), y_perm)
        p_train = null_model.predict_proba(feature_matrix(train))[:, 1]
        t_null = float(np.quantile(p_train, 1 - target_rate)) if target_rate > 0 else np.inf
        p_oos = null_model.predict_proba(feature_matrix(cands))[:, 1]
        t = run_sequential(cands, p_oos >= t_null)
        null_n.append(len(t))
        null_means.append(float(t["pnl_pct"].mean()) if len(t) else 0.0)
        if (r + 1) % 50 == 0:
            print(f"  null retrain {r + 1}/{N_NULL_RETRAINS}")
    null_means = np.array(null_means)
    primary_p = (1 + int((null_means >= a2_mean).sum())) / (1 + N_NULL_RETRAINS)
    primary = {
        "endpoint": "A2 mean pnl per trade, 2022-2025, vs shuffled-label null (one-sided, alpha 0.05)",
        "A2_n": arms["A2_ml"]["n"], "A2_mean_pnl_pct": arms["A2_ml"]["mean_pnl_pct"],
        "null_retrains": N_NULL_RETRAINS, "null_mean_of_means": float(null_means.mean()),
        "null_ci95": [float(np.percentile(null_means, 2.5)), float(np.percentile(null_means, 97.5))],
        "null_mean_n_trades": float(np.mean(null_n)), "null_zero_trade_runs": int(np.sum(np.array(null_n) == 0)),
        "p_one_sided": primary_p, "significant_at_0_05": primary_p < 0.05,
    }

    # OOS discrimination (descriptive).
    discrimination = {
        "oos_resolved_candidates": int(len(resolved)), "oos_base_rate": float(resolved["label"].mean()),
        "oos_log_loss_model": float(log_loss(resolved["label"], resolved["p"], labels=[0, 1])),
        "oos_log_loss_train_base_rate": float(log_loss(resolved["label"], np.full(len(resolved), frozen["train_base_rate"]), labels=[0, 1])),
    }
    from sklearn.metrics import roc_auc_score
    discrimination["oos_auc"] = float(roc_auc_score(resolved["label"], resolved["p"]))

    # R1 + R2 resamples.
    r1 = {name: stationary_block_bootstrap(t["pnl_pct"], R1_BOOTSTRAP, rng_seed + 2 + k)
          for k, (name, t) in enumerate(arms_trades.items())}
    rng = np.random.default_rng(rng_seed + 10)
    closes = df["close"].to_numpy(float)
    starts = sorted(rng.integers(PREFIX_END, OOS_END - R2_WINDOW_BARS + 1, size=R2_WINDOWS).tolist())
    r2_rows = []
    for s in starts:
        e = s + R2_WINDOW_BARS
        row = {"start_bar": s, "start_time": str(df.at[s, "open_time"]), "buy_hold_pct": (closes[e - 1] / closes[s] - 1) * 100}
        for name, t in arms_trades.items():
            inside = t[(t["i"] >= s) & (t["i"] < e)]
            row[f"{name}_n"] = len(inside)
            row[f"{name}_total"] = float(inside["pnl_pct"].sum())
        r2_rows.append(row)
    r2 = pd.DataFrame(r2_rows)
    r2.to_csv(os.path.join(RESULTS_DIR, "oos_r2_windows.csv"), index=False)
    r2_summary = {
        "windows": R2_WINDOWS, "window_bars": R2_WINDOW_BARS,
        "share_A2_total_gt_0": float((r2["A2_ml_total"] > 0).mean()),
        "share_A2_gt_A1": float((r2["A2_ml_total"] > r2["A1_all_total"]).mean()),
        "share_A2_gt_A0": float((r2["A2_ml_total"] > r2["A0_rules_total"]).mean()),
        "share_A2_gt_buy_hold": float((r2["A2_ml_total"] > r2["buy_hold_pct"]).mean()),
        "share_A0_total_gt_0": float((r2["A0_rules_total"] > 0).mean()),
        "share_A1_total_gt_0": float((r2["A1_all_total"] > 0).mean()),
        "share_A0_gt_buy_hold": float((r2["A0_rules_total"] > r2["buy_hold_pct"]).mean()),
        "median_A2_n": float(r2["A2_ml_n"].median()), "median_A2_total": float(r2["A2_ml_total"].median()),
        "median_A0_total": float(r2["A0_rules_total"].median()), "median_buy_hold": float(r2["buy_hold_pct"].median()),
    }

    # Passive benchmarks over the OOS window (paper's helpers).
    passive = {
        "buy_and_hold_gross": bot._run_lump_sum_dollar_arm(window_df, 10000.0),
        "dca_gross": bot._run_dca_dollar_arm(window_df, 10000.0),
        "buy_and_hold_fee": bot._run_lump_sum_dollar_arm(window_df, 10000.0, drag_pct=bot.BENCHMARK_ONE_SIDE_DRAG_PCT),
        "dca_fee": bot._run_dca_dollar_arm(window_df, 10000.0, drag_pct=bot.BENCHMARK_ONE_SIDE_DRAG_PCT),
    }
    passive = {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, np.ndarray, pd.Series))}
               for k, v in passive.items()}

    # Section 10: rule-side ablation, both windows.
    prefix_df, prefix_obs, prefix_cands = _prefix_candidates()
    rule_side = {
        "2018_2021": rule_ablation(prefix_cands, _window_frame(prefix_df, 0, PREFIX_END), 0, rng_seed + 100),
        "2022_2025": rule_ablation(cands, window_df, PREFIX_END, rng_seed + 200),
    }

    # Section 10: ML-side ablation (A6).
    base_ll = discrimination["oos_log_loss_model"]
    a2_pnl = arms_trades["A2_ml"]["pnl_pct"]
    drop_rows = []
    for k, (group, cols) in enumerate(FEATURE_GROUPS.items()):
        keep = [c for c in FEATURE_COLUMNS if c not in cols]
        m = make_model(family, params)
        m.fit(feature_matrix(train, keep), train["label"].to_numpy())
        p = m.predict_proba(feature_matrix(cands, keep))[:, 1]
        t = run_sequential(cands, p >= threshold)
        pr = p[cands["resolved"].to_numpy()]
        row = {"group": group, "dropped_columns": cols, "n_trades": len(t),
               "mean_pnl_pct": float(t["pnl_pct"].mean()) if len(t) else None,
               "oos_log_loss": float(log_loss(resolved["label"], pr, labels=[0, 1])),
               "delta_log_loss_vs_A2": float(log_loss(resolved["label"], pr, labels=[0, 1]) - base_ll)}
        row.update({f"A2_minus_dropped_{k2}": v for k2, v in diff_of_means_bootstrap(
            a2_pnl, t["pnl_pct"], ABLATION_BOOTSTRAP, rng_seed + 300 + k).items()})
        drop_rows.append(row)
    holm(drop_rows, key="A2_minus_dropped_p_two_sided", out_key="A2_minus_dropped_p_holm")

    rng = np.random.default_rng(rng_seed + 400)
    X_res = feature_matrix(resolved)
    y_res = resolved["label"].to_numpy()
    perm_rows = []
    for group, cols in FEATURE_GROUPS.items():
        idx = [FEATURE_COLUMNS.index(c) for c in cols]
        deltas = []
        for _ in range(PERMUTATION_REPEATS):
            Xp = X_res.copy()
            Xp[:, idx] = Xp[rng.permutation(len(Xp))][:, idx]
            deltas.append(log_loss(y_res, model.predict_proba(Xp)[:, 1], labels=[0, 1]) - base_ll)
        perm_rows.append({"group": group, "mean_delta_log_loss": float(np.mean(deltas)),
                          "sd_delta_log_loss": float(np.std(deltas, ddof=1))})

    report = {
        "phase": "oos", "window": "2022-01-01 .. 2025-12-31 (bars [8750, 17517))",
        "frozen_model_sha256": frozen["model_sha256"], "chosen": {"family": family, "params": params, "threshold": threshold},
        "oos_candidates": len(cands), "oos_candidates_taken_by_A2_threshold": int(take_a2.sum()),
        "primary_endpoint": primary, "arms": arms, "discrimination": discrimination,
        "R1_stationary_block_bootstrap": r1, "R2_random_12m_windows": r2_summary,
        "passive_benchmarks": passive, "rule_side_ablation": rule_side,
        "ml_side_ablation": {"drop_column": drop_rows, "group_permutation_importance": perm_rows},
    }
    _save("oos", report)
    print(json.dumps({"primary": primary, "A0": arms["A0_rules"]["n"], "A1": arms["A1_all"]["n"],
                      "A2": arms["A2_ml"]["n"], "A3": arms["A3_ml_on_rules"]["n"]}, indent=2, default=_json_default))
    return True


# ============================================================================
# PHASE: LOCKBOX (Jan-Aug 2026, one shot)
# ============================================================================

def phase_lockbox(confirmed):
    if not confirmed:
        print("Refusing: the lockbox is one-shot. Re-run with --i-understand-this-is-one-shot.")
        return False
    if os.path.exists(LOCKBOX_MARKER_PATH):
        print(f"Refusing: lockbox already used ({os.path.relpath(LOCKBOX_MARKER_PATH, BASE_DIR)} exists).")
        return False
    frozen, model = load_frozen()
    with open(LOCKBOX_MARKER_PATH, "w", encoding="utf-8") as f:
        f.write(f"lockbox opened {pd.Timestamp.utcnow().isoformat()} with model sha256 {frozen['model_sha256']}\n")

    with open(EXTENDED_JSON_PATH, encoding="utf-8") as f:
        total_bars = len(json.load(f))
    df, obs = load_extended_series(total_bars, "lockbox")
    cands = build_candidates(df, obs, OOS_END, total_bars)
    cands = label_candidates(df, obs, cands, total_bars)
    cands["p"] = model.predict_proba(feature_matrix(cands))[:, 1]
    take_a2 = cands["p"].to_numpy() >= frozen["threshold"]
    window_df = _window_frame(df, OOS_END, total_bars)
    arms_trades = {
        "A0_rules": run_sequential(cands, rule_mask(cands)),
        "A1_all": run_sequential(cands, np.ones(len(cands), bool)),
        "A2_ml": run_sequential(cands, take_a2),
        "A3_ml_on_rules": run_sequential(cands, rule_mask(cands) & take_a2),
    }
    for name, t in arms_trades.items():
        _trades_csv(f"lockbox_trades_{name}", t)
    closes = df["close"].to_numpy(float)
    report = {
        "phase": "lockbox", "window": f"{df.at[OOS_END, 'open_time']} .. {df.at[total_bars - 1, 'open_time']} (bars [{OOS_END}, {total_bars}))",
        "frozen_model_sha256": frozen["model_sha256"], "candidates": len(cands),
        "resolved_candidates": int(cands["resolved"].sum()),
        "arms": {name: summarize(t, window_df, OOS_END) for name, t in arms_trades.items()},
        "R1_stationary_block_bootstrap": {name: stationary_block_bootstrap(t["pnl_pct"], R1_BOOTSTRAP, MASTER_SEED + 500 + k)
                                          for k, (name, t) in enumerate(arms_trades.items())},
        "buy_hold_pct": float((closes[-1] / closes[OOS_END] - 1) * 100),
        "rule_side_ablation": rule_ablation(cands, window_df, OOS_END, MASTER_SEED + 600),
    }
    _save("lockbox", report)
    print(json.dumps({k: {"n": v["n"], "mean": v["mean_pnl_pct"], "total": v["total_pnl_pct"]}
                      for k, v in report["arms"].items()}, indent=2, default=_json_default))
    return True


# ============================================================================
# PHASE: REPORT (RESULTS.md, every number read from results/*.json)
# ============================================================================

def _fmt(x, nd=2, signed=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _arm_row(name, a):
    d = a.get("dollar_net") or {}
    return (f"| {name} | {a['n']} | {_fmt(a['win_rate_pct'], 1)} | {_fmt(a['mean_pnl_pct'], 3, True)} | "
            f"{_fmt(a['total_pnl_pct'], 2, True)} | {_fmt(a['total_net_pnl_pct'], 2, True)} | "
            f"{_fmt(d.get('sharpe'), 2)} | {_fmt(d.get('max_drawdown_pct'), 1)} |")


ARM_TABLE_HEADER = ("| Arm | Trades | Win % | Mean pnl/trade % | Total % (gross) | Total % (net 0.20) | Sharpe (net) | Max DD % (net) |\n"
                    "|---|---|---|---|---|---|---|---|")
ARM_LABELS = {"A0_rules": "A0 locked rules", "A1_all": "A1 take every candidate", "A2_ml": "**A2 ML filter (primary)**",
              "A3_ml_on_rules": "A3 ML on rule-passing only"}


def _rule_table(block):
    lines = ["| Arm | Gates on | Trades | Win % | Mean % | Total % | Δ mean vs A0 [95% CI] | p (two-sided) | p (Holm) |",
             "|---|---|---|---|---|---|---|---|---|"]
    a0 = block["A0"]
    lines.append(f"| A0 (reference) | all 4 | {a0['n']} | {_fmt(a0['win_rate_pct'], 1)} | {_fmt(a0['mean_pnl_pct'], 3, True)} | "
                 f"{_fmt(a0['total_pnl_pct'], 2, True)} | — | — | — |")
    for r in block["arms"]:
        ci = r.get("vs_A0_ci95")
        ci_s = f"{_fmt(r.get('vs_A0_diff'), 3, True)} [{_fmt(ci[0], 2, True)}, {_fmt(ci[1], 2, True)}]" if ci else "n/a"
        lines.append(f"| {r['arm']} | {', '.join(r['gates_on'])} | {r['n']} | {_fmt(r['win_rate_pct'], 1)} | "
                     f"{_fmt(r['mean_pnl_pct'], 3, True)} | {_fmt(r['total_pnl_pct'], 2, True)} | {ci_s} | "
                     f"{_fmt(r.get('vs_A0_p_two_sided'), 3)} | {_fmt(r.get('vs_A0_p_holm'), 3)} |")
    lines.append(f"\nSanity: all four gates on reproduces A0 trade for trade: **{block['all_gates_on_equals_A0']}**.")
    return "\n".join(lines)


def phase_report():
    def load(name):
        path = os.path.join(RESULTS_DIR, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    parity, select, frozen, oos, lockbox = (load(n) for n in ("parity", "select", "frozen_model", "oos", "lockbox"))
    pe = oos["primary_endpoint"]
    arms = oos["arms"]
    disc = oos["discrimination"]
    r2 = oos["R2_random_12m_windows"]
    out = []
    w = out.append

    w("# Results: ML meta-labeling experiment\n")
    w("> Generated by `python experimental/ml_meta_labeling.py --phase report` from `experimental/results/*.json`. "
      "Do not edit numbers by hand. Design: [PREREGISTRATION.md](PREREGISTRATION.md). Exploratory, and not part of the paper.\n")

    w("## Bottom line\n")
    verdict = "REJECTS" if pe["significant_at_0_05"] else "does NOT reject"
    w(f"- **Primary endpoint (pre-registered, one test):** A2's mean pnl per trade in 2022–2025 is "
      f"**{_fmt(pe['A2_mean_pnl_pct'], 3, True)}%** over **{pe['A2_n']}** trades. The shuffled-label null gives "
      f"{_fmt(pe['null_mean_of_means'], 3, True)}% (95% of null runs fall in [{_fmt(pe['null_ci95'][0], 2, True)}, "
      f"{_fmt(pe['null_ci95'][1], 2, True)}]). One-sided p = **{_fmt(pe['p_one_sided'], 3)}** over {pe['null_retrains']} retrains. "
      f"At α = 0.05 this **{verdict}** the null that the model's selection is no better than a model trained on noise.")
    a0, a2 = arms["A0_rules"], arms["A2_ml"]
    w(f"- **Trade count:** A2 takes {a2['n']} trades in 2022–2025, against {a0['n']} for the locked rules on the same "
      f"stream (the paper's figure is 27 on `candles.csv`).")
    w(f"- **Out-of-sample discrimination:** AUC {_fmt(disc['oos_auc'], 3)}. Log-loss is {_fmt(disc['oos_log_loss_model'], 4)} for the model "
      f"vs {_fmt(disc['oos_log_loss_train_base_rate'], 4)} for a constant 2018–21 base rate (lower is better). "
      f"The OOS base rate is {_fmt(disc['oos_base_rate'] * 100, 1)}%.")
    w(f"- **Does it hold across 50 random 12-month windows (R2)?** A2's total is > 0 in {_fmt(r2['share_A2_total_gt_0'] * 100, 0)}% of windows. "
      f"It beats A1 in {_fmt(r2['share_A2_gt_A1'] * 100, 0)}%, beats A0 in {_fmt(r2['share_A2_gt_A0'] * 100, 0)}%, and beats buy-and-hold "
      f"in {_fmt(r2['share_A2_gt_buy_hold'] * 100, 0)}%. For comparison, A0's total is > 0 in {_fmt(r2['share_A0_total_gt_0'] * 100, 0)}% of windows.")
    if lockbox:
        lb = lockbox["arms"]
        w(f"- **Lockbox (Jan–Aug 2026, run once):** A2 {lb['A2_ml']['n']} trades, mean {_fmt(lb['A2_ml']['mean_pnl_pct'], 3, True)}%, "
          f"total {_fmt(lb['A2_ml']['total_pnl_pct'], 2, True)}%. A0 {lb['A0_rules']['n']} trades, total {_fmt(lb['A0_rules']['total_pnl_pct'], 2, True)}%. "
          f"Buy-and-hold {_fmt(lockbox['buy_hold_pct'], 2, True)}%.")
    else:
        w("- **Lockbox (Jan–Aug 2026):** not opened yet.")
    w("")

    w("## Integrity gates\n")
    w(f"- Parity: the single-trade simulator + rule policy reproduces the locked trades exactly: **{parity['parity_exact']}** "
      f"({parity['reproduced_trades']}/{parity['locked_trades']}).")
    w(f"- Truncation invariance (features don't change when future bars are appended): **{parity['truncation_invariant']}** "
      f"(cuts at bars {', '.join(str(c['cut_bar']) for c in parity['truncation_checks'])}).")
    w(f"- 2022+ date guard raises inside select/freeze: **{parity['date_guard_raises']}**.")
    lt = select["lookahead_shift_test"]
    w(f"- One-bar shift test on CV log-loss (unshifted {_fmt(lt['lag_minus_1']['cv_log_loss_unshifted_same_rows'], 4)}): "
      f"lagged features {_fmt(lt['lag_minus_1']['cv_log_loss_shifted'], 4)} (expected: not better). "
      f"Lead features, the positive control, {_fmt(lt['lead_plus_1']['cv_log_loss_shifted'], 4)} (expected: better). "
      f"This shows the test can detect leakage.")
    w(f"- Frozen model sha256 `{frozen['model_sha256']}`, committed before the OOS run and checked by `oos`.")
    repro = load("reproducibility")
    if repro:
        w(f"- Re-running `oos` with the same seeds: every non-float field is identical, and "
          f"{repro['float_fields_differing']} float fields differ by at most {repro['max_abs_difference']:.1e}. "
          f"So the result is not byte-identical. Cause: {repro['cause']}")
    w("")

    w("## Model selection (2018–2021 only)\n")
    gg = select["go_no_go"]
    w(f"{gg['resolved_candidates']} resolved candidates on {gg['distinct_obs']} distinct OBs, minority share "
      f"{_fmt(gg['minority_share'] * 100, 1)}%: GO. Purged, embargoed (30 bars), OB-grouped walk-forward CV, 4 test folds.\n")
    w("| # | Family | Params | Mean CV log-loss |\n|---|---|---|---|")
    for k, r in enumerate(select["model_grid"]):
        mark = " **(chosen)**" if k == select["chosen"]["grid_index"] else ""
        w(f"| {k} | {r['family']} | `{json.dumps(r['params'])}` | {_fmt(r['mean_cv_log_loss'], 5)}{mark} |")
    w(f"\nConstant base-rate reference: {_fmt(select['base_rate_mean_cv_log_loss'], 5)}.\n")
    w("Threshold (chosen config, out-of-fold, sequential one-position policy inside each fold):\n")
    w("| t | Pooled OOF trades | Mean pnl/trade % |\n|---|---|---|")
    for r in select["threshold_table"]:
        mark = " **(chosen)**" if r["threshold"] == select["threshold"] else ""
        w(f"| {r['threshold']:.2f}{mark} | {r['pooled_trades']} | {_fmt(r['mean_pnl_pct'], 3, True)} |")
    w("")

    w("## Out-of-sample 2022–2025: arms\n")
    w(f"{oos['oos_candidates']} candidates, {oos['oos_candidates_taken_by_A2_threshold']} with p ≥ {oos['chosen']['threshold']}. "
      "Every arm uses the same candidate stream, the same exit simulator and the same one-position policy.\n")
    w(ARM_TABLE_HEADER)
    for name in ("A0_rules", "A1_all", "A2_ml", "A3_ml_on_rules"):
        w(_arm_row(ARM_LABELS[name], arms[name]))
    a4 = arms["A4_random"]
    w(f"\n**A4 random filter** at A2's candidate take-rate (q = {_fmt(a4['take_rate_q'], 4)}), {a4['seeds']} seeds: about "
      f"{_fmt(a4['mean_n'], 1)} trades per run, and the median of the per-run mean pnl is {_fmt(a4['mean_pnl_pct_median'], 3, True)}% "
      f"(95% range [{_fmt(a4['mean_pnl_pct_ci95'][0], 2, True)}, {_fmt(a4['mean_pnl_pct_ci95'][1], 2, True)}]). "
      f"{_fmt(a4['share_seeds_mean_ge_A2'] * 100, 1)}% of seeds match or beat A2's mean, and "
      f"{_fmt(a4['share_seeds_total_ge_A2'] * 100, 1)}% match or beat its total.\n")
    w(f"**A5 shuffled-label null:** {pe['null_retrains']} retrains, {_fmt(pe['null_mean_n_trades'], 1)} trades per run on average, "
      f"{pe['null_zero_trade_runs']} runs with zero trades (counted as mean 0).\n")
    pb = oos["passive_benchmarks"]
    w("**Passive, same window (the paper's helpers, $10,000):**\n")
    w("| Benchmark | Final capital | Total % | Sharpe | Max DD % |\n|---|---|---|---|---|")
    for k, lab in (("buy_and_hold_gross", "Buy & hold (gross)"), ("buy_and_hold_fee", "Buy & hold (0.10% fee)"),
                   ("dca_gross", "Weekly DCA (gross)"), ("dca_fee", "Weekly DCA (0.10% fee)")):
        b = pb[k]
        w(f"| {lab} | {_fmt(b.get('final_capital'), 0)} | {_fmt(b.get('total_return_pct'), 2, True)} | {_fmt(b.get('sharpe'), 2)} | "
          f"{_fmt(b.get('max_drawdown_pct'), 1)} |")
    w("")

    w("## Resamples\n")
    w("**R1: stationary block bootstrap of each arm's OOS trade sequence (B = 1,000)**\n")
    w("| Arm | Block len | Mean pnl 95% CI | Total pnl 95% CI | P(total ≤ 0) |\n|---|---|---|---|---|")
    for name, r in oos["R1_stationary_block_bootstrap"].items():
        if r is None:
            w(f"| {ARM_LABELS[name]} | — | no trades | — | — |")
            continue
        w(f"| {ARM_LABELS[name]} | {r['expected_block_length']} | [{_fmt(r['mean_ci95'][0], 3, True)}, {_fmt(r['mean_ci95'][1], 3, True)}] | "
          f"[{_fmt(r['total_ci95'][0], 1, True)}, {_fmt(r['total_ci95'][1], 1, True)}] | {_fmt(r['p_total_le_0'], 3)} |")
    w(f"\n**R2: {r2['windows']} random contiguous 12-month windows inside 2022–2025** (per-window rows in `results/oos_r2_windows.csv`)\n")
    w("| Statistic | Value |\n|---|---|")
    for k, lab in (("share_A2_total_gt_0", "Share of windows A2 total > 0"), ("share_A0_total_gt_0", "Share of windows A0 total > 0"),
                   ("share_A1_total_gt_0", "Share of windows A1 total > 0"), ("share_A2_gt_A1", "Share A2 > A1"),
                   ("share_A2_gt_A0", "Share A2 > A0"), ("share_A2_gt_buy_hold", "Share A2 > buy & hold"),
                   ("share_A0_gt_buy_hold", "Share A0 > buy & hold")):
        w(f"| {lab} | {_fmt(r2[k] * 100, 0)}% |")
    w(f"| Median A2 trades / window | {_fmt(r2['median_A2_n'], 0)} |")
    w(f"| Median total %: A2 / A0 / buy & hold | {_fmt(r2['median_A2_total'], 2, True)} / {_fmt(r2['median_A0_total'], 2, True)} / "
      f"{_fmt(r2['median_buy_hold'], 2, True)} |")
    w("\nThe windows overlap heavily (12 months drawn inside 48), so these 50 are not independent draws. "
      "Read the shares as stability across sub-periods, not as a probability.\n")

    w("## Individual indicator effects (exploratory, Holm-corrected within each table)\n")
    w("Gates are only switched on or off; thresholds are never changed. Each Δ is an independent bootstrap (B = 2,000) of "
      "mean pnl/trade vs A0. One-at-a-time ablation misses interactions, which is why both B-LOO and B-ONLY are shown.\n")
    for key, lab in (("2018_2021", "2018–2021 (formulation period, in-sample for the rules)"), ("2022_2025", "2022–2025")):
        w(f"### Rule side: {lab}\n")
        w(_rule_table(oos["rule_side_ablation"][key]))
        w("")
    if lockbox:
        w("### Rule side: lockbox Jan–Aug 2026\n")
        w(_rule_table(lockbox["rule_side_ablation"]))
        w("")
    w("### ML side (A6), 2022–2025\n")
    w("Drop-column: the frozen config refit on 2018–21 without the group, with the frozen threshold kept.\n")
    w("| Group dropped | Trades | Mean % | OOS log-loss | Δ log-loss vs A2 | A2 − dropped mean [95% CI] | p | p (Holm) |\n"
      "|---|---|---|---|---|---|---|---|")
    for r in oos["ml_side_ablation"]["drop_column"]:
        ci = r.get("A2_minus_dropped_ci95")
        ci_s = f"{_fmt(r.get('A2_minus_dropped_diff'), 3, True)} [{_fmt(ci[0], 2, True)}, {_fmt(ci[1], 2, True)}]" if ci else "n/a"
        w(f"| {r['group']} | {r['n_trades']} | {_fmt(r['mean_pnl_pct'], 3, True)} | {_fmt(r['oos_log_loss'], 4)} | "
          f"{_fmt(r['delta_log_loss_vs_A2'], 4, True)} | {ci_s} | {_fmt(r.get('A2_minus_dropped_p_two_sided'), 3)} | "
          f"{_fmt(r.get('A2_minus_dropped_p_holm'), 3)} |")
    w("\nA positive Δ log-loss means the model is worse without the group, so the group was helping out of sample.\n")
    w("Group permutation importance on OOS candidates (frozen model, the group's columns permuted jointly, 30 repeats):\n")
    w("| Group | Mean Δ log-loss | SD |\n|---|---|---|")
    for r in sorted(oos["ml_side_ablation"]["group_permutation_importance"], key=lambda r: -r["mean_delta_log_loss"]):
        w(f"| {r['group']} | {_fmt(r['mean_delta_log_loss'], 5, True)} | {_fmt(r['sd_delta_log_loss'], 5)} |")
    w("")

    if lockbox:
        w("## Lockbox: Jan–Aug 2026 (one shot)\n")
        w(f"Window {lockbox['window']}. {lockbox['candidates']} candidates ({lockbox['resolved_candidates']} resolved).\n")
        w(ARM_TABLE_HEADER)
        for name in ("A0_rules", "A1_all", "A2_ml", "A3_ml_on_rules"):
            w(_arm_row(ARM_LABELS[name], lockbox["arms"][name]))
        w(f"\nBuy & hold over the lockbox: {_fmt(lockbox['buy_hold_pct'], 2, True)}%.\n")

    w("## Limitations\n")
    w("- 2018–2021 is the period the rule structure itself was formulated on (`docs/SCRATCH_RESULTS_METHODS.md`). "
      "Training there is legitimate for the ML, but the A0/B rule arms on 2018–21 are in-sample.")
    same_as_paper = (a0["n"] == bot.LOCKED_BASELINE_TRADE_COUNT
                     and abs(a0["total_pnl_pct"] - bot.LOCKED_BASELINE_TOTAL_RETURN_PCT) < 0.01)
    w("- A0 here starts fresh at 2022-01-01 on the extended series, with indicators warmed up since 2018. "
      "The paper's 27 come from `candles.csv`, which warms up at 2022-01-01. "
      + (f"Here they coincide: A0 = {a0['n']} trades, {_fmt(a0['total_pnl_pct'], 2, True)}%, matching the paper's locked figure."
         if same_as_paper else
         f"They differ here (A0 = {a0['n']} trades, {_fmt(a0['total_pnl_pct'], 2, True)}% vs the paper's 27, +30.31%), and both are reported."))
    w("- Candidates overlap: the same OB is touched on consecutive bars. The effective sample is closer to the number of OBs "
      "than the number of candidates, which is why CV is grouped by OB.")
    w("- One position at a time means the arms trade different subsets. Δ-mean comparisons between arms are on different trades, "
      "so they use independent rather than paired bootstraps.")
    w("- Exploratory tests (sections on indicators, R1, R2, A4) are not confirmatory, even after Holm correction.")
    text = "\n".join(out) + "\n"
    path = os.path.join(EXPERIMENT_DIR, "RESULTS.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[saved] {os.path.relpath(path, BASE_DIR)}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", required=True, choices=["parity", "select", "freeze", "oos", "lockbox", "report"])
    parser.add_argument("--i-understand-this-is-one-shot", action="store_true")
    args = parser.parse_args()
    t0 = time.time()
    phases = {"parity": phase_parity, "select": phase_select, "freeze": phase_freeze, "oos": phase_oos,
              "lockbox": lambda: phase_lockbox(args.i_understand_this_is_one_shot), "report": phase_report}
    ok = phases[args.phase]()
    print(f"[{args.phase}] done in {time.time() - t0:.0f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
