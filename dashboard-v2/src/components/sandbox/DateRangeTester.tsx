import { useEffect, useRef, useState } from 'react';
import { createChart, LineSeries, type Time } from 'lightweight-charts';
import { fetchLiveKlines } from '../../api/client';
import { computeDateRangeIndicators, type IndicatorRow } from './dateRangeIndicators';

type IndicatorChoice = 'all' | 'ema' | 'macd' | 'atr' | 'kdj';

const WARMUP_MS = 35 * 24 * 60 * 60 * 1000; // ~35 days, matches gui.js:1528

export function DateRangeTester() {
  const [startStr, setStartStr] = useState('');
  const [endStr, setEndStr] = useState('');
  const [indicator, setIndicator] = useState<IndicatorChoice>('all');
  const [rows, setRows] = useState<IndicatorRow[]>([]);
  const [status, setStatus] = useState<{ text: string; isError: boolean }>({ text: '', isError: false });
  const [loading, setLoading] = useState(false);

  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || rows.length === 0) return;
    const container = chartContainerRef.current;
    container.innerHTML = '';
    const chart = createChart(container, {
      layout: { background: { color: 'var(--surface-0)' }, textColor: '#94a3b8' },
    });
    const series = chart.addSeries(LineSeries, { color: '#2a78d6', lineWidth: 2 });
    series.setData(rows.map((d) => ({ time: d.time as Time, value: d.close })));
    chart.timeScale().fitContent();
    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    });
    resizeObserver.observe(container);
    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [rows]);

  async function runTest() {
    setStatus({ text: '', isError: false });
    if (!startStr || !endStr) {
      setStatus({ text: 'Please select both dates.', isError: true });
      return;
    }
    const startTime = new Date(startStr).getTime();
    const endTime = new Date(endStr).getTime() + 86400000; // include end date, gui.js:1525
    const fetchStart = startTime - WARMUP_MS;

    setLoading(true);
    setStatus({ text: 'Fetching data from Binance API...', isError: false });
    try {
      const raw = await fetchLiveKlines(fetchStart, endTime);
      setStatus({ text: 'Calculating indicators...', isError: false });
      const withIndicators = computeDateRangeIndicators(raw).filter((d) => d.time * 1000 >= startTime);
      setRows(withIndicators);
      setStatus({ text: `Success: ${withIndicators.length} candles tested.`, isError: false });
    } catch (err) {
      setRows([]);
      setStatus({ text: `Error: ${(err as Error).message}`, isError: true });
    } finally {
      setLoading(false);
    }
  }

  const columns = columnsFor(indicator);

  return (
    <div className="calc-card full-width">
      <h3>Date Range Indicator Tester</h3>
      <p className="calc-subtitle">
        Fetch historical OHLC data from Binance and compute indicators dynamically to verify logic.
      </p>
      <div className="tester-layout">
        <div className="tester-controls">
          <div className="input-group">
            <label>
              Start Date
              <input type="date" value={startStr} onChange={(e) => setStartStr(e.target.value)} />
            </label>
            <label>
              End Date
              <input type="date" value={endStr} onChange={(e) => setEndStr(e.target.value)} />
            </label>
            <label>
              Indicator
              <select value={indicator} onChange={(e) => setIndicator(e.target.value as IndicatorChoice)}>
                <option value="all">All Indicators</option>
                <option value="ema">EMA (200)</option>
                <option value="macd">MACD (12, 26, 9)</option>
                <option value="atr">ATR (14)</option>
                <option value="kdj">KDJ (9, 3, 3)</option>
              </select>
            </label>
          </div>
          <button type="button" onClick={runTest} disabled={loading}>
            {loading ? 'Running...' : 'Run Test'}
          </button>
          {status.text && (
            <div className="tester-status" style={{ color: status.isError ? 'var(--critical)' : 'var(--good)' }}>
              {status.text}
            </div>
          )}
        </div>
        <div className="tester-output">
          <div className="tester-mini-chart" ref={chartContainerRef} />
          <div className="table-container tester-table-container">
            <table className="tester-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Date</th>
                  <th>C</th>
                  {columns.map((c) => (
                    <th key={c.label}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={2 + columns.length} style={{ textAlign: 'center', padding: '1rem' }}>
                      Run test to see data
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.time}>
                      <td style={{ textAlign: 'left' }}>{new Date(row.time * 1000).toLocaleString()}</td>
                      <td>{row.close.toFixed(2)}</td>
                      {columns.map((c) => (
                        <td key={c.label}>{c.value(row).toFixed(2)}</td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function columnsFor(indicator: IndicatorChoice): { label: string; value: (row: IndicatorRow) => number }[] {
  switch (indicator) {
    case 'ema':
      return [{ label: 'EMA200', value: (r) => r.ema }];
    case 'macd':
      return [
        { label: 'MACD', value: (r) => r.macd },
        { label: 'Signal', value: (r) => r.signal },
        { label: 'Hist', value: (r) => r.hist },
      ];
    case 'atr':
      return [{ label: 'ATR14', value: (r) => r.atr }];
    case 'kdj':
      return [
        { label: 'K', value: (r) => r.k },
        { label: 'D', value: (r) => r.d },
        { label: 'J', value: (r) => r.j },
      ];
    default:
      return [
        { label: 'EMA200', value: (r) => r.ema },
        { label: 'ATR', value: (r) => r.atr },
        { label: 'MACD', value: (r) => r.macd },
      ];
  }
}
