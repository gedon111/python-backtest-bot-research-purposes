import { useMemo, useState } from 'react';
import './ChartTab.css';
import { useCandles, useManifest, useRunsByThreshold, useVerificationReport } from '../../api/hooks';
import { useDashboardTheme } from '../../theme/ThemeContext';
import { MultiPaneChart, type ChartHoverInfo } from '../chart/MultiPaneChart';
import { processObs, processTrades } from '../chart/chartProcessing';

const fmt = (v: number | null | undefined, digits = 2) => (v == null ? '--' : v.toFixed(digits));

export function ChartTab() {
  const manifest = useManifest();
  const candles = useCandles();
  const runs = useRunsByThreshold();
  const verification = useVerificationReport();
  const { pageTheme, dataColors } = useDashboardTheme();

  const [quality, setQuality] = useState('0');
  const [obLevel, setObLevel] = useState('all');
  const [obStructure, setObStructure] = useState('all');
  const [showObZones, setShowObZones] = useState(true);
  const [showObMarkers, setShowObMarkers] = useState(true);
  const [showTradeLines, setShowTradeLines] = useState(true);
  const [autoFit, setAutoFit] = useState(true);
  const [hover, setHover] = useState<ChartHoverInfo>({ time: null, idx: null, row: null, ob: null, trade: null });

  const candleData = candles.data ?? [];
  const run = runs.data?.[quality];

  const processedObs = useMemo(
    () => (run && candleData.length ? processObs(candleData, run.obs, obLevel, obStructure) : []),
    [candleData, run, obLevel, obStructure],
  );
  const processedTrades = useMemo(
    () => (run && candleData.length ? processTrades(candleData, run.trades) : []),
    [candleData, run],
  );

  const thresholdKeys = useMemo(
    () => (runs.data ? Object.keys(runs.data).sort((a, b) => Number(a) - Number(b)) : []),
    [runs.data],
  );

  if (manifest.loading || candles.loading || runs.loading) {
    return <div className="chart-tab-loading">Loading dashboard data...</div>;
  }
  if (manifest.error || candles.error || runs.error) {
    return (
      <div className="chart-tab-loading" role="alert">
        Failed to load artifacts. Run export_gui_data.py, then start the dashboard server.
        <br />
        {(manifest.error ?? candles.error ?? runs.error)?.message}
      </div>
    );
  }

  const activeTrade = hover.trade;
  const kdjMode = activeTrade
    ? `Adaptive KDJ (period = ${activeTrade.adaptivePeriod})`
    : 'Static KDJ (9, 3, 3)';

  return (
    <div className="chart-tab">
      <div className="chart-top-bar">
        <div className="symbol-pill">
          <span>BTCUSDT 4H</span>
          {verification.data && (
            <span className={`verify-pill ${verification.data.status.toLowerCase()}`}>
              Verification: {verification.data.status.toUpperCase()}
            </span>
          )}
        </div>
        <div className="metric-cards">
          <div className="metric-card">
            <div className="metric-label">OHLC</div>
            <div className="metric-value">
              O:{fmt(hover.row?.open)} H:{fmt(hover.row?.high)} L:{fmt(hover.row?.low)} C:{fmt(hover.row?.close)}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">MACD (12, 26, 9)</div>
            <div className="metric-value">{fmt(hover.row?.MACD)}</div>
          </div>
          <div className="metric-card" style={{ minWidth: 220 }}>
            <div className="metric-label">
              <span>{kdjMode}</span>
              <span className={`kdj-mode-badge${activeTrade ? ' active' : ''}`}>
                {activeTrade ? `EVAL p=${activeTrade.adaptivePeriod}` : 'Chart View'}
              </span>
            </div>
            <div className="metric-value">
              K:{fmt(hover.row?.K)} D:{fmt(hover.row?.D)} J:{fmt(hover.row?.J)}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">ATR (14 / 200)</div>
            <div className="metric-value">
              {fmt(hover.row?.ATR)} / {fmt(hover.row?.ATR_200)}
            </div>
          </div>
        </div>
      </div>

      <div className="chart-control-bar">
        <div className="control-group">
          <label>
            Min OB Quality
            <select value={quality} onChange={(e) => setQuality(e.target.value)}>
              {thresholdKeys.map((q) => (
                <option key={q} value={q}>
                  {q === '0' ? '0 (Baseline Dataset)' : `Quality ${q}`}
                </option>
              ))}
            </select>
          </label>
          <label>
            OB Level
            <select value={obLevel} onChange={(e) => setObLevel(e.target.value)}>
              <option value="all">All</option>
              <option value="swing">Swing</option>
              <option value="internal">Internal</option>
            </select>
          </label>
          <label>
            OB Structure
            <select value={obStructure} onChange={(e) => setObStructure(e.target.value)}>
              <option value="all">All</option>
              <option value="BOS">BOS</option>
              <option value="CHoCH">CHoCH</option>
            </select>
          </label>
        </div>
        <div className="control-group">
          <button
            type="button"
            className={`btn-toggle${showTradeLines ? ' active' : ''}`}
            onClick={() => setShowTradeLines((v) => !v)}
          >
            Trade Lines: {showTradeLines ? 'ON' : 'OFF'}
          </button>
          <label className="inline-check">
            <input type="checkbox" checked={showObZones} onChange={(e) => setShowObZones(e.target.checked)} />
            Show OB Zones
          </label>
          <label className="inline-check">
            <input type="checkbox" checked={showObMarkers} onChange={(e) => setShowObMarkers(e.target.checked)} />
            Show OB Markers
          </label>
          <button
            type="button"
            className={`btn-toggle${autoFit ? ' active' : ''}`}
            onClick={() => setAutoFit((v) => !v)}
          >
            Auto Fit: {autoFit ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      <div className="chart-layout">
        <MultiPaneChart
          candles={candleData}
          processedObs={processedObs}
          processedTrades={processedTrades}
          dataColors={dataColors}
          pageTheme={pageTheme}
          showObZones={showObZones}
          showObMarkers={showObMarkers}
          showTradeLines={showTradeLines}
          autoFit={autoFit}
          onHoverChange={setHover}
        />
        <ObInspectionPanel hover={hover} />
      </div>
    </div>
  );
}

function ObInspectionPanel({ hover }: { hover: ChartHoverInfo }) {
  const ob = hover.ob;
  return (
    <div className="ob-panel">
      <h3>Order Block Inspection</h3>
      <p className="subtitle">Hover over a marker on the chart to inspect the order block.</p>
      {!ob ? (
        <div className="ob-empty-state">
          <p>No Order Block Selected</p>
        </div>
      ) : (
        <div>
          <div className="ob-header">
            <span className={`badge ${ob.type.toLowerCase()}`}>{ob.type}</span>
            <span>{new Date(ob.startTime * 1000).toLocaleString()}</span>
          </div>
          <div className="ob-price-levels">
            <div>
              <label>Top:</label>
              {ob.top.toFixed(2)}
            </div>
            <div>
              <label>Bottom:</label>
              {ob.bottom.toFixed(2)}
            </div>
          </div>
          <div>
            <h4 style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
              Validation Rules
            </h4>
            <ul className="rule-list">
              <li className={ob.quality_displacement ? 'pass' : ''}>
                <span className="icon" /> Displacement
              </li>
              <li className={ob.quality_large_bar ? 'pass' : ''}>
                <span className="icon" /> Large Bar (&gt; 2x ATR200)
              </li>
              <li className={ob.quality_fvg ? 'pass' : ''}>
                <span className="icon" /> Fair Value Gap
              </li>
              <li className={ob.quality_liquidity_sweep ? 'pass' : ''}>
                <span className="icon" /> Liquidity Sweep
              </li>
              <li className={ob.quality_volume_expansion ? 'pass' : ''}>
                <span className="icon" /> Volume Expansion
              </li>
            </ul>
          </div>
          <div className="ob-score">
            Quality Score: <strong>{ob.quality}</strong> / 5
          </div>
          <div className="ob-kdj-eval">
            <div className="ob-kdj-eval-title">KDJ Evaluation Mode</div>
            {hover.trade ? (
              <>
                <div style={{ fontWeight: 700, color: 'var(--demand)' }}>
                  Adaptive KDJ (period = {hover.trade.adaptivePeriod} bars)
                </div>
                <div style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  OB Origin Bar <strong>{hover.trade.obBar}</strong> → Entry Bar{' '}
                  <strong>{hover.trade.entry_idx}</strong>. Trade evaluation used a dynamic{' '}
                  {hover.trade.adaptivePeriod}-bar RSV lookback window.
                </div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 700 }}>Static KDJ (9, 3, 3)</div>
                <div style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  Default chart view using static 9-period RSV lookback.
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
