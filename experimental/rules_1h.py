"""
EXPERIMENTAL -- the locked rules on 1-hour candles. Design is fixed by
experimental/PREREGISTRATION_1H.md (committed before any 1h backtest).

Not part of the paper. research_analysis.py is loaded, never edited: the
LITERAL arm runs it unchanged; the TIME-SCALED arm runs a second, separately
loaded copy of the module whose three bar-count module constants are set x4,
fed indicator columns from compute_indicators_scaled() below.

Phases (each writes experimental/results_1h/<phase>.json):
  gates    G1-G4 of the pre-registration (G5 = scratch/regression.py, run separately)
  main     2022-2025 primary endpoint + S1-S7 (bars before 2026-08-08 only)
  holdout  2026-08-08 onward, one shot (--i-understand-this-is-one-shot)
  report   regenerate experimental/RESULTS_1H.md from results_1h/*.json
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EXPERIMENT_DIR)
import ml_meta_labeling as mml  # noqa: E402  (reuses its engine instance, candidate builder and stats helpers)

bot = mml.bot
BASE_DIR = mml.BASE_DIR
RESULTS_DIR = os.path.join(EXPERIMENT_DIR, "results_1h")
CSV_PATH = os.path.join(EXPERIMENT_DIR, "data", "btcusdt_1h.csv")
MANIFEST_PATH = os.path.join(EXPERIMENT_DIR, "data", "btcusdt_1h_manifest.json")
HOLDOUT_MARKER_PATH = os.path.join(RESULTS_DIR, "HOLDOUT_USED.marker")

SCALE = 4                                   # 4h / 1h, fixed by the pre-registration, never swept
MAIN_START = pd.Timestamp("2022-01-01")
MAIN_END = pd.Timestamp("2026-01-01")
SEEN_2026_START = pd.Timestamp("2026-01-01")
HOLDOUT_START = pd.Timestamp("2026-08-08")
FEE_PCT = bot.BENCHMARK_ROUND_TRIP_DRAG_PCT  # 0.20
FEE_LEVELS = (0.10, 0.20, 0.30)
PRIMARY_SEED = 20260808
PRIMARY_BOOTSTRAP = 10_000
S2_BOOTSTRAP = 2_000
S3_SEEDS = 1_000
S4_WINDOWS = 50
S4_WINDOW_BARS = 24 * 365                   # 12 months of 1h bars
PERIODS_PER_YEAR_1H = 24 * 365.25
# The paper's dollar-arm helpers annualise Sharpe with 4h periods
# (PERIODS_PER_YEAR_4H_BARS). Sharpe scales with sqrt(periods/year), so the
# 1h value is exactly the helper's value times sqrt(8766 / 2191.5) = 2.
SHARPE_RESCALE_1H = math.sqrt(PERIODS_PER_YEAR_1H / bot.PERIODS_PER_YEAR_4H_BARS)

# Second engine instance for the time-scaled arm (module constants x4).
_spec = importlib.util.spec_from_file_location("bot_scaled", os.path.join(BASE_DIR, "research_analysis.py"))
bot_scaled = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bot_scaled)
bot_scaled.INTERNAL_STRUCTURE_LOOKBACK_BARS = bot.INTERNAL_STRUCTURE_LOOKBACK_BARS * SCALE   # 5 -> 20
bot_scaled.SWING_STRUCTURE_LOOKBACK_BARS = bot.SWING_STRUCTURE_LOOKBACK_BARS * SCALE         # 50 -> 200
bot_scaled.MAX_ORDER_BLOCK_AGE_BARS = bot.MAX_ORDER_BLOCK_AGE_BARS * SCALE                   # 500 -> 2000


# ============================================================================
# DATA + INDICATORS
# ============================================================================

def load_1h(phase):
    """G1 (hash) on every load; the main/gates phases never see holdout bars."""
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(CSV_PATH, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != manifest["csv_sha256"]:
            raise RuntimeError("G1 failed: btcusdt_1h.csv hash does not match its manifest")
    df = pd.read_csv(CSV_PATH)
    df["open_time"] = pd.to_datetime(df["open_time"])
    if phase in ("gates", "main"):
        df = df[df["open_time"] < HOLDOUT_START].reset_index(drop=True)
        assert df["open_time"].max() < HOLDOUT_START, "date guard: holdout bar leaked"
    elif phase != "holdout":
        raise ValueError(phase)
    return df


def compute_indicators_scaled(df, factor):
    """
    research_analysis.compute_indicators() with every window multiplied by
    `factor` (MACD spans, KDJ RSV window, ATR, ATR baseline). Smoothing
    alpha and all formulas are unchanged; output column names are the
    engine's own, so simulate_trades() skips its own compute_indicators().
    G2: factor=1 must equal compute_indicators() bit for bit.
    """
    df = df.copy()
    for column_name in ["open", "high", "low", "close", "volume"]:
        if column_name in df.columns:
            df[column_name] = pd.to_numeric(df[column_name], errors="coerce")

    ema_fast = df["close"].ewm(span=12 * factor, adjust=False).mean()
    ema_slow = df["close"].ewm(span=26 * factor, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=9 * factor, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    period = int(9 * factor)
    rolling_low_min = df["low"].rolling(period, min_periods=1).min()
    rolling_high_max = df["high"].rolling(period, min_periods=1).max()
    rsv_denominator = (rolling_high_max - rolling_low_min).replace(0, np.nan)
    raw_stochastic_value = ((df["close"] - rolling_low_min) / rsv_denominator * 100).fillna(50)
    kdj_smoothing_alpha = 1.0 / 3.0
    df["K"] = raw_stochastic_value.ewm(alpha=kdj_smoothing_alpha, adjust=False).mean()
    df["D"] = df["K"].ewm(alpha=kdj_smoothing_alpha, adjust=False).mean()
    df["J"] = 3 * df["K"] - 2 * df["D"]
    df["RSV"] = raw_stochastic_value

    previous_close = df["close"].shift(1)
    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR"] = true_range.rolling(14 * factor, min_periods=1).mean()
    df["ATR_200"] = true_range.rolling(200 * factor, min_periods=1).mean()   # the engine's baseline column

    if "num_trades" not in df.columns:
        df["num_trades"] = 0.0
    if "taker_buy_base" not in df.columns:
        df["taker_buy_base"] = df["volume"] * 0.5
    return df


def run_arm(raw, arm):
    """Run one arm over the whole loaded series. Returns (indicator df, OBs, trades)."""
    if arm == "literal":
        engine, df = bot, bot.compute_indicators(raw)
    else:
        engine, df = bot_scaled, compute_indicators_scaled(raw, SCALE)
    sim = engine.simulate_trades(df.copy(), min_ob_quality=0)
    obs = engine._smc_detection_cache[(len(df), float(df["close"].iloc[-1]))]
    trades = sim.attrs["trades_df"].copy()
    trades["entry_time"] = pd.to_datetime(df["open_time"].to_numpy()[trades["entry_idx"].astype(int)])
    return df, obs, trades


# ============================================================================
# STATS HELPERS
# ============================================================================

def _as_mml_trades(trades):
    return trades.rename(columns={"entry_idx": "i"})


def summarize_1h(trades, raw, start_idx, end_idx):
    window_df = raw.iloc[start_idx:end_idx].reset_index(drop=True)
    s = mml.summarize(_as_mml_trades(trades), window_df, start_idx)
    for key in ("dollar_gross", "dollar_net"):
        if key in s and s[key].get("sharpe") is not None:
            s[key]["sharpe"] = s[key]["sharpe"] * SHARPE_RESCALE_1H
    if len(trades):
        s["mean_hold_bars_hours"] = float((trades["exit_idx"] - trades["entry_idx"]).mean())
        s["trades_per_year"] = len(trades) / ((raw["open_time"].iloc[end_idx - 1] - raw["open_time"].iloc[start_idx]).days / 365.25)
    return s


def window_bounds(raw, start, end):
    t = raw["open_time"]
    idx = np.where((t >= start) & (t < end))[0]
    return int(idx[0]), int(idx[-1]) + 1


def in_window(trades, start, end):
    return trades[(trades["entry_time"] >= start) & (trades["entry_time"] < end)].reset_index(drop=True)


def primary_style_test(trades, seed):
    net = trades["pnl_pct"].to_numpy(float) - FEE_PCT
    boot = mml.stationary_block_bootstrap(net, PRIMARY_BOOTSTRAP, seed)
    return {
        "n": int(len(net)), "mean_net_pnl_pct": float(net.mean()) if len(net) else None,
        "bootstrap": boot, "p_one_sided": boot["p_total_le_0"] if boot else None,
        "significant_at_0_05": bool(boot and boot["p_total_le_0"] < 0.05),
        "underpowered_lt_10_trades": bool(len(net) < 10),
    }


def _save(name, payload):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=mml._json_default)
    print(f"[saved] {os.path.relpath(path, BASE_DIR)}")


def _trades_csv(name, trades):
    cols = ["entry_time", "side", "entry_idx", "exit_idx", "entry", "exit", "stop_loss", "take_profit", "pnl_pct",
            "exit_reason", "hold_bars"]
    trades[cols].to_csv(os.path.join(RESULTS_DIR, f"{name}.csv"), index=False)


# ============================================================================
# PHASE: GATES (G1-G4)
# ============================================================================

def phase_gates():
    report = {}
    raw = load_1h("gates")                                           # G1 inside
    report["G1_csv_hash_matches_manifest"] = True

    candles = pd.read_csv(mml.CANDLES_CSV_PATH)
    candles["open_time"] = pd.to_datetime(candles["open_time"])
    a, b = bot.compute_indicators(candles), compute_indicators_scaled(candles, 1)
    report["G2_scaled_indicators_factor1_bit_identical"] = bool(a.equals(b))

    t0 = time.time()
    df, obs, trades = run_arm(raw, "literal")
    report["literal_full_series_runtime_s"] = round(time.time() - t0, 1)
    report["literal_order_blocks"] = len(obs)
    report["literal_trades_full_series"] = len(trades)
    cands = mml.build_candidates(df, obs, 0, len(df))
    cands = mml.label_candidates(df, obs, cands, len(df))
    ours = mml.run_sequential(cands, mml.rule_mask(cands))
    same = (len(ours) == len(trades)
            and (ours["i"].to_numpy() == trades["entry_idx"].to_numpy()).all()
            and (ours["exit_idx"].astype(int).to_numpy() == trades["exit_idx"].to_numpy()).all()
            and (ours["side"].to_numpy() == trades["side"].to_numpy()).all()
            and (ours["pnl_pct"].to_numpy(float) == trades["pnl_pct"].to_numpy(float)).all()
            and (ours["exit_reason"].to_numpy() == trades["exit_reason"].to_numpy()).all())
    report["G3_candidate_builder_reproduces_literal_trades"] = bool(same)
    report["G3_detail"] = {"engine_trades": len(trades), "rebuilt_trades": len(ours), "candidates": len(cands)}

    pre = raw[raw["open_time"] < MAIN_START].reset_index(drop=True)
    pre_df = bot.compute_indicators(pre)
    pre_obs = bot.compute_smc(pre_df)
    full_c = mml.build_candidates(pre_df, pre_obs, 0, len(pre_df))
    cols = ["i", "side", "ob_id", "entry", "stop_loss", "take_profit"] + [f"gate_{g}" for g in mml.GATES] + mml.FEATURE_COLUMNS
    rng = np.random.default_rng(PRIMARY_SEED)
    checks = []
    for cut in sorted(rng.integers(5000, len(pre_df) - 2000, size=3).tolist()):
        cut_df = bot.compute_indicators(pre.iloc[:cut].reset_index(drop=True))
        cut_c = mml.build_candidates(cut_df, bot.compute_smc(cut_df), 0, cut)
        ref = full_c[full_c["i"] < cut].reset_index(drop=True)
        checks.append({"cut_bar": cut, "cut_time": str(pre.at[cut, "open_time"]), "candidates_before_cut": len(ref),
                       "identical": bool(len(ref) == len(cut_c) and ref[cols].equals(cut_c[cols]))})
    report["G4_truncation_checks"] = checks
    report["G4_truncation_invariant"] = all(c["identical"] for c in checks)

    ok = all(report[k] for k in ("G1_csv_hash_matches_manifest", "G2_scaled_indicators_factor1_bit_identical",
                                 "G3_candidate_builder_reproduces_literal_trades", "G4_truncation_invariant"))
    report["all_gates_G1_to_G4_pass"] = ok
    _save("gates", report)
    print(json.dumps(report, indent=2, default=mml._json_default))
    print("GATES:", "PASS" if ok else "FAIL -- stop and report")
    return ok


# ============================================================================
# PHASE: MAIN (2022-2025)
# ============================================================================

def phase_main():
    with open(os.path.join(RESULTS_DIR, "gates.json"), encoding="utf-8") as f:
        if not json.load(f)["all_gates_G1_to_G4_pass"]:
            raise RuntimeError("gates did not pass -- refusing to run main")
    raw = load_1h("main")
    s, e = window_bounds(raw, MAIN_START, MAIN_END)
    window_df = raw.iloc[s:e].reset_index(drop=True)
    closes = raw["close"].to_numpy(float)

    arms = {}
    for arm in ("literal", "scaled"):
        t0 = time.time()
        df, obs, trades = run_arm(raw, arm)
        arms[arm] = {"df": df, "obs": obs, "trades": trades, "runtime_s": round(time.time() - t0, 1)}
        print(f"  {arm}: {len(obs)} OBs, {len(trades)} trades on full series, {arms[arm]['runtime_s']}s")

    main_trades = {arm: in_window(a["trades"], MAIN_START, MAIN_END) for arm, a in arms.items()}
    for arm, t in main_trades.items():
        _trades_csv(f"main_trades_{arm}", t)

    primary = {"endpoint": "LITERAL arm, 2022-2025, mean pnl/trade net of 0.20% > 0 (one-sided, stationary block "
                           "bootstrap B=10,000, alpha 0.05)",
               **primary_style_test(main_trades["literal"], PRIMARY_SEED)}
    s1 = primary_style_test(main_trades["scaled"], PRIMARY_SEED + 1)

    with open(os.path.join(BASE_DIR, "scratch", "fixtures", "baseline_trades.json"), encoding="utf-8") as f:
        four_h = pd.DataFrame(json.load(f))
    four_net = four_h["pnl_pct"].to_numpy(float) - FEE_PCT
    s2 = {"paper_4h": {"n": len(four_h), "trades_per_year": len(four_h) / 4.0, "mean_net_pnl_pct": float(four_net.mean())}}
    for k, arm in enumerate(("literal", "scaled")):
        net = main_trades[arm]["pnl_pct"].to_numpy(float) - FEE_PCT
        s2[arm] = {"n": len(net), "trades_per_year": len(net) / 4.0,
                   "net_mean_minus_4h": mml.diff_of_means_bootstrap(net, four_net, S2_BOOTSTRAP, PRIMARY_SEED + 10 + k)}

    # S3: random filter over the literal arm's 2022-2025 geometry-valid candidates.
    lit = arms["literal"]
    cands = mml.build_candidates(lit["df"], lit["obs"], s, e)
    cands = mml.label_candidates(lit["df"], lit["obs"], cands, len(lit["df"]))
    rule = mml.rule_mask(cands)
    rule_trades = mml.run_sequential(cands, rule)
    q = float(rule.mean())
    rng = np.random.default_rng(PRIMARY_SEED + 20)
    rand_means, rand_n = [], []
    for _ in range(S3_SEEDS):
        t = mml.run_sequential(cands, rng.random(len(cands)) < q)
        rand_n.append(len(t))
        rand_means.append(float(t["pnl_pct"].mean()) if len(t) else 0.0)
    all_trades = mml.run_sequential(cands, np.ones(len(cands), bool))
    rule_mean = float(rule_trades["pnl_pct"].mean()) if len(rule_trades) else 0.0
    s3 = {
        "candidates": len(cands), "rule_passing_candidates": int(rule.sum()), "take_rate_q": q,
        "rule_policy_on_window_candidates": {"n": len(rule_trades), "mean_pnl_pct": rule_mean},
        "take_every_candidate": {"n": len(all_trades), "mean_pnl_pct": float(all_trades["pnl_pct"].mean()),
                                 "total_net_pnl_pct": float((all_trades["pnl_pct"] - FEE_PCT).sum())},
        "random_filter": {"seeds": S3_SEEDS, "mean_n": float(np.mean(rand_n)),
                          "median_mean_pnl_pct": float(np.median(rand_means)),
                          "ci95_mean_pnl_pct": [float(np.percentile(rand_means, 2.5)), float(np.percentile(rand_means, 97.5))],
                          "share_seeds_mean_ge_rules": float(np.mean(np.array(rand_means) >= rule_mean))},
    }

    # S4: 50 random 12-month windows.
    rng = np.random.default_rng(PRIMARY_SEED + 30)
    starts = sorted(rng.integers(s, e - S4_WINDOW_BARS + 1, size=S4_WINDOWS).tolist())
    rows = []
    for ws in starts:
        we = ws + S4_WINDOW_BARS
        row = {"start_time": str(raw.at[ws, "open_time"]), "buy_hold_pct": (closes[we - 1] / closes[ws] - 1) * 100}
        for arm in ("literal", "scaled"):
            t = arms[arm]["trades"]
            inside = t[(t["entry_idx"] >= ws) & (t["entry_idx"] < we)]
            row[f"{arm}_n"] = len(inside)
            row[f"{arm}_net_total"] = float((inside["pnl_pct"] - FEE_PCT).sum())
        rows.append(row)
    s4_df = pd.DataFrame(rows)
    s4_df.to_csv(os.path.join(RESULTS_DIR, "main_s4_windows.csv"), index=False)
    s4 = {"windows": S4_WINDOWS, "window_bars": S4_WINDOW_BARS,
          "median_buy_hold_pct": float(s4_df["buy_hold_pct"].median())}
    for arm in ("literal", "scaled"):
        s4[arm] = {"share_net_total_gt_0": float((s4_df[f"{arm}_net_total"] > 0).mean()),
                   "share_beats_buy_hold": float((s4_df[f"{arm}_net_total"] > s4_df["buy_hold_pct"]).mean()),
                   "median_n": float(s4_df[f"{arm}_n"].median()),
                   "median_net_total": float(s4_df[f"{arm}_net_total"].median())}

    s5 = {arm: {f"{fee:.2f}": float((main_trades[arm]["pnl_pct"] - fee).sum()) for fee in FEE_LEVELS}
          for arm in ("literal", "scaled")}

    bh = bot._run_lump_sum_dollar_arm(window_df, 10000.0)
    bh_fee = bot._run_lump_sum_dollar_arm(window_df, 10000.0, drag_pct=bot.BENCHMARK_ONE_SIDE_DRAG_PCT)
    for b in (bh, bh_fee):
        b["sharpe"] = b["sharpe"] * SHARPE_RESCALE_1H
    s6 = {"buy_and_hold_gross": bh, "buy_and_hold_fee": bh_fee,
          "dca_gross": bot._run_dca_dollar_arm(window_df, 10000.0),
          "dca_fee": bot._run_dca_dollar_arm(window_df, 10000.0, drag_pct=bot.BENCHMARK_ONE_SIDE_DRAG_PCT)}
    s6 = {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, np.ndarray, pd.Series))} for k, v in s6.items()}

    windows = {"2022_2025": (MAIN_START, MAIN_END), "2018_2021": (raw["open_time"].iloc[0], MAIN_START),
               "2026_01_to_2026_08_07": (SEEN_2026_START, HOLDOUT_START)}
    per_window = {}
    for label, (ws_t, we_t) in windows.items():
        ws, we = window_bounds(raw, ws_t, we_t)
        per_window[label] = {arm: summarize_1h(in_window(arms[arm]["trades"], ws_t, we_t), raw, ws, we)
                             for arm in ("literal", "scaled")}

    report = {
        "phase": "main", "data_csv_sha256_prefix": "ec24028427a9029a",
        "runtime_s": {arm: arms[arm]["runtime_s"] for arm in arms},
        "order_blocks": {arm: len(arms[arm]["obs"]) for arm in arms},
        "sharpe_rescale_1h": SHARPE_RESCALE_1H,
        "primary_endpoint": primary, "S1_scaled": s1, "S2_vs_paper_4h": s2, "S3_random_filter": s3,
        "S4_random_12m_windows": s4, "S5_fee_levels_net_total_pct": s5, "S6_passive": s6,
        "S7_per_window": per_window,
    }
    _save("main", report)
    print(json.dumps({"primary": primary, "S1": s1}, indent=2, default=mml._json_default))
    return True


# ============================================================================
# PHASE: HOLDOUT (2026-08-08 onward, one shot) -- not run until approved
# ============================================================================

def phase_holdout(confirmed):
    if not confirmed:
        print("Refusing: the holdout is one-shot. Re-run with --i-understand-this-is-one-shot.")
        return False
    if os.path.exists(HOLDOUT_MARKER_PATH):
        print(f"Refusing: holdout already used ({os.path.relpath(HOLDOUT_MARKER_PATH, BASE_DIR)} exists).")
        return False
    if not os.path.exists(os.path.join(RESULTS_DIR, "main.json")):
        print("Refusing: main results must exist (and be committed) before the holdout.")
        return False
    with open(HOLDOUT_MARKER_PATH, "w", encoding="utf-8") as f:
        f.write(f"holdout opened {pd.Timestamp.now('UTC').isoformat()}\n")
    raw = load_1h("holdout")
    s, e = len(raw) - int((raw["open_time"] >= HOLDOUT_START).sum()), len(raw)
    closes = raw["close"].to_numpy(float)
    report = {"phase": "holdout", "window": f"{raw.at[s, 'open_time']} .. {raw.at[e - 1, 'open_time']} UTC",
              "bars": e - s, "buy_hold_pct": float((closes[e - 1] / closes[s] - 1) * 100), "arms": {}}
    for arm in ("literal", "scaled"):
        _, _, trades = run_arm(raw, arm)
        t = in_window(trades, HOLDOUT_START, pd.Timestamp.max)
        _trades_csv(f"holdout_trades_{arm}", t)
        report["arms"][arm] = summarize_1h(t, raw, s, e)
    _save("holdout", report)
    return True


# ============================================================================
# PHASE: REPORT
# ============================================================================

def _f(x, nd=2, signed=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _arm_line(label, a):
    d = a.get("dollar_net") or {}
    return (f"| {label} | {a['n']} | {_f(a.get('trades_per_year'), 1)} | {_f(a['win_rate_pct'], 1)} | "
            f"{_f(a['mean_pnl_pct'], 3, True)} | {_f(a['mean_net_pnl_pct'], 3, True)} | {_f(a['total_pnl_pct'], 2, True)} | "
            f"{_f(a['total_net_pnl_pct'], 2, True)} | {_f(d.get('sharpe'), 2)} | {_f(d.get('max_drawdown_pct'), 1)} | "
            f"{_f(a.get('mean_hold_bars_hours'), 1)} |")


ARM_HEADER = ("| Arm | Trades | Trades/yr | Win % | Mean gross % | Mean net % | Total gross % | Total net % | "
              "Sharpe (net) | Max DD % (net) | Mean hold (h) |\n|---|---|---|---|---|---|---|---|---|---|---|")


def phase_report():
    def load(name):
        p = os.path.join(RESULTS_DIR, f"{name}.json")
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

    gates, main, holdout = load("gates"), load("main"), load("holdout")
    pe, s1, s2, s3, s4 = (main[k] for k in ("primary_endpoint", "S1_scaled", "S2_vs_paper_4h", "S3_random_filter",
                                            "S4_random_12m_windows"))
    w22 = main["S7_per_window"]["2022_2025"]
    out = []
    w = out.append
    w("# Results: the locked rules on 1-hour candles\n")
    w("> Generated by `python experimental/rules_1h.py --phase report` from `experimental/results_1h/*.json`. "
      "Do not edit numbers by hand. Design: [PREREGISTRATION_1H.md](PREREGISTRATION_1H.md). Exploratory, and not part of the paper.\n")

    w("## Bottom line\n")
    verdict = "**met**" if pe["significant_at_0_05"] else "**not met**"
    w(f"- **Primary endpoint (literal rules, 2022–2025, mean pnl/trade after the 0.20% fee > 0):** {pe['n']} trades, "
      f"mean net **{_f(pe['mean_net_pnl_pct'], 3, True)}%** per trade. Block-bootstrap 95% CI of the mean "
      f"[{_f(pe['bootstrap']['mean_ci95'][0], 3, True)}, {_f(pe['bootstrap']['mean_ci95'][1], 3, True)}], one-sided p = "
      f"**{_f(pe['p_one_sided'], 4)}**. Endpoint {verdict} at α = 0.05."
      + (" Flagged: fewer than 10 trades." if pe["underpowered_lt_10_trades"] else ""))
    w(f"- **Trade count vs the paper:** literal 1h {s2['literal']['n']} trades ({_f(s2['literal']['trades_per_year'], 1)}/yr), "
      f"scaled 1h {s2['scaled']['n']} ({_f(s2['scaled']['trades_per_year'], 1)}/yr), against the paper's 4h "
      f"{s2['paper_4h']['n']} ({_f(s2['paper_4h']['trades_per_year'], 1)}/yr). Mean net per trade: literal "
      f"{_f(pe['mean_net_pnl_pct'], 3, True)}%, scaled {_f(s1['mean_net_pnl_pct'], 3, True)}%, 4h "
      f"{_f(s2['paper_4h']['mean_net_pnl_pct'], 3, True)}%.")
    w(f"- **Secondary, time-scaled ×4 arm:** {s1['n']} trades, mean net {_f(s1['mean_net_pnl_pct'], 3, True)}%, "
      f"descriptive one-sided p = {_f(s1['p_one_sided'], 4)}.")
    w(f"- **Stability over 50 random 12-month windows:** literal net total > 0 in {_f(s4['literal']['share_net_total_gt_0'] * 100, 0)}%, "
      f"scaled in {_f(s4['scaled']['share_net_total_gt_0'] * 100, 0)}%. Beating buy & hold: literal "
      f"{_f(s4['literal']['share_beats_buy_hold'] * 100, 0)}%, scaled {_f(s4['scaled']['share_beats_buy_hold'] * 100, 0)}%.")
    w(f"- **Do the gates add value on 1h?** {_f(s3['random_filter']['share_seeds_mean_ge_rules'] * 100, 1)}% of 1,000 random filters "
      f"at the same take-rate match or beat the rules' mean per trade.")
    w("- **Holdout (2026-08-08 onward):** " + ("opened. See the holdout section." if holdout else "**not opened**.") + "\n")

    w("## Gates\n")
    w(f"- G1, the data hash matches the manifest: **{gates['G1_csv_hash_matches_manifest']}**.")
    w(f"- G2, the scaled indicator code at factor 1 is bit-identical to `compute_indicators()`: **{gates['G2_scaled_indicators_factor1_bit_identical']}**.")
    g3 = gates["G3_detail"]
    w(f"- G3, the candidate builder reproduces the literal 1h trades: **{gates['G3_candidate_builder_reproduces_literal_trades']}** "
      f"({g3['rebuilt_trades']}/{g3['engine_trades']} trades over the full pre-holdout series, {g3['candidates']} candidates).")
    w(f"- G4, truncation invariance: **{gates['G4_truncation_invariant']}** "
      f"(cuts at {', '.join(c['cut_time'] for c in gates['G4_truncation_checks'])}).")
    w("- G5, `scratch/regression.py` passes and `research_analysis.py` has no diff vs `development`: checked at commit time "
      "(see the commit message).\n")

    w("## 2022–2025 (main window)\n")
    w(ARM_HEADER)
    w(_arm_line("Literal 1h (primary)", w22["literal"]))
    w(_arm_line("Time-scaled ×4 1h", w22["scaled"]))
    w(f"\nOrder Blocks detected over 2018 → 2026-08-07: literal {main['order_blocks']['literal']}, scaled "
      f"{main['order_blocks']['scaled']}. Sharpe values are annualised for 1h bars (the paper helpers' 4h Sharpe × "
      f"{_f(main['sharpe_rescale_1h'], 3)}). Max drawdown and totals are unaffected by that rescaling.\n")

    w("**Bootstrap of the net mean per trade (B = 10,000, stationary blocks)**\n")
    w("| Arm | n | Block len | Mean net 95% CI | P(mean ≤ 0) |\n|---|---|---|---|---|")
    for lab, r in (("Literal (primary)", pe), ("Scaled ×4", s1)):
        b = r["bootstrap"]
        if b is None:
            w(f"| {lab} | 0 | — | — | — |")
            continue
        w(f"| {lab} | {r['n']} | {b['expected_block_length']} | [{_f(b['mean_ci95'][0], 3, True)}, {_f(b['mean_ci95'][1], 3, True)}] | "
          f"{_f(r['p_one_sided'], 4)} |")

    w("\n**S2: versus the paper's 4h trades (net of 0.20%)**\n")
    w("| Arm | Trades | Trades/yr | 1h net mean − 4h net mean [95% CI] | p (two-sided) |\n|---|---|---|---|---|")
    w(f"| Paper 4h (reference) | {s2['paper_4h']['n']} | {_f(s2['paper_4h']['trades_per_year'], 2)} | — | — |")
    for arm, lab in (("literal", "Literal 1h"), ("scaled", "Scaled ×4 1h")):
        d = s2[arm]["net_mean_minus_4h"]
        ci = f"{_f(d['diff'], 3, True)} [{_f(d['ci95'][0], 2, True)}, {_f(d['ci95'][1], 2, True)}]" if d["ci95"] else "n/a"
        w(f"| {lab} | {s2[arm]['n']} | {_f(s2[arm]['trades_per_year'], 2)} | {ci} | {_f(d['p_two_sided'], 3)} |")

    w("\n**S3: do the four gates add value on 1h? (literal arm, 2022–2025 candidate stream)**\n")
    rf = s3["random_filter"]
    w(f"- {s3['candidates']} geometry-valid OB-touch candidates, {s3['rule_passing_candidates']} passing all four gates "
      f"(take-rate {_f(s3['take_rate_q'] * 100, 2)}%).")
    w(f"- The rules run on this candidate stream from a fresh start: {s3['rule_policy_on_window_candidates']['n']} trades, mean "
      f"{_f(s3['rule_policy_on_window_candidates']['mean_pnl_pct'], 3, True)}% gross.")
    w(f"- Random filter at the same take-rate, {rf['seeds']} seeds: about {_f(rf['mean_n'], 1)} trades per run, median mean "
      f"{_f(rf['median_mean_pnl_pct'], 3, True)}% (95% range [{_f(rf['ci95_mean_pnl_pct'][0], 2, True)}, "
      f"{_f(rf['ci95_mean_pnl_pct'][1], 2, True)}]). {_f(rf['share_seeds_mean_ge_rules'] * 100, 1)}% of seeds match or beat the rules.")
    te = s3["take_every_candidate"]
    w(f"- Taking every candidate: {te['n']} trades, mean {_f(te['mean_pnl_pct'], 3, True)}% gross, total "
      f"{_f(te['total_net_pnl_pct'], 1, True)}% after fees.")

    w("\n**S4: 50 random 12-month windows inside 2022–2025** (rows in `results_1h/main_s4_windows.csv`)\n")
    w("| Arm | Share net total > 0 | Share beating buy & hold | Median trades/window | Median net total % |\n|---|---|---|---|---|")
    for arm, lab in (("literal", "Literal"), ("scaled", "Scaled ×4")):
        r = s4[arm]
        w(f"| {lab} | {_f(r['share_net_total_gt_0'] * 100, 0)}% | {_f(r['share_beats_buy_hold'] * 100, 0)}% | "
          f"{_f(r['median_n'], 0)} | {_f(r['median_net_total'], 2, True)} |")
    w(f"\nMedian buy & hold over these windows: {_f(s4['median_buy_hold_pct'], 1, True)}%. The windows overlap heavily, "
      "so the shares describe stability across sub-periods; they are not probabilities.\n")

    w("**S5: total net pnl at other fee levels (2022–2025, sum of per-trade %)**\n")
    w("| Arm | 0.10% | 0.20% (primary) | 0.30% |\n|---|---|---|---|")
    for arm, lab in (("literal", "Literal"), ("scaled", "Scaled ×4")):
        r = main["S5_fee_levels_net_total_pct"][arm]
        w(f"| {lab} | {_f(r['0.10'], 2, True)} | {_f(r['0.20'], 2, True)} | {_f(r['0.30'], 2, True)} |")

    w("\n**S6: passive benchmarks, same window ($10,000, the paper's helpers)**\n")
    w("| Benchmark | Total % | Sharpe | Max DD % |\n|---|---|---|---|")
    for k, lab in (("buy_and_hold_gross", "Buy & hold (gross, Sharpe on 1h bars)"), ("buy_and_hold_fee", "Buy & hold (0.10%)"),
                   ("dca_gross", "Weekly DCA (gross, weekly Sharpe)"), ("dca_fee", "Weekly DCA (0.10%)")):
        b = main["S6_passive"][k]
        w(f"| {lab} | {_f(b['total_return_pct'], 2, True)} | {_f(b['sharpe'], 2)} | {_f(b['max_drawdown_pct'], 1)} |")

    w("\n## S7: other windows (descriptive)\n")
    for label, title in (("2018_2021", "2018–2021: the rules were formulated on this period at 4h, so it is not out-of-sample for them"),
                         ("2026_01_to_2026_08_07", "Jan 1 – Aug 7, 2026: already seen once at 4h (the spent lockbox)")):
        w(f"### {title}\n")
        w(ARM_HEADER)
        w(_arm_line("Literal 1h", main["S7_per_window"][label]["literal"]))
        w(_arm_line("Time-scaled ×4 1h", main["S7_per_window"][label]["scaled"]))
        w("")

    if holdout:
        w("## Holdout: 2026-08-08 onward (one shot)\n")
        w(f"Window {holdout['window']}, {holdout['bars']} bars. Buy & hold {_f(holdout['buy_hold_pct'], 2, True)}%.\n")
        w(ARM_HEADER)
        w(_arm_line("Literal 1h", holdout["arms"]["literal"]))
        w(_arm_line("Time-scaled ×4 1h", holdout["arms"]["scaled"]))
        w("")

    w("## Limitations\n")
    w("- Trades are assigned to a window by entry bar. A trade still open when a window ends is counted in full in that window's "
      "trade statistics, but the paper's dollar-equity helper only books exits inside the window.")
    w("- The scaled arm scales windows only. Pattern shapes (2-bar MACD rise, the 3-bar K-acceleration and its [1, 6] range, the "
      "bar-3 KDJ exit rule, OB quality windows) stay literal, so it is only partly the same strategy in clock time.")
    w("- There are 122 missing hours in the 1h feed, mostly 2018–2021 exchange outages. They are not filled, and the engine "
      "treats bars as consecutive, the same as the 4h data.")
    w("- This is a second look at the same 2022–2025 market the paper used. A positive result here would still share that "
      "period's regime; the holdout is the only data no version of the strategy has seen.")
    text = "\n".join(out) + "\n"
    with open(os.path.join(EXPERIMENT_DIR, "RESULTS_1H.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print("[saved] experimental/RESULTS_1H.md")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", required=True, choices=["gates", "main", "holdout", "report"])
    parser.add_argument("--i-understand-this-is-one-shot", action="store_true")
    args = parser.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    t0 = time.time()
    ok = {"gates": phase_gates, "main": phase_main, "report": phase_report,
          "holdout": lambda: phase_holdout(args.i_understand_this_is_one_shot)}[args.phase]()
    print(f"[{args.phase}] done in {time.time() - t0:.0f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
