"""
Build all eight figures for the rebuilt HEDGE paper.

Offline only. Reads artifacts/candles.csv, artifacts/export_trades_and_results.json,
artifacts/fee_slippage_analysis.json and artifacts/benchmark_dca_analysis.json.
Imports research_analysis.py read-only for its ISO-week contribution schedule so
Figure 6's weekly arm uses the same bars the reported table used. Nothing here
writes to the repository outside docs/finalists/src-images/.

Every PNG is written at dpi=200 and is at least 1800 x 1000 pixels.

Run:  python scratch/paper/make_figures.py
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "docs", "finalists", "src-images")
ART = os.path.join(REPO, "artifacts")
DPI = 200

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11,
    "axes.edgecolor": "black",
    "savefig.facecolor": "white",
    "figure.facecolor": "white",
})

GREY = "#e4e4e4"
LINE = "black"


# ---------------------------------------------------------------- primitives

def new_canvas(w_in, h_in):
    fig = plt.figure(figsize=(w_in, h_in))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fill="white", bold_first=False, size=11,
        rounded=False, align="center"):
    style = "round,pad=0,rounding_size=1.2" if rounded else "square,pad=0"
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style,
                                linewidth=1.1, edgecolor=LINE, facecolor=fill))
    if align == "center":
        tx, ha = x + w / 2, "center"
    else:
        tx, ha = x + 1.5, "left"
    if bold_first:
        lines = text.split("\n")
        ax.text(tx, y + h - 4.0, lines[0], ha=ha, va="center",
                fontsize=size, fontweight="bold")
        ax.text(tx, y + h / 2 - 3.0, "\n".join(lines[1:]), ha=ha, va="center",
                fontsize=size)
    else:
        ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=size)


def arrow(ax, x1, y1, x2, y2, label=None, label_side="right"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=LINE, linewidth=1.1,
                                mutation_scale=12))
    if label:
        if abs(y2 - y1) < 0.01:            # horizontal: label sits above the line
            ax.text((x1 + x2) / 2, y1 + 1.1, label, fontsize=9.5,
                    style="italic", ha="center", va="bottom")
        else:                              # vertical: label sits beside the line
            ax.text(x1 + 1.1, (y1 + y2) / 2, label, fontsize=9.5,
                    style="italic", ha="left", va="center")


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    from PIL import Image
    with Image.open(path) as im:
        w, h = im.size
    assert w >= 1800 and h >= 1000, f"{name} is {w}x{h}, below the 1800x1000 floor"
    print(f"  wrote {name}  {w} x {h}")


# ------------------------------------------------------------------ figure 1

def figure_01():
    fig, ax = new_canvas(11, 5.6)
    y, h = 66, 12
    spans = [(6, 34, "Formulation period", GREY),
             (40, 34, "Primary reported window", "white"),
             (74, 20, "Forward test", "white")]
    for x, w, label, fill in spans:
        box(ax, x, y, w, h, label, fill=fill, size=13)
    ax.plot([6, 94], [y - 1.5, y - 1.5], color=LINE, lw=1.0)
    for tick, lab in [(6, "2018-01"), (40, "2022-01"), (74, "2026-01"), (94, "2026-07")]:
        ax.plot([tick, tick], [y - 4, y - 1.5], color=LINE, lw=1.0)
        ax.text(tick, y - 7, lab, ha="center", fontsize=11)
    ax.text(23, y + h + 3, "2018-01 to 2022-01", ha="center", fontsize=11.5)
    ax.text(57, y + h + 3, "2022-01 to 2026-01", ha="center", fontsize=11.5)
    ax.text(84, y - 13, "4 trades; code frozen beforehand", ha="center",
            fontsize=10.5, style="italic")

    arrow(ax, 23, y - 9, 23, 41)
    arrow(ax, 57, y - 9, 57, 41)
    box(ax, 6, 12, 34, 28,
        "Rules set by eye from charts, using\nprior trading experience.\n"
        "No sweep, no optimizer, and no\nparameter fitted to a measured\noutcome.\n"
        "N = 25 trades", rounded=True, size=11.5)
    box(ax, 40, 12, 34, 28,
        "Rules already frozen before this\nwindow was measured. Every\n"
        "headline result comes from here.\nCode was later audited using\n"
        "this window.\nN = 27 trades", rounded=True, size=11.5)
    save(fig, "fig01.png")


# ------------------------------------------------------------------ figure 2

def figure_02():
    fig, ax = new_canvas(12, 5.6)
    steps = [
        "Step 1\nBinance public\nprice endpoint\nBTC/USDT, 4-hour",
        "Step 2\nRead in\nbatches of\n1,000 candles",
        "Step 3\nConvert epoch\nmilliseconds\nto date and time",
        "Step 4\nShift every stamp\nby +8 hours\n(stored as UTC+8)",
        "Step 5\nTrim to\n2022-01-01 08:00 to\n2026-01-01 08:00",
    ]
    w, gap, y, h = 16.4, 3.0, 62, 26
    x0 = 3.0
    for k, s in enumerate(steps):
        x = x0 + k * (w + gap)
        box(ax, x, y, w, h, s, bold_first=True, size=10.5)
        if k < len(steps) - 1:
            arrow(ax, x + w + 0.4, y + h / 2, x + w + gap - 0.4, y + h / 2)
    mid = x0 + 2 * (w + gap) + w / 2
    arrow(ax, mid, y - 0.5, mid, 40.5)
    box(ax, 3.0, 14, 94, 26,
        "Verified dataset: 1,461 calendar days x 6 bars per day = 8,766 intervals,\n"
        "plus 1 closing row = 8,767 rows\n\n"
        "Gap check: every interval between consecutive candles equals exactly\n"
        "four hours, with no duplicate stamps, so no candle is missing",
        fill=GREY, size=11.5)
    save(fig, "fig02.png")


# ------------------------------------------------------------------ figure 3

def figure_03():
    fig, ax = new_canvas(11.5, 6.4)
    box(ax, 5, 87, 42, 10, "Pass 1: internal structure\n5-candle pivot lookback", size=11.5)
    box(ax, 53, 87, 42, 10, "Pass 2: swing structure\n50-candle pivot lookback", size=11.5)
    arrow(ax, 26, 86.5, 26, 79.5)
    arrow(ax, 74, 86.5, 74, 79.5)
    rows = [
        (67, 12, "Confirm a pivot using right-side candles only: the pivot high must exceed\n"
                 "every high that follows it up to the breakout candle.\n"
                 "No future candle is ever read in this comparison.", "white"),
        (54, 9, "Break of structure: price closes across the tracked pivot level", "white"),
        (39.5, 11, "Create the Order Block from the price segment between the pivot candle\n"
                   "and the candle whose close confirms the break", "white"),
        (22, 14.5, "Score five independent true-or-false criteria. Every forward search is\n"
                   "bounded at the Order Block's own confirmation candle.\n"
                   "Displacement · Large Origin Candle · Fair Value Gap · Liquidity Sweep · Volume Expansion",
         GREY),
        (7, 11, "Eligible for entry only strictly after the confirmation candle. Expires after\n"
                "500 candles, or once price closes back through the block boundary.", "white"),
    ]
    for y, h, text, fill in rows:
        box(ax, 5, y, 90, h, text, fill=fill, size=11)
    for top, bottom in [(67, 63), (54, 50.5), (39.5, 36.5), (22, 18)]:
        arrow(ax, 50, top - 0.4, 50, bottom)
    save(fig, "fig03.png")


# ------------------------------------------------------------------ figure 4

def figure_04():
    fig, ax = new_canvas(11.5, 7.2)
    box(ax, 15, 92.5, 55, 6, "A new 4-hour candle closes", fill=GREY, size=12)
    arrow(ax, 42.5, 92.0, 42.5, 89.6)
    conds = [
        "Price is interacting with an active, unmitigated demand\nOrder Block that meets the quality threshold",
        "MACD histogram is negative and rising for at least\ntwo consecutive candles",
        "Fixed-series K is below 50 and rising, with J below 60",
        "The rate of change of K falls inside its bounded\ntwo-candle window",
        "The ratio of ATR(14) to ATR(200) lies outside the rejected\nnarrow-volatility band",
        "Stop distance is at least 1.5% of entry price and\nreward-to-risk is at least 1.5",
    ]
    top, h, gap = 79.5, 9.8, 2.6
    for k, c in enumerate(conds):
        y = top - k * (h + gap)
        box(ax, 7, y, 6, h, str(k + 1), fill=GREY, size=12)
        box(ax, 15, y, 55, h, c, size=11)
        arrow(ax, 70.6, y + h / 2, 78.4, y + h / 2, "fails")
        if k < len(conds) - 1:
            arrow(ax, 10, y - 0.3, 10, y - gap + 0.3, "holds")
    last_y = top - 5 * (h + gap)          # 17.5
    arrow(ax, 42.5, last_y - 0.3, 42.5, last_y - 6.2)
    box(ax, 15, last_y - 14.5, 55, 8.2,
        "Open a long position, size the risk from ATR(14),\nand set the stop-loss and take-profit",
        fill=GREY, size=11)
    box(ax, 79, last_y - 14.5, 16, 98.5 - (last_y - 14.5),
        "No trade is\nopened on\nthis candle.\n\nEvery condition\nmust hold at\nthe same\ncandle close.", size=10.5)
    ax.text(50, 1.4,
            "Short entries mirror every condition against a supply Order Block, with K above 70 and J at or below 100.",
            ha="center", fontsize=10.5, style="italic")
    save(fig, "fig04.png")


# ------------------------------------------------------------------ figure 5

def figure_05():
    fig, ax = new_canvas(12, 5.8)
    rows = [
        ("Trailing exit", "50% giveback of peak profit, once that peak reaches 1.5%"),
        ("KDJ-reset exit", "adaptive post-entry series; cannot fire before the third candle"),
        ("ATR-move exit", "roughly 1.8 times the entry-candle ATR of favourable movement"),
        ("Breakeven-stop adjustment", "at 2.0 times ATR favourable; moves the stop, does not close it"),
        ("Hard stop-loss", "fixed loss boundary set at entry"),
        ("Hard take-profit", "fixed profit boundary set at entry"),
    ]
    top, h, gap = 84, 11, 2.6
    for k, (name, desc) in enumerate(rows):
        y = top - k * (h + gap)
        box(ax, 4, y, 6, h, str(k + 1), fill=GREY, size=12)
        ax.add_patch(FancyBboxPatch((12, y), 84, h, boxstyle="square,pad=0",
                                    linewidth=1.1, edgecolor=LINE, facecolor="white"))
        ax.text(14, y + h / 2, name, ha="left", va="center", fontsize=11.5,
                fontweight="bold")
        ax.text(44, y + h / 2, desc, ha="left", va="center", fontsize=11.5)
        if k < len(rows) - 1:
            arrow(ax, 7, y - 0.4, 7, y - gap - 0.2)
    ax.text(50, 3.0,
            "Checked in this order on every candle. The first condition satisfied triggers the exit;\n"
            "the remaining conditions are not evaluated for that candle.",
            ha="center", fontsize=10.5, style="italic")
    save(fig, "fig05.png")


# ------------------------------------------------------------------ figure 6

def figure_06():
    import research_analysis as ra

    df = pd.read_csv(os.path.join(ART, "candles.csv"))
    df["open_time"] = pd.to_datetime(df["open_time"])
    trades = pd.DataFrame(
        json.load(open(os.path.join(ART, "export_trades_and_results.json")))
        ["main_window"]["trades"])
    assert len(df) == 8767 and len(trades) == 27

    n = len(df)
    close = df["close"].values
    t = df["open_time"].values

    # Strategy arm: idle cash, compounding only at each exit bar.
    strat = np.full(n, 10000.0)
    running = 10000.0
    exits = dict(zip(trades["exit_idx"].astype(int), trades["pnl_pct"]))
    for i in range(1, n):
        if i in exits:
            running *= (1 + exits[i] / 100)
        strat[i] = running

    # Weekly arm: equal contribution on the first bar of each ISO week, at close.
    weeks = ra._iso_week_first_bars(df)
    contribution = 10000.0 / len(weeks)
    week_set = set(int(b) for b in weeks)
    units = 0.0
    dca = np.empty(n)
    for i in range(n):
        if i in week_set:
            units += contribution / close[i]
        dca[i] = units * close[i]
    last_contribution_bar = int(weeks[-1])

    # Lump-sum arm: full capital at the first bar's open, held to the last close.
    lump = (10000.0 / df["open"].iloc[0]) * close

    assert round(strat[-1], 2) == 13417.77, strat[-1]
    assert round(dca[last_contribution_bar], 2) == 22312.94, dca[last_contribution_bar]
    assert round(lump[-1], 2) == 19007.32, lump[-1]

    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.plot(t[:last_contribution_bar + 1], dca[:last_contribution_bar + 1],
            color="#111111", lw=1.6, label="Weekly dollar-cost averaging into Bitcoin")
    ax.plot(t, lump, color="#777777", lw=1.6, ls="--", label="Lump-sum buy-and-hold")
    ax.plot(t, strat, color="#111111", lw=1.6, ls=":", label="Order-Block-gated strategy")
    ax.axhline(10000, color="#bbbbbb", lw=0.9)

    for idx, value, label in [
            (last_contribution_bar, 22312.94, "$22,312.94"),
            (n - 1, 19007.32, "$19,007.32"),
            (n - 1, 13417.77, "$13,417.77")]:
        ax.annotate(label, xy=(t[idx], value), xytext=(9, -4),
                    textcoords="offset points", ha="left", fontsize=11,
                    annotation_clip=False)
    span = t[-1] - t[0]
    ax.set_xlim(t[0], t[-1] + span // 12)

    ax.set_ylabel("Portfolio value in dollars")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_ylim(0, 32000)
    ax.grid(axis="y", color="#dddddd", lw=0.7)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=11)
    ax.text(0.5, -0.16,
            "Each arm starts from $10,000 on 2022-01-01. The weekly arm is drawn to its final contribution bar,\n"
            "which is where its reported final value is measured. Gross of costs.",
            transform=ax.transAxes, ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(left=0.10, right=0.97, top=0.96, bottom=0.20)
    save(fig, "fig06.png")


# ------------------------------------------------------------------ figure 7

def figure_07():
    rows = json.load(open(os.path.join(ART, "fee_slippage_analysis.json")))
    rows = sorted(rows, key=lambda r: r["drag_pct"])
    labels = ["Gross\n0.00%", "Fee only\n0.10%", "Low band\n0.14%",
              "Primary\n0.20%", "Mid band\n0.24%", "High band\n0.40%"]
    win = [r["win_rate_pct"] for r in rows]
    pval = [r["binomial_p_one_sided"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1]})
    x = np.arange(6)
    ax1.bar(x, win, width=0.55, color="#dcdcdc", edgecolor="black", lw=1.0)
    ax1.axhline(50, color="black", lw=1.0, ls="--")
    ax1.text(-0.45, 51.5, "50% coin-flip line", ha="left", fontsize=10, style="italic")
    for xi, v in zip(x, win):
        ax1.text(xi, v + 1.2, f"{v:.2f}%", ha="center", fontsize=10.5)
    ax1.set_ylim(0, 85)
    ax1.set_ylabel("Win rate")
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))

    ax2.plot(x, pval, color="black", lw=1.5, marker="o", ms=6, mfc="white")
    ax2.axhline(0.05, color="black", lw=1.0, ls="--")
    ax2.text(5.45, 0.065, "0.05 significance threshold", ha="right", fontsize=10, style="italic")
    for xi, v in zip(x, pval):
        ax2.text(xi, v + 0.022, f"{v:.4f}", ha="center", fontsize=10.5)
    ax2.set_ylim(0, 0.42)
    ax2.set_ylabel("One-sided binomial p")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=10.5)
    ax2.set_xlabel("Round-trip transaction cost scenario")

    for ax in (ax1, ax2):
        ax.grid(axis="y", color="#e5e5e5", lw=0.7)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.text(0.5, 0.015,
             "Significance is lost from the low band onward, when two marginal trades cross from winners into losers.",
             ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(left=0.11, right=0.97, top=0.97, bottom=0.16, hspace=0.12)
    save(fig, "fig07.png")


# ------------------------------------------------------------------ figure 8

def figure_08():
    blend = json.load(open(os.path.join(ART, "benchmark_dca_analysis.json")))["section_2_dca_blend"]
    base = blend["splits"][0]["dca_only"]
    shares = [0, 10, 20, 30]
    sharpe = [base["sharpe"]] + [s["combined"]["sharpe"] for s in blend["splits"]]
    mdd = [base["max_drawdown_principal_inclusive_pct"]] + [
        s["combined"]["max_drawdown_principal_inclusive_pct"] for s in blend["splits"]]

    assert round(sharpe[0], 3) == 0.556 and round(sharpe[-1], 3) == 0.637
    assert round(mdd[0], 2) == -27.85 and round(mdd[-1], 2) == -23.18

    fig, axes = plt.subplots(1, 2, figsize=(9, 5.2))
    panels = [
        (axes[0], sharpe, "Annualized Sharpe ratio", "{:.3f}", (0.50, 0.70)),
        (axes[1], mdd, "Maximum drawdown", "−{:.2f}%", (-30, -20)),
    ]
    for ax, vals, title, fmt, ylim in panels:
        ax.plot(shares, vals, color="black", lw=1.6, marker="o", ms=7, mfc="white")
        for xi, v in zip(shares, vals):
            ax.annotate(fmt.format(abs(v) if v < 0 else v), xy=(xi, v),
                        xytext=(9, -13), textcoords="offset points",
                        ha="left", fontsize=10.5)
        ax.set_title(title, fontsize=12, pad=12)
        ax.set_xticks(shares)
        ax.set_xticklabels([f"{s}%" for s in shares])
        ax.set_xlim(-4, 41)
        ax.set_ylim(*ylim)
        ax.set_xlabel("Share of weekly contributions\nplaced in the strategy", fontsize=10.5)
        ax.grid(axis="y", color="#e5e5e5", lw=0.7)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.text(0.5, 0.025,
             "Both measures improve at every step from 0% to 30%. Drawdown improves by becoming shallower.\n"
             "Computed on 210 weekly contributions over 2022 to 2026. Descriptive only, with no p-value attached.",
             ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.90, bottom=0.28, wspace=0.30)
    save(fig, "fig08.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("building figures into", OUT)
    figure_01()
    figure_02()
    figure_03()
    figure_04()
    figure_05()
    figure_06()
    figure_07()
    figure_08()
    print("all eight figures built and size-checked")
