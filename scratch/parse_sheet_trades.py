import pandas as pd
import numpy as np

def extract_trades_from_csv(filepath):
    df = pd.read_csv(filepath)
    # Strip column names and string cells just in case
    df.columns = [c.strip() for c in df.columns]
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        
    trades = []
    active_trade = None
    
    for idx, row in df.iterrows():
        status = row.get("Trade Status", "")
        if pd.isna(status) or status == "" or status == "nan":
            continue
            
        date_time = row.get("Date/Time", "")
        close = float(row.get("Close", 0))
        
        # Parse numeric columns safely
        def get_float(col_name):
            val = row.get(col_name, "")
            if pd.isna(val) or val == "" or val == "nan":
                return None
            try:
                # remove % if present
                if isinstance(val, str):
                    val = val.replace('%', '')
                return float(val)
            except:
                return None
                
        entry_price = get_float("Entry Price")
        sl = get_float("Stop Loss")
        tp = get_float("Take Profit")
        exit_price = get_float("Exit Price")
        pnl = get_float("Running PnL %")
        
        if "OPEN" in status:
            side = "LONG" if "LONG" in status else "SHORT"
            active_trade = {
                "side": side,
                "entry_time": date_time,
                "entry_price": entry_price if entry_price is not None else close,
                "sl": sl,
                "tp": tp,
                "entry_idx": idx
            }
        elif "RUNNING" in status:
            if active_trade is not None:
                # Update SL/TP if they trail/change
                if sl is not None:
                    active_trade["sl"] = sl
                if tp is not None:
                    active_trade["tp"] = tp
        elif status in ["HIT STOP LOSS", "HIT TAKE PROFIT", "TRAILING EXIT (50% RETRACE)", "KDJ RESET EXIT", "ATR MOVE EXIT", "TRAILING EXIT", "J EXHAUSTION EXIT"]:
            if active_trade is not None:
                active_trade["exit_time"] = date_time
                active_trade["exit_price"] = exit_price if exit_price is not None else close
                active_trade["exit_type"] = status
                active_trade["pnl_pct"] = pnl
                active_trade["exit_idx"] = idx
                active_trade["hold_bars"] = idx - active_trade["entry_idx"]
                trades.append(active_trade)
                active_trade = None
                
    return pd.DataFrame(trades)

if __name__ == "__main__":
    for q in [0, 1, 2, 3]:
        filepath = f"scratch/Quality_{q}.csv"
        trades_df = extract_trades_from_csv(filepath)
        print(f"\n--- Quality {q} Trades extracted: {len(trades_df)} ---")
        if not trades_df.empty:
            print(trades_df[["side", "entry_time", "entry_price", "exit_time", "exit_price", "exit_type", "pnl_pct"]].head(5))
            win_rate = (trades_df["pnl_pct"] > 0).mean() * 100
            total_pnl = trades_df["pnl_pct"].sum()
            print(f"Parsed Stats: Win Rate = {win_rate:.2f}%, Total Net Return = {total_pnl:.2f}%")
