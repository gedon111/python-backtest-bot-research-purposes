import { useManifest, useCandles } from '../../api/hooks';

/**
 * Structural stub. Real chart rendering (candles + MACD/KDJ/ATR panes + OB
 * overlays + trade markers, state-driven pane sync) is Phase 2 — not built here.
 * This only proves the data layer round-trips against the live server.
 */
export function ChartTab() {
  const manifest = useManifest();
  const candles = useCandles();

  return (
    <section id="chart-tab" className="tab-pane">
      <h2>Chart (stub)</h2>
      {manifest.loading && <p>Loading manifest...</p>}
      {manifest.error && <p role="alert">manifest.json: {manifest.error.message}</p>}
      {manifest.data && (
        <p>
          {manifest.data.symbol} {manifest.data.timeframe} — {manifest.data.candle_count} candles
          ({manifest.data.start_time} to {manifest.data.end_time})
        </p>
      )}
      {candles.loading && <p>Loading candles...</p>}
      {candles.error && <p role="alert">candles.json: {candles.error.message}</p>}
      {candles.data && <p>{candles.data.length} candles fetched.</p>}
    </section>
  );
}
