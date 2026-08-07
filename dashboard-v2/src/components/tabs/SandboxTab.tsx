import { useState, type ReactNode } from 'react';
import './SandboxTab.css';
import { fetchLiveKlines, type LiveCandle } from '../../api/client';
import { calculateATR, calculateEMA, calculateKDJ, calculateMACDSandbox } from '../sandbox/calculators';
import { computeDateRangeIndicators, type IndicatorRow } from '../sandbox/dateRangeIndicators';
import { Latex } from '../common/Latex';

const fmt = (v: number, digits = 4) => (Number.isFinite(v) ? v.toFixed(digits) : '--');

export function SandboxTab() {
  return (
    <div className="sandbox-tab">
      <section className="sandbox-section">
        <h3>Formula Calculators</h3>
        <p className="sandbox-desc text-muted">
          Enter raw values and compute the strategy's indicator formulas directly -- the same functions
          <code> compute_indicators()</code> uses, ported here for manual verification.
        </p>
        <div className="calc-grid">
          <EmaCalculator />
          <MacdCalculator />
          <AtrCalculator />
          <KdjCalculator />
        </div>
      </section>

      <section className="sandbox-section">
        <h3>Date Range Indicator Tester</h3>
        <p className="sandbox-desc text-muted">
          Fetches live BTCUSDT 4H candles from Binance for a date range and recurses the same indicator
          formulas forward from the first bar -- independent of the offline backtest artifacts.
        </p>
        <DateRangeTester />
      </section>
    </div>
  );
}

function CalcCard({ title, tex, children }: { title: string; tex: string; children: ReactNode }) {
  return (
    <div className="calc-card panel">
      <div className="calc-title">{title}</div>
      <Latex block className="calc-formula" tex={tex} />
      {children}
    </div>
  );
}

function NumField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="calc-field">
      <span>{label}</span>
      <input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function EmaCalculator() {
  const [n, setN] = useState(12);
  const [close, setClose] = useState(90000);
  const [prevEma, setPrevEma] = useState(89500);
  const result = calculateEMA(n, close, prevEma);
  return (
    <CalcCard title="EMA" tex="\text{EMA}_n = (\text{Close} - \text{EMA}_{\text{prev}}) \times \dfrac{2}{n+1} + \text{EMA}_{\text{prev}}">
      <div className="calc-fields">
        <NumField label="n (period)" value={n} onChange={setN} />
        <NumField label="Close" value={close} onChange={setClose} />
        <NumField label="Prev EMA" value={prevEma} onChange={setPrevEma} />
      </div>
      <div className="calc-result">
        EMA = <strong>{fmt(result)}</strong>
      </div>
    </CalcCard>
  );
}

function MacdCalculator() {
  const [ema12, setEma12] = useState(90200);
  const [ema26, setEma26] = useState(89800);
  const [prevSignal, setPrevSignal] = useState(300);
  const result = calculateMACDSandbox(ema12, ema26, prevSignal);
  return (
    <CalcCard
      title="MACD (12, 26, 9)"
      tex="\text{MACD} = \text{EMA}_{12} - \text{EMA}_{26}, \quad \text{Signal} = \text{EMA}_9(\text{MACD}), \quad \text{Hist} = \text{MACD} - \text{Signal}"
    >
      <div className="calc-fields">
        <NumField label="EMA 12" value={ema12} onChange={setEma12} />
        <NumField label="EMA 26" value={ema26} onChange={setEma26} />
        <NumField label="Prev Signal" value={prevSignal} onChange={setPrevSignal} />
      </div>
      <div className="calc-result">
        MACD = <strong>{fmt(result.macdLine)}</strong> · Signal = <strong>{fmt(result.signalLine)}</strong> · Hist ={' '}
        <strong>{fmt(result.hist)}</strong>
      </div>
    </CalcCard>
  );
}

function AtrCalculator() {
  const [n, setN] = useState(14);
  const [trText, setTrText] = useState('1200, 980, 1450, 1100, 1330');
  const trValues = trText
    .split(',')
    .map((s) => Number(s.trim()))
    .filter((v) => Number.isFinite(v));
  const result = calculateATR(n, trValues);
  return (
    <CalcCard title="ATR" tex="\text{ATR}_n = \dfrac{1}{n} \sum_{i=1}^{n} \text{TR}_i, \quad \text{TR} = \max(H-L,\, |H-C_{\text{prev}}|,\, |L-C_{\text{prev}}|)">
      <div className="calc-fields">
        <NumField label="n (period)" value={n} onChange={setN} />
        <label className="calc-field calc-field-wide">
          <span>TR values (comma-separated)</span>
          <input type="text" value={trText} onChange={(e) => setTrText(e.target.value)} />
        </label>
      </div>
      <div className="calc-result">
        ATR = <strong>{result ? fmt(result.atr) : '--'}</strong>{' '}
        <span className="text-muted">({result ? result.count : 0} values used)</span>
      </div>
    </CalcCard>
  );
}

function KdjCalculator() {
  const [close, setClose] = useState(90000);
  const [ll, setLl] = useState(88500);
  const [hh, setHh] = useState(91500);
  const [prevK, setPrevK] = useState(55);
  const [prevD, setPrevD] = useState(52);
  const result = calculateKDJ(close, ll, hh, prevK, prevD);
  return (
    <CalcCard
      title="KDJ (9, 3, 3)"
      tex="\text{RSV} = \dfrac{C - LL}{HH - LL} \times 100, \quad K = \tfrac{2}{3}K_{\text{prev}} + \tfrac{1}{3}\text{RSV}, \quad D = \tfrac{2}{3}D_{\text{prev}} + \tfrac{1}{3}K, \quad J = 3K - 2D"
    >
      <div className="calc-fields">
        <NumField label="Close" value={close} onChange={setClose} />
        <NumField label="Lowest Low" value={ll} onChange={setLl} />
        <NumField label="Highest High" value={hh} onChange={setHh} />
        <NumField label="Prev K" value={prevK} onChange={setPrevK} />
        <NumField label="Prev D" value={prevD} onChange={setPrevD} />
      </div>
      <div className="calc-result">
        RSV = <strong>{fmt(result.rsv, 2)}</strong> · K = <strong>{fmt(result.k, 2)}</strong> · D ={' '}
        <strong>{fmt(result.d, 2)}</strong> · J = <strong>{fmt(result.j, 2)}</strong>
      </div>
    </CalcCard>
  );
}

const WARMUP_BARS = 220; // enough for EMA200 to settle before the requested range starts

function DateRangeTester() {
  const [start, setStart] = useState(() => {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - 14);
    return d.toISOString().slice(0, 10);
  });
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10));
  const [rows, setRows] = useState<IndicatorRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    setRows(null);
    try {
      const startMs = new Date(start + 'T00:00:00Z').getTime();
      const endMs = new Date(end + 'T00:00:00Z').getTime();
      const warmupStartMs = startMs - WARMUP_BARS * 4 * 60 * 60 * 1000;
      const raw: LiveCandle[] = await fetchLiveKlines(warmupStartMs, endMs);
      const withIndicators = computeDateRangeIndicators(raw);
      const trimmed = withIndicators.filter((r) => r.time * 1000 >= startMs);
      setRows(trimmed);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="date-range-tester panel">
      <div className="control-group">
        <label className="control-field">
          <span>Start</span>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="control-field">
          <span>End</span>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button type="button" className="btn-toggle" onClick={run} disabled={loading}>
          {loading ? 'Fetching...' : 'Fetch & Compute'}
        </button>
      </div>

      {error && <div className="rail rail-critical tester-error">{error}</div>}

      {rows && (
        <div className="tester-results">
          <div className="tester-summary text-muted">{rows.length} bars, live from api.binance.com</div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Time (UTC)</th>
                  <th>Close</th>
                  <th>EMA200</th>
                  <th>MACD</th>
                  <th>Signal</th>
                  <th>Hist</th>
                  <th>ATR</th>
                  <th>K</th>
                  <th>D</th>
                  <th>J</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.time}>
                    <td>{new Date(r.time * 1000).toISOString().slice(0, 16).replace('T', ' ')}</td>
                    <td>{r.close.toFixed(2)}</td>
                    <td>{r.ema.toFixed(2)}</td>
                    <td>{r.macd.toFixed(2)}</td>
                    <td>{r.signal.toFixed(2)}</td>
                    <td>{r.hist.toFixed(2)}</td>
                    <td>{r.atr.toFixed(2)}</td>
                    <td>{r.k.toFixed(2)}</td>
                    <td>{r.d.toFixed(2)}</td>
                    <td>{r.j.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
