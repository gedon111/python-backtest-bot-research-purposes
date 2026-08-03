import { useMemo, useState } from 'react';
import './ChartTab.css';
import { useCandles, useManifest, useRunsByThreshold, useVerificationReport } from '../../api/hooks';
import { useDashboardTheme } from '../../theme/ThemeContext';
import { MultiPaneChart, type ChartHoverInfo } from '../chart/MultiPaneChart';
import { processObs, processTrades } from '../chart/chartProcessing';
import {
  verifyDisplacement,
  verifyFvg,
  verifyLargeBar,
  verifyLiquiditySweep,
  verifyVolumeExpansion,
} from '../chart/obQualityVerification';
import type { Candle } from '../../types/artifacts';
import { Latex } from '../common/Latex';
import { SectionTag } from '../common/SectionTag';

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
        <div
          className="metric-cards"
          title="Indicator values are precomputed offline by the Python backtest engine's compute_indicators() and read directly from candles.json -- see the Formula Sandbox tab for the MACD/KDJ/ATR formulas."
        >
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
        <ObInspectionPanel hover={hover} candles={candleData} />
      </div>
    </div>
  );
}

interface RuleSpec {
  label: string;
  tex: string;
  recorded: boolean;
  check: () => { pass: boolean; matchesRecorded: boolean; detail: string };
}

function ObInspectionPanel({ hover, candles }: { hover: ChartHoverInfo; candles: Candle[] }) {
  const ob = hover.ob;

  const rules: RuleSpec[] | null = useMemo(() => {
    if (!ob) return null;
    const obIdx = ob.exactIdx;
    const createdAt = ob.created_at;
    return [
      {
        label: 'Displacement',
        tex: '|\\text{Close}_j - \\text{Open}_j| \\geq 1.5 \\times \\text{ATR200}',
        recorded: ob.quality_displacement,
        check: () => verifyDisplacement(candles, obIdx, createdAt, ob.type, ob.quality_displacement),
      },
      {
        label: 'Large Bar',
        tex: '\\text{High} - \\text{Low} \\geq \\text{ATR200}',
        recorded: ob.quality_large_bar,
        check: () => verifyLargeBar(candles, obIdx, ob.quality_large_bar),
      },
      {
        label: 'Fair Value Gap',
        tex: '\\text{Low}_{j+2} > \\text{High}_j \\ (\\text{3-candle gap})',
        recorded: ob.quality_fvg,
        check: () => verifyFvg(candles, obIdx, createdAt, ob.type, ob.quality_fvg),
      },
      {
        label: 'Liquidity Sweep',
        tex: '\\text{Low}_{\\text{ob}} \\leq \\min(\\text{Low}_{[i-10,\\,i)})',
        recorded: ob.quality_liquidity_sweep,
        check: () => verifyLiquiditySweep(candles, obIdx, ob.type, ob.quality_liquidity_sweep),
      },
      {
        label: 'Volume Expansion',
        tex: '\\text{vol} \\geq 1.25 \\times \\overline{\\text{vol}}_{20} \\ \\text{OR} \\ \\dfrac{|\\text{body}|}{\\text{range}} > 0.6',
        recorded: ob.quality_volume_expansion,
        check: () => verifyVolumeExpansion(candles, obIdx, ob.quality_volume_expansion),
      },
    ];
  }, [ob, candles]);

  return (
    <div className="ob-panel">
      <h3>Order Block Inspection</h3>
      <p className="subtitle">Hover over a marker on the chart to inspect the order block.</p>
      {!ob || !rules ? (
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
            <h4 className="ob-section-title">
              Validation Rules <SectionTag kind="live" />
            </h4>
            <p className="ob-section-note">
              Independently re-derived in your browser from the raw candles, per{' '}
              <code>Binance backtest bot.py</code> -- not just read from the record.
            </p>
            <ul className="rule-list">
              {rules.map((rule) => {
                const result = rule.check();
                return (
                  <li key={rule.label} className={rule.recorded ? 'pass' : ''}>
                    <div className="rule-row">
                      <span className="icon" /> {rule.label}
                      {!result.matchesRecorded && <span className="rule-mismatch">⚠ mismatch</span>}
                    </div>
                    <Latex block className="rule-formula" tex={rule.tex} />
                    <div className="rule-detail">{result.detail}</div>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="ob-score">
            Quality Score: <strong>{ob.quality}</strong> / 5
          </div>
          <div className="ob-section-title" style={{ marginTop: '1rem' }}>
            Zone Extent <SectionTag kind="live" />
          </div>
          <div className="ob-zone-extent">
            Drawn from bar <strong>{ob.exactIdx}</strong> to <strong>{ob.endIdx}</strong> (
            {ob.endIdx - ob.exactIdx} bars). Extends until price closes back through the zone
            {ob.mitigated_at != null ? `, or the recorded mitigation bar (${ob.mitigated_at})` : ''}, whichever comes
            first -- capped at 500 bars.
          </div>
          <div className="ob-kdj-eval">
            <div className="ob-kdj-eval-title">
              KDJ Evaluation Mode {hover.trade && <SectionTag kind="live" />}
            </div>
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
                <Latex
                  block
                  className="rule-formula"
                  tex={`K_i = K_{i-1} \\times \\tfrac{2}{3} + \\text{RSV}_i \\times \\tfrac{1}{3}, \\quad p = ${hover.trade.adaptivePeriod}`}
                />
              </>
            ) : (
              <>
                <div style={{ fontWeight: 700 }}>Static KDJ (9, 3, 3)</div>
                <div style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  Default chart view using static 9-period RSV lookback, precomputed offline (see{' '}
                  <code>compute_indicators()</code>) -- same recursion as the Formula Sandbox's KDJ calculator, with
                  p = 9 fixed instead of a per-trade adaptive period.
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
