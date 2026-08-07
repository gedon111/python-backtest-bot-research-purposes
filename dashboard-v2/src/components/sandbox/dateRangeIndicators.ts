import type { LiveCandle } from '../../api/client';

export interface IndicatorRow extends LiveCandle {
  ema: number;
  macd: number;
  signal: number;
  hist: number;
  atr: number;
  k: number;
  d: number;
  j: number;
}

/**
 * Ported verbatim from gui.js's runDateRangeTester indicator loop
 * (gui.js:1547-1597): EMA200, MACD(12,26,9), ATR(14, SMA-of-TR), KDJ(9,3,3),
 * all recursed forward from the first fetched candle -- including the warmup
 * window the caller is expected to prepend and later trim.
 */
export function computeDateRangeIndicators(data: LiveCandle[]): IndicatorRow[] {
  const trs = data.map((row, i) => {
    if (i === 0) return row.high - row.low;
    const pc = data[i - 1].close;
    return Math.max(row.high - row.low, Math.abs(row.high - pc), Math.abs(row.low - pc));
  });

  let ema200 = data[0].close;
  let ema12 = data[0].close;
  let ema26 = data[0].close;
  let macdSignal = 0;
  let kdjK = 50;
  let kdjD = 50;

  return data.map((row, i) => {
    const { close: c, high: h, low: l } = row;

    ema200 = (c - ema200) * (2 / 201) + ema200;
    ema12 = (c - ema12) * (2 / 13) + ema12;
    ema26 = (c - ema26) * (2 / 27) + ema26;

    const macd = ema12 - ema26;
    macdSignal = (macd - macdSignal) * (2 / 10) + macdSignal;
    const hist = macd - macdSignal;

    const start = Math.max(0, i - 13);
    let sum = 0;
    for (let j = start; j <= i; j++) sum += trs[j];
    const atr = sum / (i - start + 1);

    let ll = l;
    let hh = h;
    for (let j = Math.max(0, i - 8); j <= i; j++) {
      if (data[j].low < ll) ll = data[j].low;
      if (data[j].high > hh) hh = data[j].high;
    }
    const rsv = hh !== ll ? ((c - ll) / (hh - ll)) * 100 : 50;
    kdjK = kdjK * (2 / 3) + rsv * (1 / 3);
    kdjD = kdjD * (2 / 3) + kdjK * (1 / 3);
    const j = 3 * kdjK - 2 * kdjD;

    return { ...row, ema: ema200, macd, signal: macdSignal, hist, atr, k: kdjK, d: kdjD, j };
  });
}
