import pandas as pd
import json

print("--- Inspecting candles.csv ---")
try:
    df_csv = pd.read_csv("artifacts/candles.csv")
    print("Columns:", df_csv.columns.tolist())
    print("Shape:", df_csv.shape)
    print("First 3 rows:")
    print(df_csv.head(3))
except Exception as e:
    print("Error reading candles.csv:", e)

print("\n--- Inspecting candles.json ---")
try:
    with open("artifacts/candles.json", "r") as f:
        data = json.load(f)
    print("Type of data:", type(data))
    if isinstance(data, list):
        print("Length of list:", len(data))
        print("First element:", data[0])
    elif isinstance(data, dict):
        print("Keys:", list(data.keys()))
except Exception as e:
    print("Error reading candles.json:", e)
