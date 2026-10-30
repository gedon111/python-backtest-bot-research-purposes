import type { Candle, TradeRecord } from '../../types/artifacts';

/**
 * Dollar equity curves for the Stats tab's comparison graphic, recomputed in
 * the browser from candles.json + /api/trades -- independent of the Python
 * side, mirroring research_analysis.py's _run_ob_gated_arm (compound each
 * trade's pnl_pct on its exit bar) and _run_dca_dollar_arm (starting capital
 * split evenly across ISO weeks, bought at each week's first-bar close).
 *
 * One deliberate presentation difference: the DCA curve here is holdings PLUS
 * the cash not yet invested, so both lines start at the same $10,000 and are
 * comparable on one axis. At the last weekly buy all cash is invested, so the
 * DCA value there equals the published final_capital exactly.
 */
export interface CurvePoint {
  time: number;
  strategy: number;
  dca: number;
}

export interface BenchmarkCurves {
  points: CurvePoint[];
  /** strategy value at the last weekly buy (the chart's final point) */
  strategyFinal: number;
  dcaFinalAtLastBuy: number;
  nWeeks: number;
}

/** ISO-8601 week key ("2022-W52") of a unix-seconds UTC timestamp. */
function isoWeekKey(unixSeconds: number): string {
  const d = new Date(unixSeconds * 1000);
  const day = (d.getUTCDay() + 6) % 7; // Mon=0..Sun=6
  const thursday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - day + 3));
  const isoYear = thursday.getUTCFullYear();
  const jan4 = new Date(Date.UTC(isoYear, 0, 4));
  const week = 1 + Math.round((thursday.getTime() - jan4.getTime()) / 86_400_000 / 7 - 3 / 7 + ((jan4.getUTCDay() + 6) % 7) / 7);
  return `${isoYear}-W${week}`;
}

export function computeBenchmarkCurves(
  candles: Candle[],
  baseTrades: TradeRecord[],
  startingCapital: number,
): BenchmarkCurves {
  const n = candles.length;
  const idxByTime = new Map(candles.map((c, i) => [c.time, i]));

  const exitPnlByBar = new Map<number, number>();
  for (const t of baseTrades) {
    const i = idxByTime.get(t.exit_time);
    if (i == null) throw new Error(`trade ${t.trade_id}: exit_time ${t.exit_time} not in candles`);
    exitPnlByBar.set(i, t.pnl_pct);
  }

  const seenWeeks = new Set<string>();
  const contributionBars = new Set<number>();
  candles.forEach((c, i) => {
    const k = isoWeekKey(c.time);
    if (!seenWeeks.has(k)) {
      seenWeeks.add(k);
      contributionBars.add(i);
    }
  });
  const nWeeks = contributionBars.size;
  const contribution = startingCapital / nWeeks;
  const lastBuyBar = Math.max(...contributionBars);

  let strategy = startingCapital;
  let units = 0;
  let cash = startingCapital;
  let dcaFinalAtLastBuy = NaN;
  const points: CurvePoint[] = [];
  for (let i = 0; i < n; i++) {
    const close = candles[i].close;
    if (i > 0 && exitPnlByBar.has(i)) strategy *= 1 + exitPnlByBar.get(i)! / 100;
    if (contributionBars.has(i)) {
      units += contribution / close;
      cash -= contribution;
    }
    const dca = units * close + Math.max(cash, 0);
    if (i === lastBuyBar) {
      // The chart ends here: DCA's published final_capital is valued at its
      // last weekly buy, so both lines stop on the same bar as published.
      dcaFinalAtLastBuy = units * close;
      points.push({ time: candles[i].time, strategy, dca });
      break;
    }
    // one point per UTC day (its last 4h bar), plus the final bar
    const nextDay = i + 1 < n ? Math.floor(candles[i + 1].time / 86_400) : -1;
    if (nextDay !== Math.floor(candles[i].time / 86_400)) points.push({ time: candles[i].time, strategy, dca });
  }
  return { points, strategyFinal: strategy, dcaFinalAtLastBuy, nWeeks };
}
