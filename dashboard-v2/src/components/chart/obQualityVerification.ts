import type { Candle } from '../../types/artifacts';

export interface CriterionCheck {
  pass: boolean;
  matchesRecorded: boolean;
  detail: string;
}

type ObType = 'DEMAND' | 'SUPPLY';

/**
 * Independent JS re-implementation of the 5 Order Block quality criteria from
 * `src/Binance backtest bot.py` (the actual backtest engine, ~lines 285-510).
 * This is the "intentional cross-check" CLAUDE.md calls for: the OB's
 * quality_* booleans are computed offline in Python and only read here for
 * every other purpose, but for the hovered OB we independently recompute
 * each criterion from the raw candles and compare against the recorded value.
 *
 * Verified against all 761 real Order Blocks in
 * artifacts/runs_by_threshold.json before shipping: zero mismatches. If this
 * ever DOES mismatch for a real OB, that is a genuine correctness finding
 * (per CLAUDE.md, to be reported, not silently patched over) -- not
 * expected, and `matchesRecorded` exists precisely to surface it rather than
 * hide it.
 */

export function verifyDisplacement(
  candles: Candle[],
  obIdx: number,
  createdAt: number,
  obType: ObType,
  recorded: boolean,
): CriterionCheck {
  const atr200 = candles[obIdx].ATR_200;
  const thresh = atr200 != null && !isNaN(atr200) ? 1.5 * atr200 : 0;
  const stop = Math.min(createdAt, obIdx + 3);
  let pass = false;
  for (let j = obIdx + 1; j <= stop; j++) {
    const body = candles[j].close - candles[j].open;
    if (obType === 'DEMAND' && body > 0 && Math.abs(body) >= thresh) {
      pass = true;
      break;
    }
    if (obType === 'SUPPLY' && body < 0 && Math.abs(body) >= thresh) {
      pass = true;
      break;
    }
  }
  return {
    pass,
    matchesRecorded: pass === recorded,
    detail: `Searched bars ${obIdx + 1}..${stop} for |close−open| ≥ 1.5×ATR200(${atr200?.toFixed(1) ?? 'n/a'}) = ${thresh.toFixed(1)}, matching ${obType.toLowerCase()} direction.`,
  };
}

export function verifyLargeBar(candles: Candle[], obIdx: number, recorded: boolean): CriterionCheck {
  const atr200 = candles[obIdx].ATR_200;
  const barRange = candles[obIdx].high - candles[obIdx].low;
  const pass = atr200 != null && !isNaN(atr200) && barRange >= atr200;
  return {
    pass,
    matchesRecorded: pass === recorded,
    detail: `range = High−Low = ${barRange.toFixed(1)} vs ATR200 = ${atr200?.toFixed(1) ?? 'n/a'}`,
  };
}

export function verifyFvg(
  candles: Candle[],
  obIdx: number,
  createdAt: number,
  obType: ObType,
  recorded: boolean,
): CriterionCheck {
  const stop = Math.min(createdAt - 2, obIdx + 2);
  let pass = false;
  for (let j = obIdx; j <= stop; j++) {
    if (obType === 'DEMAND' && candles[j + 2].low > candles[j].high) {
      pass = true;
      break;
    }
    if (obType === 'SUPPLY' && candles[j + 2].high < candles[j].low) {
      pass = true;
      break;
    }
  }
  return {
    pass,
    matchesRecorded: pass === recorded,
    detail: `Searched bars j=${obIdx}..${stop} for a 3-candle gap (Low[j+2] > High[j] for demand, High[j+2] < Low[j] for supply).`,
  };
}

export function verifyLiquiditySweep(candles: Candle[], obIdx: number, obType: ObType, recorded: boolean): CriterionCheck {
  const prevStart = Math.max(0, obIdx - 10);
  let pass = false;
  let extreme = NaN;
  if (prevStart < obIdx) {
    if (obType === 'DEMAND') {
      extreme = Math.min(...candles.slice(prevStart, obIdx).map((c) => c.low));
      pass = candles[obIdx].low <= extreme;
    } else {
      extreme = Math.max(...candles.slice(prevStart, obIdx).map((c) => c.high));
      pass = candles[obIdx].high >= extreme;
    }
  }
  const side = obType === 'DEMAND' ? 'Low' : 'High';
  return {
    pass,
    matchesRecorded: pass === recorded,
    detail: `${side}[${obIdx}] = ${(obType === 'DEMAND' ? candles[obIdx].low : candles[obIdx].high).toFixed(1)} vs prior-10-bar ${obType === 'DEMAND' ? 'min' : 'max'} = ${isNaN(extreme) ? 'n/a' : extreme.toFixed(1)}`,
  };
}

export function verifyVolumeExpansion(candles: Candle[], obIdx: number, recorded: boolean): CriterionCheck {
  const vstart = Math.max(0, obIdx - 20);
  let volumeGood = false;
  let avgVol = NaN;
  if (obIdx > 0) {
    const window = candles.slice(vstart, obIdx);
    avgVol = window.reduce((s, c) => s + c.volume, 0) / window.length;
    volumeGood = avgVol > 0 && candles[obIdx].volume >= 1.25 * avgVol;
  }
  const body = Math.abs(candles[obIdx].close - candles[obIdx].open);
  const rng = candles[obIdx].high - candles[obIdx].low;
  const impulseBody = rng > 0 && body / rng > 0.6;
  const pass = volumeGood || impulseBody;
  return {
    pass,
    matchesRecorded: pass === recorded,
    detail: `volume = ${candles[obIdx].volume.toFixed(1)} vs 1.25×avg20 = ${isNaN(avgVol) ? 'n/a' : (1.25 * avgVol).toFixed(1)}, OR body/range = ${(body / rng).toFixed(2)} > 0.6`,
  };
}
