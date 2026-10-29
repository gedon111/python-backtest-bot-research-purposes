# 2-Minute Script: Rule-Based Bitcoin Strategy vs. DCA

Corrected 2026-10-29 against `research_analysis.py` and
`docs/SCRATCH_RESULTS_METHODS.md`. Changes from the first draft are listed at
the bottom.

[0:00–0:10] INTRO: Bitcoin passes from hand to hand
EUAN (V.O.): "Bitcoin. Created in 2009 by the anonymous Satoshi Nakamoto. A decentralized digital asset, built to store wealth without needing a bank."
(Bitcoin lands in Gideon's hands.)

[0:10–0:22] GIDEON at his PC
GIDEON: "I've been using DCA, buying a little every week. But I want a beginner-friendly, low-risk strategy to compare it with. Let me search... ooh, this video looks good."
(Clicks the video.)

[0:22–0:52] YOUTUBE VIDEO: Euan at the board (you write the rules as he speaks)
EUAN: "This strategy reads 4-hour candles. To go long, ALL of these must be true at the candle close:
1. Price touches an untouched Order Block.
2. The MACD histogram is negative but rising for two candles.
3. KDJ's K is below 50 and rising, picking up speed, with J below 60.
4. Volatility, measured by ATR, is not stuck in its middle dead zone.
5. The stop is at least 1.5% away, with at least 1.5 reward-to-risk.

Shorts use their own version of these rules. You exit at the first of these to hit: once a trade is up 1.5%, a trailing exit that gives back half the peak profit; a KDJ reset; a 1.8× ATR move; the stop-loss; or the take-profit."

[0:52–0:58] EUAN (to camera, warm)
EUAN: "Rules are just rules until you see them work. Why not give it a go and see for yourself?"

[0:58–1:08] GIDEON exits the video, starts coding
GIDEON: "Alright, let's test it. I'll feed it Bitcoin data from 2022 to 2026, one 4-hour candle at a time."
(Montage: typing code, candles scrolling, results appear.)

[1:08–1:30] RESULTS: Gideon writes in his notebook
GIDEON: "Oh, so this is what happens! 27 trades, 19 wins. That's a 70.37% win rate. Average return per trade: +1.12%. And it was in the market only 2.63% of the time. Starting with $10,000, it ended at $13,417.77."
(On-screen note: "before trading costs.")

[1:30–1:42] COMPARISON GRAPHIC
GIDEON: "Now the DCA. It ended with $22,312.94, more than the strategy. But look at the risk: the strategy's worst drop was only −6.64%, while DCA's was −36.02%."
(Split screen: Strategy 70.37% | $13,417.77. DCA no trades to win or lose | $22,312.94.)
(On-screen note: "worst drop measured on daily closes.")

[1:42–1:58] CLOSE-UP
EUAN: "So why does our study matter?
It's beginner-friendly: clear rules, no guessing.
It's low risk: smaller drops than DCA.
It's rarely in the market: just 2.63% of the time.
It works beside DCA: putting 30% of weekly buys into it improved risk-adjusted returns."

[1:58–2:05] FINAL LINE
EUAN: "And this is A Rule-Based Bitcoin Trading Strategy Tested Against Dollar-Cost Averaging, 2022 to 2026."

---

## Changes from the first draft

| Line | Was | Now | Why (code) |
| --- | --- | --- | --- |
| Rule 3 | "K below 50 and rising, with J below 60" | adds "picking up speed" | K-acceleration must be 1 to 6 (`1 <= kdj_k_acceleration <= 6`) |
| Rule 4 | "ATR is not too quiet" | "not stuck in its middle dead zone" | entry is skipped only when `0.8 <= atr_regime_ratio <= 1.0`; quiet markets pass |
| Shorts | "simply mirror this" | "use their own version" | short thresholds are K >= 70, J < 100, not a mirror of 50/60 |
| Trailing exit | always on | "once a trade is up 1.5%" | `if peak_pnl_pct >= 1.5` |
| "To enter a trade" | | "To go long" | the five rules listed are the long rules |

Numbers were unchanged; all trace to `docs/SCRATCH_RESULTS_METHODS.md`.
Two caveats a judge may raise, left as published:
- $13,417.77 is compounded (+34.18%); the paper's +30.31% is the arithmetic
  sum. Don't pair the two on screen.
- DCA $22,312.94 is valued at the last weekly contribution, not the last
  candle ($22,395.86). This is a recorded OPEN item awaiting review.
