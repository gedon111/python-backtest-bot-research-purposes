import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { DashboardTheme } from '../types/artifacts';
import { getTheme, saveTheme } from '../api/client';

/**
 * Verbatim from gui.js's LIGHT_PRESET/DARK_PRESET (gui.js:3-33) -- these are the
 * chart data-series colors, distinct from the app shell's design-token palette in
 * theme.css. Kept as-is: this is a user-editable cosmetic setting, not a figure
 * in the paper, so there's nothing to "correct" here.
 */
export const LIGHT_PRESET: DashboardTheme['dataColors'] = {
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

export const DARK_PRESET: DashboardTheme['dataColors'] = {
  candleUp: '#26a69a',
  candleDown: '#ef5350',
  candleWick: '#475569',
  demand: '#00f0ff',
  supply: '#f97316',
  macd: '#3b82f6',
  macdSignal: '#f97316',
  macdHist: '#22c55e',
  kdjK: '#00f0ff',
  kdjD: '#3b82f6',
  kdjJ: '#f43f5e',
  atr14: '#a78bfa',
  atr200: '#94a3b8',
};

interface DashboardThemeContextValue {
  pageTheme: 'light' | 'dark';
  dataColors: DashboardTheme['dataColors'];
  setPageTheme: (theme: 'light' | 'dark') => void;
  setDataColors: (colors: DashboardTheme['dataColors']) => void;
  applyPreset: (preset: DashboardTheme['dataColors']) => void;
}

const DashboardThemeContext = createContext<DashboardThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pageTheme, setPageThemeState] = useState<'light' | 'dark'>('light');
  const [dataColors, setDataColorsState] = useState<DashboardTheme['dataColors']>(LIGHT_PRESET);

  // Load order matches gui.js's loadThemeSettings: server default, then
  // localStorage override on top (gui.js:1184-1208).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let next: DashboardTheme = { pageTheme: 'light', dataColors: LIGHT_PRESET };
      try {
        const remote = await getTheme();
        next = { pageTheme: remote.pageTheme || 'light', dataColors: { ...LIGHT_PRESET, ...remote.dataColors } };
      } catch {
        // no server theme yet -- fall through to defaults
      }
      const localTheme = localStorage.getItem('pageTheme');
      if (localTheme === 'light' || localTheme === 'dark') next.pageTheme = localTheme;
      const localColors = localStorage.getItem('dataColors');
      if (localColors) {
        try {
          next.dataColors = { ...next.dataColors, ...JSON.parse(localColors) };
        } catch {
          // ignore malformed cache
        }
      }
      if (!cancelled) {
        setPageThemeState(next.pageTheme);
        setDataColorsState(next.dataColors);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', pageTheme);
  }, [pageTheme]);

  const persist = (theme: 'light' | 'dark', colors: DashboardTheme['dataColors']) => {
    localStorage.setItem('pageTheme', theme);
    localStorage.setItem('dataColors', JSON.stringify(colors));
    saveTheme({ pageTheme: theme, dataColors: colors }).catch(() => {
      // best-effort, matches gui.js's saveThemeSettings (gui.js:1210-1226)
    });
  };

  const setPageTheme = (theme: 'light' | 'dark') => {
    setPageThemeState(theme);
    persist(theme, dataColors);
  };

  const setDataColors = (colors: DashboardTheme['dataColors']) => {
    setDataColorsState(colors);
    persist(pageTheme, colors);
  };

  const applyPreset = (preset: DashboardTheme['dataColors']) => setDataColors(preset);

  const value = useMemo(
    () => ({ pageTheme, dataColors, setPageTheme, setDataColors, applyPreset }),
    [pageTheme, dataColors],
  );

  return <DashboardThemeContext.Provider value={value}>{children}</DashboardThemeContext.Provider>;
}

export function useDashboardTheme() {
  const ctx = useContext(DashboardThemeContext);
  if (!ctx) throw new Error('useDashboardTheme must be used within a ThemeProvider');
  return ctx;
}
