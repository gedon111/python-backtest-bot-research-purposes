import { useEffect, useState } from 'react';
import {
  getCandles,
  getIterations,
  getManifest,
  getRunsByThreshold,
  getTheme,
  getTrades,
  getVerificationReport,
} from './client';

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
export const useRunsByThreshold = () => useAsync(getRunsByThreshold);
export const useVerificationReport = () => useAsync(getVerificationReport);
export const useTrades = (minObQuality?: number) =>
  useAsync(() => getTrades(minObQuality), [minObQuality]);
export const useTheme = () => useAsync(getTheme);
export const useIterations = () => useAsync(getIterations);
