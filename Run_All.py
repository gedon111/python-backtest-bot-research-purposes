import subprocess
import sys
import os
import argparse


def ensure_dashboard_built():
    """
    Builds dashboard-v2 (npm run build) if artifacts/dist is missing or stale
    relative to src/, so export_gui_data.py has something to serve at
    /dashboard/. Skipped when already up to date, so a normal backtest-only
    run doesn't pay the build cost every time.
    """
    dist_index = os.path.join("dashboard-v2", "dist", "index.html")
    src_dir = os.path.join("dashboard-v2", "src")

    needs_build = not os.path.isfile(dist_index)
    if not needs_build:
        dist_mtime = os.path.getmtime(dist_index)
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                if os.path.getmtime(os.path.join(root, f)) > dist_mtime:
                    needs_build = True
                    break
            if needs_build:
                break

    if not needs_build:
        print("[Dashboard] dashboard-v2/dist is up to date, skipping build.")
        return

    print("[Dashboard] Building dashboard-v2 (npm run build)...")
    # shell=True: on Windows, npm resolves to npm.cmd, which subprocess can't
    # exec directly as an argv list without going through the shell.
    subprocess.run("npm run build", cwd="dashboard-v2", check=True, shell=True)


def main():
    parser = argparse.ArgumentParser(description="Binance Backtest Bot - Unified Pipeline Runner")
    args = parser.parse_args()

    print("==================================================")
    print("  Binance Backtest Bot - Unified Pipeline Runner  ")
    print("==================================================")

    total_steps = 3
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

    # dashboard build
    print(f"\n[Step {current_step}/{total_steps}] Preparing dashboard-v2...")
    try:
        ensure_dashboard_built()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (dashboard build) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    current_step += 1

    # web
    print(f"\n[Step {current_step}/{total_steps}] Launching local web server and opening Dashboard...")
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
