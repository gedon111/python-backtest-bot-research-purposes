"""
Figures 7 and 8 of bitcoin (7), redrawn from committed results.

Figure 7: the three arms' dollar value, 2022-2026, gross of costs. The
strategy line is now marked to market (_mtm_strategy_equity()), so open
trades show their swings; every final value is unchanged.
Figure 8: Table 12 net of costs -- Sharpe and maximum drawdown at the UTC
daily close for the strategy sleeve and the cash-sleeve control, read from
artifacts/benchmark_mtm.json (run_benchmark_mark_to_market()).

Reads artifacts/candles.csv through research_analysis.py (read-only) and
artifacts/benchmark_mtm.json. Writes only docs/finalists/src-images/
fig07_equity_mtm.png, fig08_blend_cash.png and experimental/results/
fig07_fig08_points.json (the labelled numbers, for the consistency check).
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
sys.path.insert(0, BASE_DIR)

import research_analysis as ra  # noqa: E402

OUT_DIR = os.path.join(BASE_DIR, "docs", "finalists", "src-images")
POINTS_PATH = os.path.join(EXPERIMENT_DIR, "results", "fig07_fig08_points.json")
DPI = 200

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 11,
    "axes.edgecolor": "black", "savefig.facecolor": "white", "figure.facecolor": "white",
})


def money(v):
    return f"${v:,.2f}"


def figure_07(df, trades):
    close = df["close"].values
    t = df["open_time"].values
    n = len(df)
    strat = ra._mtm_strategy_equity(df, trades, 10000.0)
    weeks = ra._iso_week_first_bars(df)
    units, dca, week_set = 0.0, np.empty(n), set(weeks.tolist())
    for i in range(n):
        if i in week_set:
            units += 10000.0 / len(weeks) / close[i]
        dca[i] = units * close[i]
    last_week = int(weeks[-1])
    lump = 10000.0 / df["open"].iloc[0] * close

    finals = {"dca": ra._run_dca_dollar_arm(df, 10000.0)["final_capital"],
              "lump": ra._run_lump_sum_dollar_arm(df, 10000.0)["final_capital"],
              "strategy": ra._run_strategy_dollar_arm(df, trades, 10000.0)["final_capital"]}
    assert abs(dca[last_week] - finals["dca"]) < 1e-6
    assert abs(lump[-1] - finals["lump"]) < 1e-6 and abs(strat[-1] - finals["strategy"]) < 1e-6

    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.plot(t[:last_week + 1], dca[:last_week + 1], color="#111111", lw=1.6,
            label="Weekly dollar-cost averaging into Bitcoin")
    ax.plot(t, lump, color="#777777", lw=1.6, ls="--", label="Lump-sum buy-and-hold")
    ax.plot(t, strat, color="#111111", lw=1.4, ls=":", label="Combined strategy (marked to market)")
    ax.axhline(10000, color="#bbbbbb", lw=0.9)
    for idx, value in ((last_week, finals["dca"]), (n - 1, finals["lump"]), (n - 1, finals["strategy"])):
        ax.annotate(money(value), xy=(t[idx], value), xytext=(9, -4), textcoords="offset points",
                    ha="left", fontsize=11, annotation_clip=False)
    span = t[-1] - t[0]
    ax.set_xlim(t[0], t[-1] + span // 12)
    ax.set_ylabel("Portfolio value in dollars")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_ylim(0, 32000)
    ax.grid(axis="y", color="#dddddd", lw=0.7)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=11)
    fig.text(0.5, 0.02,
             "Lump sum and strategy invest \\$10,000 on 2022-01-01. Weekly buying invests the same \\$10,000 in 210 equal\n"
             "weekly parts, so its line starts near \\$0; it is drawn to its last contribution bar, where its value is measured.\n"
             "Gross of costs.",
             ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(left=0.10, right=0.97, top=0.96, bottom=0.23)
    fig.savefig(os.path.join(OUT_DIR, "fig07_equity_mtm.png"), dpi=DPI)
    plt.close(fig)
    return {k: round(v, 2) for k, v in finals.items()}


def figure_08(mtm):
    blend = mtm["main_window"]["blend_net"]
    shares = [0, 10, 20, 30]
    base = blend["baseline_100_0"]
    series = {
        "strategy": ([base["sharpe_daily_mtm"]] + [r["strategy_sleeve"]["sharpe_daily_mtm"] for r in blend["splits"]],
                     [base["max_drawdown_daily_pct"]] + [r["strategy_sleeve"]["max_drawdown_daily_pct"]
                                                         for r in blend["splits"]]),
        "cash": ([base["sharpe_daily_mtm"]] + [r["cash_sleeve"]["sharpe_daily_mtm"] for r in blend["splits"]],
                 [base["max_drawdown_daily_pct"]] + [r["cash_sleeve"]["max_drawdown_daily_pct"] for r in blend["splits"]]),
    }
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.4))
    for ax, k, title, fmt in ((axes[0], 0, "Annualized Sharpe ratio", "{:.3f}"),
                              (axes[1], 1, "Maximum drawdown", "−{:.2f}%")):
        sv, cv = series["strategy"][k], series["cash"][k]
        ax.plot(shares, sv, color="black", lw=1.6, marker="o", ms=7, mfc="white", label="Strategy sleeve")
        ax.plot(shares, cv, color="#777777", lw=1.4, ls="--", marker="s", ms=6, mfc="#777777",
                label="Cash sleeve (control, earns 0%)")
        for xi, v in zip(shares, sv):
            ax.annotate(fmt.format(abs(v)), xy=(xi, v), xytext=(9, -4) if xi == 0 else (-6, 9),
                        textcoords="offset points", ha="left" if xi == 0 else "right", fontsize=10)
        for xi, v in zip(shares[1:], cv[1:]):
            ax.annotate(fmt.format(abs(v)), xy=(xi, v), xytext=(7, -14), textcoords="offset points",
                        ha="left", fontsize=10, color="#555555")
        ax.set_title(title, fontsize=12, pad=12)
        ax.set_xticks(shares)
        ax.set_xticklabels([f"{s}%" for s in shares])
        ax.set_xlim(-6, 40)
        ax.set_xlabel("Share of weekly contributions\nmoved out of Bitcoin buying", fontsize=10.5)
        ax.grid(axis="y", color="#e5e5e5", lw=0.7)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylim(0.54, 0.64)
    axes[1].set_ylim(-38, -24)
    axes[0].legend(loc="upper left", frameon=False, fontsize=10)
    fig.text(0.5, 0.025,
             "Net of costs (0.20% per strategy trade, 0.10% per Bitcoin purchase). Valued at every daily close, open trades\n"
             "marked to market. At every share the strategy sleeve is above the cash sleeve on both measures. Descriptive only.",
             ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.90, bottom=0.27, wspace=0.28)
    fig.savefig(os.path.join(OUT_DIR, "fig08_blend_cash.png"), dpi=DPI)
    plt.close(fig)
    return {name: {"sharpe": [round(v, 3) for v in s], "max_drawdown": [round(v, 2) for v in d]}
            for name, (s, d) in series.items()}


def main():
    df = ra.load_candles()
    trades = ra.simulate_trades(ra.compute_indicators(df.copy()), min_ob_quality=0).attrs["trades_df"]
    assert len(trades) == 27
    with open(os.path.join(BASE_DIR, ra.BENCHMARK_MTM_JSON), encoding="utf-8") as f:
        mtm = json.load(f)
    blend = mtm["main_window"]["blend_net"]
    assert blend["h2_strategy_beats_cash_on_both_at_every_share"], "caption claims strategy > cash; it is not"
    points = {"figure_7_final_values": figure_07(df, trades), "figure_8_net": figure_08(mtm)}
    with open(POINTS_PATH, "w", encoding="utf-8") as f:
        json.dump(points, f, indent=2)
    print(json.dumps(points, indent=1))


if __name__ == "__main__":
    main()
