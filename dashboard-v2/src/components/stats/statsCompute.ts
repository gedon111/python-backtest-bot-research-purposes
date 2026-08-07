import type { TradeRecord } from '../../types/artifacts';
import {
  binomialTestGreater,
  bootstrapPercentileCI,
  computeCorrelationPearson,
  computeCorrelationSpearman,
  fisherExactTwoSided,
  mdeNormalApprox,
  welchTTest,
  type BootstrapCIResult,
  type MdeResult,
  type WelchResult,
} from './statMath';

/** Baseline trade set used across the whole tab: min_ob_quality = 0, gui.js:1913-1914's fallback preserved. */
export function baselineTrades(trades: TradeRecord[]): TradeRecord[] {
  const base = trades.filter((t) => t.min_ob_quality === 0);
  return base.length > 0 ? base : trades;
}

const median = (arr: number[]) => {
  if (arr.length === 0) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 !== 0 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
};

const sum = (arr: number[]) => arr.reduce((a, b) => a + b, 0);

export interface OrthogonalCriterionRow {
  label: string;
  subgroup: 'True' | 'False';
  n: number;
  pctOfTrades: number;
  sumPnl: number;
  pctOfTotalReturn: number;
  meanReturn: number;
  medianReturn: number;
  bestTrade: number;
}

const CRITERIA: { label: string; key: keyof TradeRecord }[] = [
  { label: 'Displacement', key: 'quality_displacement' },
  { label: 'LargeBar', key: 'quality_large_bar' },
  { label: 'FVG', key: 'quality_fvg' },
  { label: 'LiqSweep', key: 'quality_liquidity_sweep' },
  { label: 'VolExpansion', key: 'quality_volume_expansion' },
];

/** Ported from gui.js's renderOrthogonalCriteria (gui.js:2009-2087). */
export function computeOrthogonalCriteria(trades: TradeRecord[]): OrthogonalCriterionRow[] {
  const base = baselineTrades(trades);
  const nTotal = base.length;
  if (nTotal === 0) return [];
  const totalPnl = sum(base.map((t) => t.pnl_pct));

  const rows: OrthogonalCriterionRow[] = [];
  for (const criterion of CRITERIA) {
    for (const subgroup of ['True', 'False'] as const) {
      const list = base.filter((t) => Boolean(t[criterion.key]) === (subgroup === 'True'));
      const n = list.length;
      const pnls = list.map((t) => t.pnl_pct);
      const s = sum(pnls);
      rows.push({
        label: criterion.label,
        subgroup,
        n,
        pctOfTrades: (n / nTotal) * 100,
        sumPnl: s,
        pctOfTotalReturn: totalPnl !== 0 ? (s / totalPnl) * 100 : 0,
        meanReturn: n > 0 ? s / n : 0,
        medianReturn: median(pnls),
        bestTrade: n > 0 ? Math.max(...pnls) : 0,
      });
    }
  }
  return rows;
}

export interface CriterionTestRow {
  label: string;
  trueN: number;
  trueWins: number;
  falseN: number;
  falseWins: number;
  fisherP: number;
  welch: WelchResult;
  mde: MdeResult;
  // Additive: raw pnl_pct values behind trueN/falseN, so the Solutions tab can
  // show how welch.m1/v1 etc. were actually computed, not just state them.
  trueValues: number[];
  falseValues: number[];
}

/**
 * Fisher's exact test (win/loss x criterion-true) and Welch's t-test
 * (pnl_pct x criterion-true), independently per orthogonal criterion, over
 * the N=27 baseline -- the live, in-browser counterpart to
 * analysis/fee_slippage_analysis.py's per-criterion table. Computed
 * entirely from /api/trades, independent of any Python-precomputed value.
 */
export function computeCriteriaTests(trades: TradeRecord[]): CriterionTestRow[] {
  const base = baselineTrades(trades);
  return CRITERIA.map((criterion) => {
    const trueList = base.filter((t) => Boolean(t[criterion.key]));
    const falseList = base.filter((t) => !t[criterion.key]);
    const trueWins = trueList.filter((t) => t.pnl_pct > 0).length;
    const falseWins = falseList.filter((t) => t.pnl_pct > 0).length;
    const fisherP = fisherExactTwoSided(trueWins, trueList.length - trueWins, falseWins, falseList.length - falseWins);
    const welch = welchTTest(
      trueList.map((t) => t.pnl_pct),
      falseList.map((t) => t.pnl_pct)
    );
    const mde = mdeNormalApprox(
      trueList.map((t) => t.pnl_pct),
      falseList.map((t) => t.pnl_pct)
    );
    return {
      label: criterion.label,
      trueN: trueList.length,
      trueWins,
      falseN: falseList.length,
      falseWins,
      fisherP,
      welch,
      mde,
      trueValues: trueList.map((t) => t.pnl_pct),
      falseValues: falseList.map((t) => t.pnl_pct),
    };
  });
}

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

/** Per-threshold descriptive stats, same shape as gui.js's computeAllStatistics (gui.js:1951-1982). Dead code in gui.js (never called/rendered there) but kept available here since it's cheap and correct -- not wired into any UI section unless a future pass needs it. */
export function computeAllStatistics(trades: TradeRecord[]) {
  const byThreshold: Record<number, { n: number; wins: number; wr: number; total: number; avg: number; sd: number; binomP: number }> = {};
  for (const q of [0, 1, 2, 3]) {
    const list = trades.filter((t) => t.min_ob_quality === q);
    const n = list.length;
    const wins = list.filter((t) => t.pnl_pct > 0).length;
    const wr = n > 0 ? (wins / n) * 100 : 0;
    const total = sum(list.map((t) => t.pnl_pct));
    const avg = n > 0 ? total / n : 0;
    const sd = n > 1 ? Math.sqrt(sum(list.map((t) => (t.pnl_pct - avg) ** 2)) / (n - 1)) : 0;
    byThreshold[q] = { n, wins, wr, total, avg, sd, binomP: binomialTestGreater(n, wins, 0.5) };
  }
  return byThreshold;
}
