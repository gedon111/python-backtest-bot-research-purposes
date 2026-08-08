"""
Full trade-log + results-summary export, per window (2022-2026 locked
baseline, 2018-2022 formulation period) -- the data source behind the
Google Sheets "Trades ..." / "Results ..." tabs (src/Binance backtest
bot.py's push_trades_and_results_to_gsheet(), wired via
export_gui_data.py's push_trades_and_results()).

Read-only, additive analysis. Reuses load_bot()/load_main_window()/
load_formulation_window()/reconcile_formulation_window() imported directly
from analysis/benchmark_vs_passive.py -- that script already loads both
windows correctly and fully offline (artifacts/candles.csv +
artifacts/candles_extended.json); this script does not load candle data a
third way.

TRADES table: every column that exists in simulate_trades()'s own trades_df
(src/Binance backtest bot.py, the close_trade() closures inside the LONG and
SHORT branches -- 26 fields, identical schema for both sides), plus two
derived, lossless convenience columns (entry_time/exit_time, resolved from
entry_idx/exit_idx against that window's own candle open_time -- the same
resolution analysis/oos_validation_analysis.py already does). Nothing is
filtered, truncated, or summarized -- this is the complete per-trade record
the rest of the codebase actually operates on (every analysis/*.py script
reads this exact trades_df).

RESULTS table: trade_stats (Total Trades, Total Net Return %, Avg
Return/Trade %, Win Rate %) is minimal by itself, so this extends it with
the same additional figures every other results table in this repo already
reports (Wins, Losses, SD, one/two-sided binomial p), computed the same way
analysis/fee_slippage_analysis.py and analysis/oos_validation_analysis.py
already do (scipy.stats.binomtest). Deliberately NOT the full per-criterion
Fisher/Welch battery -- that already exists elsewhere (Stats/Solutions
tabs), and computing it fresh for the 2018-2022 window would be new,
unrequested analysis.

REPRODUCIBILITY: fully offline, same two committed artifacts
analysis/benchmark_vs_passive.py already validated. Deliberately NOT added
to scratch/regression.py for the same reason that script and
analysis/fee_slippage_analysis.py/analysis/ablation_reconstruction.py
aren't either -- that harness is narrowly scoped to the deterministic core
simulate_trades() pipeline against the frozen candles.csv snapshot only.
This script's own guard is load_main_window()'s assert len(trades) == 27
(inherited from benchmark_vs_passive.py) plus
reconcile_formulation_window()'s MATCH/DIVERGE check.

Usage (run from repo root):
    python analysis/export_trades_and_results.py
    python analysis/export_trades_and_results.py --json-out artifacts/export_trades_and_results.json
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats as sstats

from _json_utils import write_json
from benchmark_vs_passive import (
    FORMULATION_WINDOW_LABEL,
    MAIN_WINDOW_LABEL,
    load_bot,
    load_formulation_window,
    load_main_window,
    reconcile_formulation_window,
)

OUTPUT_COLUMNS = [
    "side", "entry_idx", "entry_time", "exit_idx", "exit_time",
    "entry", "exit", "stop_loss", "take_profit", "pnl_pct", "hold_bars", "exit_reason",
    "entry_ob_bar", "entry_ob_created_at", "entry_ob_type", "entry_ob_level", "entry_ob_quality",
    "entry_ob_quality_displacement", "entry_ob_quality_large_bar", "entry_ob_quality_fvg",
    "entry_ob_quality_liquidity_sweep", "entry_ob_quality_volume_expansion",
    "entry_ob_displacement_max_body_move", "entry_ob_displacement_threshold",
    "entry_ob_large_bar_range", "entry_ob_large_bar_threshold",
    "entry_ob_fvg_max_gap",
    "entry_ob_liquidity_sweep_ob_extreme", "entry_ob_liquidity_sweep_prior_10bar_extreme",
    "entry_ob_volume", "entry_ob_volume_avg_20bar", "entry_ob_volume_ratio", "entry_ob_body_ratio",
    "tp_is_structural", "tp_ob_bar", "tp_ob_created_at", "tp_ob_type", "tp_ob_level", "tp_ob_quality",
]


def compute_ob_criteria_diagnostics(df: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """Read-only reimplementation of the 5 orthogonal OB quality criteria's
    underlying NUMBERS (not just the boolean each one resolves to), faithful
    to the current src/Binance backtest bot.py compute_smc() source (the
    internal-pass block at lines ~292-392, byte-identical to the swing-pass
    block at ~444-517 -- verified identical before writing this). Does NOT
    call or modify compute_smc()/simulate_trades() -- reads only df's raw
    high/low/open/close/volume/ATR_200 columns plus each trade's already-
    computed entry_ob_bar (=ob_idx) / entry_ob_created_at (=i, the OB's own
    confirmation bar) / entry_ob_type, exactly mirroring compute_smc()'s own
    no-lookahead window bounds (post the disclosed Bug #3 fix). See
    verify_ob_criteria_diagnostics() below for the mandatory cross-check
    against the already-trusted, already-locked boolean columns."""
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values
    volumes = df["volume"].values
    atr200 = df["ATR_200"].values

    rows = []
    for _, tr in t.iterrows():
        ob_idx = int(tr["entry_ob_bar"])
        i = int(tr["entry_ob_created_at"])
        ob_type = tr["entry_ob_type"]

        # Displacement: max qualifying-direction |body| in (ob_idx, min(i, ob_idx+3)]
        threshold = 1.5 * float(atr200[ob_idx])
        max_body_move = 0.0
        for j in range(ob_idx + 1, min(i + 1, ob_idx + 4)):
            body = float(closes[j]) - float(opens[j])
            if ob_type == "DEMAND" and body > 0:
                max_body_move = max(max_body_move, abs(body))
            elif ob_type == "SUPPLY" and body < 0:
                max_body_move = max(max_body_move, abs(body))

        # LargeBar
        bar_range = float(highs[ob_idx]) - float(lows[ob_idx])
        large_bar_threshold = float(atr200[ob_idx])

        # FVG: max signed gap over [ob_idx, min(i-1, ob_idx+3)); None if the
        # window is empty (mirrors the original's range()-never-executes case)
        max_gap = None
        for j in range(ob_idx, min(i - 1, ob_idx + 3)):
            if ob_type == "DEMAND":
                gap = float(lows[j + 2]) - float(highs[j])
            else:
                gap = float(lows[j]) - float(highs[j + 2])
            max_gap = gap if max_gap is None else max(max_gap, gap)

        # LiquiditySweep
        prev_start = max(0, ob_idx - 10)
        if prev_start < ob_idx:
            if ob_type == "DEMAND":
                ob_extreme = float(lows[ob_idx])
                prior_extreme = float(lows[prev_start:ob_idx].min())
            else:
                ob_extreme = float(highs[ob_idx])
                prior_extreme = float(highs[prev_start:ob_idx].max())
        else:
            ob_extreme = float(lows[ob_idx]) if ob_type == "DEMAND" else float(highs[ob_idx])
            prior_extreme = None

        # VolumeExpansion
        vstart = max(0, ob_idx - 20)
        if ob_idx > 0:
            vol = float(volumes[ob_idx])
            avg_vol = float(volumes[vstart:ob_idx].mean())
        else:
            vol, avg_vol = float(volumes[ob_idx]), None
        body = abs(float(closes[ob_idx]) - float(opens[ob_idx]))
        rng = float(highs[ob_idx]) - float(lows[ob_idx])
        volume_ratio = (vol / avg_vol) if avg_vol else None
        body_ratio = (body / rng) if rng > 0 else None

        rows.append({
            "entry_ob_displacement_max_body_move": max_body_move,
            "entry_ob_displacement_threshold": threshold,
            "entry_ob_large_bar_range": bar_range,
            "entry_ob_large_bar_threshold": large_bar_threshold,
            "entry_ob_fvg_max_gap": max_gap,
            "entry_ob_liquidity_sweep_ob_extreme": ob_extreme,
            "entry_ob_liquidity_sweep_prior_10bar_extreme": prior_extreme,
            "entry_ob_volume": vol,
            "entry_ob_volume_avg_20bar": avg_vol,
            "entry_ob_volume_ratio": volume_ratio,
            "entry_ob_body_ratio": body_ratio,
        })
    return pd.DataFrame(rows, index=t.index)


def verify_ob_criteria_diagnostics(label: str, t: pd.DataFrame) -> bool:
    """Recomputes each of the 5 booleans from the numeric diagnostic columns
    compute_ob_criteria_diagnostics() just added, and diffs against the
    already-trusted entry_ob_quality_* columns already on t. Per CLAUDE.md:
    "If you find a THIRD bug, STOP and report it. Do not fix it silently" --
    this prints an explicit MATCH/DIVERGE verdict per criterion rather than
    assuming the reimplementation is correct."""
    checks = {
        "Displacement": t["entry_ob_displacement_max_body_move"] >= t["entry_ob_displacement_threshold"],
        "LargeBar": t["entry_ob_large_bar_range"] >= t["entry_ob_large_bar_threshold"],
        "FVG": t["entry_ob_fvg_max_gap"].apply(lambda v: v is not None and v > 0),
        "LiqSweep": pd.Series(
            [
                (row["entry_ob_liquidity_sweep_prior_10bar_extreme"] is not None) and (
                    row["entry_ob_liquidity_sweep_ob_extreme"] <= row["entry_ob_liquidity_sweep_prior_10bar_extreme"]
                    if row["entry_ob_type"] == "DEMAND" else
                    row["entry_ob_liquidity_sweep_ob_extreme"] >= row["entry_ob_liquidity_sweep_prior_10bar_extreme"]
                )
                for _, row in t.iterrows()
            ],
            index=t.index,
        ),
        "VolExpansion": pd.Series(
            [
                (row["entry_ob_volume_ratio"] is not None and row["entry_ob_volume_ratio"] >= 1.25)
                or (row["entry_ob_body_ratio"] is not None and row["entry_ob_body_ratio"] > 0.6)
                for _, row in t.iterrows()
            ],
            index=t.index,
        ),
    }
    stored = {
        "Displacement": t["entry_ob_quality_displacement"],
        "LargeBar": t["entry_ob_quality_large_bar"],
        "FVG": t["entry_ob_quality_fvg"],
        "LiqSweep": t["entry_ob_quality_liquidity_sweep"],
        "VolExpansion": t["entry_ob_quality_volume_expansion"],
    }
    print("=" * 100)
    print(f"  OB-CRITERIA DIAGNOSTIC CROSS-CHECK -- {label}")
    print("  Recomputed boolean (from the new numeric columns) vs. the already-trusted, already-locked value.")
    print("=" * 100)
    all_match = True
    total_checks = 0
    total_matches = 0
    for name, recomputed in checks.items():
        matches = (recomputed.astype(bool) == stored[name].astype(bool))
        n_match = int(matches.sum())
        n_total = len(matches)
        total_checks += n_total
        total_matches += n_match
        all_match = all_match and (n_match == n_total)
        print(f"  {name:<14} {n_match}/{n_total} match" + ("" if n_match == n_total else "  <-- DIVERGE, see rows below"))
        if n_match != n_total:
            for idx in matches[~matches].index:
                print(f"    entry_idx={int(t.loc[idx, 'entry_idx'])}: recomputed={bool(recomputed.loc[idx])} "
                      f"stored={bool(stored[name].loc[idx])}")
    print(f"\n  TOTAL: {total_matches}/{total_checks} boolean checks match. "
          f"{'ALL CLEAR -- diagnostics are faithful.' if all_match else 'DIVERGENCE FOUND -- STOP, see CLAUDE.md Known-bugs protocol before using these numbers.'}")
    print()
    return all_match


def trades_table(df: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.sort_values("entry_idx").reset_index(drop=True).copy()
    t["entry_time"] = df.loc[t["entry_idx"].astype(int), "open_time"].values
    t["exit_time"] = df.loc[t["exit_idx"].astype(int), "open_time"].values
    diagnostics = compute_ob_criteria_diagnostics(df, t)
    t = pd.concat([t, diagnostics], axis=1)
    t = t[OUTPUT_COLUMNS]
    # Non-structural-TP trades leave tp_ob_bar/tp_ob_quality/etc. as pandas
    # NaN (not None) once mixed into a float column -- NaN round-trips fine
    # through Python's own json.dump/json.load (non-standard but permissive),
    # but gspread's underlying request serialization enforces strict JSON and
    # rejects it outright ("Out of range float values are not JSON
    # compliant"). Normalize to None here, at the source, same pattern
    # src/Binance backtest bot.py's _format_df_for_export() already uses for
    # its own per-bar export.
    return t.astype(object).where(pd.notnull(t), None)


def results_table(trades: pd.DataFrame) -> dict:
    n = len(trades)
    wins = int((trades["pnl_pct"] > 0).sum())
    losses = n - wins
    win_rate = (wins / n * 100) if n else float("nan")
    total_return = trades["pnl_pct"].sum()
    avg_return = trades["pnl_pct"].mean()
    sd_return = trades["pnl_pct"].std(ddof=1) if n > 1 else float("nan")
    p_one = sstats.binomtest(wins, n, 0.5, alternative="greater").pvalue if n else float("nan")
    p_two = sstats.binomtest(wins, n, 0.5, alternative="two-sided").pvalue if n else float("nan")
    return {
        "Total Trades": n,
        "Wins": wins,
        "Losses": losses,
        "Win Rate (%)": win_rate,
        "Total Net Return (%)": total_return,
        "Avg Return/Trade (%)": avg_return,
        "SD (Return/Trade %)": sd_return,
        "Binomial p (one-sided)": p_one,
        "Binomial p (two-sided)": p_two,
    }


def print_trades(label: str, t: pd.DataFrame) -> None:
    print("=" * 100)
    print(f"  TRADES -- {label}  ({len(t)} trades, {len(t.columns)} columns)")
    print("=" * 100)
    with pd.option_context("display.max_columns", None, "display.width", 240, "display.max_rows", None):
        print(t.to_string(index=False))
    print()


def print_results(label: str, results: dict) -> None:
    print("=" * 100)
    print(f"  RESULTS -- {label}")
    print("=" * 100)
    for k, v in results.items():
        if isinstance(v, float):
            print(f"  {k:<26} {v:+.4f}")
        else:
            print(f"  {k:<26} {v}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write results as JSON (does not change printed output)")
    args = parser.parse_args()

    bot = load_bot()

    df_main, trades_main = load_main_window(bot)
    main_start, main_end = str(df_main["open_time"].iloc[0]), str(df_main["open_time"].iloc[-1])
    main_trades = trades_table(df_main, trades_main)
    main_diag_ok = verify_ob_criteria_diagnostics(MAIN_WINDOW_LABEL, main_trades)
    main_results = results_table(trades_main)
    print_trades(MAIN_WINDOW_LABEL, main_trades)
    print_results(MAIN_WINDOW_LABEL, main_results)

    df_form, trades_form = load_formulation_window(bot)
    form_start, form_end = str(df_form["open_time"].iloc[0]), str(df_form["open_time"].iloc[-1])
    reconcile_formulation_window(trades_form)
    form_trades = trades_table(df_form, trades_form)
    form_diag_ok = verify_ob_criteria_diagnostics(FORMULATION_WINDOW_LABEL, form_trades)
    form_results = results_table(trades_form)
    print_trades(FORMULATION_WINDOW_LABEL, form_trades)
    print_results(FORMULATION_WINDOW_LABEL, form_results)

    if not (main_diag_ok and form_diag_ok):
        print("!" * 100)
        print("  OB-CRITERIA DIAGNOSTIC CROSS-CHECK FAILED FOR AT LEAST ONE WINDOW.")
        print("  Per CLAUDE.md's Known-bugs protocol: STOP, do not treat the new numeric")
        print("  diagnostic columns above as trustworthy, and report this before proceeding.")
        print("!" * 100)

    if args.json_out:
        write_json({
            "main_window": {
                "label": MAIN_WINDOW_LABEL, "window_start": main_start, "window_end": main_end,
                "trades": main_trades.to_dict(orient="records"), "results": main_results,
            },
            "formulation_period_window": {
                "label": FORMULATION_WINDOW_LABEL, "window_start": form_start, "window_end": form_end,
                "trades": form_trades.to_dict(orient="records"), "results": form_results,
            },
        }, args.json_out)


if __name__ == "__main__":
    main()
