import { useState } from 'react';
import './App.css';
import { useDashboardTheme } from './theme/ThemeContext';

type TabId = 'chart' | 'sandbox' | 'stats';

const TABS: { id: TabId; label: string }[] = [
  { id: 'chart', label: 'Chart' },
  { id: 'sandbox', label: 'Sandbox' },
  { id: 'stats', label: 'Stats' },
];

export function App() {
  const [tab, setTab] = useState<TabId>('chart');
  const { pageTheme, toggleTheme } = useDashboardTheme();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <span className="topbar-brand">Backtest Terminal</span>
          <span className="topbar-symbol">BTCUSDT · 4H</span>
        </div>
        <nav className="topbar-nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`topbar-nav-item${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <button type="button" className="topbar-btn" onClick={toggleTheme}>
            {pageTheme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>
      </header>
      <main className="app-content">
        {tab === 'chart' && <div className="tab-placeholder">Chart tab -- Stage 4</div>}
        {tab === 'sandbox' && <div className="tab-placeholder">Sandbox tab -- Stage 5</div>}
        {tab === 'stats' && <div className="tab-placeholder">Stats tab -- Stage 6</div>}
      </main>
    </div>
  );
}
