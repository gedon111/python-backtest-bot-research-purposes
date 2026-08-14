import pandas as pd
import importlib.util

spec = importlib.util.spec_from_file_location("bot", "research_analysis.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)
obs = bot.compute_smc(df)

# Check qualifying indicator signals
signals = []
start_bar = bot.SWING_STRUCTURE_LOOKBACK_BARS + 5
for i in range(start_bar, len(df)):
    close = float(df.at[i, 'close'])
    hist = float(df.at[i, 'MACD_hist'])
    p_hist = float(df.at[i - 1, 'MACD_hist'])
    pp_hist = float(df.at[i - 2, 'MACD_hist'])
    K = float(df.at[i, 'K'])
    D = float(df.at[i, 'D'])
    J = float(df.at[i, 'J'])
    K_prev = float(df.at[i - 1, 'K'])
    K2 = float(df.at[i - 2, 'K'])
    ATR = float(df.at[i, 'ATR'])
    ATR_200 = float(df.at[i, 'ATR_200'])
    k_accel = (K - K_prev) - (K_prev - K2)
    atr_r = ATR / ATR_200 if ATR_200 > 0 else 1.0

    # LONG indicator signal
    if (hist < 0 and hist > p_hist) and (p_hist > pp_hist) and (K < 50 and K > K_prev and J < 60) and (1 <= k_accel <= 6) and not (0.8 <= atr_r <= 1.0):
        signals.append({'bar': i, 'side': 'LONG'})
    # SHORT indicator signal
    elif (hist > 0 and hist < p_hist) and (p_hist < pp_hist) and (K > 50 and J > K > D) and (1 <= k_accel <= 6) and not (0.8 <= atr_r <= 1.0) and (K >= 70) and (J <= 100):
        signals.append({'bar': i, 'side': 'SHORT'})

print(f"Total qualifying indicator signals: {len(signals)}")
# Note: this is the raw pre-risk-filter count. The paper's "190 signals" figure
# additionally requires sl_ratio_min (0.015) against a 1.5*ATR-anchored stop;
# it is not directly comparable to this number without that filter applied.
