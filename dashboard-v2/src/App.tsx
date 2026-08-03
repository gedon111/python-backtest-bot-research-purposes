import { useState } from 'react';
import './App.css';
import { Sidebar, type TabId } from './components/Sidebar';
import { SettingsDrawer } from './components/SettingsDrawer';
import { ChartTab } from './components/tabs/ChartTab';
import { SandboxTab } from './components/tabs/SandboxTab';
import { StatsTab } from './components/tabs/StatsTab';

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('chart');
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main>
        {activeTab === 'chart' && <ChartTab />}
        {activeTab === 'sandbox' && <SandboxTab />}
        {activeTab === 'stats' && <StatsTab />}
      </main>
      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

export default App;
