import subprocess
import sys
import os

def main():
    print("==================================================")
    print("  Binance Backtest Bot - Unified Pipeline Runner  ")
    print("==================================================")
    
    # Step 1: Run backtest and export base data to SQLite
    print("\n[Step 1/4] Running backtest simulations & loading database...")
    try:
        subprocess.run(
            [sys.executable, "export_gui_data.py", "--levels", "0,1,2,3", "--no-server"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step 1 (export_gui_data) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

    # Step 2: Verify SQL database schema & feature engineering
    print("\n[Step 2/4] Verifying database schema & features...")
    try:
        subprocess.run(
            [sys.executable, "read_data_for_ml.py"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step 2 (read_data_for_ml) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

    # Step 3: Run the ML Optimizer
    print("\n[Step 3/4] Running ML Optimizer (randomized search parameter tuning & RF classifier training)...")
    try:
        subprocess.run(
            [sys.executable, "ml_optimizer.py", "ML Pipeline Auto Run"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step 3 (ml_optimizer) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

    # Step 4: Run the Dashboard Web Server
    print("\n[Step 4/4] Launching local web server and opening Dashboard GUI...")
    try:
        subprocess.run(
            [sys.executable, "export_gui_data.py", "--levels", "0,1,2,3"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step 4 (export_gui_data dashboard server) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

if __name__ == '__main__':
    main()
