# Order Block Quality Criteria: Per-Trade Definition, Code Trace, and Dataset Reference

> **Repository:** Binance Backtest Bot Research Package (`BTCUSDT` 4H Dataset, 2022–2026)  
> **Dataset Baseline:** $N = 27$ Unique Historical Trades (`min_ob_quality = 0` Baseline)  
> **Audit Status:** Post-Bug #3 (Commit `cb4ed93` / No-Lookahead Bounded Search Verified)  

---

## 1. Overview

This document details where the composite Order Block (OB) quality score (0–5) and the 5 individual orthogonal boolean criteria (**Displacement**, **LargeBar**, **FVG**, **LiqSweep**, **VolExpansion**) are defined, computed, stored, and exported across the codebase.

It provides:
1. Exact file paths and line numbers for the composite score and the 5 criteria.
2. The backward calculation trace from the raw candle OHLCV arrays.
3. The schema and locations where raw per-trade booleans are exported.
4. Python and SQL generation snippets to produce trade-level tables.
5. An audit of the no-lookahead boundary fixes.
6. The complete 27-trade raw boolean reference table.

---

## 2. Composite Quality Score (0–5) Calculation

* **File:** [`src/Binance backtest bot.py`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L198-L534)
* **Function:** `compute_smc(df)`

The composite quality score `ob['quality']` is computed as an integer sum ($0 \le \text{quality} \le 5$) of the 5 orthogonal booleans for each detected Order Block in two places:

### Bullish (DEMAND) Order Blocks ([`src/Binance backtest bot.py:L383-393`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L383-L393))
```python
ob['quality_displacement'] = bool(displacement)
ob['quality_large_bar'] = bool(large_bar)
ob['quality_fvg'] = bool(fvg)
ob['quality_liquidity_sweep'] = bool(liquidity_sweep)
ob['quality_volume_expansion'] = bool(vol_expansion)
ob['quality'] = int(
    ob['quality_displacement'] + ob['quality_large_bar'] +
    ob['quality_fvg'] + ob['quality_liquidity_sweep'] +
    ob['quality_volume_expansion']
)
```

### Bearish (SUPPLY) Order Blocks ([`src/Binance backtest bot.py:L508-518`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L508-L518))
```python
ob['quality_displacement'] = bool(displacement)
ob['quality_large_bar'] = bool(large_bar)
ob['quality_fvg'] = bool(fvg)
ob['quality_liquidity_sweep'] = bool(liquidity_sweep)
ob['quality_volume_expansion'] = bool(vol_expansion)
ob['quality'] = int(
    ob['quality_displacement'] + ob['quality_large_bar'] +
    ob['quality_fvg'] + ob['quality_liquidity_sweep'] +
    ob['quality_volume_expansion']
)
```

---

## 3. Backward Trace: Calculation of the 5 Individual Criteria

Inside `compute_smc(df)` in [`src/Binance backtest bot.py`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py):
* `ob_idx`: The bar index of the Order Block origin candle.
* `i` (`created_at`): The confirmation/crossover bar index when the BOS/CHoCH occurs.

```
+-------------------------------------------------------------------------+
|                  SMC Order Block Timeline & Windows                     |
|                                                                         |
|  [ob_idx - 20]     [ob_idx - 10]        [ob_idx]                [i]     |
|       |                 |                  |                     |      |
|       |                 +-- LiqSweep lookback                     |      |
|       |                     (prior 10 bars)|                     |      |
|       +------------------------------------+                     |      |
|         VolExpansion 20-bar avg lookback   |                     |      |
|                                            +-- LargeBar          |      |
|                                                (origin range)    |      |
|                                            |                     |      |
|                                            +--- FVG / Displace --+      |
|                                                 Forward Search          |
|                                                 [ob_idx .. min(i)]      |
+-------------------------------------------------------------------------+
```

### A. Displacement
* **Code:** [`src/Binance backtest bot.py:L292-321`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L292-L321) (DEMAND) & [`L417-446`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L417-L446) (SUPPLY)
* **Definition:** A large directional candle body ($\ge 1.5 \times \text{ATR}_{200}[\text{ob\_idx}]$) occurring in the 1 to 3 bars following the OB, strictly on or before confirmation bar $i$.
```python
displacement = False
for j in range(ob_idx + 1, min(i + 1, ob_idx + 4)):
    assert j <= i  # No-lookahead invariant
    body = float(df.at[j, 'close']) - float(df.at[j, 'open'])
    thresh = 1.5 * float(atr200[ob_idx]) if not np.isnan(atr200[ob_idx]) else 0
    if ob['type'] == 'DEMAND' and body > 0 and abs(body) >= thresh:
        displacement = True
        break
    if ob['type'] == 'SUPPLY' and body < 0 and abs(body) >= thresh:
        displacement = True
        break
```

### B. LargeBar (Large Origin Candle)
* **Code:** [`src/Binance backtest bot.py:L322-327`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L322-L327) (DEMAND) & [`L447-452`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L447-L452) (SUPPLY)
* **Definition:** The OB origin candle's full range $(\text{high} - \text{low})$ is greater than or equal to $\text{ATR}_{200}[\text{ob\_idx}]$.
```python
bar_range = float(highs[ob_idx]) - float(lows[ob_idx])
large_bar = (not np.isnan(atr200[ob_idx]) and bar_range >= float(atr200[ob_idx]))
```

### C. FVG (Fair Value Gap)
* **Code:** [`src/Binance backtest bot.py:L328-358`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L328-L358) (DEMAND) & [`L453-483`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L453-L483) (SUPPLY)
* **Definition:** A classic 3-candle imbalance formed between bar $j$ and $j+2$ within 3 bars of the OB origin, with bar $j+2$ closed on or before confirmation bar $i$.
```python
fvg = False
for j in range(ob_idx, min(i - 1, ob_idx + 3)):
    assert j + 2 <= i  # No-lookahead invariant
    if ob['type'] == 'DEMAND' and float(lows[j + 2]) > float(highs[j]):
        fvg = True
        break
    if ob['type'] == 'SUPPLY' and float(highs[j + 2]) < float(lows[j]):
        fvg = True
        break
```

### D. LiqSweep (Liquidity Sweep)
* **Code:** [`src/Binance backtest bot.py:L359-367`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L359-L367) (DEMAND) & [`L484-492`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L484-L492) (SUPPLY)
* **Definition:** The OB origin candle pierced the extreme (lowest low for DEMAND, highest high for SUPPLY) of the preceding 10 bars.
```python
prev_start = max(0, ob_idx - 10)
if ob['type'] == 'DEMAND':
    liquidity_sweep = float(lows[ob_idx]) <= float(lows[prev_start:ob_idx].min())
else:
    liquidity_sweep = float(highs[ob_idx]) >= float(highs[prev_start:ob_idx].max())
```

### E. VolExpansion (Volume Expansion)
* **Code:** [`src/Binance backtest bot.py:L368-382`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L368-L382) (DEMAND) & [`L493-507`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L493-L507) (SUPPLY)
* **Definition:** Either the OB origin volume exceeds $1.25 \times \text{mean}(\text{volume}_{[\text{ob\_idx}-20:\text{ob\_idx}]})$, OR the candle body occupies $> 60\%$ of the origin candle's range.
```python
vstart = max(0, ob_idx - 20)
if ob_idx > 0:
    vol = float(df.at[ob_idx, 'volume'])
    avg_vol = float(df['volume'].iloc[vstart:ob_idx].mean())
    volume_good = (avg_vol > 0 and vol >= 1.25 * avg_vol)
else:
    volume_good = False
body = abs(float(df.at[ob_idx, 'close']) - float(df.at[ob_idx, 'open']))
rng = float(highs[ob_idx]) - float(lows[ob_idx])
impulse_body = (rng > 0 and body / rng > 0.6)
vol_expansion = (volume_good or impulse_body)
```

---

## 4. Attachment to Executed Trades

In `simulate_trades(df)` in [`src/Binance backtest bot.py`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py), each trade records its triggering entry Order Block's boolean criteria directly upon position close:

* **LONG trades:** [`L908–913`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L908-L913)
* **SHORT trades:** [`L989–994`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L989-L994)

```python
trades.append({
    'side': 'LONG',  # or 'SHORT'
    'entry_idx': entry_idx,
    'exit_idx': i,
    'entry': entry_price,
    'exit': close,
    'pnl_pct': pnl,
    'entry_ob_bar': (current_entry_ob.get('ob_bar') if current_entry_ob else None),
    'entry_ob_quality': (current_entry_ob.get('quality') if current_entry_ob else None),
    'entry_ob_quality_displacement': (bool(current_entry_ob.get('quality_displacement')) if current_entry_ob else False),
    'entry_ob_quality_large_bar': (bool(current_entry_ob.get('quality_large_bar')) if current_entry_ob else False),
    'entry_ob_quality_fvg': (bool(current_entry_ob.get('quality_fvg')) if current_entry_ob else False),
    'entry_ob_quality_liquidity_sweep': (bool(current_entry_ob.get('quality_liquidity_sweep')) if current_entry_ob else False),
    'entry_ob_quality_volume_expansion': (bool(current_entry_ob.get('quality_volume_expansion')) if current_entry_ob else False),
    # ... structural TP fields, hold bars, exit reason ...
})
```

---

## 5. Stored Locations & Available Exports

The boolean flags are persisted and accessible across the repository in:

1. **[`artifacts/export_trades_and_results.json`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/artifacts/export_trades_and_results.json)**  
   * Full trade dictionary under `main_window.trades` (27 trades) and `formulation_period_window.trades`.
   * Includes all 5 booleans + 11 underlying numeric measurements (e.g. `entry_ob_displacement_max_body_move`, `entry_ob_displacement_threshold`, etc.).
2. **`backtest_results.db` (SQLite Database)**  
   * `order_blocks` table: Columns `quality_displacement`, `quality_large_bar`, `quality_fvg`, `quality_liquidity_sweep`, `quality_volume_expansion` ([`db_manager.py:L65-69`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/db_manager.py#L65-L69)).
   * `trades` table: Linked via `entry_ob_id` foreign key.
   * `GET /api/trades` HTTP endpoint in [`export_gui_data.py:L663-701`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/export_gui_data.py#L663-L701).
3. **[`artifacts/orderblocks_default_view.csv`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/artifacts/orderblocks_default_view.csv)** & **[`artifacts/runs_by_threshold.json`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/artifacts/runs_by_threshold.json)**  
   * All 761 Order Blocks with all 5 boolean flags.
4. **[`artifacts/trades_default_view.csv`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/artifacts/trades_default_view.csv)**  
   * CSV export of trades under the default view (`min_quality = 1`, 25 trades).
5. **Google Sheets Export**  
   * Written by `push_trades_and_results_to_gsheet()` ([`src/Binance backtest bot.py:L1427-1442`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/src/Binance%20backtest%20bot.py#L1427-L1442)).

---

## 6. How to Extract / Regenerate the 27-Trade Table

### Option A: Python Script
```python
import importlib.util
import pandas as pd

# Load trading bot module
spec = importlib.util.spec_from_file_location("bot", "src/Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

# Load 4H candles & compute indicators
df = pd.read_csv("artifacts/candles.csv")
df["open_time"] = pd.to_datetime(df["open_time"])
df = bot.compute_indicators(df)

# Simulate trades at baseline threshold 0 (all 27 trades)
sim_df = bot.simulate_trades(df, min_ob_quality=0)
trades_df = sim_df.attrs["trades_df"]

cols = [
    "entry_idx", "side", "entry", "exit", "pnl_pct", "hold_bars", "entry_ob_quality",
    "entry_ob_quality_displacement",
    "entry_ob_quality_large_bar",
    "entry_ob_quality_fvg",
    "entry_ob_quality_liquidity_sweep",
    "entry_ob_quality_volume_expansion"
]
result_df = trades_df[cols].copy()
result_df.to_csv("trades_with_quality_flags_27.csv", index=False)
```

### Option B: SQLite SQL Query
```sql
SELECT 
    t.trade_id,
    t.side,
    t.entry_time,
    t.exit_time,
    t.entry_price,
    t.exit_price,
    t.pnl_pct,
    t.hold_bars,
    t.exit_reason,
    ob.quality AS quality_score,
    ob.quality_displacement AS displacement,
    ob.quality_large_bar AS large_bar,
    ob.quality_fvg AS fvg,
    ob.quality_liquidity_sweep AS liq_sweep,
    ob.quality_volume_expansion AS vol_expansion
FROM trades t
JOIN order_blocks ob ON t.entry_ob_id = ob.ob_id
WHERE t.min_ob_quality = 0
ORDER BY t.entry_time ASC;
```

---

## 7. Lookahead Bug Audit Trail & Verification

> [!IMPORTANT]
> **No-Lookahead Fix Audit ([`CLAUDE.md:L85-99`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/CLAUDE.md#L85-L99)):**
> Prior to commit `cb4ed93`, the forward search loops for FVG and Displacement were bounded by dataset length $n$, allowing criteria checks to read $1 \text{--} 2$ bars past confirmation bar $i$ (`created_at`).

1. **Displacement Fix:** Window is bounded by `min(i + 1, ob_idx + 4)` with `assert j <= i`.
2. **FVG Fix:** Window is bounded by `min(i - 1, ob_idx + 3)` with `assert j + 2 <= i`.
3. **Impact on the 27 Baseline Trades:**
   * Trade entries/exits are identical (threshold 0 does not filter by quality).
   * 4 of the 27 trades had their `quality_fvg` flag correctly flip from `True` to `False` (`entry_idx` 673, 1158, 3100, and 6040).
   * All current outputs and tables reflect the **corrected post-fix values**.

---

## 8. Complete 27-Trade Baseline Table with Raw Booleans

Source: [`artifacts/export_trades_and_results.json`](file:///e:/PROGRAMMING/git-projects/Binance%20Backtest%20Bot%20Package%20%28compliance%20ver%29/artifacts/export_trades_and_results.json) (`main_window.trades`)

| # | Entry Index | Entry Time | Side | PnL (%) | Quality | Displacement | LargeBar | FVG | LiqSweep | VolExpansion |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 335 | 2022-02-26 04:00 | SHORT | -0.66% | 2 | **True** | False | False | False | **True** |
| 2 | 359 | 2022-03-02 04:00 | SHORT | +6.69% | 4 | False | **True** | **True** | **True** | **True** |
| 3 | 673 | 2022-04-23 12:00 | LONG | -0.38% | 4 | **True** | **True** | False | **True** | **True** |
| 4 | 902 | 2022-05-31 16:00 | SHORT | +3.22% | 2 | False | **True** | False | False | **True** |
| 5 | 1050 | 2022-06-25 08:00 | SHORT | +0.44% | 3 | False | **True** | **True** | **True** | False |
| 6 | 1158 | 2022-07-13 08:00 | LONG | -0.09% | 1 | False | False | False | **True** | False |
| 7 | 1913 | 2022-11-16 04:00 | SHORT | +1.23% | 0 | False | False | False | False | False |
| 8 | 2624 | 2023-03-14 16:00 | SHORT | -4.65% | 4 | False | **True** | **True** | **True** | **True** |
| 9 | 2859 | 2023-04-22 20:00 | LONG | +0.25% | 3 | False | **True** | False | **True** | **True** |
| 10 | 3100 | 2023-06-02 00:00 | LONG | +0.77% | 0 | False | False | False | False | False |
| 11 | 3196 | 2023-06-18 00:00 | SHORT | -0.78% | 2 | False | **True** | **True** | False | False |
| 12 | 3859 | 2023-10-06 12:00 | LONG | +0.63% | 2 | False | **True** | False | **True** | False |
| 13 | 3947 | 2023-10-21 04:00 | SHORT | -1.60% | 3 | False | **True** | False | **True** | **True** |
| 14 | 4455 | 2024-01-13 20:00 | LONG | -1.15% | 3 | False | **True** | **True** | False | **True** |
| 15 | 5800 | 2024-08-25 00:00 | SHORT | +2.79% | 2 | False | **True** | **True** | False | False |
| 16 | 5825 | 2024-08-29 04:00 | LONG | +0.38% | 3 | False | False | **True** | **True** | **True** |
| 17 | 6040 | 2024-10-04 00:00 | LONG | +1.38% | 1 | **True** | False | False | False | False |
| 18 | 6109 | 2024-10-15 12:00 | SHORT | -2.03% | 3 | False | **True** | False | **True** | **True** |
| 19 | 6366 | 2024-11-27 08:00 | LONG | +4.36% | 2 | False | **True** | False | False | **True** |
| 20 | 6537 | 2024-12-25 20:00 | SHORT | +3.47% | 3 | False | **True** | **True** | False | **True** |
| 21 | 6991 | 2025-03-11 12:00 | LONG | +1.63% | 4 | **True** | **True** | **True** | **True** | False |
| 22 | 7109 | 2025-03-31 04:00 | LONG | +3.51% | 4 | False | **True** | **True** | **True** | **True** |
| 23 | 7938 | 2025-08-16 08:00 | LONG | +0.12% | 2 | False | **True** | False | False | **True** |
| 24 | 7964 | 2025-08-20 16:00 | LONG | +2.38% | 2 | False | **True** | False | **True** | False |
| 25 | 8188 | 2025-09-27 00:00 | LONG | +0.13% | 3 | False | **True** | False | **True** | **True** |
| 26 | 8280 | 2025-10-12 08:00 | LONG | +4.62% | 2 | False | **True** | False | **True** | False |
| 27 | 8596 | 2025-12-04 00:00 | SHORT | +3.65% | 1 | False | False | **True** | False | False |
