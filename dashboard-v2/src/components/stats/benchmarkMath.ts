/**
 * Independent JS re-derivation of the Sharpe/Sortino/Max-Drawdown benchmark
 * analysis in analysis/benchmark_vs_passive.py and
 * analysis/benchmark_dca_analysis.py -- ported formula-for-formula (same
 * definitions, same computation order) from those two files, not imported
 * from them and not fetching their JSON output. Per CLAUDE.md, this
 * dashboard's stats module is a deliberately INDEPENDENT cross-check of the
 * Python backtest; the Python figures appear only as a labelled comparison
 * (see derivationSteps.ts's benchmark cards), never as the source of these
 * numbers. If the two disagree, that is a finding to report, not to paper
 * over by tuning this file to match.
 *
 * Formula sources:
 *   - analysis/benchmark_dca_analysis.py:54-85 (PERIODS_PER_YEAR_4H/_WEEKLY,
 *     max_drawdown_pct, sharpe_sortino)
 *   - analysis/benchmark_vs_passive.py:212-329 (strategy_arm/dca_arm/lump_sum_arm)
 */
import type { Candle, TradeRecord } from '../../types/artifacts';

export const PERIODS_PER_YEAR_4H = 6 * 365.25;
export const PERIODS_PER_YEAR_WEEKLY = 52;

export interface MaxDrawdownResult {
  minDd: number;
  troughIndex: number;
  troughEquity: number;
  troughRunningMax: number;
}

/** min_t (E_t - runningMax_t)/runningMax_t * 100 -- benchmark_dca_analysis.py:72-75. */
export function maxDrawdownPct(equity: number[]): MaxDrawdownResult {
  let runningMax = -Infinity;
  let minDd = Infinity;
  let troughIndex = 0;
  let troughEquity = equity[0];
  let troughRunningMax = equity[0];
  for (let i = 0; i < equity.length; i++) {
    const e = equity[i];
    if (e > runningMax) runningMax = e;
    const dd = ((e - runningMax) / runningMax) * 100;
    if (dd < minDd) {
      minDd = dd;
      troughIndex = i;
      troughEquity = e;
      troughRunningMax = runningMax;
    }
  }
  return { minDd, troughIndex, troughEquity, troughRunningMax };
}

export interface SharpeSortinoResult {
  n: number;
  meanR: number;
  stdR: number; // sample SD, ddof=1
  sharpe: number;
  downsideDev: number; // sqrt(mean(min(r,0)^2)), ddof=0
  sortino: number;
}

/** benchmark_dca_analysis.py:78-85 -- risk-free rate 0, annualized by sqrt(periodsPerYear). */
export function sharpeSortino(barReturns: number[], periodsPerYear: number): SharpeSortinoResult {
  const n = barReturns.length;
  const meanR = barReturns.reduce((s, r) => s + r, 0) / n;
  const variance = n > 1 ? barReturns.reduce((s, r) => s + (r - meanR) ** 2, 0) / (n - 1) : 0;
  const stdR = Math.sqrt(variance);
  const sharpe = stdR > 0 ? (meanR / stdR) * Math.sqrt(periodsPerYear) : NaN;
  const downsideSqMean = barReturns.reduce((s, r) => s + Math.min(r, 0) ** 2, 0) / n;
  const downsideDev = Math.sqrt(downsideSqMean);
  const sortino = downsideDev > 0 ? (meanR / downsideDev) * Math.sqrt(periodsPerYear) : NaN;
  return { n, meanR, stdR, sharpe, downsideDev, sortino };
}

function pctChange(series: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < series.length; i++) out.push((series[i] - series[i - 1]) / series[i - 1]);
  return out;
}

export interface EquityPoint {
  index: number;
  time: number;
  equity: number;
}

export interface ArmResult {
  arm: string;
  startingCapital: number;
  /** Number of bars in the priced window (candles.length) -- the strategy/lump-sum equity series has exactly this many points; the DCA arm samples only nContributions of them. */
  nBars: number;
  totalReturnPct: number;
  finalCapital: number;
  timeInMarketPct: number;
  /** First few points, to illustrate the equity-curve construction without enumerating every bar. */
  equitySample: EquityPoint[];
  troughPoint: EquityPoint & { runningMax: number };
  maxDrawdownPct: number;
  returns: SharpeSortinoResult;
  periodsPerYear: number;
  dragPct: number;
}

/** ISO-8601 (year, week) for a unix-second timestamp, UTC, Thursday rule -- matches pandas' .dt.isocalendar(). */
export function isoWeek(timeSec: number): { year: number; week: number } {
  const d = new Date(timeSec * 1000);
  const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dayNum = date.getUTCDay() || 7; // Mon=1 .. Sun=7
  date.setUTCDate(date.getUTCDate() + 4 - dayNum); // Thursday of this ISO week
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return { year: date.getUTCFullYear(), week };
}

/** First bar index of every ISO calendar week in `candles` -- same grouping idiom as benchmark_vs_passive.py's _iso_week_first_bars. */
export function isoWeekFirstBars(candles: Candle[]): number[] {
  const firstByWeek = new Map<string, number>();
  candles.forEach((c, i) => {
    const { year, week } = isoWeek(c.time);
    const key = `${year}-W${week}`;
    if (!firstByWeek.has(key)) firstByWeek.set(key, i);
  });
  return [...firstByWeek.values()].sort((a, b) => a - b);
}

/** Arm A -- benchmark_vs_passive.py:212-251. Event-driven equity curve, flat between trades, compounds only at each trade's exit bar. `baselineTrades` must already be the min_ob_quality=0 filtered set (statsCompute.ts's baselineTrades). */
export function strategyArm(candles: Candle[], baselineTrades: TradeRecord[], startingCapital: number, dragPct = 0): ArmResult {
  const nBars = candles.length;
  const timeIndex = new Map<number, number>();
  candles.forEach((c, i) => timeIndex.set(c.time, i));

  const exitMap = new Map<number, number>();
  for (const t of baselineTrades) {
    const exitIdx = timeIndex.get(t.exit_time);
    if (exitIdx != null) exitMap.set(exitIdx, t.pnl_pct - dragPct);
  }

  const equity = new Array<number>(nBars);
  equity[0] = startingCapital;
  let eq = startingCapital;
  for (let i = 1; i < nBars; i++) {
    const adjPnl = exitMap.get(i);
    if (adjPnl != null) eq *= 1 + adjPnl / 100;
    equity[i] = eq;
  }

  const totalReturnPct = baselineTrades.reduce((s, t) => s + (t.pnl_pct - dragPct), 0);
  const holdBarsSum = baselineTrades.reduce((s, t) => s + t.hold_bars, 0);
  const timeInMarketPct = (holdBarsSum / nBars) * 100;
  const returns = sharpeSortino(pctChange(equity), PERIODS_PER_YEAR_4H);
  const dd = maxDrawdownPct(equity);

  return {
    arm: 'OB-gated strategy',
    startingCapital,
    nBars,
    totalReturnPct,
    finalCapital: equity[nBars - 1],
    timeInMarketPct,
    equitySample: equity.slice(0, 5).map((e, i) => ({ index: i, time: candles[i].time, equity: e })),
    troughPoint: { index: dd.troughIndex, time: candles[dd.troughIndex].time, equity: dd.troughEquity, runningMax: dd.troughRunningMax },
    maxDrawdownPct: dd.minDd,
    returns,
    periodsPerYear: PERIODS_PER_YEAR_4H,
    dragPct,
  };
}

export interface DcaArmResult extends ArmResult {
  nContributions: number;
  contributionPerWeek: number;
}

/** Arm B -- benchmark_vs_passive.py:265-308. Weekly DCA, bought at each ISO week's first-bar CLOSE. Sharpe/Sortino/MaxDD are computed on the weekly-sampled series, not every 4h bar -- matches Python exactly. */
export function dcaArm(candles: Candle[], startingCapital: number, dragPct = 0): DcaArmResult {
  const nBars = candles.length;
  const contributionBars = isoWeekFirstBars(candles);
  const nWeeks = contributionBars.length;
  const contribution = startingCapital / nWeeks;
  const contributionSet = new Set(contributionBars);

  let units = 0;
  const value = new Array<number>(nBars);
  for (let i = 0; i < nBars; i++) {
    const px = candles[i].close;
    if (contributionSet.has(i)) {
      const buyPx = px * (1 + dragPct / 100);
      units += contribution / buyPx;
    }
    value[i] = units * px;
  }

  const V = contributionBars.map((i) => value[i]);
  const C = contributionBars.map(() => contribution);
  const r: number[] = [];
  for (let k = 1; k < V.length; k++) r.push((V[k] - C[k]) / V[k - 1] - 1);

  const returns = sharpeSortino(r, PERIODS_PER_YEAR_WEEKLY);
  const dd = maxDrawdownPct(V);
  const totalContributed = C.reduce((s, c) => s + c, 0);
  const finalValue = V[V.length - 1];
  const totalReturnPct = ((finalValue - totalContributed) / totalContributed) * 100;
  const troughBarIdx = contributionBars[dd.troughIndex];

  return {
    arm: 'Weekly DCA into BTC',
    startingCapital,
    nBars,
    totalReturnPct,
    finalCapital: finalValue,
    timeInMarketPct: 100,
    equitySample: contributionBars.slice(0, 5).map((i) => ({ index: i, time: candles[i].time, equity: value[i] })),
    troughPoint: { index: troughBarIdx, time: candles[troughBarIdx].time, equity: dd.troughEquity, runningMax: dd.troughRunningMax },
    maxDrawdownPct: dd.minDd,
    returns,
    periodsPerYear: PERIODS_PER_YEAR_WEEKLY,
    dragPct,
    nContributions: nWeeks,
    contributionPerWeek: contribution,
  };
}

/** Arm C -- benchmark_vs_passive.py:311-329. All capital deployed at the window's first bar's OPEN price. */
export function lumpSumArm(candles: Candle[], startingCapital: number, dragPct = 0): ArmResult {
  const nBars = candles.length;
  const open0 = candles[0].open * (1 + dragPct / 100);
  const units = startingCapital / open0;
  const equity = candles.map((c) => units * c.close);
  const totalReturnPct = ((equity[nBars - 1] - startingCapital) / startingCapital) * 100;
  const returns = sharpeSortino(pctChange(equity), PERIODS_PER_YEAR_4H);
  const dd = maxDrawdownPct(equity);

  return {
    arm: 'Lump-sum buy-and-hold',
    startingCapital,
    nBars,
    totalReturnPct,
    finalCapital: equity[nBars - 1],
    timeInMarketPct: 100,
    equitySample: equity.slice(0, 5).map((e, i) => ({ index: i, time: candles[i].time, equity: e })),
    troughPoint: { index: dd.troughIndex, time: candles[dd.troughIndex].time, equity: dd.troughEquity, runningMax: dd.troughRunningMax },
    maxDrawdownPct: dd.minDd,
    returns,
    periodsPerYear: PERIODS_PER_YEAR_4H,
    dragPct,
  };
}
