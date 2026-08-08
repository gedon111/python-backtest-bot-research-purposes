"""
Per-bar candle-level export for the Google Sheets "Candles ..." tabs.

Read-only, additive. Reuses load_bot()/load_main_window()/
load_formulation_window() imported directly from
analysis/benchmark_vs_passive.py (both now return the fully-simulated
dataframe -- Trade_Status/Entry_Price/Active_Supply/Active_Demand/etc. all
populated, not just raw candles+indicators), and reuses
src/Binance backtest bot.py's `_format_df_for_export_full()` -- EVERY
column present on the simulated dataframe (26 columns as of this writing,
including `volume`, `time`, `RSV`, `num_trades`, `taker_buy_base`, none of
which the older, curated `_format_df_for_export()` includes), not a subset.
The cell-level formatting/stringification convention is the same one
`_format_df_for_export()` established; only the column selection differs.
src/Binance backtest bot.py's push_candles_to_gsheet() hands the result
straight to the existing `_write_sheet()`/`_apply_pnl_formatting()`
(unchanged), so the proven per-cell PnL coloring is untouched. This script
produces one row per bar, per WINDOW (2022-2026 locked baseline, 2018-2022
formulation period), matching the rest of this pipeline's window-based
sheet structure (Trades/Results/Benchmark).

REPRODUCIBILITY: fully offline, same two committed artifacts every other
script in this family already validated (artifacts/candles.csv,
artifacts/candles_extended.json). Deliberately NOT added to
scratch/regression.py for the same reason as the rest of this family --
that harness is narrowly scoped to the deterministic core simulate_trades()
pipeline against the frozen candles.csv snapshot only.

Usage (run from repo root):
    python analysis/export_candles_for_gsheet.py
    python analysis/export_candles_for_gsheet.py --json-out artifacts/export_candles_for_gsheet.json
"""
import argparse

from _json_utils import write_json
from benchmark_vs_passive import (
    FORMULATION_WINDOW_LABEL,
    MAIN_WINDOW_LABEL,
    load_bot,
    load_formulation_window,
    load_main_window,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to write results as JSON (does not change printed output)")
    args = parser.parse_args()

    bot = load_bot()

    sim_main, _ = load_main_window(bot)
    main_rows = bot._format_df_for_export_full(sim_main).to_dict(orient="records")
    print(f"Main window ({MAIN_WINDOW_LABEL}): {len(main_rows)} candle rows, "
          f"{len(main_rows[0]) if main_rows else 0} columns")

    sim_form, _ = load_formulation_window(bot)
    form_rows = bot._format_df_for_export_full(sim_form).to_dict(orient="records")
    print(f"Formulation-period window ({FORMULATION_WINDOW_LABEL}): {len(form_rows)} candle rows, "
          f"{len(form_rows[0]) if form_rows else 0} columns")

    if args.json_out:
        write_json({
            "main_window": {"label": MAIN_WINDOW_LABEL, "rows": main_rows},
            "formulation_period_window": {"label": FORMULATION_WINDOW_LABEL, "rows": form_rows},
        }, args.json_out)


if __name__ == "__main__":
    main()
