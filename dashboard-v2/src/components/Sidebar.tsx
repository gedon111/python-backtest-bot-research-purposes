export type TabId = 'chart' | 'sandbox' | 'stats';

const TABS: { id: TabId; label: string }[] = [
  { id: 'chart', label: 'Chart' },
  { id: 'sandbox', label: 'Formula Sandbox' },
  { id: 'stats', label: 'Research Statistics & Methodology Synthesis' },
];

interface SidebarProps {
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  onOpenSettings: () => void;
}

/**
 * Structural stub only — mirrors gui.html's 3 real tabs (chart-tab, sandbox-tab,
 * stats-tab; gui.html:20,24,28). No visual design yet; that comes from the
 * separate Claude Design pass.
 */
export function Sidebar({ activeTab, onSelectTab, onOpenSettings }: SidebarProps) {
  return (
    <nav className="sidebar" aria-label="Dashboard sections">
      <h2>Backtest Bot</h2>
      <div className="nav-items">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`nav-item${activeTab === tab.id ? ' active' : ''}`}
            data-tab={tab.id}
            onClick={() => onSelectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <button type="button" onClick={onOpenSettings}>
        Settings
      </button>
    </nav>
  );
}
