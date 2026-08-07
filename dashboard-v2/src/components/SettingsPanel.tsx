import './SettingsPanel.css';
import { useDashboardTheme } from '../theme/ThemeContext';
import type { DashboardTheme } from '../types/artifacts';

const COLOR_FIELDS: { key: keyof DashboardTheme['dataColors']; label: string }[] = [
  { key: 'candleUp', label: 'Candle Up' },
  { key: 'candleDown', label: 'Candle Down' },
  { key: 'candleWick', label: 'Candle Wick' },
  { key: 'demand', label: 'Demand Zone' },
  { key: 'supply', label: 'Supply Zone' },
  { key: 'macd', label: 'MACD Line' },
  { key: 'macdSignal', label: 'MACD Signal' },
  { key: 'macdHist', label: 'MACD Hist' },
  { key: 'kdjK', label: 'KDJ K' },
  { key: 'kdjD', label: 'KDJ D' },
  { key: 'kdjJ', label: 'KDJ J' },
  { key: 'atr14', label: 'ATR 14' },
  { key: 'atr200', label: 'ATR 200' },
];

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const { pageTheme, toggleTheme, dataColors, setDataColor } = useDashboardTheme();

  return (
    <>
      <div className="settings-scrim" onClick={onClose} />
      <div className="settings-panel panel">
        <div className="settings-header">
          <span>Settings</span>
          <button type="button" className="btn-toggle" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="settings-row">
          <span>Theme</span>
          <button type="button" className="btn-toggle" onClick={toggleTheme}>
            {pageTheme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
          </button>
        </div>

        <div className="settings-section-title text-muted">Chart Series Colors</div>
        <div className="settings-colors">
          {COLOR_FIELDS.map((f) => (
            <label key={f.key} className="settings-color-field">
              <input
                type="color"
                value={dataColors[f.key]}
                onChange={(e) => setDataColor(f.key, e.target.value)}
              />
              <span>{f.label}</span>
              <code className="text-muted">{dataColors[f.key]}</code>
            </label>
          ))}
        </div>
      </div>
    </>
  );
}
