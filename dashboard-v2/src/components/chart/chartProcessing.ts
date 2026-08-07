import type { Candle, OrderBlockRecord, RunTradeRecord } from '../../types/artifacts';

export interface ProcessedOb extends OrderBlockRecord {
  exactIdx: number;
  endIdx: number;
  startTime: number;
  endTime: number;
}

export interface ProcessedTrade extends RunTradeRecord {
  obBar: number;
  adaptivePeriod: number;
  adaptiveKdjK: { time: number; value: number }[];
  adaptiveKdjD: { time: number; value: number }[];
  adaptiveKdjJ: { time: number; value: number }[];
  startTime: number;
  endTime: number;
  hitTp: boolean;
}

/**
 * Bar indices of Order Blocks that were the actual entry trigger for a
 * trade -- used to default the chart's OB rendering to "relevant only"
 * instead of every detected OB. Deliberately does NOT fall back to
 * `entry_idx` the way `processTrades`'s internal `obBar` does below: that
 * fallback is a UI convenience for the adaptive-period window math, not a
 * real claim that a trade came from a specific OB, and using it here would
 * wrongly mark unrelated OBs as "used."
 */
export function usedObBars(trades: RunTradeRecord[]): Set<number> {
  const set = new Set<number>();
  for (const t of trades) {
    const bar = t.entry_ob_bar ?? t.ob_bar;
    if (bar != null) set.add(bar);
  }
  return set;
}

/**
 * Ported from gui.js's processData (gui.js:416-469) OB half. Finds where an OB
 * zone visually ends: scan forward up to 500 bars until price closes back
 * through the zone, or the OB's own recorded mitigation bar, whichever first.
 */
export function processObs(
  candles: Candle[],
  obs: OrderBlockRecord[],
  levelFilter: string,
  structureFilter: string,
  usedBars: Set<number> | null = null,
): ProcessedOb[] {
  const filtered = obs.filter(
    (ob) =>
      (levelFilter === 'all' || ob.level === levelFilter) &&
      (structureFilter === 'all' || ob.structure === structureFilter) &&
      (usedBars === null || usedBars.has(ob.ob_bar ?? ob.created_at)),
  );

  const processed: ProcessedOb[] = [];
  for (const ob of filtered) {
    const exactIdx = ob.ob_bar ?? ob.created_at;
    if (exactIdx == null || exactIdx < 0 || exactIdx >= candles.length) continue;

    let endIdx = exactIdx;
    for (let i = exactIdx + 1; i < Math.min(exactIdx + 501, candles.length); i++) {
      endIdx = i;
      if (ob.type === 'DEMAND' && candles[i].close < ob.bottom) break;
      if (ob.type === 'SUPPLY' && candles[i].close > ob.top) break;
      if (ob.mitigated_at != null && i >= ob.mitigated_at) {
        endIdx = ob.mitigated_at;
        break;
      }
    }

    processed.push({
      ...ob,
      exactIdx,
      endIdx,
      startTime: candles[exactIdx].time,
      endTime: candles[endIdx].time,
    });
  }
  return processed;
}

/**
 * Ported from gui.js's processData trade half (gui.js:473-539) and
 * updateKdjModeIndicator's adaptive-KDJ recursion. One deliberate correction:
 * gui.js reads `t.tp`/`t.sl`, fields that don't exist on any real trade record
 * (only `take_profit`/`stop_loss` do), so its fallback ATR approximation fired
 * unconditionally and its chart never drew a trade's actual recorded risk
 * levels -- a real bug, flagged this session and fixed per instruction: this
 * version reads take_profit/stop_loss directly.
 */
export function processTrades(candles: Candle[], trades: RunTradeRecord[]): ProcessedTrade[] {
  const processed: ProcessedTrade[] = [];

  for (const t of trades) {
    if (t.entry_idx == null || t.exit_idx == null || t.entry_idx >= candles.length) continue;

    const obBar = t.entry_ob_bar ?? t.ob_bar ?? t.entry_idx;
    const period = Math.max(1, t.entry_idx - obBar);

    const adaptiveKdjK: { time: number; value: number }[] = [];
    const adaptiveKdjD: { time: number; value: number }[] = [];
    const adaptiveKdjJ: { time: number; value: number }[] = [];

    let k = candles[t.entry_idx].K ?? 50;
    let d = candles[t.entry_idx].D ?? 50;
    const alpha = 1 / 3;

    const lastIdx = Math.min(t.exit_idx, candles.length - 1);
    for (let i = t.entry_idx; i <= lastIdx; i++) {
      if (i > t.entry_idx) {
        const windowStart = Math.max(0, i - period + 1);
        let highest = -Infinity;
        let lowest = Infinity;
        for (let w = windowStart; w <= i; w++) {
          if (candles[w].high > highest) highest = candles[w].high;
          if (candles[w].low < lowest) lowest = candles[w].low;
        }
        const denom = highest - lowest;
        const rsv = denom > 0 ? ((candles[i].close - lowest) / denom) * 100 : 50;
        k = k * (1 - alpha) + rsv * alpha;
        d = d * (1 - alpha) + k * alpha;
      }
      const j = 3 * k - 2 * d;
      const time = candles[i].time;
      adaptiveKdjK.push({ time, value: k });
      adaptiveKdjD.push({ time, value: d });
      adaptiveKdjJ.push({ time, value: j });
    }

    processed.push({
      ...t,
      obBar,
      adaptivePeriod: period,
      adaptiveKdjK,
      adaptiveKdjD,
      adaptiveKdjJ,
      startTime: candles[t.entry_idx].time,
      endTime: candles[lastIdx].time,
      hitTp: t.pnl_pct > 0,
    });
  }

  return processed;
}
