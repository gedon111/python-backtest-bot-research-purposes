import type { TradeRecord } from '../../types/artifacts';
import { bootstrapPercentileCI, computeCorrelationPearson, computeCorrelationSpearman, type BootstrapCIResult } from './statMath';

/** Baseline trade set used across the whole tab: min_ob_quality = 0, gui.js:1913-1914's fallback preserved. */
export function baselineTrades(trades: TradeRecord[]): TradeRecord[] {
  const base = trades.filter((t) => t.min_ob_quality === 0);
  return base.length > 0 ? base : trades;
}

export interface BaselineProvenance {
  totalTrades: number;
  matchedByFilter: number;
  n: number;
  fallbackUsed: boolean;
}

/** Which branch of baselineTrades' filter/fallback actually fired, and against
 * how many total trades -- so the Solutions tab can state "n and k come from
 * filtering /api/trades to min_ob_quality===0" truthfully instead of
 * presenting n as a bare given. Does not alter baselineTrades' own behavior. */
export function baselineProvenance(trades: TradeRecord[]): BaselineProvenance {
  const matched = trades.filter((t) => t.min_ob_quality === 0).length;
  const fallbackUsed = matched === 0 && trades.length > 0;
  return {
    totalTrades: trades.length,
    matchedByFilter: matched,
    n: fallbackUsed ? trades.length : matched,
    fallbackUsed,
  };
}

const sum = (arr: number[]) => arr.reduce((a, b) => a + b, 0);

/** Percentile bootstrap CI on the baseline's own total/average return -- live counterpart to analysis/bootstrap_power_analysis.py's part (a). */
export function computeOwnBootstrapCI(trades: TradeRecord[], b = 2000, seed = 42): BootstrapCIResult {
  const base = baselineTrades(trades);
  return bootstrapPercentileCI(
    base.map((t) => t.pnl_pct),
    b,
    seed
  );
}

export interface BaselineOverviewRow {
  label: string;
  n: number;
  winRate: number;
  totalPnl: number;
  shareOfReturn: number;
  avgReturn: number;
  stdDev: number | null;
}

/** Ported from gui.js's renderBaselineOverview (gui.js:2090-2164). */
export function computeBaselineOverview(trades: TradeRecord[]): BaselineOverviewRow[] {
  const base = baselineTrades(trades);
  const n = base.length;
  if (n === 0) return [];
  const wins = base.filter((t) => t.pnl_pct > 0).length;
  const total = sum(base.map((t) => t.pnl_pct));
  const mean = total / n;
  const sd = n > 1 ? Math.sqrt(sum(base.map((t) => (t.pnl_pct - mean) ** 2)) / (n - 1)) : 0;

  const sorted = [...base].sort((a, b) => b.pnl_pct - a.pnl_pct);
  const top3 = sorted.slice(0, 3);
  const top3Sum = sum(top3.map((t) => t.pnl_pct));

  const rows: BaselineOverviewRow[] = [
    {
      label: `Full Baseline Strategy (N = ${n})`,
      n,
      winRate: (wins / n) * 100,
      totalPnl: total,
      shareOfReturn: 100,
      avgReturn: mean,
      stdDev: sd,
    },
    ...top3.map((t, i) => ({
      label: `Rank ${i + 1} Winner (OB #${t.entry_ob_id ?? t.trade_id}, ${t.side})`,
      n: 1,
      winRate: 100,
      totalPnl: t.pnl_pct,
      shareOfReturn: (t.pnl_pct / total) * 100,
      avgReturn: t.pnl_pct,
      stdDev: null,
    })),
    {
      label: 'Top 3 Winners Combined',
      n: 3,
      winRate: 100,
      totalPnl: top3Sum,
      shareOfReturn: (top3Sum / total) * 100,
      avgReturn: top3Sum / 3,
      stdDev: null,
    },
  ];
  return rows;
}

export interface CorrelationSummary {
  n: number;
  pearson: { r: number; p: number; t: number };
  spearman: { rho: number; p: number };
}

/** Ported from gui.js's renderCorrelations (gui.js:2262-2311): hold_bars vs pnl_pct. */
export function computeCorrelations(trades: TradeRecord[]): CorrelationSummary {
  const base = baselineTrades(trades);
  const holdBars = base.map((t) => t.hold_bars);
  const pnl = base.map((t) => t.pnl_pct);
  const pearson = computeCorrelationPearson(holdBars, pnl);
  const spearman = computeCorrelationSpearman(holdBars, pnl);
  return { n: base.length, pearson, spearman: { rho: spearman.rho, p: spearman.p } };
}

export interface ExitReasonRow {
  reason: string;
  n: number;
  pct: number;
  avgPnl: number;
  winRate: number;
}

const STANDARD_EXIT_REASONS = [
  'ATR MOVE EXIT',
  'KDJ RESET EXIT',
  'TRAILING EXIT (50% RETRACE)',
  'HIT STOP LOSS',
  'HIT TAKE PROFIT',
];

/** Ported from gui.js's renderExitReasons (gui.js:2337-2382). */
export function computeExitReasons(trades: TradeRecord[]): ExitReasonRow[] {
  const base = baselineTrades(trades);
  const total = base.length;
  if (total === 0) return [];
  const groups = new Map<string, TradeRecord[]>();
  for (const t of base) {
    const list = groups.get(t.exit_reason) ?? [];
    list.push(t);
    groups.set(t.exit_reason, list);
  }
  return STANDARD_EXIT_REASONS.map((reason) => {
    const list = groups.get(reason) ?? [];
    const n = list.length;
    const s = sum(list.map((t) => t.pnl_pct));
    const wins = list.filter((t) => t.pnl_pct > 0).length;
    return { reason, n, pct: (n / total) * 100, avgPnl: n > 0 ? s / n : 0, winRate: n > 0 ? (wins / n) * 100 : 0 };
  });
}

export interface LongShortRow {
  side: 'LONG' | 'SHORT';
  n: number;
  winRate: number;
  total: number;
  avg: number;
  sd: number;
}

/** Ported from gui.js's renderLongShort (gui.js:2384-2419). */
export function computeLongShort(trades: TradeRecord[]): LongShortRow[] {
  const base = baselineTrades(trades);
  return (['LONG', 'SHORT'] as const).map((side) => {
    const list = base.filter((t) => t.side === side);
    const n = list.length;
    const wins = list.filter((t) => t.pnl_pct > 0).length;
    const total = sum(list.map((t) => t.pnl_pct));
    const avg = n > 0 ? total / n : 0;
    const sd = n > 1 ? Math.sqrt(sum(list.map((t) => (t.pnl_pct - avg) ** 2)) / (n - 1)) : 0;
    return { side, n, winRate: n > 0 ? (wins / n) * 100 : 0, total, avg, sd };
  });
}
