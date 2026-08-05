"""
Paper/codebase sync-check report.

Read-only, additive analysis: loads artifacts/candles.csv, runs the
UNMODIFIED src/Binance backtest bot.py strategy, and only reads from its
outputs. Never touches simulate_trades()/compute_smc(), never writes to
backtest_results.db, never changes a locked/reported headline number.

Recomputes every checkable figure fresh from data+code, then cross-checks
it against the exact wording of CLAUDE.md's "Locked results" section (the
in-repo source of truth). Ablation A/B figures are the one exception: no
committed script reproduces them (see STUDY_REFERENCE.md Sec.6.4/Sec.7), so
they are passed through from CLAUDE.md only, explicitly flagged as
unverified this run rather than silently re-derived.

If a live-recomputed figure disagrees with CLAUDE.md's locked figure, this
script prints a STOP banner and exits non-zero. It never edits CLAUDE.md or
"corrects" a mismatch itself -- per CLAUDE.md's own rule ("If you find a
THIRD bug, STOP and report it"), a genuine mismatch here is a correctness
finding for a human to review.

The actual paper draft lives outside this repo, so this script cannot diff
it directly. The "Paper draft checklist" section at the end of the report
is a static list of known paper-text staleness items, sourced from
CLAUDE.md's own "Known bugs" and "Open question" sections, for the user to
check against their draft by eye.

Usage (run from repo root):
    python analysis/paper_sync_report.py
    python analysis/paper_sync_report.py --out artifacts/paper_sync_report.md
"""
import argparse
import importlib.util
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats as sstats

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_MD_PATH = os.path.join(BASE_DIR, "CLAUDE.md")
CANDLES_PATH = os.path.join(BASE_DIR, "artifacts", "candles.csv")
DEFAULT_OUT_PATH = os.path.join(BASE_DIR, "artifacts", "paper_sync_report.md")

CRITERIA = {
    "Displacement": "entry_ob_quality_displacement",
    "LargeBar": "entry_ob_quality_large_bar",
    "FVG": "entry_ob_quality_fvg",
    "LiqSweep": "entry_ob_quality_liquidity_sweep",
    "VolExpansion": "entry_ob_quality_volume_expansion",
}

OB_QUALITY_FIELDS = {
    "Displacement": "quality_displacement",
    "LargeBar": "quality_large_bar",
    "FVG": "quality_fvg",
    "LiqSweep": "quality_liquidity_sweep",
    "VolExpansion": "quality_volume_expansion",
}


def load_bot():
    spec = importlib.util.spec_from_file_location(
        "bot", os.path.join(BASE_DIR, "src", "Binance backtest bot.py")
    )
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def load_candles():
    df = pd.read_csv(CANDLES_PATH)
    df["open_time"] = pd.to_datetime(df["open_time"])
    return df


# ---------------------------------------------------------------------------
# Live recomputation
# ---------------------------------------------------------------------------

def compute_bar_count(df):
    return {
        "n_bars": int(len(df)),
        "first_open_time": str(df["open_time"].iloc[0]),
        "last_open_time": str(df["open_time"].iloc[-1]),
    }


def compute_threshold_sweep(bot, base_df):
    rows = []
    for q in range(6):
        sim_df = bot.simulate_trades(base_df.copy(), min_ob_quality=q)
        trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
        n = len(trades_df)
        if n == 0:
            rows.append({"q": q, "n": 0})
            continue
        wins = int((trades_df["pnl_pct"] > 0).sum())
        losses = n - wins
        win_rate = wins / n * 100
        total_return = float(trades_df["pnl_pct"].sum())
        avg_return = float(trades_df["pnl_pct"].mean())
        sd = float(trades_df["pnl_pct"].std()) if n > 1 else float("nan")
        p_one = sstats.binomtest(wins, n, 0.5, alternative="greater").pvalue
        p_two = sstats.binomtest(wins, n, 0.5, alternative="two-sided").pvalue
        rows.append({
            "q": q, "n": n, "wins": wins, "losses": losses,
            "win_rate": win_rate, "total_return": total_return,
            "avg_return": avg_return, "sd": sd,
            "p_one_sided": p_one, "p_two_sided": p_two,
        })
    return rows


def compute_ob_population(obs):
    total = len(obs)
    counts = {name: sum(1 for ob in obs if ob.get(field)) for name, field in OB_QUALITY_FIELDS.items()}
    quality_dist = {q: 0 for q in range(6)}
    for ob in obs:
        quality_dist[int(ob.get("quality", 0))] += 1
    return {"total": total, "criteria_true_counts": counts, "quality_distribution": quality_dist}


def compute_criteria_tests(trades_df):
    results = {}
    for name, col in CRITERIA.items():
        true_pnl = trades_df.loc[trades_df[col] == True, "pnl_pct"]
        false_pnl = trades_df.loc[trades_df[col] == False, "pnl_pct"]
        true_n, false_n = len(true_pnl), len(false_pnl)
        true_wins = int((true_pnl > 0).sum())
        false_wins = int((false_pnl > 0).sum())
        table = [[true_wins, true_n - true_wins], [false_wins, false_n - false_wins]]
        _, fisher_p = sstats.fisher_exact(table)
        t_stat, welch_p = sstats.ttest_ind(true_pnl, false_pnl, equal_var=False)
        results[name] = {
            "true_n": true_n, "true_wins": true_wins,
            "false_n": false_n, "false_wins": false_wins,
            "fisher_p": float(fisher_p), "welch_t": float(t_stat), "welch_p": float(welch_p),
        }
    return results


# ---------------------------------------------------------------------------
# CLAUDE.md locked-figure parsing
# ---------------------------------------------------------------------------

def parse_claude_md():
    with open(CLAUDE_MD_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    locked = {}
    checks = [
        ("baseline_trades", r"Baseline \(min_ob_quality=0\):\s*(\d+)\s*trades", int),
        ("baseline_win_rate", r"(\d+\.\d+)%\s*win rate", float),
        ("baseline_total_return", r"\+(\d+\.\d+)%\s*total net\s*\n?\s*return", float),
        ("baseline_avg_return", r"\+(\d+\.\d+)%\s*avg return/trade", float),
        ("baseline_sd", r"SD\s*(\d+\.\d+)%", float),
        ("baseline_p_one_sided", r"One-sided binomial p\s*=\s*(\d+\.\d+)", float),
        ("baseline_p_two_sided", r"two-sided\s*(\d+\.\d+)\)\s*for the q>=0 baseline", float),
        ("total_obs", r"(\d+)\s*detected Order Blocks", int),
        ("fvg_true_count", r"FVG criterion true for\s*(\d+)\s*\(", int),
        ("fvg_true_pct", r"FVG criterion true for\s*\d+\s*\((\d+\.\d+)%\)", float),
        ("bar_count", r"(\d[\d,]*)\s*bars \(1,461 days", lambda s: int(s.replace(",", ""))),
    ]
    for key, pattern, cast in checks:
        m = re.search(pattern, text)
        locked[key] = cast(m.group(1)) if m else None

    qdist_m = re.search(
        r"OB quality distribution \(post-fix.*?\):\s*"
        r"q0=(\d+), q1=(\d+),\s*\n?\s*q2=(\d+), q3=(\d+), q4=(\d+), q5=(\d+)",
        text,
    )
    locked["quality_distribution"] = (
        {i: int(qdist_m.group(i + 1)) for i in range(6)} if qdist_m else None
    )

    ablation_a_m = re.search(
        r"Ablation A \(indicators-only, entry-ATR stop\):\s*(\d+) trades,\s*(\d+\.\d+)%,\s*(-?\d+\.\d+)%",
        text,
    )
    ablation_b_m = re.search(
        r"Ablation B \(indicators-only, swing-pivot stop\):\s*(\d+) trades,\s*(\d+\.\d+)%,\s*(-?\d+\.\d+)%",
        text,
    )
    locked["ablation_a"] = (
        {"n": int(ablation_a_m.group(1)), "win_rate": float(ablation_a_m.group(2)),
         "total_return": float(ablation_a_m.group(3))} if ablation_a_m else None
    )
    locked["ablation_b"] = (
        {"n": int(ablation_b_m.group(1)), "win_rate": float(ablation_b_m.group(2)),
         "total_return": float(ablation_b_m.group(3))} if ablation_b_m else None
    )
    return locked, text


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

class Check:
    def __init__(self, metric, locked_val, live_val, fmt=None, tol=None):
        self.metric = metric
        self.locked_val = locked_val
        self.live_val = live_val
        self.fmt = fmt or (lambda v: str(v))
        self.tol = tol

    @property
    def status(self):
        if self.locked_val is None:
            return "NO-PARSE"
        if self.live_val is None:
            return "NO-DATA"
        if self.tol is not None:
            ok = abs(float(self.locked_val) - float(self.live_val)) <= self.tol
        else:
            ok = self.locked_val == self.live_val
        return "MATCH" if ok else "MISMATCH"

    def row(self):
        locked_s = self.fmt(self.locked_val) if self.locked_val is not None else "(not found in CLAUDE.md)"
        live_s = self.fmt(self.live_val) if self.live_val is not None else "(not computed)"
        mark = {"MATCH": "MATCH", "MISMATCH": "MISMATCH -- STOP", "NO-PARSE": "NO-PARSE",
                "NO-DATA": "NO-DATA"}[self.status]
        return f"| {self.metric} | {locked_s} | {live_s} | {mark} |"


PAPER_CHECKLIST = """
## Paper draft checklist

The paper draft itself lives outside this repo, so these items were not
diffed automatically -- check each by eye against your current draft.
Sourced from `CLAUDE.md`'s "Known bugs" and "Open question" sections.

1. **Dataset size.** Draft should say **8,767 bars**, not 8,760. (1,461
   days incl. the 2024 leap day x 6 bars/day, plus one boundary-inclusive
   endpoint bar -- the original 8,760 figure was a plain arithmetic slip,
   since corrected in code and in `CLAUDE.md`.)
2. **FVG rate in the methodology/correction narrative (paper Section F).**
   If the draft's account of the FVG correction stops at "FVG registered
   true for 47.6%," it is describing the Bug #2 (three-candle definition)
   fix only. Bug #3 (the no-lookahead fix) subsequently corrected this
   further to **33.2% (253/761)**. Both the fix and its further correction
   should be disclosed if the draft mentions either.
3. **Welch's t-test p-value range (paper Results, orthogonal criteria).**
   `CLAUDE.md` says this should now read **"0.38-0.78"**, not "0.38-0.90."
   Only FVG's value moved under the Bug #3 fix (0.8956 -> 0.5996);
   LargeBar's 0.7751 is now the max. Note: "0.38" is Displacement's p-value
   (0.3775) even though the paper's own prose says the range covers only
   "the four adequately-sampled criteria" that were formally tested
   (Displacement excluded, n=4) -- see the live report's Welch section
   above for both framings side by side. Resolve this wording tension
   before finalizing the sentence.
4. **"190 total qualifying indicator signals."** `CLAUDE.md` marks this
   figure as an **open, unresolved question** -- it was derived under the
   indicators-only ablation's own 1.5x ATR entry-anchored stop, not the
   OB-gated strategy's risk rules, so the two populations are filtered
   differently. If the draft cites 190 as a settled denominator for the
   92.6% coincidence claim, that framing is not yet supported.
5. **Ablation A/B reproducibility (140-trade / 138-trade figures).** These
   match `CLAUDE.md` and are reported below, but no committed script in
   this repository currently reproduces them from scratch -- the
   originating script was never committed, and a reconstruction attempt
   diverges by >10 win-rate points from the published figures. This is a
   disclosed reproducibility gap, not a numeric error; see
   `STUDY_REFERENCE.md` Sec.6.4/Sec.7 if present, or flag it directly in
   the paper's limitations if not already covered.
""".strip()


def build_report(bar_info, sweep_rows, ob_pop, criteria_tests, locked, generated_at):
    checks = []
    q0 = next(r for r in sweep_rows if r["q"] == 0)

    checks.append(Check("Bar count", locked.get("bar_count"), bar_info["n_bars"]))
    checks.append(Check("Baseline (q>=0) trades", locked.get("baseline_trades"), q0.get("n")))
    checks.append(Check("Baseline win rate (%)", locked.get("baseline_win_rate"), q0.get("win_rate"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01))
    checks.append(Check("Baseline total net return (%)", locked.get("baseline_total_return"), q0.get("total_return"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01))
    checks.append(Check("Baseline avg return/trade (%)", locked.get("baseline_avg_return"), q0.get("avg_return"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01))
    checks.append(Check("Baseline SD (%)", locked.get("baseline_sd"), q0.get("sd"),
                         fmt=lambda v: f"{v:.2f}", tol=0.01))
    checks.append(Check("Baseline p (one-sided)", locked.get("baseline_p_one_sided"), q0.get("p_one_sided"),
                         fmt=lambda v: f"{v:.3f}", tol=0.001))
    checks.append(Check("Total detected Order Blocks", locked.get("total_obs"), ob_pop["total"]))
    checks.append(Check("FVG-true count", locked.get("fvg_true_count"), ob_pop["criteria_true_counts"]["FVG"]))
    fvg_pct_live = (ob_pop["criteria_true_counts"]["FVG"] / ob_pop["total"] * 100) if ob_pop["total"] else None
    checks.append(Check("FVG-true (%)", locked.get("fvg_true_pct"), fvg_pct_live,
                         fmt=lambda v: f"{v:.1f}", tol=0.05))
    qdist_locked = locked.get("quality_distribution") or {}
    for q in range(6):
        checks.append(Check(f"OB quality distribution q{q}", qdist_locked.get(q), ob_pop["quality_distribution"][q]))

    welch_ps_excl_displacement = [v["welch_p"] for k, v in criteria_tests.items() if k != "Displacement"]
    welch_range_excl = (
        (min(welch_ps_excl_displacement), max(welch_ps_excl_displacement))
        if welch_ps_excl_displacement else (None, None)
    )
    welch_ps_all5 = [v["welch_p"] for v in criteria_tests.values()]
    welch_range_all5 = (min(welch_ps_all5), max(welch_ps_all5)) if welch_ps_all5 else (None, None)

    lines = []
    lines.append("# Paper/codebase sync report")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("")
    lines.append(
        "Recomputed live from `artifacts/candles.csv` and the current "
        "`src/Binance backtest bot.py`, then cross-checked against the "
        "figures parsed out of `CLAUDE.md`'s \"Locked results\" section. "
        "A MISMATCH row is a correctness finding, not something this script "
        "resolves automatically -- see `CLAUDE.md`'s rule on newly found bugs."
    )
    lines.append("")
    lines.append("## Cross-check summary")
    lines.append("")
    lines.append("| Metric | Locked (CLAUDE.md) | Live (this run) | Status |")
    lines.append("|---|---|---|---|")
    for c in checks:
        lines.append(c.row())
    lines.append("")

    lines.append("## Full q0-q5 threshold sweep (live)")
    lines.append("")
    lines.append("| q | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (one-sided) | p (two-sided) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in sweep_rows:
        if r.get("n", 0) == 0:
            lines.append(f"| {r['q']} | 0 | - | - | - | - | - | - | - | - |")
            continue
        sd_s = f"{r['sd']:.2f}" if not np.isnan(r["sd"]) else "n/a (n=1)"
        lines.append(
            f"| {r['q']} | {r['n']} | {r['wins']} | {r['losses']} | {r['win_rate']:.2f}% | "
            f"{r['total_return']:+.2f}% | {r['avg_return']:+.4f}% | {sd_s} | "
            f"{r['p_one_sided']:.4f} | {r['p_two_sided']:.4f} |"
        )
    lines.append("")

    lines.append("## Per-criterion Fisher's exact + Welch's t-test (live, q>=0 baseline)")
    lines.append("")
    lines.append("| Criterion | True n (wins) | False n (wins) | Fisher p | Welch t | Welch p |")
    lines.append("|---|---|---|---|---|---|")
    for name in CRITERIA:
        r = criteria_tests[name]
        lines.append(
            f"| {name} | {r['true_n']} ({r['true_wins']}) | {r['false_n']} ({r['false_wins']}) | "
            f"{r['fisher_p']:.4f} | {r['welch_t']:+.4f} | {r['welch_p']:.4f} |"
        )
    lines.append("")
    if welch_range_all5[0] is not None:
        lines.append(
            f"Welch p-value range across **all 5** criteria "
            f"(the framing `CLAUDE.md`'s pending-correction note uses): "
            f"**{welch_range_all5[0]:.4f}-{welch_range_all5[1]:.4f}** "
            f"(rounds to \"0.38-0.78\"). This is the figure `CLAUDE.md` says the "
            f"paper's Results sentence should be updated to."
        )
        lines.append("")
        lines.append(
            f"Welch p-value range across the four adequately-sampled criteria "
            f"the paper's own prose says the range covers "
            f"(excludes Displacement, n=4, per the paper's stated methodology "
            f"of excluding it from significance testing): "
            f"**{welch_range_excl[0]:.4f}-{welch_range_excl[1]:.4f}** "
            f"(rounds to \"0.39-0.78\")."
        )
        lines.append("")
        lines.append(
            "**Note:** these two framings disagree at the low end (0.38 vs. 0.39) "
            "because `CLAUDE.md`'s range spans all 5 criteria's p-values (so "
            "Displacement's 0.3775 sets the floor) while the paper's prose says "
            "the range is \"across the four adequately-sampled criteria\" that "
            "were actually tested. This inconsistency predates this script and "
            "is not resolved here -- pick one framing and make the paper's "
            "prose and the reported range agree."
        )
    lines.append("")

    lines.append("## Ablation A/B -- passthrough from CLAUDE.md, UNVERIFIED this run")
    lines.append("")
    lines.append(
        "No committed script in this repository reproduces these figures from "
        "current code (see the paper draft checklist item #5 below). Printed "
        "here only as cited from `CLAUDE.md`, not independently recomputed."
    )
    lines.append("")
    a = locked.get("ablation_a")
    b = locked.get("ablation_b")
    lines.append("| Configuration | N | Win rate | Total return |")
    lines.append("|---|---|---|---|")
    if a:
        lines.append(f"| Indicators-only (entry-ATR stop) | {a['n']} | {a['win_rate']:.2f}% | {a['total_return']:+.2f}% |")
    if b:
        lines.append(f"| Indicators-only (swing-pivot stop) | {b['n']} | {b['win_rate']:.2f}% | {b['total_return']:+.2f}% |")
    lines.append("")

    lines.append(PAPER_CHECKLIST)
    lines.append("")

    mismatches = [c for c in checks if c.status == "MISMATCH"]
    return "\n".join(lines), mismatches, checks


def generate_report(bot=None, out_path=DEFAULT_OUT_PATH, verbose=True):
    """
    Recompute all figures live, cross-check against CLAUDE.md, write the
    markdown report to out_path, and return (report_text, mismatches, checks).

    Never calls sys.exit -- callers (the CLI below, or export_gui_data.py's
    pipeline) decide for themselves how loudly to react to `mismatches`.
    Pass an already-loaded `bot` module to avoid re-importing
    src/Binance backtest bot.py when the caller has it loaded already.
    """
    from datetime import datetime, timezone
    generated_at = datetime.now(timezone.utc).isoformat()

    def log(msg):
        if verbose:
            print(msg)

    log("[paper_sync_report] Loading candles and strategy module...")
    if bot is None:
        bot = load_bot()
    raw_df = load_candles()
    bar_info = compute_bar_count(raw_df)

    log("[paper_sync_report] Computing indicators and Order Blocks...")
    base_df = bot.compute_indicators(raw_df.copy())
    obs = bot.compute_smc(base_df)
    ob_pop = compute_ob_population(obs)

    log("[paper_sync_report] Running q0-q5 threshold sweep...")
    sweep_rows = compute_threshold_sweep(bot, base_df)

    log("[paper_sync_report] Running per-criterion Fisher/Welch tests on the q>=0 baseline...")
    q0_sim = bot.simulate_trades(base_df.copy(), min_ob_quality=0)
    q0_trades = q0_sim.attrs.get("trades_df", pd.DataFrame())
    criteria_tests = compute_criteria_tests(q0_trades)

    log("[paper_sync_report] Parsing CLAUDE.md locked results...")
    locked, _ = parse_claude_md()

    report, mismatches, checks = build_report(bar_info, sweep_rows, ob_pop, criteria_tests, locked, generated_at)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    log(f"[paper_sync_report] Wrote {out_path}")

    no_parse = [c for c in checks if c.status == "NO-PARSE"]
    if no_parse and verbose:
        print("[paper_sync_report] WARNING: could not parse the following figures out of "
              "CLAUDE.md (regex no longer matches its current wording):")
        for c in no_parse:
            print(f"  - {c.metric}")

    if mismatches and verbose:
        print("\n" + "=" * 70)
        print("[paper_sync_report] STOP: live-recomputed figures disagree with "
              "CLAUDE.md's locked results.")
        print("This is a correctness finding, not something to silently reconcile.")
        print("=" * 70)
        for c in mismatches:
            print(f"  - {c.metric}: locked={c.locked_val!r} live={c.live_val!r}")
    elif verbose:
        print("[paper_sync_report] All parsed CLAUDE.md figures match live recomputation.")

    return report, mismatches, checks


def main():
    parser = argparse.ArgumentParser(description="Generate the paper/codebase sync report.")
    parser.add_argument("--out", default=DEFAULT_OUT_PATH, help="Output markdown path.")
    args = parser.parse_args()

    _, mismatches, _ = generate_report(out_path=args.out)

    if mismatches:
        sys.exit(1)


if __name__ == "__main__":
    main()
