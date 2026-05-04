import subprocess
import sys
import time

def main():
    print("==========================================")
    print("  Binance Backtest Bot Dashboard Runner")
    print("==========================================")
    print("\nInitializing the pipeline... Please wait.")
    
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
