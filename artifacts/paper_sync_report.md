# Paper/codebase sync report

Generated: 2026-08-05T13:58:22.380762+00:00

Recomputed live from `artifacts/candles.csv` and the current `src/Binance backtest bot.py`, then cross-checked against the figures parsed out of `CLAUDE.md`'s "Locked results" section. A MISMATCH row is a correctness finding, not something this script resolves automatically -- see `CLAUDE.md`'s rule on newly found bugs.

## Cross-check summary

| Metric | Locked (CLAUDE.md) | Live (this run) | Status |
|---|---|---|---|
| Bar count | 8767 | 8767 | MATCH |
| Baseline (q>=0) trades | 27 | 27 | MATCH |
| Baseline win rate (%) | 70.37 | 70.37 | MATCH |
| Baseline total net return (%) | 30.31 | 30.31 | MATCH |
| Baseline avg return/trade (%) | 1.12 | 1.12 | MATCH |
| Baseline SD (%) | 2.41 | 2.41 | MATCH |
| Baseline p (one-sided) | 0.026 | 0.026 | MATCH |
| Total detected Order Blocks | 761 | 761 | MATCH |
| FVG-true count | 253 | 253 | MATCH |
| FVG-true (%) | 33.2 | 33.2 | MATCH |
| OB quality distribution q0 | 93 | 93 | MATCH |
| OB quality distribution q1 | 154 | 154 | MATCH |
| OB quality distribution q2 | 206 | 206 | MATCH |
| OB quality distribution q3 | 197 | 197 | MATCH |
| OB quality distribution q4 | 90 | 90 | MATCH |
| OB quality distribution q5 | 21 | 21 | MATCH |

## Full q0-q5 threshold sweep (live)

| q | N | Wins | Losses | Win rate | Total return | Avg/trade | SD | p (one-sided) | p (two-sided) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 27 | 19 | 8 | 70.37% | +30.31% | +1.1225% | 2.41 | 0.0261 | 0.0522 |
| 1 | 25 | 17 | 8 | 68.00% | +28.31% | +1.1323% | 2.51 | 0.0539 | 0.1078 |
| 2 | 23 | 15 | 8 | 65.22% | +23.28% | +1.0120% | 2.56 | 0.1050 | 0.2100 |
| 3 | 14 | 8 | 6 | 57.14% | +6.59% | +0.4709% | 2.76 | 0.3953 | 0.7905 |
| 4 | 6 | 3 | 3 | 50.00% | +6.71% | +1.1177% | 3.85 | 0.6562 | 1.0000 |
| 5 | 1 | 0 | 1 | 0.00% | -0.38% | -0.3809% | n/a (n=1) | 1.0000 | 1.0000 |

## Per-criterion Fisher's exact + Welch's t-test (live, q>=0 baseline)

| Criterion | True n (wins) | False n (wins) | Fisher p | Welch t | Welch p |
|---|---|---|---|---|---|
| Displacement | 4 (2) | 23 (17) | 0.5583 | -0.9277 | 0.3775 |
| LargeBar | 20 (14) | 7 (5) | 1.0000 | +0.2895 | 0.7751 |
| FVG | 11 (8) | 16 (11) | 1.0000 | +0.5360 | 0.5996 |
| LiqSweep | 15 (10) | 12 (9) | 0.6957 | -0.8195 | 0.4204 |
| VolExpansion | 15 (9) | 12 (10) | 0.2357 | -0.8835 | 0.3864 |

Welch p-value range across **all 5** criteria (the framing `CLAUDE.md`'s pending-correction note uses): **0.3775-0.7751** (rounds to "0.38-0.78"). This is the figure `CLAUDE.md` says the paper's Results sentence should be updated to.

Welch p-value range across the four adequately-sampled criteria the paper's own prose says the range covers (excludes Displacement, n=4, per the paper's stated methodology of excluding it from significance testing): **0.3864-0.7751** (rounds to "0.39-0.78").

**Note:** these two framings disagree at the low end (0.38 vs. 0.39) because `CLAUDE.md`'s range spans all 5 criteria's p-values (so Displacement's 0.3775 sets the floor) while the paper's prose says the range is "across the four adequately-sampled criteria" that were actually tested. This inconsistency predates this script and is not resolved here -- pick one framing and make the paper's prose and the reported range agree.

## Ablation A/B -- passthrough from CLAUDE.md, UNVERIFIED this run

No committed script in this repository reproduces these figures from current code (see the paper draft checklist item #5 below). Printed here only as cited from `CLAUDE.md`, not independently recomputed.

| Configuration | N | Win rate | Total return |
|---|---|---|---|
| Indicators-only (entry-ATR stop) | 140 | 60.00% | -14.63% |
| Indicators-only (swing-pivot stop) | 138 | 55.07% | -25.50% |

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
