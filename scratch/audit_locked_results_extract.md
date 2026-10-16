## Locked results - must not change

These numbers appear in the paper. Any code change that alters them is a bug in
the change, not an improvement:

- Baseline (min_ob_quality=0): 27 trades, 70.37% win rate, +30.31% total net
  return, +1.12% avg return/trade, SD 2.41%
- One-sided binomial p = 0.026 (two-sided 0.052) for the q>=0 baseline.
- q>=1 one-sided binomial p: 0.038 (n=26, pre-fix) -> 0.054 (n=25,
  post-fix as of commit cb4ed93). This is a SIGNIFICANCE-CONCLUSION FLIP
  (marginally significant -> not significant at alpha=0.05), not a modest
  revision - driven by a single trade (entry_idx=3100) losing its only
  quality point (FVG) under the corrected no-lookahead computation. See
  Known bugs #3. Consistent with the Limitations section's existing
  small-sample caveat about q>=1's thin N.
- 761 detected Order Blocks; FVG criterion true for 253 (33.2%) as of
  commit cb4ed93 (was 362 / 47.6% pre-fix; corrected, see Known bugs #3).
- OB quality distribution (post-fix, commit cb4ed93): q0=93, q1=154,
  q2=206, q3=197, q4=90, q5=21 (was q0=77, q1=147, q2=200, q3=192, q4=112,
  q5=33 pre-fix; corrected, see Known bugs #3).
- Ablation A (indicators-only, entry-ATR stop): 140 trades, 60.00%, -14.63%
- Ablation B (indicators-only, swing-pivot stop): 138 trades, 55.07%, -25.50%
- Dataset: artifacts/candles.csv, 8,767 bars (1,461 days incl. 2024 leap day
  x 6 bars/day, plus one boundary-inclusive endpoint bar). NOT 8,760 - the
  paper's original figure was arithmetic, since corrected. Do not trim bars.
- Benchmark-vs-passive (research_analysis.py's run_benchmark_vs_passive(),
  Section 5B, originally analysis/benchmark_vs_passive.py, $10,000 notional
  starting capital, gross unless stated): 2022-2026 window - OB-gated
  strategy +30.31% -> $13,417.77 (Sharpe 1.114, MaxDD -6.46%,
  2.63% time-in-market); Weekly DCA into BTC +123.13% -> $22,312.94 (Sharpe
  0.556, MaxDD -27.85%, 100%); Lump-sum B&H +90.07% -> $19,007.32 (Sharpe
  0.564, MaxDD -67.21%, 100%). DCA and lump-sum B&H BOTH beat the strategy
  in raw terminal value this window - do not let a future session state or
  imply the strategy "beats DCA/BTC" without the exposure-time caveat
  (2.63% vs 100%) attached in the same breath. Fee-adjusted variant: strategy
  +24.91% -> $12,719.01. 2018-2022 formulation-period window (NOT
  out-of-sample): strategy +21.82% -> $12,282.53; DCA +439.88% -> $53,987.55;
  lump-sum +236.96% -> $33,696.49.

