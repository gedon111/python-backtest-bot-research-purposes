"""
Item 2 (revision session): post-hoc fee/slippage sensitivity on a COPY of the
27-trade min_ob_quality=0 baseline PnL. Does NOT modify simulate_trades() or
any committed artifact -- this is a standalone, gitignored scratch script
(per repo convention) that loads the same offline artifacts/candles.csv
every other scratch script uses, runs the unmodified strategy, and only
mutates an in-memory copy of trades_df.

FEE FIGURE, CORRECTED THIS REVISION: the prior session's "4-10bps" fee
assumption was an unverified placeholder. Confirmed this session via web
search against Binance's official fee-schedule FAQ (binance.com/en/support/
faq/detail/360033544231, cross-checked against independent fee-tracking
sites, August 2026): USDT-M Futures standard tier (VIP 0 / regular user, NO
BNB fee discount) taker fee = 0.05% (5bps) per side, maker = 0.02% (2bps)
per side. We use the taker rate (0.05%/side) since backtest entries/exits
here are simulated at bar-close crossing a threshold, i.e. a market-order-like
fill, not a resting limit order. Round-trip (entry+exit) fee = 2 x 0.05% =
0.10%. This is a HIGHER, more conservative number than the prior "LOW"
scenario's 4bps/side placeholder, and lower than its "MID" 7bps/side guess --
it supersedes both as the defensible figure for a standard-tier account with
no BNB discount.

Slippage is kept STRICTLY SEPARATE from the fee line item per this session's
brief -- it is not a Binance-published number, it's a conservative estimate
for BTC/USDT 4H bar-close execution on a deep, liquid pair. We use 5bps/side
(10bps round trip = 0.10%) as that conservative estimate, unchanged from the
prior session's own conservative assumption.

Scenarios reported:
  - GROSS:            0.00% (no fee, no slippage -- as currently reported)
  - FEE ONLY:          0.10% round trip (0.05%/side taker, confirmed, no slippage)
  - PRIMARY (fee + conservative slippage): 0.10% + 0.10% = 0.20% round trip
  - Prior-session LOW/MID/HIGH band, kept ONLY as a sensitivity comparison
    (these bundled fee+slippage guesses at 0.14/0.24/0.40% predate this
    session's fee confirmation and should not be read as re-verified)

Reruns the one-sided/two-sided exact binomial test (win rate), Fisher's exact
(win/loss x criterion-true) and Welch's t-test (pnl_pct x criterion-true) for
all 5 orthogonal quality criteria, on the fee-adjusted PnL.
"""
import importlib.util
import pandas as pd
import numpy as np
from scipy import stats as sstats

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)

sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
trades = sim.attrs.get("trades_df").copy()
assert len(trades) == 27, f"expected 27 baseline trades, got {len(trades)}"

CRITERIA = {
    "Displacement":  "entry_ob_quality_displacement",
    "LargeBar":      "entry_ob_quality_large_bar",
    "FVG":           "entry_ob_quality_fvg",
    "LiqSweep":      "entry_ob_quality_liquidity_sweep",
    "VolExpansion":  "entry_ob_quality_volume_expansion",
}

SCENARIOS = [
    ("GROSS (no fees, no slippage -- as currently reported)", 0.0),
    ("FEE ONLY (confirmed 0.05%/side taker, no slippage, round trip)", 0.10),
    ("PRIMARY: FEE (confirmed) + CONSERVATIVE SLIPPAGE (0.05%+0.05%/side, round trip)", 0.20),
    ("[sensitivity band, pre-confirmation] LOW  (4bps taker + 3bps slip, round trip)", 0.14),
    ("[sensitivity band, pre-confirmation] MID  (7bps taker + 5bps slip, round trip)", 0.24),
    ("[sensitivity band, pre-confirmation] HIGH (10bps taker + 10bps slip, round trip)", 0.40),
]


def run_scenario(label, drag_pct):
    t = trades.copy()
    t["pnl_pct_adj"] = t["pnl_pct"] - drag_pct

    total_return = t["pnl_pct_adj"].sum()
    avg_return = t["pnl_pct_adj"].mean()
    sd_return = t["pnl_pct_adj"].std(ddof=1)
    wins = int((t["pnl_pct_adj"] > 0).sum())
    n = len(t)

    flipped = t[(trades["pnl_pct"] > 0) & (t["pnl_pct_adj"] <= 0)]

    bt = sstats.binomtest(wins, n, 0.5, alternative="greater")
    bt_two = sstats.binomtest(wins, n, 0.5, alternative="two-sided")

    print("=" * 100)
    print(f"  SCENARIO: {label}  (drag = {drag_pct:.2f}% round trip per trade)")
    print("=" * 100)
    print(f"  Total net return:      {total_return:+.4f}%  (gross was {trades['pnl_pct'].sum():+.4f}%)")
    print(f"  Avg return/trade:      {avg_return:+.4f}%")
    print(f"  SD (return/trade):     {sd_return:.4f}%")
    print(f"  Win rate:              {wins}/{n} = {wins/n*100:.2f}%  (gross was {(trades['pnl_pct']>0).sum()}/{n})")
    print(f"  One-sided binomial p:  {bt.pvalue:.4f}")
    print(f"  Two-sided binomial p:  {bt_two.pvalue:.4f}")
    if not flipped.empty:
        print(f"  Trades flipped WIN->LOSS ({len(flipped)}):")
        for _, r in flipped.iterrows():
            print(f"    entry_idx={int(r['entry_idx']):<6} gross={r['pnl_pct']:+.4f}%  net={r['pnl_pct_adj']:+.4f}%")
    else:
        print("  Trades flipped WIN->LOSS: none")

    print(f"\n  Per-criterion Fisher's exact (win/loss) and Welch's t-test (pnl_pct), fee-adjusted:")
    print(f"  {'Criterion':<14} | {'True n(w)':<10} | {'False n(w)':<11} | {'Fisher p':<10} | {'Welch t':<10} | {'Welch p':<10}")
    for name, col in CRITERIA.items():
        mask = t[col].astype(bool)
        true_grp = t.loc[mask, "pnl_pct_adj"]
        false_grp = t.loc[~mask, "pnl_pct_adj"]
        true_wins = int((true_grp > 0).sum())
        false_wins = int((false_grp > 0).sum())
        true_losses = len(true_grp) - true_wins
        false_losses = len(false_grp) - false_wins
        _, fisher_p = sstats.fisher_exact([[true_wins, true_losses], [false_wins, false_losses]])
        t_stat, welch_p = sstats.ttest_ind(true_grp, false_grp, equal_var=False)
        print(f"  {name:<14} | {len(true_grp)} ({true_wins})".ljust(24) +
              f"| {len(false_grp)} ({false_wins})".ljust(15) +
              f"| {fisher_p:<10.4f} | {t_stat:<+10.4f} | {welch_p:<10.4f}")
    print()


for label, drag in SCENARIOS:
    run_scenario(label, drag)
