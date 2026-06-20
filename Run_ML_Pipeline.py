import subprocess
import sys
import os

def main():
    print("==========================================")
    print("  Binance Backtest Bot SQL Pipeline")
    print("==========================================")
    
    print("\n[Pipeline] Running backtest and exporting database data...")
    # Run export_gui_data.py to run the simulations and load the SQLite DB
    try:
        subprocess.run(
            [sys.executable, "export_gui_data.py", "--levels", "0,1,2,3", "--no-server"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Backtest export failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
        
    print("\n[Pipeline] Verifying SQL database schema and feature engineering...")
    # Run read_data_for_ml.py to check tables and verify data joins
    try:
        subprocess.run(
            [sys.executable, "read_data_for_ml.py"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Verification script failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
        
    print("\n[Pipeline] Done! Database is loaded and ready for ML analysis.")

if __name__ == '__main__':
    main()
