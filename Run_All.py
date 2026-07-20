import subprocess
import sys
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="Binance Backtest Bot - Unified Pipeline Runner")
    args = parser.parse_args()

    print("==================================================")
    print("  Binance Backtest Bot - Unified Pipeline Runner  ")
    print("==================================================")
    
    total_steps = 2
    current_step = 1

    # backtest and sql
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

    # web
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
