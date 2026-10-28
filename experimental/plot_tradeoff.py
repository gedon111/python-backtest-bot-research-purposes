"""
Figure 11 of the regional paper revision (2026-10-28): trades per year (x)
against average net return per trade after the 0.20% round-trip cost (y),
for every 2022-2026 gate setting of Table 13, the 4h baseline, and both
1h versions of Table 15.

Reads committed results only (no recomputation of any trade):
  experimental/results/oos.json       rule_side_ablation["2022_2025"]
  experimental/results_1h/main.json   S2_vs_paper_4h, primary_endpoint, S1_scaled
Writes docs/finalists/src-images/fig11_tradeoff.png (300 dpi) and the
plotted points as experimental/results/fig11_points.json
for the paper's changelog.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(EXPERIMENT_DIR)
OOS_JSON = os.path.join(EXPERIMENT_DIR, "results", "oos.json")
MAIN_1H_JSON = os.path.join(EXPERIMENT_DIR, "results_1h", "main.json")
OUT_PNG = os.path.join(BASE_DIR, "docs", "finalists", "src-images", "fig11_tradeoff.png")
OUT_POINTS = os.path.join(EXPERIMENT_DIR, "results", "fig11_points.json")
YEARS = 4.0  # 2022-01-01 .. 2026-01-01

GATE_LABELS = {
    "B-LOO minus macd": "Remove MACD", "B-LOO minus kdj": "Remove KDJ",
    "B-LOO minus kacc": "Remove K-accel.", "B-LOO minus atr": "Remove ATR regime",
    "B-ONLY macd": "MACD only", "B-ONLY kdj": "KDJ only", "B-ONLY kacc": "K-accel. only",
    "B-ONLY atr": "ATR regime only", "B+Q quality>=1": "All four + OB quality ≥ 1",
}
GATE_COLOR = "#2a78d6"
ONE_HOUR_COLOR = "#eb6834"
INK = "#1f1f1e"
MUTED = "#6b6a63"


def collect_points():
    with open(OOS_JSON, encoding="utf-8") as f:
        block = json.load(f)["rule_side_ablation"]["2022_2025"]
    with open(MAIN_1H_JSON, encoding="utf-8") as f:
        one_hour = json.load(f)
    base = block["A0"]
    points = [{"group": "baseline", "label": "4-hour baseline (all four gates)", "n": base["n"],
               "trades_per_year": base["n"] / YEARS, "mean_net_pnl_pct": base["mean_net_pnl_pct"]}]
    for arm in block["arms"]:
        points.append({"group": "gate", "label": GATE_LABELS[arm["arm"]], "n": arm["n"],
                       "trades_per_year": arm["n"] / YEARS, "mean_net_pnl_pct": arm["mean_net_pnl_pct"]})
    s2 = one_hour["S2_vs_paper_4h"]
    points.append({"group": "1h", "label": "1-hour literal", "n": s2["literal"]["n"],
                   "trades_per_year": s2["literal"]["trades_per_year"],
                   "mean_net_pnl_pct": one_hour["primary_endpoint"]["mean_net_pnl_pct"]})
    points.append({"group": "1h", "label": "1-hour time-scaled ×4", "n": s2["scaled"]["n"],
                   "trades_per_year": s2["scaled"]["trades_per_year"],
                   "mean_net_pnl_pct": one_hour["S1_scaled"]["mean_net_pnl_pct"]})
    assert abs(points[0]["trades_per_year"] - s2["paper_4h"]["trades_per_year"]) < 1e-12
    return points


# Label offsets in points, hand-placed so no label overlaps a marker or another label.
OFFSETS = {
    "4-hour baseline (all four gates)": (8, 6, "left"),
    "All four + OB quality ≥ 1": (-4, -16, "left"),
    "Remove ATR regime": (8, 2, "left"),
    "Remove K-accel.": (8, 2, "left"),
    "Remove KDJ": (8, 2, "left"),
    "Remove MACD": (8, 2, "left"),
    "MACD only": (-8, -3, "right"),
    "KDJ only": (8, -10, "left"),
    "K-accel. only": (8, 2, "left"),
    "ATR regime only": (-8, 6, "right"),
    "1-hour literal": (8, -10, "left"),
    "1-hour time-scaled ×4": (8, -10, "left"),
}


def main():
    points = collect_points()
    plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10})
    fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=300)
    ax.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    for p in points:
        if p["group"] == "baseline":
            ax.scatter(p["trades_per_year"], p["mean_net_pnl_pct"], s=220, marker="*", color=INK,
                       edgecolor="white", linewidth=1.2, zorder=4)
        elif p["group"] == "gate":
            ax.scatter(p["trades_per_year"], p["mean_net_pnl_pct"], s=36, marker="o", color=GATE_COLOR,
                       edgecolor="white", linewidth=1.0, zorder=3)
        else:
            ax.scatter(p["trades_per_year"], p["mean_net_pnl_pct"], s=40, marker="s", color=ONE_HOUR_COLOR,
                       edgecolor="white", linewidth=1.0, zorder=3)
        dx, dy, ha = OFFSETS[p["label"]]
        ax.annotate(f"{p['label']} ({p['n']})", (p["trades_per_year"], p["mean_net_pnl_pct"]),
                    xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=7.5, color=INK)
    ax.set_xscale("log")
    ax.set_xticks([2, 5, 10, 20, 50, 100])
    ax.set_xticklabels(["2", "5", "10", "20", "50", "100"])
    ax.set_xlim(2.5, 140)
    ax.set_ylim(-0.45, 1.15)
    ax.set_xlabel("Trades per year (log scale), 2022 to 2026")
    ax.set_ylabel("Average net return per trade (%),\nafter 0.20% round-trip cost")
    ax.grid(True, which="major", color="#e4e3dd", linewidth=0.5, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=9)
    handles = [
        plt.Line2D([], [], marker="*", linestyle="", color=INK, markersize=10, label="4-hour baseline"),
        plt.Line2D([], [], marker="o", linestyle="", color=GATE_COLOR, markersize=6, label="4-hour gate setting"),
        plt.Line2D([], [], marker="s", linestyle="", color=ONE_HOUR_COLOR, markersize=6, label="1-hour version"),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=300, facecolor="white")
    with open(OUT_POINTS, "w", encoding="utf-8") as f:
        json.dump(points, f, indent=2)
    for p in points:
        print(f"{p['label']:<34} n={p['n']:>4}  tpy={p['trades_per_year']:6.2f}  net/trade={p['mean_net_pnl_pct']:+.3f}%")


if __name__ == "__main__":
    main()
