"""
Read-only scope audit for the FVG/displacement lookahead finding.

Binance backtest bot.py now contains hard assertions (added as the
CLAUDE.md-mandated no-lookahead enforcement step) that raise AssertionError
the moment compute_smc() tries to read a bar past an OB's own confirmation
bar while scoring the FVG or displacement quality criteria. That assertion
is intentionally left in place and unweakened per project rule -- this
script does NOT touch it.

To measure how widespread the violation is (not just report the first hit),
this script runs ONLY under `python -O`, which compiles all `assert`
statements in the whole process (including the ones just added) to no-ops
for this diagnostic pass alone. The source file itself is untouched --
regression.py and every normal invocation still hit the real assertion.
This is solely to let compute_smc() run to completion so its returned
Order Block list (with created_at/ob_bar/quality_fvg already populated) can
be independently re-audited here, bar by bar, without needing to duplicate
or hand-transcribe the detection algorithm.

For every OB, independently re-derive: did the FVG (and displacement)
determination read data from a bar strictly after the OB's own
created_at (its earliest possible usable bar in simulate_trades' entry
filter, `ob['created_at'] < i`)?
"""
import sys
import os
import importlib.util
import pandas as pd
import numpy as np

if __debug__:
    print("FATAL: this script must be run with `python -O` (assertions must "
          "be disabled for this diagnostic pass). Re-run as: python -O "
          + os.path.basename(__file__))
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bot_path = os.path.join(BASE_DIR, "src", "Binance backtest bot.py")
CANDLES_CACHE_PATH = os.path.join(BASE_DIR, "artifacts", "candles.csv")

spec = importlib.util.spec_from_file_location("bot_scope", bot_path)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)


def refvg_trigger(ob, highs, lows, n):
    """Re-derive the exact (j, j+2) that set quality_fvg, matching the
    live loop bound `range(ob_idx, min(n-2, ob_idx+3))` exactly."""
    ob_idx = ob['ob_bar']
    for j in range(ob_idx, min(n - 2, ob_idx + 3)):
        if ob['type'] == 'DEMAND' and float(lows[j + 2]) > float(highs[j]):
            return j, j + 2
        if ob['type'] == 'SUPPLY' and float(highs[j + 2]) < float(lows[j]):
            return j, j + 2
    return None, None


def redisp_trigger(ob, df, atr200, n):
    ob_idx = ob['ob_bar']
    for j in range(ob_idx + 1, min(n, ob_idx + 4)):
        body = float(df.at[j, 'close']) - float(df.at[j, 'open'])
        thresh = 1.5 * float(atr200[ob_idx]) if not np.isnan(atr200[ob_idx]) else 0
        if ob['type'] == 'DEMAND' and body > 0 and abs(body) >= thresh:
            return j
        if ob['type'] == 'SUPPLY' and body < 0 and abs(body) >= thresh:
            return j
    return None


def main():
    df_raw = pd.read_csv(CANDLES_CACHE_PATH)
    df_raw["open_time"] = pd.to_datetime(df_raw["open_time"])
    df = bot.compute_indicators(df_raw)
    n = len(df)
    highs = df['high'].values
    lows = df['low'].values
    atr200 = df['ATR_200'].values

    print("Running compute_smc() with assertions disabled (-O) for scope measurement...")
    obs = bot.compute_smc(df)
    print(f"Total OBs detected: {len(obs)}")

    fvg_true = [ob for ob in obs if ob.get('quality_fvg')]
    disp_true = [ob for ob in obs if ob.get('quality_displacement')]
    print(f"quality_fvg=True: {len(fvg_true)} / {len(obs)}")
    print(f"quality_displacement=True: {len(disp_true)} / {len(obs)}")

    fvg_violations = []
    for ob in fvg_true:
        j, j2 = refvg_trigger(ob, highs, lows, n)
        if j2 is not None and j2 > ob['created_at']:
            fvg_violations.append({
                "ob_bar": ob['ob_bar'], "created_at": ob['created_at'],
                "type": ob['type'], "level": ob['level'],
                "trigger_j": j, "trigger_j_plus_2": j2,
                "bars_read_past_confirmation": j2 - ob['created_at'],
            })

    disp_violations = []
    for ob in disp_true:
        j = redisp_trigger(ob, df, atr200, n)
        if j is not None and j > ob['created_at']:
            disp_violations.append({
                "ob_bar": ob['ob_bar'], "created_at": ob['created_at'],
                "type": ob['type'], "level": ob['level'],
                "trigger_j": j,
                "bars_read_past_confirmation": j - ob['created_at'],
            })

    print(f"\nFVG lookahead violations: {len(fvg_violations)} / {len(fvg_true)} "
          f"of FVG-true OBs ({len(fvg_violations) / max(1, len(fvg_true)) * 100:.1f}%)")
    print(f"Displacement lookahead violations: {len(disp_violations)} / {len(disp_true)} "
          f"of displacement-true OBs ({len(disp_violations) / max(1, len(disp_true)) * 100:.1f}%)")

    if fvg_violations:
        overshoots = [v["bars_read_past_confirmation"] for v in fvg_violations]
        print(f"FVG overshoot (bars read past created_at): min={min(overshoots)} "
              f"median={sorted(overshoots)[len(overshoots)//2]} max={max(overshoots)}")
        print(f"First FVG violation: {fvg_violations[0]}")

    if disp_violations:
        overshoots = [v["bars_read_past_confirmation"] for v in disp_violations]
        print(f"Displacement overshoot (bars read past created_at): min={min(overshoots)} "
              f"median={sorted(overshoots)[len(overshoots)//2]} max={max(overshoots)}")
        print(f"First displacement violation: {disp_violations[0]}")

    # ── Cross-reference against the 27 locked baseline trades ──
    print("\n--- Cross-reference against 27 baseline trades (min_ob_quality=0) ---")
    sim_df = bot.simulate_trades(df.copy(), min_ob_quality=0)
    trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
    fvg_violation_bars = {v["ob_bar"] for v in fvg_violations}
    disp_violation_bars = {v["ob_bar"] for v in disp_violations}
    affected_trades = []
    for _, r in trades_df.iterrows():
        eob = int(r["entry_ob_bar"])
        if eob in fvg_violation_bars or eob in disp_violation_bars:
            affected_trades.append({
                "entry_idx": int(r["entry_idx"]), "side": r["side"],
                "entry_ob_bar": eob,
                "entry_ob_quality_fvg": bool(r["entry_ob_quality_fvg"]),
                "fvg_tainted": eob in fvg_violation_bars,
                "displacement_tainted": eob in disp_violation_bars,
            })
    print(f"Of the 27 baseline trades, {len(affected_trades)} used an entry OB whose "
          f"FVG and/or displacement criterion was set via a lookahead read:")
    for t in affected_trades:
        print(f"  {t}")
    print("\nNote: baseline (min_ob_quality=0) does not filter entries by `quality`, "
          "so this does not change which trades were taken or their PnL -- it means "
          "the reported entry_ob_quality_fvg / composite quality value for these "
          "specific trades' entry OBs may not reflect what was knowable at entry time.")


if __name__ == "__main__":
    main()
