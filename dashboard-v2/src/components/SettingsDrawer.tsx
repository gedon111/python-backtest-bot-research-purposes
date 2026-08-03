import { DARK_PRESET, LIGHT_PRESET, useDashboardTheme } from '../theme/ThemeContext';
import type { DashboardTheme } from '../types/artifacts';

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
}

type ColorKey = keyof DashboardTheme['dataColors'];

const COLOR_GROUPS: { title: string; items: { key: ColorKey; label: string }[] }[] = [
  {
    title: 'Candles',
    items: [
      { key: 'candleUp', label: 'Bullish Candle' },
      { key: 'candleDown', label: 'Bearish Candle' },
      { key: 'candleWick', label: 'Wicks' },
    ],
  },
  {
    title: 'Order Blocks',
    items: [
      { key: 'demand', label: 'Demand Zone' },
      { key: 'supply', label: 'Supply Zone' },
    ],
  },
  {
    title: 'MACD Pane',
    items: [
      { key: 'macd', label: 'MACD Line' },
      { key: 'macdSignal', label: 'Signal Line' },
      { key: 'macdHist', label: 'Histogram' },
    ],
  },
  {
    title: 'KDJ Pane',
    items: [
      { key: 'kdjK', label: 'K Line' },
      { key: 'kdjD', label: 'D Line' },
      { key: 'kdjJ', label: 'J Line' },
    ],
  },
  {
    title: 'ATR Pane',
    items: [
      { key: 'atr14', label: 'ATR(14)' },
      { key: 'atr200', label: 'ATR(200)' },
    ],
  },
];

/** Normalizes to a 6-digit hex so it's always a valid <input type="color"> value. */
function toSixDigitHex(hex: string): string {
  const match = /^#?([a-f\d]{6})/i.exec(hex);
  return match ? `#${match[1]}` : '#808080';
}

export function SettingsDrawer({ open, onClose }: SettingsDrawerProps) {
  const { pageTheme, dataColors, setPageTheme, setDataColors, applyPreset } = useDashboardTheme();

  if (!open) return null;

  const setColor = (key: ColorKey, value: string) => {
    setDataColors({ ...dataColors, [key]: value });
  };

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label="Chart Settings">
        <div className="drawer-header">
          <h3>Chart Settings</h3>
          <button type="button" className="drawer-close-btn" onClick={onClose} aria-label="Close settings">
            &times;
          </button>
        </div>
        <div className="drawer-body">
          <div className="drawer-section">
            <h4>Page Theme</h4>
            <div className="theme-switch-row">
              <span>Dark Mode (Page Chrome)</span>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={pageTheme === 'dark'}
                  onChange={(e) => setPageTheme(e.target.checked ? 'dark' : 'light')}
                />
                <span className="slider" />
              </label>
            </div>
          </div>

          <div className="drawer-section">
            <h4>Presets</h4>
            <div className="preset-row">
              <button type="button" className="btn-preset" onClick={() => applyPreset(LIGHT_PRESET)}>
                Load Light Preset
              </button>
              <button type="button" className="btn-preset" onClick={() => applyPreset(DARK_PRESET)}>
                Load Dark Preset
              </button>
            </div>
            <div className="preset-row" style={{ marginTop: '0.5rem' }}>
              <button type="button" className="btn-preset" onClick={() => applyPreset(LIGHT_PRESET)}>
                Reset to Defaults
              </button>
            </div>
          </div>

          {COLOR_GROUPS.map((group) => (
            <div className="drawer-section" key={group.title}>
              <h4>{group.title}</h4>
              {group.items.map((item) => (
                <div className="picker-item" key={item.key}>
                  <span>{item.label}</span>
                  <span className="color-swatch-btn">
                    <input
                      type="color"
                      value={toSixDigitHex(dataColors[item.key])}
                      onChange={(e) => setColor(item.key, e.target.value)}
                      aria-label={item.label}
                    />
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
