/**
 * Shapes verified against the real files this session produced, not guessed:
 *   artifacts/manifest.json, artifacts/candles.json, artifacts/runs_by_threshold.json,
 *   artifacts/verification_report.json
 * and the /api/trades response built in export_gui_data.py's SilentHandler.
 */

export interface Manifest {
  schema_version: string;
  generated_at_utc: string;
  symbol: string;
  timeframe: string;
  start_time: string;
  end_time: string;
  levels: number[];
  candle_count: number;
}

/** One row of artifacts/candles.json — OHLCV plus the indicators computed by compute_indicators(). */
export interface Candle {
  time: number; // unix seconds, matches Lightweight Charts' Time
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  MACD: number;
  MACD_signal: number;
  MACD_hist: number;
  K: number;
  D: number;
  J: number;
  ATR: number;
  ATR_200: number;
  Trade_Status: string;
}

/** One Order Block as stored in runs_by_threshold.json's `obs` array. Field names verified against the real JSON (no `ob_id` -- OBs are identified by position, not an id). */
export interface OrderBlockRecord {
  type: 'DEMAND' | 'SUPPLY';
  top: number;
  bottom: number;
  created_at: number;
  ob_bar: number;
  level: 'swing' | 'internal';
  structure: 'BOS' | 'CHoCH';
  quality: number;
  quality_displacement: boolean;
  quality_large_bar: boolean;
  quality_fvg: boolean;
  quality_liquidity_sweep: boolean;
  quality_volume_expansion: boolean;
  mitigated_at?: number | null;
  [key: string]: unknown;
}

/**
 * One trade as stored in runs_by_threshold.json's `trades` array. Field names
 * verified directly against the real JSON, not against gui.js's usage: gui.js
 * reads `t.tp`/`t.sl`, which do not exist on any trade record in any threshold
 * (0/1/2/3) -- only `take_profit`/`stop_loss` do, so gui.js's fallback ATR
 * approximation fires unconditionally and its chart never draws a trade's real
 * recorded risk levels. Flagged and fixed per user decision this session; use
 * take_profit/stop_loss directly here, not an approximation.
 */
export interface RunTradeRecord {
  side: 'LONG' | 'SHORT';
  entry_idx: number;
  exit_idx: number;
  entry: number;
  exit: number;
  stop_loss: number;
  take_profit: number;
  pnl_pct: number;
  entry_ob_bar?: number | null;
  ob_bar?: number | null;
  entry_ob_quality?: number;
  hold_bars?: number;
  exit_reason?: string;
  [key: string]: unknown;
}

export interface RunStats {
  [key: string]: unknown;
}

export interface ThresholdRun {
  obs: OrderBlockRecord[];
  trades: RunTradeRecord[];
  stats: RunStats;
}

/** artifacts/runs_by_threshold.json — keyed by quality threshold, "0" through "3". */
export type RunsByThreshold = Record<string, ThresholdRun>;

export interface VerificationReport {
  status: string;
  notes: string[];
  source_checks: {
    symbol_match: boolean;
    timeframe_match: boolean;
    has_candles: boolean;
    first_candle_utc: string;
    last_candle_utc: string;
  };
  snapshot_hashes: {
    ohlc_hash: string;
    indicator_hash: string;
  };
  recalculation_hashes_by_threshold: Record<
    string,
    {
      orderblocks_hash: string;
      trades_hash: string;
      stats_hash: string;
    }
  >;
}

/** GET /api/trades — export_gui_data.py:520-543, joined with OrderBlock quality fields. */
export interface TradeRecord {
  trade_id: number;
  side: 'LONG' | 'SHORT';
  min_ob_quality: number;
  // Integer columns in db_manager.py's Trade model, populated in
  // export_gui_data.py:388-389 as int(base_df.loc[idx, 'time']) -- unix
  // seconds, matching Candle.time exactly, not an ISO string.
  entry_time: number;
  exit_time: number;
  entry_price: number;
  exit_price: number;
  stop_loss: number;
  take_profit: number;
  pnl_pct: number;
  hold_bars: number;
  exit_reason: string;
  entry_ob_id: number;
  tp_ob_id: number | null;
  quality_score: number;
  quality_displacement: boolean;
  quality_large_bar: boolean;
  quality_fvg: boolean;
  quality_liquidity_sweep: boolean;
  quality_volume_expansion: boolean;
}

/**
 * GET /api/get_theme, POST /api/save_theme — persisted to chart_theme.json at the
 * repo root (export_gui_data.py:626-673). Field set verified against the default
 * fallback object the handler returns when chart_theme.json doesn't exist yet.
 */
export interface DashboardTheme {
  pageTheme: 'light' | 'dark';
  dataColors: {
    candleUp: string;
    candleDown: string;
    candleWick: string;
    demand: string;
    supply: string;
    macd: string;
    macdSignal: string;
    macdHist: string;
    kdjK: string;
    kdjD: string;
    kdjJ: string;
    atr14: string;
    atr200: string;
  };
}

/**
 * GET /api/iterations (export_gui_data.py:557-624) — exists server-side but is
 * never fetched by the current gui.js. It's a leftover shape from the removed ML
 * classifier pipeline (per CODEBASE_MAP.md): always returns a single-element array
 * with a hardcoded "Heuristic Base (No ML)" iteration wrapping real per-threshold
 * trade metrics from the DB. Typed here so the decision to carry it forward or drop
 * it is explicit, not an accident of omission.
 */
export interface IterationMetric {
  base_trades: number;
  base_pnl: number;
  base_wr: number;
  tuned_trades: number;
  tuned_pnl: number;
  tuned_wr: number;
}

export interface Iteration {
  iteration_id: number;
  label: string;
  created_at: number;
  model_type: string;
  parameters: Record<string, number>;
  metrics: Record<'q0' | 'q1' | 'q2' | 'q3', IterationMetric>;
  pattern_diff: {
    tuned_parameters: Record<string, number>;
    pnl_improvement_pct: number;
    reweighted_failures_count: number;
  };
}

export type IterationsResponse = Iteration[];

/**
 * artifacts/ablation_reconstruction.json, produced by
 * analysis/ablation_reconstruction.py --json-out. Not recomputable in-browser
 * (the 140/138-trade indicators-only pools aren't exposed via /api/trades) --
 * this is genuinely Reference data, read as-is, never presented as a live
 * recomputation. See that script's docstring: this is a best-faith
 * reconstruction from the documented ablation design, not the original
 * (never-committed) generating script, and its win rate diverges from the
 * locked figures even though its trade counts match exactly.
 */
export interface AblationArmSummary {
  n: number;
  wins?: number;
  win_rate: number;
  total_return: number;
  avg_return?: number;
  sd?: number | null;
}

export interface AblationArm {
  label: string;
  reconstructed: AblationArmSummary;
  locked: { n: number; win_rate: number; total_return: number };
  status_vs_locked: 'MATCH' | 'DIVERGE';
  bootstrap_vs_baseline: {
    b: number;
    seed: number;
    n: number;
    win_rate_percentiles: { p2_5: number; p50: number; p97_5: number };
    avg_return_percentiles: { p2_5: number; p50: number; p97_5: number };
    empirical_p_win_rate_ge_baseline: number;
    empirical_p_avg_return_ge_baseline: number;
  } | null;
}

export interface AblationReconstructionReport {
  baseline: AblationArmSummary;
  arms: {
    flat_atr: AblationArm;
    swing_pivot: AblationArm;
  };
}
