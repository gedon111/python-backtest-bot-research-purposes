import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { getTheme, saveTheme } from '../api/client';
import type { DashboardTheme } from '../types/artifacts';

/** Mirrors the server's own fallback (export_gui_data.py's handle_get_theme,
 * used when chart_theme.json doesn't exist yet) so there's no flash of
 * undefined colors before the initial fetch resolves. */
const DEFAULT_DATA_COLORS: DashboardTheme['dataColors'] = {
  candleUp: '#26a69a',
  candleDown: '#ef5350',
  candleWick: '#475569',
  demand: '#0d9488',
  supply: '#ea580c',
  macd: '#1d4ed8',
  macdSignal: '#f97316',
  macdHist: '#10b981',
  kdjK: '#0d9488',
  kdjD: '#3b82f6',
  kdjJ: '#ec4899',
  atr14: '#8b5cf6',
  atr200: '#6b7280',
};

interface ThemeContextValue {
  pageTheme: 'light' | 'dark';
  dataColors: DashboardTheme['dataColors'];
  loaded: boolean;
  toggleTheme: () => void;
  setDataColor: (key: keyof DashboardTheme['dataColors'], value: string) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pageTheme, setPageTheme] = useState<'light' | 'dark'>('dark');
  const [dataColors, setDataColors] = useState<DashboardTheme['dataColors']>(DEFAULT_DATA_COLORS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getTheme()
      .then((theme) => {
        if (cancelled) return;
        setPageTheme(theme.pageTheme);
        setDataColors(theme.dataColors);
        setLoaded(true);
      })
      .catch(() => {
        // No persisted theme yet (or backend unreachable) -- keep the
        // dark-native defaults above rather than blocking render on it.
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', pageTheme);
  }, [pageTheme]);

  const persist = (next: DashboardTheme) => {
    saveTheme(next).catch(() => {
      /* best-effort persistence; local UI state already reflects the change */
    });
  };

  const toggleTheme = () => {
    const next: 'light' | 'dark' = pageTheme === 'dark' ? 'light' : 'dark';
    setPageTheme(next);
    persist({ pageTheme: next, dataColors });
  };

  const setDataColor = (key: keyof DashboardTheme['dataColors'], value: string) => {
    const next = { ...dataColors, [key]: value };
    setDataColors(next);
    persist({ pageTheme, dataColors: next });
  };

  const value = useMemo(
    () => ({ pageTheme, dataColors, loaded, toggleTheme, setDataColor }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pageTheme, dataColors, loaded],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useDashboardTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useDashboardTheme must be used within a ThemeProvider');
  return ctx;
}
