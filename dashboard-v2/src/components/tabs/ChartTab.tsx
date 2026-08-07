import { useEffect, useMemo, useState } from 'react';
import './ChartTab.css';
import { useCandles, useExtendedCandles, useManifest, useRunsByThreshold, useVerificationReport } from '../../api/hooks';
import type { Time } from 'lightweight-charts';
import { useDashboardTheme } from '../../theme/ThemeContext';
import { MultiPaneChart, type ChartHoverInfo } from '../chart/MultiPaneChart';
import { processObs, processTrades, usedObBars } from '../chart/chartProcessing';
import {
  verifyDisplacement,
  verifyFvg,
  verifyLargeBar,
  verifyLiquiditySweep,
  verifyVolumeExpansion,
} from '../chart/obQualityVerification';
import type { Candle } from '../../types/artifacts';
import { Latex } from '../common/Latex';

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
  const [obUsedOnly, setObUsedOnly] = useState(true);
  const [showObZones, setShowObZones] = useState(true);
  const [showTradeZones, setShowTradeZones] = useState(true);
  const [autoFit, setAutoFit] = useState(true);
  const [hover, setHover] = useState<ChartHoverInfo>({ time: null, idx: null, row: null, ob: null, trade: null });

  // 'locked' = the paper's 2022-2026 backtest window (default, unchanged
  // behavior). 'extended' = 2018-today, fetched lazily -- see useExtendedCandles.
  const [viewMode, setViewMode] = useState<'locked' | 'extended'>('locked');
  const [rangeStart, setRangeStart] = useState('');
  const [rangeEnd, setRangeEnd] = useState('');
  const [appliedRange, setAppliedRange] = useState<{ from: Time; to: Time } | null>(null);
  const extendedCandles = useExtendedCandles(viewMode === 'extended');

  // The LOCKED candle set -- OBs/trades are always processed against this,
  // never the extended set, so their bar indices stay valid (see
  // MultiPaneChart's timeToIndex-based lookups, which resolve position by
  // timestamp for whichever array actually ends up mounted).
  const candleData = candles.data ?? [];
  const chartCandles = viewMode === 'extended' && extendedCandles.data ? extendedCandles.data : candleData;
  const run = runs.data?.[quality];

  const usedBars = useMemo(() => (run ? usedObBars(run.trades) : new Set<number>()), [run]);

  const processedObs = useMemo(
    () =>
      run && candleData.length
        ? processObs(candleData, run.obs, obLevel, obStructure, obUsedOnly ? usedBars : null)
        : [],
    [candleData, run, obLevel, obStructure, obUsedOnly, usedBars],
  );
  const processedTrades = useMemo(
    () => (run && candleData.length ? processTrades(candleData, run.trades) : []),
    [candleData, run],
  );

  const lockedWindowStart = candleData[0]?.time ?? null;
  const lockedWindowEnd = candleData[candleData.length - 1]?.time ?? null;

  const applyDateRange = () => {
    if (!rangeStart || !rangeEnd) return;
    const from = Math.floor(new Date(`${rangeStart}T00:00:00Z`).getTime() / 1000);
    const to = Math.floor(new Date(`${rangeEnd}T23:59:59Z`).getTime() / 1000);
    setAppliedRange({ from: from as Time, to: to as Time });
  };

  const thresholdKeys = useMemo(
    () => (runs.data ? Object.keys(runs.data).sort((a, b) => Number(a) - Number(b)) : []),
    [runs.data],
  );

  // Changing OB filters recomputes processedObs/processedTrades, but `hover` is
  // otherwise only updated from mouse movement over the chart -- without this,
  // the Inspection Panel could keep showing an ob/trade no longer in the
  // filtered set. Clear only what's now invalid; row/idx/time (derived from the
  // candle under the cursor, not from filters) stay put.
  useEffect(() => {
    setHover((prev) => {
      const obStillValid = !prev.ob || processedObs.some((o) => o.startTime === prev.ob!.startTime);
      const tradeStillValid = !prev.trade || processedTrades.some((t) => t.entry_idx === prev.trade!.entry_idx);
      if (obStillValid && tradeStillValid) return prev;
      return { ...prev, ob: obStillValid ? prev.ob : null, trade: tradeStillValid ? prev.trade : null };
    });
  }, [processedObs, processedTrades]);

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
  const kdjMode = activeTrade ? `ADAPTIVE (p=${activeTrade.adaptivePeriod})` : 'STATIC (9,3,3)';

  return (
    <div className="chart-tab">
      <div className="chart-top-bar">
        <div className="metric-cards">
          <div className="metric-card panel">
            <div className="metric-label">OHLC</div>
            <div className="metric-value">
              O:{fmt(hover.row?.open)} H:{fmt(hover.row?.high)} L:{fmt(hover.row?.low)} C:{fmt(hover.row?.close)}
            </div>
          </div>
          <div className="metric-card panel">
            <div className="metric-label">MACD (12,26,9)</div>
            <div className="metric-value">{fmt(hover.row?.MACD)}</div>
          </div>
          <div className="metric-card panel">
            <div className="metric-label">
              KDJ <span className={`tag ${activeTrade ? 'tag-live' : 'tag-ref'}`}>{kdjMode}</span>
            </div>
            <div className="metric-value">
              K:{fmt(hover.row?.K)} D:{fmt(hover.row?.D)} J:{fmt(hover.row?.J)}
            </div>
          </div>
          <div className="metric-card panel">
            <div className="metric-label">ATR (14/200)</div>
            <div className="metric-value">
              {fmt(hover.row?.ATR)} / {fmt(hover.row?.ATR_200)}
            </div>
          </div>
          {verification.data && (
            <div className="metric-card panel">
              <div className="metric-label">Verification</div>
              <div className="metric-value">
                <span className={`tag ${verification.data.status.toLowerCase() === 'pass' ? 'tag-good' : 'tag-critical'}`}>
                  {verification.data.status}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="chart-control-bar">
        <div className="control-group">
          <label className="control-field">
            <span>Min Quality</span>
            <select value={quality} onChange={(e) => setQuality(e.target.value)}>
              {thresholdKeys.map((q) => (
                <option key={q} value={q}>
                  {q === '0' ? 'Q0 (baseline)' : `Q${q}`}
                </option>
              ))}
            </select>
          </label>
          <label className="control-field">
            <span>Level</span>
            <select value={obLevel} onChange={(e) => setObLevel(e.target.value)}>
              <option value="all">All</option>
              <option value="swing">Swing</option>
              <option value="internal">Internal</option>
            </select>
          </label>
          <label className="control-field">
            <span>Structure</span>
            <select value={obStructure} onChange={(e) => setObStructure(e.target.value)}>
              <option value="all">All</option>
              <option value="BOS">BOS</option>
              <option value="CHoCH">CHoCH</option>
            </select>
          </label>
        </div>
        <div className="control-group">
          <button type="button" className={`btn-toggle${showObZones ? ' active' : ''}`} onClick={() => setShowObZones((v) => !v)}>
            OB Zones: {showObZones ? 'ON' : 'OFF'}
          </button>
          <button type="button" className={`btn-toggle${obUsedOnly ? ' active' : ''}`} onClick={() => setObUsedOnly((v) => !v)}>
            OB Filter: {obUsedOnly ? 'USED ONLY' : 'ALL'}
          </button>
          <button
            type="button"
            className={`btn-toggle${showTradeZones ? ' active' : ''}`}
            onClick={() => setShowTradeZones((v) => !v)}
          >
            Trade Zones: {showTradeZones ? 'ON' : 'OFF'}
          </button>
          <button type="button" className={`btn-toggle${autoFit ? ' active' : ''}`} onClick={() => setAutoFit((v) => !v)}>
            Auto Fit: {autoFit ? 'ON' : 'OFF'}
          </button>
        </div>
        <div className="control-group">
          <button
            type="button"
            className={`btn-toggle${viewMode === 'extended' ? ' active' : ''}`}
            onClick={() => setViewMode((v) => (v === 'extended' ? 'locked' : 'extended'))}
          >
            Full History: {viewMode === 'extended' ? 'ON (2018-today)' : 'OFF (2022-2026 locked)'}
          </button>
          {viewMode === 'extended' && (
            <>
              <label className="control-field">
                <span>From</span>
                <input type="date" value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} />
              </label>
              <label className="control-field">
                <span>To</span>
                <input type="date" value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} />
              </label>
              <button type="button" className="btn-toggle" onClick={applyDateRange} disabled={extendedCandles.loading}>
                Apply Range
              </button>
              {extendedCandles.loading && <span className="text-muted">Loading extended history...</span>}
              {extendedCandles.error && <span className="tag tag-critical">Failed to load extended history</span>}
            </>
          )}
        </div>
      </div>

      <div className="chart-layout">
        <MultiPaneChart
          candles={chartCandles}
          processedObs={processedObs}
          processedTrades={processedTrades}
          dataColors={dataColors}
          pageTheme={pageTheme}
          showObZones={showObZones}
          showTradeZones={showTradeZones}
          autoFit={autoFit}
          onHoverChange={setHover}
          visibleRange={viewMode === 'extended' ? appliedRange : null}
          lockedWindowStart={viewMode === 'extended' ? lockedWindowStart : null}
          lockedWindowEnd={viewMode === 'extended' ? lockedWindowEnd : null}
        />
        <InspectionPanel hover={hover} candles={candleData} />
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

function InspectionPanel({ hover, candles }: { hover: ChartHoverInfo; candles: Candle[] }) {
  const ob = hover.ob;
  const trade = hover.trade;

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
    <div className="ob-panel panel">
      <h3>Inspection</h3>
      {!trade && !ob ? (
        <p className="ob-empty-state text-muted">Hover a chart bar to inspect trade and Order Block data.</p>
      ) : (
        <div>
          {trade && (
            <div className="inspection-block">
              <h4 className="ob-section-title">
                Trade <span className="tag tag-live">LIVE</span>
              </h4>
              <div className="ob-header">
                <span className={`tag ${trade.side === 'LONG' ? 'tag-good' : 'tag-critical'}`}>{trade.side}</span>
                <span className={trade.pnl_pct >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                  {trade.pnl_pct >= 0 ? '+' : ''}
                  {fmt(trade.pnl_pct)}%
                </span>
              </div>
              <div className="ob-price-levels">
                <div>
                  <span className="text-muted">Entry</span> {fmt(trade.entry)}
                </div>
                <div>
                  <span className="text-muted">Exit</span> {fmt(trade.exit)}
                </div>
                <div>
                  <span className="text-muted">Stop Loss</span> {fmt(trade.stop_loss)}
                </div>
                <div>
                  <span className="text-muted">Take Profit</span> {fmt(trade.take_profit)}
                </div>
              </div>
              <div className="ob-price-levels">
                <div>
                  <span className="text-muted">Hold Bars</span> {trade.hold_bars ?? trade.exit_idx - trade.entry_idx}
                </div>
                <div>
                  <span className="text-muted">Exit Reason</span> {trade.exit_reason ?? '--'}
                </div>
                <div>
                  <span className="text-muted">Entry OB Quality</span> {trade.entry_ob_quality ?? '--'}
                </div>
              </div>
              <div className="ob-zone-extent text-muted">
                Adaptive KDJ, period = {trade.adaptivePeriod} bars. OB origin bar {trade.obBar}, entry bar {trade.entry_idx},
                exit bar {trade.exit_idx}.
              </div>
            </div>
          )}

          {ob && rules && (
            <div className="inspection-block">
              <h4 className="ob-section-title">Order Block Inspection</h4>
              <div className="ob-header">
                <span className={`tag ${ob.type === 'DEMAND' ? 'tag-good' : 'tag-critical'}`}>{ob.type}</span>
                <span className="text-muted">{new Date(ob.startTime * 1000).toLocaleString()}</span>
              </div>
              <div className="ob-price-levels">
                <div>
                  <span className="text-muted">Top</span> {ob.top.toFixed(2)}
                </div>
                <div>
                  <span className="text-muted">Bottom</span> {ob.bottom.toFixed(2)}
                </div>
                <div>
                  <span className="text-muted">Score</span> {ob.quality}/5
                </div>
              </div>

              <h4 className="ob-section-title">
                Validation <span className="tag tag-live">LIVE</span>
              </h4>
              <p className="ob-section-note text-muted">
                Independently re-derived in-browser from raw candles, not read from the record.
              </p>
              <ul className="rule-list">
                {rules.map((rule) => {
                  const result = rule.check();
                  return (
                    <li key={rule.label} className={`rail ${rule.recorded ? 'rail-good' : ''}`}>
                      <div className="rule-row">
                        <span>{rule.label}</span>
                        <span className={`tag ${rule.recorded ? 'tag-good' : 'tag-ref'}`}>
                          {rule.recorded ? 'PASS' : 'FALSE'}
                        </span>
                        {!result.matchesRecorded && <span className="tag tag-warning">MISMATCH</span>}
                      </div>
                      <Latex block className="rule-formula" tex={rule.tex} />
                      <div className="rule-detail text-muted">{result.detail}</div>
                    </li>
                  );
                })}
              </ul>

              <h4 className="ob-section-title">Zone Extent</h4>
              <div className="ob-zone-extent text-muted">
                Bar {ob.exactIdx} to {ob.endIdx} ({ob.endIdx - ob.exactIdx} bars)
                {ob.mitigated_at != null ? `, mitigated at bar ${ob.mitigated_at}` : ', not yet mitigated'}.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
