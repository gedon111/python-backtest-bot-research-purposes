import os
import pandas as pd
from sqlalchemy import create_engine
import db_manager

def main():
    print("==========================================")
    print("  Backtest Database Verification Utility")
    print("==========================================")

    # 1. Connect to the database
    db_url = db_manager.get_db_url()
    print(f"\nConnecting to database: {db_url}")
    engine = create_engine(db_url)
    
    # 2. Check record counts
    print("\n--- Table Record Counts ---")
    tables = ['candles', 'order_blocks', 'ob_touches', 'trades']
    
    for table in tables:
        try:
            count = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table}", engine)['cnt'].iloc[0]
            print(f"  {table.ljust(15)}: {count} rows")
        except Exception as e:
            print(f"  {table.ljust(15)}: Error ({e})")

    # 3. Verify Candle Data and Indicators
    print("\n--- Candle Indicators Sample ---")
    try:
        candles_df = pd.read_sql("SELECT * FROM candles ORDER BY time DESC LIMIT 5", engine)
        print(candles_df[['symbol', 'interval', 'time', 'close', 'macd_hist', 'k', 'atr_14']])
    except Exception as e:
        print(f"  Error reading candles: {e}")

    # 4. Join trades with their entry candles and entry OB details
    print("\n--- Merged Trade Features Dataset (For Machine Learning) ---")
    try:
        # SQL Join joining trades, candles (indicators at entry time) and order_blocks (OB quality)
        query = """
            SELECT 
                t.trade_id,
                t.side,
                t.min_ob_quality as run_min_ob_quality,
                t.entry_time,
                t.exit_time,
                t.entry_price,
                t.exit_price,
                t.pnl_pct,
                t.hold_bars,
                t.exit_reason,
                -- Indicator values at trade entry
                c.close as entry_candle_close,
                c.macd_hist as entry_macd_hist,
                c.k as entry_k,
                c.d as entry_d,
                c.j as entry_j,
                c.atr_14 as entry_atr_14,
                c.atr_200 as entry_atr_200,
                (c.atr_14 / c.atr_200) as entry_atr_ratio,
                -- Order Block quality parameters
                ob.type as ob_type,
                ob.level as ob_level,
                ob.structure as ob_structure,
                ob.quality as ob_quality,
                ob.quality_displacement,
                ob.quality_large_bar,
                ob.quality_fvg,
                ob.quality_liquidity_sweep,
                ob.quality_volume_expansion
            FROM trades t
            JOIN candles c 
                ON t.symbol = c.symbol 
                AND t.interval = c.interval 
                AND t.entry_time = c.time
            JOIN order_blocks ob 
                ON t.entry_ob_id = ob.ob_id
            ORDER BY t.entry_time ASC
        """
        
        ml_df = pd.read_sql(query, engine)
        
        if ml_df.empty:
            print("  No trade records found in the database. Run a backtest first!")
        else:
            print(f"  Success: Loaded {len(ml_df)} trades with joined indicator features.")
            print("\n  DataFrame Info:")
            print(ml_df.info())
            
            # Print statistics by trade side
            print("\n  Trade Stats by Side:")
            stats = ml_df.groupby('side').agg(
                count=('trade_id', 'count'),
                avg_pnl=('pnl_pct', 'mean'),
                win_rate=('pnl_pct', lambda x: (x > 0).mean() * 100)
            )
            print(stats)
            
            # Print stats by Order Block Quality
            print("\n  Trade Stats by Entry Order Block Quality:")
            ob_stats = ml_df.groupby('ob_quality').agg(
                count=('trade_id', 'count'),
                avg_pnl=('pnl_pct', 'mean'),
                win_rate=('pnl_pct', lambda x: (x > 0).mean() * 100)
            )
            print(ob_stats)
            
            # Show sample rows
            print("\n  Sample Joined ML Dataset Rows:")
            pd.set_option('display.max_columns', 10)
            print(ml_df.head(3))
            
    except Exception as e:
        print(f"  Error joining trade features: {e}")

    # 5. Join Touch Events
    print("\n--- Merged OB Touch Events Dataset ---")
    try:
        touch_query = """
            SELECT 
                ot.touch_id,
                ot.time as touch_time,
                ot.touch_price,
                ot.macd_hist,
                ot.k,
                ot.j,
                ot.k_accel,
                ot.atr_14,
                ob.type as ob_type,
                ob.level as ob_level,
                ob.quality as ob_quality
            FROM ob_touches ot
            JOIN order_blocks ob ON ot.ob_id = ob.ob_id
            LIMIT 5
        """
        touch_df = pd.read_sql(touch_query, engine)
        if touch_df.empty:
            print("  No OB touch events found.")
        else:
            print(f"  Sample OB Touch Events (total recorded):")
            print(touch_df)
    except Exception as e:
        print(f"  Error loading touch events: {e}")

if __name__ == '__main__':
    main()
