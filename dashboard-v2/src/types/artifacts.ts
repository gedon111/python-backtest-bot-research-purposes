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

/** One Order Block as stored in runs_by_threshold.json's `obs` array. */
export interface OrderBlockRecord {
  ob_id: number;
  type: 'DEMAND' | 'SUPPLY';
  top: number;
  bottom: number;
  quality: number;
  quality_displacement: boolean;
  quality_large_bar: boolean;
  quality_fvg: boolean;
  quality_liquidity_sweep: boolean;
  quality_volume_expansion: boolean;
  mitigated_at?: number | null;
  [key: string]: unknown; // additional fields exist; only the ones actually consumed are typed strictly
}

/** One trade as stored in runs_by_threshold.json's `trades` array (superset of /api/trades' TradeRecord). */
export interface RunTradeRecord {
  trade_id: number;
  side: 'LONG' | 'SHORT';
  entry_idx: number;
  exit_idx: number;
  entry: number;
  tp?: number | null;
  sl?: number | null;
  entry_ob_bar?: number | null;
  ob_bar?: number | null;
  pnl_pct: number;
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
  entry_time: string;
  exit_time: string;
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
