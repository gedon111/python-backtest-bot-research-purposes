import pandas as pd

df = pd.read_csv("scratch/Sheet1.csv")
df.columns = [c.strip() for c in df.columns]
print("Sheet1 Row Count:", len(df))
print("Start Date/Time:", df["Date/Time"].iloc[0])
print("End Date/Time:", df["Date/Time"].iloc[-1])
print("Indicators on Row 0:")
cols = ["Date/Time", "Close", "MACD", "K", "D", "J", "ATR (14)", "ATR (200)"]
for col in cols:
    if col in df.columns:
        print(f"  {col}: {df[col].iloc[0]}")
