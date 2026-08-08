"""
Head-to-head benchmark: OB-gated strategy vs. weekly DCA into BTC vs.
lump-sum buy-and-hold, computed from the actual trade log(s) and the actual
BTCUSDT 4H price series -- not estimated, not modeled separately from the
rest of the pipeline.

Read-only, additive analysis. Reuses the UNMODIFIED src/Binance backtest
bot.py strategy (compute_indicators()/simulate_trades()) and the low-level
sharpe_sortino()/max_drawdown_pct() formulas already established in
analysis/benchmark_dca_analysis.py (imported from there, not reimplemented).
Never touches simulate_trades(), never writes to backtest_results.db or any
locked artifact.

This script builds its own capital-normalized, drag-parameterized equity
curves per arm rather than calling benchmark_dca_analysis.py's
section_1_benchmark()/section_2_dca_blend() directly: those return
100-indexed (not dollar-denominated) curves and have no transaction-cost
parameter, and adding one to that file in place would risk changing output
already cited verbatim in docs/results_section_addition_draft.md. The
per-arm equity-curve loops below are therefore adapted from, not identical
to, that file's Section 1/2 loops -- the ISO-week contribution-bar helper
(_iso_week_first_bars) intentionally duplicates that file's tiny grouping
idiom for the same reason, kept small so the two cannot silently drift.

TWO WINDOWS, computed and reported completely separately, never merged:
  - 2022-01-01 08:00:00 .. 2026-01-01 08:00:00 (the locked baseline window,
    artifacts/candles.csv, 8,767 bars).
  - 2018-01-01 08:00:00 .. 2022-01-01 04:00:00 ("formulation period" -- the
    period the strategy's rule STRUCTURE was originally tuned against,
    explicitly NOT out-of-sample, and NOT the same window as the existing
    2026 forward-OOS test in analysis/oos_validation_analysis.py). Sourced
    from artifacts/candles_extended.json records [0:8750] -- already
    committed, no live pull needed (see that file's own manifest,
    segment_bar_counts.prefix_pre_2022 = 8750). The resulting strategy-arm
    trade count/return/win-rate is cross-checked against the already-
    published figures in artifacts/oos_validation_analysis.json's
    section_2_backfill_audit.pre_window_not_oos block (N=25, 60.00% win
    rate, +21.82% total return, +0.87%/trade, p=0.2122) and an explicit
    MATCH/DIVERGE verdict is printed -- never silently trusted.

THREE ARMS, same total capital per window (--starting-capital, default
$10,000 -- a clean round number, not tied to any real position-sizing
model, since the strategy's own trades are pure percentage returns):
  Arm A -- OB-gated strategy. $10,000 notionally available; compounds only
    at each trade's exit bar by that trade's pnl_pct (capital sits idle
    between trades -- this is what "own capitalization" means for a
    non-overlapping trade-return series). Trade log is NOT recomputed for
    the main window -- it is the existing locked 27-trade baseline.
  Arm B -- Weekly DCA into BTC. $10,000 total, split evenly across every
    ISO calendar week in the window, bought at that week's first-bar CLOSE
    price -- reusing the exact contribution-timing convention
    analysis/benchmark_dca_analysis.py's Section 2 already established
    (not a second, conflicting DCA-timing convention).
  Arm C -- Lump-sum buy-and-hold. $10,000 deployed entirely at the
    window's very first bar's OPEN price -- a deliberately different
    anchor than Section 1's own BTC buy-and-hold row (which uses first-bar
    CLOSE, for a different existing purpose); flagged explicitly here.

GROSS vs. FEE-ADJUSTED: the locked baseline (+30.31%) is GROSS -- no fee or
slippage is modeled anywhere in simulate_trades() (confirmed: no fee/
slippage/commission term exists in that function; analysis/
fee_slippage_analysis.py applies drag only to an in-memory copy, post hoc,
and explicitly labels the currently-reported numbers its own "GROSS"
scenario). This script's PRIMARY tables are therefore gross, for a true
apples-to-apples comparison against Arm A's own published number. A
SEPARATE, clearly-labeled fee-adjusted table (main window only) reuses
analysis/fee_slippage_analysis.py's confirmed primary-scenario constants
(5bps/side taker + 5bps/side slippage): Arm A gets the standard 0.20%
round-trip drag per trade (matching that script's convention exactly);
Arms B/C -- which are held, not round-tripped, within the window -- get a
one-sided 0.10% (taker+slippage, one side only) effective-price markup
applied at each buy. This is an explicit, documented simplifying
assumption (not the round-trip figure, since there is no corresponding
sell inside the window for a buy-and-hold-style position).

REPRODUCIBILITY: fully offline (artifacts/candles.csv +
artifacts/candles_extended.json, both already committed -- no live Binance
pull). Deliberately NOT added to scratch/regression.py: that harness is
narrowly scoped to the deterministic core simulate_trades() pipeline
against the frozen candles.csv snapshot only (27-trade gross baseline,
indicator columns) -- it has zero coverage of Sharpe/Sortino/drawdown/
benchmark math anywhere, and analysis/fee_slippage_analysis.py and
analysis/ablation_reconstruction.py are excluded from it for the identical
reason. This script instead carries its own internal sanity guards: an
assert len(trades) == 27 for the main window, and the MATCH/DIVERGE
reconciliation described above for the formulation-period window.

Usage (run from repo root):
    python analysis/benchmark_vs_passive.py
    python analysis/benchmark_vs_passive.py --starting-capital 25000
    python analysis/benchmark_vs_passive.py --json-out artifacts/benchmark_vs_passive.json --csv-out-dir artifacts
"""
import argparse
import csv
import importlib.util
import json
import os

import numpy as np
import pandas as pd
from scipy import stats as sstats

from _json_utils import write_json
from benchmark_dca_analysis import (
    PERIODS_PER_YEAR_4H,
    PERIODS_PER_YEAR_WEEKLY,
    max_drawdown_pct,
    sharpe_sortino,
)

TAKER_FEE_BPS = 5.0   # matches analysis/fee_slippage_analysis.py's confirmed default
SLIPPAGE_BPS = 5.0    # matches analysis/fee_slippage_analysis.py's confirmed default
ROUND_TRIP_DRAG_PCT = 2 * TAKER_FEE_BPS * 0.01 + 2 * SLIPPAGE_BPS * 0.01   # 0.20%, strategy arm (round trip)
ONE_SIDE_DRAG_PCT = TAKER_FEE_BPS * 0.01 + SLIPPAGE_BPS * 0.01             # 0.10%, buy-and-hold-style arms (one side)

MAIN_WINDOW_LABEL = "locked baseline window"
FORMULATION_WINDOW_LABEL = "formulation period -- NOT out-of-sample, NOT the 2026 forward-OOS test"

FORMULATION_PREFIX_BARS = 8750  # artifacts/candles_extended_manifest.json: segment_bar_counts.prefix_pre_2022


def load_bot():
    spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def load_main_window(bot):
    df = pd.read_csv("artifacts/candles.csv")
    df["open_time"] = pd.to_datetime(df["open_time"])
    df = bot.compute_indicators(df)
    sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
    trades = sim.attrs.get("trades_df").copy()
    assert len(trades) == 27, f"expected 27 baseline trades on the locked window, got {len(trades)}"
    # Return sim (not the pre-simulation df) -- sim is a strict superset,
    # carrying Trade_Status/Entry_Price/Active_Supply/Active_Demand/etc.
    # columns simulate_trades() writes onto its own copy, needed by callers
    # that want the fully-populated per-bar frame (e.g. candle-level export).
    return sim, trades


def load_formulation_window(bot):
    with open("artifacts/candles_extended.json", encoding="utf-8") as f:
        records = json.load(f)
    prefix = records[:FORMULATION_PREFIX_BARS]
    df = pd.DataFrame(prefix)
    df["open_time"] = pd.to_datetime(df["open_time"])
    last_open_time = str(df["open_time"].iloc[-1])
    assert last_open_time == "2022-01-01 04:00:00", (
        f"expected the formulation-period slice to end at 2022-01-01 04:00:00 (one bar "
        f"before the locked window starts), got {last_open_time} -- "
        f"artifacts/candles_extended.json's segment boundaries may have changed; "
        f"do not proceed without checking artifacts/candles_extended_manifest.json"
    )
    df = bot.compute_indicators(df)
    sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
    trades = sim.attrs.get("trades_df").copy()
    return sim, trades  # see load_main_window()'s comment: sim is a strict superset of df


def reconcile_formulation_window(trades: pd.DataFrame):
    """Cross-checks this script's own formulation-period trade set against the
    already-published figures in artifacts/oos_validation_analysis.json
    (analysis/oos_validation_analysis.py --section 2's pre_window_not_oos
    block). Returns True (match), False (diverge), or None (no published
    figure to check against) -- never silently assumed."""
    print("=" * 100)
    print("  RECONCILIATION: formulation-period trade set vs. already-published figures")
    print("  (artifacts/oos_validation_analysis.json, section_2_backfill_audit.pre_window_not_oos)")
    print("=" * 100)
    path = "artifacts/oos_validation_analysis.json"
    if not os.path.isfile(path):
        print(f"  [SKIPPED] {path} not found -- cannot reconcile. Run "
              f"'python analysis/oos_validation_analysis.py --section 2' to produce it.\n")
        return None
    with open(path, encoding="utf-8") as f:
        published = json.load(f)["section_2_backfill_audit"]["pre_window_not_oos"]

    n = len(trades)
    wins = int((trades["pnl_pct"] > 0).sum())
    total_pnl = trades["pnl_pct"].sum()
    avg_pnl = trades["pnl_pct"].mean()
    binom_p = sstats.binomtest(wins, n, 0.5, alternative="greater").pvalue if n else float("nan")

    fields = [
        ("n", n, published.get("n")),
        ("wins", wins, published.get("wins")),
        ("win_rate_pct", (wins / n * 100) if n else float("nan"), published.get("win_rate_pct")),
        ("total_pnl_pct", total_pnl, published.get("total_pnl_pct")),
        ("avg_pnl_pct", avg_pnl, published.get("avg_pnl_pct")),
        ("binomial_p_one_sided", binom_p, published.get("binomial_p_one_sided")),
    ]
    all_match = True
    for name, live, pub in fields:
        if pub is None:
            print(f"  {name:<22} live={live!r:<24} published=<not present in artifact>  N/A -- "
                  f"regenerate with 'python analysis/oos_validation_analysis.py --section 2 "
                  f"--json-out artifacts/oos_validation_analysis.json' for a full check")
            continue
        match = abs(live - pub) < 1e-6
        all_match = all_match and match
        print(f"  {name:<22} live={live!r:<24} published={pub!r:<24} {'MATCH' if match else 'DIVERGE'}")
    print(f"\n  VERDICT: {'MATCH -- safe to proceed' if all_match else 'DIVERGE -- STOP, investigate before trusting the formulation-period arms below'}\n")
    return all_match


# ─────────────────────────────────────────────────────────────────────────
# Per-arm equity-curve builders (capital-normalized, drag-parameterized)
# ─────────────────────────────────────────────────────────────────────────

def strategy_arm(df: pd.DataFrame, trades: pd.DataFrame, starting_capital: float, drag_pct: float = 0.0) -> dict:
    n_bars = len(df)
    t = trades.copy()
    if drag_pct:
        t["pnl_pct"] = t["pnl_pct"] - drag_pct  # flat round-trip drag, matches fee_slippage_analysis.py's convention

    total_return_pct = t["pnl_pct"].sum()
    hold_bars_sum = t["hold_bars"].sum()
    time_in_market_pct = hold_bars_sum / n_bars * 100

    equity = np.full(n_bars, np.nan)
    equity[0] = starting_capital
    eq = starting_capital
    exit_map = dict(zip(t["exit_idx"].astype(int), t["pnl_pct"]))
    for i in range(1, n_bars):
        if i in exit_map:
            eq *= (1 + exit_map[i] / 100)
        equity[i] = eq
    equity = pd.Series(equity)
    bar_returns = equity.pct_change().dropna()
    sharpe, sortino = sharpe_sortino(bar_returns, PERIODS_PER_YEAR_4H)
    max_dd = max_drawdown_pct(equity)

    return {
        "arm": "OB-gated strategy",
        "total_return_pct": total_return_pct,
        # final_capital is the REAL final value of the compounded, sequential
        # equity curve above -- NOT back-derived from total_return_pct. The
        # two can differ very slightly: total_return_pct is an intentional
        # simple SUM of each trade's pnl_pct (matching the locked +30.31%
        # headline convention), while the equity curve compounds
        # multiplicatively trade-to-trade. Shown separately, not reconciled
        # away, so the divergence (if any) is visible rather than hidden.
        "final_capital": float(equity.iloc[-1]),
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": max_dd,
        "time_in_market_pct": time_in_market_pct,
        "starting_capital": starting_capital,
    }


def _iso_week_first_bars(df: pd.DataFrame) -> np.ndarray:
    """First bar index of every ISO calendar week in df -- the same grouping
    idiom as benchmark_dca_analysis.py's section_2_dca_blend(), intentionally
    duplicated in miniature (see module docstring) because that function has
    no drag parameter and this script needs one."""
    open_time = df["open_time"]
    week_key = open_time.dt.isocalendar().year.astype(str) + "-W" + open_time.dt.isocalendar().week.astype(str)
    bars = df.groupby(week_key).apply(lambda g: g.index.min()).sort_values().values
    return np.array(sorted(set(int(x) for x in bars)))


def dca_arm(df: pd.DataFrame, starting_capital: float, drag_pct: float = 0.0) -> dict:
    n_bars = len(df)
    close = df["close"].values
    contribution_bars = _iso_week_first_bars(df)
    n_weeks = len(contribution_bars)
    contribution = starting_capital / n_weeks
    contribution_set = set(contribution_bars.tolist())

    units = 0.0
    value = np.empty(n_bars)
    contrib_this_bar = np.zeros(n_bars)
    for i in range(n_bars):
        px = close[i]
        if i in contribution_set:
            buy_px = px * (1 + drag_pct / 100)  # one-sided fee+slippage markup on the effective buy price
            units += contribution / buy_px
            contrib_this_bar[i] = contribution
        value[i] = units * px

    idx = contribution_bars
    V = value[idx]
    C = contrib_this_bar[idx]
    r = np.empty(len(V) - 1)
    for k in range(1, len(V)):
        r[k - 1] = (V[k] - C[k]) / V[k - 1] - 1.0
    sharpe, sortino = sharpe_sortino(r, PERIODS_PER_YEAR_WEEKLY)
    max_dd = max_drawdown_pct(pd.Series(V))

    total_contributed = float(np.cumsum(C)[-1])
    final_value = float(V[-1])
    total_return_pct = (final_value - total_contributed) / total_contributed * 100

    return {
        "arm": "Weekly DCA into BTC",
        "total_return_pct": total_return_pct,
        "final_capital": final_value,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": max_dd,
        "time_in_market_pct": 100.0,
        "starting_capital": starting_capital,
        "n_contributions": int(n_weeks),
        "contribution_per_week": contribution,
    }


def lump_sum_arm(df: pd.DataFrame, starting_capital: float, drag_pct: float = 0.0) -> dict:
    open0 = df["open"].iloc[0] * (1 + drag_pct / 100)  # one-sided fee+slippage markup on the single buy
    units = starting_capital / open0
    equity = units * df["close"]
    total_return_pct = (equity.iloc[-1] - starting_capital) / starting_capital * 100
    bar_returns = equity.pct_change().dropna()
    sharpe, sortino = sharpe_sortino(bar_returns, PERIODS_PER_YEAR_4H)
    max_dd = max_drawdown_pct(equity)

    return {
        "arm": "Lump-sum buy-and-hold",
        "total_return_pct": total_return_pct,
        "final_capital": float(equity.iloc[-1]),
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": max_dd,
        "time_in_market_pct": 100.0,
        "starting_capital": starting_capital,
    }


# ─────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────

CSV_COLUMNS = ["Arm", "Total Return %", "Final Capital $", "Sharpe", "Sortino", "Max Drawdown %",
               "% Time In-Market", "Starting Capital", "Window Start", "Window End"]


def print_table(title: str, window_start, window_end, rows) -> None:
    print("=" * 100)
    print(f"  {title}")
    print(f"  Window: {window_start} .. {window_end}")
    print("=" * 100)
    print(f"{'Arm':<24} | {'Total Return %':>15} | {'Final Capital $':>16} | {'Sharpe':>8} | {'Sortino':>8} | "
          f"{'Max DD %':>10} | {'% In-Market':>12} | {'Capital':>12}")
    print("-" * 100)
    for row in rows:
        print(f"{row['arm']:<24} | {row['total_return_pct']:>+14.2f}% | ${row['final_capital']:>14,.2f} | "
              f"{row['sharpe']:>8.3f} | {row['sortino']:>8.3f} | {row['max_drawdown_pct']:>9.2f}% | "
              f"{row['time_in_market_pct']:>11.2f}% | ${row['starting_capital']:>10,.0f}")
    print()


def write_csv(rows, window_start, window_end, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([
                row["arm"], f"{row['total_return_pct']:.4f}", f"{row['final_capital']:.2f}",
                f"{row['sharpe']:.4f}", f"{row['sortino']:.4f}", f"{row['max_drawdown_pct']:.4f}",
                f"{row['time_in_market_pct']:.4f}", row["starting_capital"],
                window_start, window_end,
            ])
    print(f"[csv-out] wrote {path}")


def print_dca_bh_detail(rows, window_label: str) -> None:
    dca = next(r for r in rows if r["arm"] == "Weekly DCA into BTC")
    print(f"  [DCA detail, {window_label}] {dca['n_contributions']} weekly contributions of "
          f"${dca['contribution_per_week']:,.2f} each (total ${dca['starting_capital']:,.0f}), "
          f"bought at each ISO week's first-bar CLOSE price.")
    print(f"  [Lump-sum detail, {window_label}] ${rows[2]['starting_capital']:,.0f} bought entirely "
          f"at the window's first bar's OPEN price, held to the window's last bar's close.")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--starting-capital", type=float, default=10000.0,
                         help="Total capital committed per arm, per window (default: $10,000)")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write results as JSON (does not change printed output)")
    parser.add_argument("--csv-out-dir", type=str, default=None,
                         help="Optional directory to write one CSV per window "
                              "(benchmark_vs_passive_2022_2026.csv, benchmark_vs_passive_2018_2022.csv)")
    args = parser.parse_args()

    bot = load_bot()
    cap = args.starting_capital

    print("#" * 100)
    print("  HEAD-TO-HEAD BENCHMARK: OB-GATED STRATEGY vs. WEEKLY DCA vs. LUMP-SUM BUY-AND-HOLD")
    print(f"  Starting capital per arm, per window: ${cap:,.0f}")
    print("#" * 100)
    print()

    # ---- Main window (2022-2026, locked) ----
    df_main, trades_main = load_main_window(bot)
    main_start, main_end = df_main["open_time"].iloc[0], df_main["open_time"].iloc[-1]

    main_rows_gross = [
        strategy_arm(df_main, trades_main, cap),
        dca_arm(df_main, cap),
        lump_sum_arm(df_main, cap),
    ]
    print_table(f"MAIN WINDOW -- GROSS (no fees/slippage; matches the locked +30.31% headline convention) "
                f"-- {MAIN_WINDOW_LABEL}", main_start, main_end, main_rows_gross)
    print_dca_bh_detail(main_rows_gross, "main window, gross")

    main_rows_fee_adj = [
        strategy_arm(df_main, trades_main, cap, drag_pct=ROUND_TRIP_DRAG_PCT),
        dca_arm(df_main, cap, drag_pct=ONE_SIDE_DRAG_PCT),
        lump_sum_arm(df_main, cap, drag_pct=ONE_SIDE_DRAG_PCT),
    ]
    print_table(f"MAIN WINDOW -- FEE-ADJUSTED (strategy: {ROUND_TRIP_DRAG_PCT:.2f}% round-trip/trade; "
                f"DCA/B&H: {ONE_SIDE_DRAG_PCT:.2f}% one-sided buy markup) -- {MAIN_WINDOW_LABEL}",
                main_start, main_end, main_rows_fee_adj)

    # ---- Formulation-period window (2018-2022, NOT OOS) ----
    df_form, trades_form = load_formulation_window(bot)
    form_start, form_end = df_form["open_time"].iloc[0], df_form["open_time"].iloc[-1]
    reconcile_formulation_window(trades_form)

    form_rows_gross = [
        strategy_arm(df_form, trades_form, cap),
        dca_arm(df_form, cap),
        lump_sum_arm(df_form, cap),
    ]
    print_table(f"FORMULATION-PERIOD WINDOW -- GROSS -- {FORMULATION_WINDOW_LABEL}",
                form_start, form_end, form_rows_gross)
    print_dca_bh_detail(form_rows_gross, "formulation period, gross")

    if args.csv_out_dir:
        os.makedirs(args.csv_out_dir, exist_ok=True)
        write_csv(main_rows_gross, str(main_start), str(main_end),
                   os.path.join(args.csv_out_dir, "benchmark_vs_passive_2022_2026.csv"))
        write_csv(form_rows_gross, str(form_start), str(form_end),
                   os.path.join(args.csv_out_dir, "benchmark_vs_passive_2018_2022.csv"))

    if args.json_out:
        write_json({
            "starting_capital": cap,
            "fee_model": {
                "taker_fee_bps_per_side": TAKER_FEE_BPS, "slippage_bps_per_side": SLIPPAGE_BPS,
                "strategy_round_trip_drag_pct": ROUND_TRIP_DRAG_PCT,
                "buy_and_hold_style_one_side_drag_pct": ONE_SIDE_DRAG_PCT,
            },
            "main_window": {
                "label": MAIN_WINDOW_LABEL, "window_start": str(main_start), "window_end": str(main_end),
                "gross": main_rows_gross, "fee_adjusted": main_rows_fee_adj,
            },
            "formulation_period_window": {
                "label": FORMULATION_WINDOW_LABEL, "window_start": str(form_start), "window_end": str(form_end),
                "gross": form_rows_gross,
            },
        }, args.json_out)


if __name__ == "__main__":
    main()
