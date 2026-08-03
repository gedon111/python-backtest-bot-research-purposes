# Project context

Research codebase for an ISEF science-fair paper. Backtests a rule-based
BTC/USDT strategy (MACD + KDJ + ATR + SMC Order Blocks) on 4h candles,
Jan 2022 - Jan 2026. This is a scientific artifact, not a production system.
Correctness and auditability outrank performance, elegance, and convenience.

## Locked results - must not change

These numbers appear in the paper. Any code change that alters them is a bug in
the change, not an improvement:

- Baseline (min_ob_quality=0): 27 trades, 70.37% win rate, +30.31% total net
  return, +1.12% avg return/trade, SD 2.41%
- One-sided binomial p = 0.026 (two-sided 0.052) for the q>=0 baseline.
- q>=1 one-sided binomial p: 0.038 (n=26, pre-fix) -> 0.054 (n=25,
  post-fix as of commit 7ad6caa). This is a SIGNIFICANCE-CONCLUSION FLIP
  (marginally significant -> not significant at alpha=0.05), not a modest
  revision - driven by a single trade (entry_idx=3100) losing its only
  quality point (FVG) under the corrected no-lookahead computation. See
  Known bugs #3. Consistent with the Limitations section's existing
  small-sample caveat about q>=1's thin N.
- 761 detected Order Blocks; FVG criterion true for 253 (33.2%) as of
  commit 7ad6caa (was 362 / 47.6% pre-fix; corrected, see Known bugs #3).
- OB quality distribution (post-fix, commit 7ad6caa): q0=93, q1=154,
  q2=206, q3=197, q4=90, q5=21 (was q0=77, q1=147, q2=200, q3=192, q4=112,
  q5=33 pre-fix; corrected, see Known bugs #3).
- Ablation A (indicators-only, entry-ATR stop): 140 trades, 60.00%, -14.63%
- Ablation B (indicators-only, swing-pivot stop): 138 trades, 55.07%, -25.50%
- Dataset: artifacts/candles.csv, 8,767 bars (1,461 days incl. 2024 leap day
  x 6 bars/day, plus one boundary-inclusive endpoint bar). NOT 8,760 - the
  paper's original figure was arithmetic, since corrected. Do not trim bars.

## Regression harness

scratch/regression.py is the golden master; fixtures in scratch/fixtures/.
Run it after EVERY change. Any diff = revert the change.
It aligns trades by entry_idx and names the first divergent trade.
--generate regenerates fixtures. Never run it without asking first.

## Known bugs - already found, corrected, and DISCLOSED in the paper

Do not "fix" anything that looks related to these without asking. Apparent
oddities nearby may be intentional:

1. The composite 0-5 quality score was non-orthogonal (higher-scored sets were
   nested subsets of lower-scored ones). Replaced by independent per-criterion
   evaluation. The score field still exists and is still computed; it is no
   longer used as an ordinal threshold for analysis.
2. FVG used an adjacent-candle test (lows[j+1] > highs[j]) instead of the
   three-candle definition (lows[j+2] > highs[j]). Corrected.
3. FVG and displacement quality criteria could read 1-2 bars past an Order
   Block's own confirmation bar - the forward-search loop was bounded by
   dataset length, not by the confirmation bar. Found via the no-lookahead
   audit; fixed by freezing the search window at the confirmation bar.
   Affects 110/761 OBs' quality scores (FVG true: 362->253, 47.6%->33.2%;
   displacement true: 112->107). Does not change the 27-trade q>=0 baseline
   (unaffected by quality filtering) but drops q>=1 from 26->25 trades,
   flipping its one-sided binomial significance (0.038->0.054). Corrected
   as of commit 7ad6caa. Distinct in kind from bugs #1-2 above (those were
   definitional corrections; this was data leakage across the confirmation
   boundary). Pending: the paper's Results narrative sentence reporting the
   Welch's t-test p-value range across all 5 orthogonal criteria (currently
   "0.38-0.90" pre-fix) should become "0.38-0.78" post-fix (only FVG's
   value moved, from 0.8956 to 0.5996; LargeBar's 0.7751 is now the max).
   The paper itself has not been touched by this correction pass.

If you find a THIRD bug, STOP and report it. Do not fix it silently. A newly
discovered error changes what the paper claims, so I need to see it first.

## Open question - do not assume resolved

The paper reports "190 total qualifying indicator signals" as the denominator
for the claim that 25 of 27 OB-gated trades (92.6%) coincided with independent
indicator signals. That 190 was derived using the indicators-only ablation's
1.5*ATR entry-anchored stop, NOT the OB-gated strategy's own risk rules. The
two populations are filtered differently. This is unresolved. Do not cite 190
as settled.

## Rules

- No strategy logic, threshold, or formula changes. Refactoring only.
- Parameters are fixed and pre-registered. Never sweep, tune, or optimize them.
- Keep the JS verification dashboard's recalculation INDEPENDENT of the Python
  side. It is an intentional cross-check. Never make it import from Python.
- All scratch scripts run offline from artifacts/candles.csv. No live API calls.
- Report null and unfavorable results as they come. Do not soften them.
- No-lookahead enforcement is a SEPARATE final step, not part of general
  refactoring. If the harness fails after it, do not revert and do not weaken
  the assertion - stop and report the bar, value, and computation that reached
  forward. That would be a correctness finding, not a regression.

## Git Branching Rules

This applies going forward, to all future sessions, not just the one that
added it:

- New features (a new analysis capability, a new script, a new metric that
  didn't exist before) -> a new feature branch, named `feature/<short-desc>`.
- Development/tweaks on an already-integrated feature (adjusting an
  existing script's parameters, fixing a bug in a promoted script, refining
  existing analysis) -> a `dev/<short-desc>` branch, or the shared
  `development` branch if the change doesn't warrant its own branch. Check
  whether `development` already exists before creating a new dev branch.
- Only fully reviewed, finalized work gets merged to `main`.
- Never commit directly to `main`.
- Do not merge a branch into `development` or `main` unless explicitly
  asked to. Leave finished branches open for review.

## KDJ architecture - two separate systems, by design

- Entry gating (every K/D/J reference in entry conditions) reads the
  STATIC full-history KDJ(9,3,3) from compute_indicators(). w has NO
  effect on entry — confirmed by read-only audit.
- The post-entry EXIT signal uses a separate state machine
  (kdj_reset_init/update/exit) seeded from the static KDJ value AT
  the entry bar (not 50, not backfilled), recursed forward with
  period = entry_idx - triggering_OB_bar, frozen for that trade's
  life. Governs exit timing only.
- Observed w range, 27 baseline trades: 14-439 (median 74). w never
  approaches single digits - the paper's "two-bar window" example is
  illustrative only and is being corrected, not the code.
- Do NOT unify these into one KDJ or change kdj_reset_init's seed
  source without asking. This is a disclosed, deliberate design,
  verified via read-only audit.