import { useEffect, useState } from 'react';
import {
  getAblationReconstruction,
  getCandles,
  getCandlesExtended,
  getIterations,
  getManifest,
  getRunsByThreshold,
  getTheme,
  getTrades,
  getVerificationReport,
} from './client';
import type { Candle } from '../types/artifacts';

export interface AsyncResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncResult<T> {
  const [state, setState] = useState<AsyncResult<T>>({ data: null, error: null, loading: true });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, error: null, loading: true });
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ data: null, error, loading: false });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

export const useManifest = () => useAsync(getManifest);
export const useCandles = () => useAsync(getCandles);

/**
 * Lazy, fetch-once-then-cache variant of useAsync -- only pulls
 * candles_extended.json when `enabled` first becomes true (the Chart tab's
 * "Full History" toggle), not on every Chart tab mount. Doesn't use useAsync
 * itself because useAsync's effect fires unconditionally on mount.
 */
export function useExtendedCandles(enabled: boolean): AsyncResult<Candle[]> {
  const [state, setState] = useState<AsyncResult<Candle[]>>({ data: null, error: null, loading: false });

  useEffect(() => {
    if (!enabled || state.data || state.loading) return;
    let cancelled = false;
    setState({ data: null, error: null, loading: true });
    getCandlesExtended()
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ data: null, error, loading: false });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return state;
}
export const useRunsByThreshold = () => useAsync(getRunsByThreshold);
export const useVerificationReport = () => useAsync(getVerificationReport);
export const useTrades = (minObQuality?: number) =>
  useAsync(() => getTrades(minObQuality), [minObQuality]);
export const useTheme = () => useAsync(getTheme);
export const useIterations = () => useAsync(getIterations);
export const useAblationReconstruction = () => useAsync(getAblationReconstruction);
