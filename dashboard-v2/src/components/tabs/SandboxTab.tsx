import { useState } from 'react';
import './SandboxTab.css';
import { calculateATR, calculateEMA, calculateKDJ, calculateMACDSandbox } from '../sandbox/calculators';
import { DateRangeTester } from '../sandbox/DateRangeTester';
import { Latex } from '../common/Latex';

export function SandboxTab() {
  return (
    <div className="sandbox-tab">
      <div className="sandbox-header">
        <h2>Formula Sandbox</h2>
        <p>Input values to test the math behind the bot's indicators manually.</p>
      </div>
      <div className="sandbox-grid">
        <EmaCard />
        <MacdCard />
        <AtrCard />
        <KdjCard />
        <DateRangeTester />
      </div>
    </div>
  );
}

function EmaCard() {
  const [n, setN] = useState(200);
  const [close, setClose] = useState(61000);
  const [prev, setPrev] = useState(60000);
  const result = calculateEMA(n, close, prev);

  return (
    <div className="calc-card">
      <h3>EMA (Exponential Moving Average)</h3>
      <div className="formula-block">
        <Latex block tex="\text{Multiplier} = \dfrac{2}{n + 1}" />
        <Latex block tex="\text{EMA}_n = (\text{Close} - \text{EMA}_{n-1}) \times \text{Multiplier} + \text{EMA}_{n-1}" />
      </div>
      <div className="input-group">
        <label>
          Period (n)
          <input type="number" value={n} onChange={(e) => setN(Number(e.target.value))} />
        </label>
        <label>
          Close
          <input type="number" value={close} onChange={(e) => setClose(Number(e.target.value))} />
        </label>
        <label>
          Prev EMA
          <input type="number" value={prev} onChange={(e) => setPrev(Number(e.target.value))} />
        </label>
      </div>
      <div className="result">Result: EMA = {result.toFixed(4)}</div>
    </div>
  );
}

function MacdCard() {
  const [ema12, setEma12] = useState(61500);
  const [ema26, setEma26] = useState(60000);
  const [prevSig, setPrevSig] = useState(1400);
  const { macdLine, signalLine, hist } = calculateMACDSandbox(ema12, ema26, prevSig);

  return (
    <div className="calc-card">
      <h3>MACD</h3>
      <div className="formula-block">
        <Latex block tex="\text{MACD Line} = \text{EMA}_{12} - \text{EMA}_{26}" />
        <Latex block tex="\text{Signal Line} = \text{EMA}_{9}(\text{MACD Line})" />
        <Latex block tex="\text{Histogram} = \text{MACD Line} - \text{Signal Line}" />
      </div>
      <div className="input-group">
        <label>
          EMA(12)
          <input type="number" value={ema12} onChange={(e) => setEma12(Number(e.target.value))} />
        </label>
        <label>
          EMA(26)
          <input type="number" value={ema26} onChange={(e) => setEma26(Number(e.target.value))} />
        </label>
        <label>
          Prev Signal
          <input type="number" value={prevSig} onChange={(e) => setPrevSig(Number(e.target.value))} />
        </label>
      </div>
      <div className="result">
        Result: MACD: {macdLine.toFixed(2)} | Signal: {signalLine.toFixed(2)} | Hist: {hist.toFixed(2)}
      </div>
    </div>
  );
}

function AtrCard() {
  const [n, setN] = useState(14);
  const [valuesStr, setValuesStr] = useState('500,520,480,510,490,500,530,470,460,520,510,490,500,550');
  const vals = valuesStr
    .split(',')
    .map((x) => parseFloat(x.trim()))
    .filter((x) => !isNaN(x));
  const result = calculateATR(n, vals);

  return (
    <div className="calc-card">
      <h3>ATR (Simple Moving Average)</h3>
      <div className="formula-block">
        <Latex block tex="\text{TR} = \max(\,|H - L|,\ |H - C_{n-1}|,\ |L - C_{n-1}|\,)" />
        <Latex block tex="\text{ATR}_n = \dfrac{1}{n} \sum_{i=1}^{n} \text{TR}_i" />
        <div className="formula-note">H = High, L = Low, C = Close</div>
      </div>
      <div className="input-group">
        <label>
          Period (n)
          <input type="number" value={n} onChange={(e) => setN(Number(e.target.value))} />
        </label>
        <label style={{ gridColumn: 'span 2' }}>
          TR Values (comma-separated)
          <input type="text" value={valuesStr} onChange={(e) => setValuesStr(e.target.value)} />
        </label>
      </div>
      <div className="result">
        {result ? `Used ${result.count} values | ATR = ${result.atr.toFixed(4)}` : 'Please enter valid TR values.'}
      </div>
    </div>
  );
}

function KdjCard() {
  const [close, setClose] = useState(60500);
  const [ll, setLl] = useState(59000);
  const [hh, setHh] = useState(62000);
  const [pk, setPk] = useState(50);
  const [pd, setPd] = useState(50);
  const { rsv, k, d, j } = calculateKDJ(close, ll, hh, pk, pd);

  return (
    <div className="calc-card">
      <h3>KDJ (Stochastic)</h3>
      <div className="formula-block">
        <Latex
          block
          tex="\text{RSV} = \left[ \dfrac{\text{Close}_n - \text{Lowest Low}_n}{\text{Highest High}_n - \text{Lowest Low}_n} \right] \times 100"
        />
        <Latex block tex="K_n = K_{n-1} \times \dfrac{2}{3} + \text{RSV} \times \dfrac{1}{3}" />
        <Latex block tex="D_n = D_{n-1} \times \dfrac{2}{3} + K_n \times \dfrac{1}{3}" />
        <Latex block tex="J_n = 3 \times K_n - 2 \times D_n" />
      </div>
      <div className="input-group">
        <label>
          Close
          <input type="number" value={close} onChange={(e) => setClose(Number(e.target.value))} />
        </label>
        <label>
          Lowest Low (n periods)
          <input type="number" value={ll} onChange={(e) => setLl(Number(e.target.value))} />
        </label>
        <label>
          Highest High (n periods)
          <input type="number" value={hh} onChange={(e) => setHh(Number(e.target.value))} />
        </label>
        <label>
          Prev K
          <input type="number" value={pk} onChange={(e) => setPk(Number(e.target.value))} />
        </label>
        <label>
          Prev D
          <input type="number" value={pd} onChange={(e) => setPd(Number(e.target.value))} />
        </label>
      </div>
      <div className="result">
        Result: RSV = {rsv.toFixed(2)} | K = {k.toFixed(2)} | D = {d.toFixed(2)} | J = {j.toFixed(2)}
      </div>
    </div>
  );
}
