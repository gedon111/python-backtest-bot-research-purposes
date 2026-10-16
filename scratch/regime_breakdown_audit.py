"""
Item 5 (investigation session): tags each of the 27 min_ob_quality=0 baseline
trades by macro regime, using price-drawdown-from-ATH (not ADX/EMA200, which
per this session's brief aren't persisted anywhere in this repo -- confirmed
absent from both artifacts/candles.csv and backtest_results.db's candles
schema in the prior investigation pass) as the primary method, cross-checked
against a simple calendar split. Read-only against artifacts/candles.csv and
the unmodified strategy; no pipeline rerun, no changes to any committed file.

DRAWDOWN-FROM-ATH METHOD:
  Running ATH is seeded at $69,000 (BTC's actual all-time high, 2021-11-10,
  which predates this dataset's 2022-01-01 start by seven weeks -- seeding
  from the dataset's own first bar would incorrectly read early-2022, which
  was already ~32% off the real ATH, as "at the high"). From there, running
  ATH = cummax(seed, close). Thresholds (judgment call, stated so they can be
  re-argued): BEAR = drawdown <= -40% (deep, established downtrend), CHOP =
  -40% < drawdown <= -12% (recovering / rangebound, not yet re-testing highs),
  BULL = drawdown > -12% (at or making new highs).

CALENDAR METHOD (cross-check): 2022 = bear, 2023 = chop, 2024-2025 = bull,
per the standard, widely-cited BTC cycle narrative for this exact window
(cycle low Nov 2022, prior-ATH breakout Mar 2024).
"""
import importlib.util
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)

sim = bot.simulate_trades(df.copy(), min_ob_quality=0)
trades = sim.attrs.get("trades_df").copy()
assert len(trades) == 27

# ─── Drawdown-from-ATH regime series ────────────────────────────────────────
ATH_SEED = 69000.0
running_ath = np.maximum.accumulate(np.concatenate([[ATH_SEED], df["close"].values]))[1:]
drawdown_pct = (df["close"].values / running_ath - 1.0) * 100.0


def dd_regime(dd):
    if dd <= -40.0:
        return "BEAR"
    elif dd <= -12.0:
        return "CHOP"
    else:
        return "BULL"


df["_dd_pct"] = drawdown_pct
df["_dd_regime"] = [dd_regime(x) for x in drawdown_pct]

# ─── Calendar regime series (cross-check) ───────────────────────────────────
def cal_regime(ts):
    y = ts.year
    if y == 2022:
        return "BEAR"
    elif y == 2023:
        return "CHOP"
    else:
        return "BULL"


df["_cal_regime"] = df["open_time"].apply(cal_regime)

# ─── Tag each trade by its entry bar's regime ───────────────────────────────
trades["entry_time"] = df.loc[trades["entry_idx"], "open_time"].values
trades["entry_dd_pct"] = df.loc[trades["entry_idx"], "_dd_pct"].values
trades["dd_regime"] = df.loc[trades["entry_idx"], "_dd_regime"].values
trades["cal_regime"] = df.loc[trades["entry_idx"], "_cal_regime"].values


def summarize(label, group_col):
    print("=" * 100)
    print(f"  REGIME BREAKDOWN -- {label}")
    print("=" * 100)
    print(f"  {'Regime':<8} | {'N':<4} | {'Wins':<5} | {'Win rate':<9} | {'Total PnL contrib':<18} | {'Avg PnL/trade':<14}")
    total_pnl = trades["pnl_pct"].sum()
    for regime in ["BEAR", "CHOP", "BULL"]:
        g = trades[trades[group_col] == regime]
        if g.empty:
            print(f"  {regime:<8} | {'0':<4} | {'-':<5} | {'-':<9} | {'-':<18} | {'-':<14}")
            continue
        n = len(g)
        wins = int((g["pnl_pct"] > 0).sum())
        wr = wins / n * 100
        total = g["pnl_pct"].sum()
        avg = g["pnl_pct"].mean()
        pct_of_total = total / total_pnl * 100
        print(f"  {regime:<8} | {n:<4} | {wins:<5} | {wr:<8.2f}% | {total:>+8.4f}% ({pct_of_total:>+6.1f}% of total) | {avg:>+12.4f}%")
    print()


summarize("Drawdown-from-ATH method (BEAR<=-40%, CHOP<=-12%, BULL>-12%)", "dd_regime")
summarize("Calendar method (2022=BEAR, 2023=CHOP, 2024-25=BULL)", "cal_regime")

# ─── Cross-tab: do the two methods agree on regime assignment? ─────────────
agree = (trades["dd_regime"] == trades["cal_regime"]).sum()
print(f"  Method agreement: {agree}/27 trades assigned the same regime by both methods")
disagree = trades[trades["dd_regime"] != trades["cal_regime"]]
if not disagree.empty:
    print("  Disagreements:")
    for _, r in disagree.iterrows():
        print(f"    entry_idx={int(r['entry_idx']):<6} {r['entry_time']} dd%={r['entry_dd_pct']:+.1f}  "
              f"dd_method={r['dd_regime']:<5} cal_method={r['cal_regime']:<5}")
print()

# ─── Direct check on the 3 top-return trades ────────────────────────────────
print("=" * 100)
print("  THE 3 CONCENTRATED WINNING TRADES -- REGIME CHECK")
print("=" * 100)
top3 = trades.nlargest(3, "pnl_pct")
for _, r in top3.iterrows():
    print(f"  entry_idx={int(r['entry_idx']):<6} {str(r['entry_time']):<20} pnl={r['pnl_pct']:+.2f}%  "
          f"drawdown-from-ATH={r['entry_dd_pct']:+.1f}% -> {r['dd_regime']:<5}   calendar -> {r['cal_regime']}")
regimes_hit = set(top3["dd_regime"]).union(set(top3["cal_regime"]))
print(f"\n  Distinct regimes among the top 3 winners (either method, union): {sorted(regimes_hit)}")
print(f"  Clustered in a single regime? {'YES' if len(set(top3['dd_regime'])) == 1 else 'NO'} (drawdown method)")
print(f"  Clustered in a single regime? {'YES' if len(set(top3['cal_regime'])) == 1 else 'NO'} (calendar method)")
