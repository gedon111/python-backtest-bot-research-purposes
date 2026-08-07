import { useState } from 'react';
import './App.css';
import { useDashboardTheme } from './theme/ThemeContext';
import { ChartTab } from './components/tabs/ChartTab';
import { SandboxTab } from './components/tabs/SandboxTab';
import { StatsTab } from './components/tabs/StatsTab';
import { SettingsPanel } from './components/SettingsPanel';

type TabId = 'chart' | 'sandbox' | 'stats';

const TABS: { id: TabId; label: string }[] = [
  { id: 'chart', label: 'Chart' },
  { id: 'sandbox', label: 'Sandbox' },
  { id: 'stats', label: 'Stats' },
];

export function App() {
  const [tab, setTab] = useState<TabId>('chart');
  const [settingsOpen, setSettingsOpen] = useState(false);
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
          <button type="button" className="topbar-btn" onClick={() => setSettingsOpen(true)}>
            Settings
          </button>
        </div>
      </header>
      <main className="app-content">
        {tab === 'chart' && <ChartTab />}
        {tab === 'sandbox' && <SandboxTab />}
        {tab === 'stats' && <StatsTab />}
      </main>
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
