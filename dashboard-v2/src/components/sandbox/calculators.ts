/** Ported verbatim from gui.js's sandbox calculators (gui.js:1468-1510). */

export function calculateEMA(n: number, close: number, prevEma: number) {
  const multiplier = 2 / (n + 1);
  return (close - prevEma) * multiplier + prevEma;
}

export function calculateMACDSandbox(ema12: number, ema26: number, prevSignal: number) {
  const macdLine = ema12 - ema26;
  const multiplier = 2 / (9 + 1);
  const signalLine = (macdLine - prevSignal) * multiplier + prevSignal;
  const hist = macdLine - signalLine;
  return { macdLine, signalLine, hist };
}

export function calculateATR(n: number, trValues: number[]) {
  const windowVals = trValues.slice(-n);
  if (windowVals.length === 0) return null;
  const sum = windowVals.reduce((a, b) => a + b, 0);
  return { atr: sum / windowVals.length, count: windowVals.length };
}

export function calculateKDJ(close: number, ll: number, hh: number, prevK: number, prevD: number) {
  const rsv = hh !== ll ? ((close - ll) / (hh - ll)) * 100 : 50;
  const k = prevK * (2 / 3) + rsv * (1 / 3);
  const d = prevD * (2 / 3) + k * (1 / 3);
  const j = 3 * k - 2 * d;
  return { rsv, k, d, j };
}
