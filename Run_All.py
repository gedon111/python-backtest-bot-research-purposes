import subprocess
import sys
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="Binance Backtest Bot - Unified Pipeline Runner")
    parser.add_argument("--ml", action="store_true", help="Run the ML Optimizer (slow randomized search & classifier training) before starting the server")
    args = parser.parse_args()

    print("  Binance Backtest Bot - Unified Pipeline Runner  ")
    
    total_steps = 4 if args.ml else 3
    current_step = 1

    # Step 1: Run backtest and export base data to SQLite
    print(f"\n[Step {current_step}/{total_steps}] Running backtest simulations & loading database...")
    try:
        subprocess.run(
            [sys.executable, "export_gui_data.py", "--levels", "0,1,2,3", "--no-server"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (export_gui_data) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    current_step += 1

    # Step 2: Verify SQL database schema & feature engineering
    print(f"\n[Step {current_step}/{total_steps}] Verifying database schema & features...")
    try:
        subprocess.run(
            [sys.executable, "read_data_for_ml.py"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (read_data_for_ml) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    current_step += 1

    # Optional Step 3: Run the ML Optimizer
    if args.ml:
        print(f"\n[Step {current_step}/{total_steps}] Running ML Optimizer (randomized search parameter tuning & RF classifier training)...")
        try:
            subprocess.run(
                [sys.executable, "ml_optimizer.py", "ML Pipeline Auto Run"],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Step {current_step} (ml_optimizer) failed with exit code {e.returncode}.")
            sys.exit(e.returncode)
        current_step += 1

    # Final Step: Run the Dashboard Web Server
    print(f"\n[Step {current_step}/{total_steps}] Launching local web server and opening Dashboard GUI...")
    try:
        subprocess.run(
            [sys.executable, "export_gui_data.py", "--levels", "0,1,2,3"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (export_gui_data dashboard server) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

if __name__ == '__main__':
    main()
