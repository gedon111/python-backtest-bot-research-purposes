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
- One-sided binomial p = 0.026 (two-sided 0.052; n=26 at q>=1 gives 0.038)
- 761 detected Order Blocks; FVG criterion true for 362 (47.6%)
- OB quality distribution: q0=77, q1=147, q2=200, q3=192, q4=112, q5=33
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
