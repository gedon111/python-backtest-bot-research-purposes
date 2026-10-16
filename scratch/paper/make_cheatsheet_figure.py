"""
Build the one new figure for the defense cheat sheet: a headline-numbers-at-
a-glance stat-tile grid. Every value here is copied verbatim from Table 3,
the bootstrap-CI line, Table 9, and Table 12 of docs/finalists/HEDGE_Paper.md
(2022-2026 window, gross of costs unless stated) -- no new computation.

Styled to match make_figures.py's fig01-fig08 (Times New Roman, black
borders, #e4e4e4 grey fill, dpi 200) so it sits visually alongside them.

Offline only. Writes docs/finalists/src-images/fig09_headline_summary.png.

Run:  python scratch/paper/make_cheatsheet_figure.py
"""

import os
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "docs", "finalists", "src-images")
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


def new_canvas(w_in, h_in):
    fig = plt.figure(figsize=(w_in, h_in))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def tile(ax, x, y, w, h, headline, subtext, fill="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0",
                                 linewidth=1.1, edgecolor=LINE, facecolor=fill))
    cx = x + w / 2
    headline_wrapped = "\n".join(
        textwrap.fill(line, width=15) for line in headline.split("\n")
    )
    subtext_wrapped = "\n".join(
        textwrap.fill(line, width=24) for line in subtext.split("\n")
    )
    ax.text(cx, y + h * 0.64, headline_wrapped, ha="center", va="center",
            fontsize=12.5, fontweight="bold", linespacing=1.35)
    ax.text(cx, y + h * 0.24, subtext_wrapped, ha="center", va="center",
            fontsize=9, linespacing=1.3)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    with Image.open(path) as im:
        w, h = im.size
    assert w >= 1800 and h >= 1000, f"{name} is {w}x{h}, below the 1800x1000 floor"
    print(f"  wrote {name}  {w} x {h}")


def figure_09():
    fig, ax = new_canvas(11, 6.4)
    ax.text(50, 96, "HEDGE — Headline Numbers at a Glance",
            ha="center", fontsize=16, fontweight="bold")
    ax.text(50, 91, "2022-01 to 2026-01 window, gross of costs unless noted",
            ha="center", fontsize=10.5, style="italic")

    tiles = [
        ("27 trades, 70.37% win rate", "19 wins / 8 losses, Table 3"),
        ("+30.31% total net return", "+1.1225% average return per trade"),
        ("p = 0.0261 (one-sided)", "exact binomial test, 19/27 wins vs. p=0.5"),
        ("Bootstrap 95% CI\n[+5.99%, +54.99%]", "10,000 resamples, seed 42; excludes zero"),
        ("Strategy: $13,417.77", "Sharpe 1.114, from $10,000"),
        ("Weekly DCA: $22,312.94", "Sharpe 0.556, 100% time in market"),
        ("2.63% time in market", "vs. 100% for both DCA and lump-sum, Table 9"),
        ("Blended sleeve, 0%→30%\nSharpe 0.556 → 0.637", "MaxDD −27.85%→−23.18%"),
    ]
    cols, rows = 4, 2
    margin_x, margin_y = 4, 12
    gap = 2
    top = 84
    bottom = 8
    grid_w = 100 - 2 * margin_x
    grid_h = top - bottom
    w = (grid_w - (cols - 1) * gap) / cols
    h = (grid_h - (rows - 1) * gap) / rows
    for idx, (headline, subtext) in enumerate(tiles):
        r, c = divmod(idx, cols)
        x = margin_x + c * (w + gap)
        y = top - h - r * (h + gap)
        fill = GREY if (r + c) % 2 == 0 else "white"
        tile(ax, x, y, w, h, headline, subtext, fill=fill)

    save(fig, "fig09_headline_summary.png")


if __name__ == "__main__":
    figure_09()
