import os
import subprocess
import sys
import time


def ensure_dashboard_built():
    """Builds dashboard-v2 (npm run build) if artifacts/dist is missing or stale relative to src/."""
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
    print("==========================================")
    print("  Binance Backtest Bot Dashboard Runner")
    print("==========================================")
    print("\nInitializing the pipeline... Please wait.")

    try:
        ensure_dashboard_built()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Building dashboard-v2 failed with exit code {e.returncode}.")
        input("Press Enter to close this window...")
        return

    try:
        # Run the export script with the required arguments
        subprocess.run(
            [sys.executable, "export_gui_data.py", "--levels", "0,1,2,3", "--export-gsheet"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] The script encountered an issue and exited with code {e.returncode}.")
        input("Press Enter to close this window...")
    except KeyboardInterrupt:
        print("\nProcess cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        input("Press Enter to close this window...")

if __name__ == '__main__':
    main()
