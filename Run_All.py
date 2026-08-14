import subprocess
import sys
import os
import argparse


def ensure_python_deps():
    """Installs/verifies Python packages from requirements.txt."""
    print("[Dependencies] Installing Python packages (pip install -r requirements.txt)...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        check=True,
    )


def ensure_npm_deps():
    """
    Installs dashboard-v2's node_modules via `npm ci` if missing. Skipped
    when already present so a repeat run doesn't pay the install cost every
    time. Not needed at all inside the Docker image, where dashboard-v2/dist
    is pre-built and npm isn't installed in the final stage - see
    ensure_dashboard_built(), which only calls this when a build is needed.
    """
    node_modules = os.path.join("dashboard-v2", "node_modules")
    if os.path.isdir(node_modules):
        return

    print("[Dependencies] Installing dashboard-v2 npm packages (npm ci)...")
    # shell=True: on Windows, npm resolves to npm.cmd, which subprocess can't
    # exec directly as an argv list without going through the shell.
    subprocess.run("npm ci", cwd="dashboard-v2", check=True, shell=True)


def ensure_dashboard_built():
    """
    Builds dashboard-v2 (npm run build) if artifacts/dist is missing or stale
    relative to src/, so research_analysis.py's --serve mode has something to
    serve at /dashboard/. Skipped when already up to date, so a normal
    backtest-only run doesn't pay the build cost every time.
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

    ensure_npm_deps()

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

    # research_analysis.py --serve does backtest simulation + database load +
    # artifact export + starting the web server all in one process. This
    # script's job is everything needed to get there from a bare clone:
    # Python deps, dashboard-v2's npm deps + build, then the pipeline itself.
    total_steps = 3
    current_step = 1

    print(f"\n[Step {current_step}/{total_steps}] Installing Python dependencies...")
    try:
        ensure_python_deps()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (pip install) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    current_step += 1

    print(f"\n[Step {current_step}/{total_steps}] Preparing dashboard-v2...")
    try:
        ensure_dashboard_built()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (dashboard build) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    current_step += 1

    print(f"\n[Step {current_step}/{total_steps}] Running backtest simulations, loading database, "
          f"and launching local web server...")
    try:
        subprocess.run(
            [sys.executable, "research_analysis.py", "--serve", "--levels", "0,1,2,3"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step {current_step} (research_analysis.py --serve) failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

if __name__ == '__main__':
    main()
