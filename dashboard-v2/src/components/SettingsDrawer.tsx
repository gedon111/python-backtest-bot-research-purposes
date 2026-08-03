interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Structural stub for the combined theme + chart-settings drawer
 * (gui.html:544+, id="settings-drawer" — theme toggle, presets, and per-series
 * data-color pickers, not theme-only). Reads/writes /api/get_theme and
 * /api/save_theme in a later phase; no visual design yet.
 */
export function SettingsDrawer({ open, onClose }: SettingsDrawerProps) {
  if (!open) return null;
  return (
    <div id="settings-drawer" role="dialog" aria-label="Chart Settings">
      <div className="drawer-header">
        <h3>Chart Settings</h3>
        <button type="button" onClick={onClose} aria-label="Close settings">
          &times;
        </button>
      </div>
      <div className="drawer-body">
        <p>Theme toggle, presets, and data-color pickers land here in a later phase.</p>
      </div>
    </div>
  );
}
