import { useEffect, useMemo } from 'react';
import './StatsTab.css';
import { useRunsByThreshold, useTrades } from '../../api/hooks';
import {
  baselineTrades,
  computeBaselineOverview,
  computeCorrelations,
  computeExitReasons,
  computeLongShort,
  computeOrthogonalCriteria,
} from '../stats/statsCompute';
import { runDistributionSelfChecks } from '../stats/statMath';

const pct = (v: number, digits = 2) => `${v.toFixed(digits)}%`;
const signedPct = (v: number, digits = 2) => `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`;
const signedNum = (v: number, digits = 4) => `${v > 0 ? '+' : ''}${v.toFixed(digits)}`;
const pnlClass = (v: number) => (v >= 0 ? 'pnl-pos' : 'pnl-neg');

export function StatsTab() {
  const trades = useTrades();
  const runs = useRunsByThreshold();

  useEffect(() => {
    const check = runDistributionSelfChecks();
    if (!check.valid) {
      console.error('[Stats Engine] Numerical approximation verification FAILED:', check.errors);
    }
  }, []);

  const allTrades = trades.data ?? [];
  const base = useMemo(() => baselineTrades(allTrades), [allTrades]);
  const orthogonal = useMemo(() => computeOrthogonalCriteria(allTrades), [allTrades]);
  const overview = useMemo(() => computeBaselineOverview(allTrades), [allTrades]);
  const correlations = useMemo(() => computeCorrelations(allTrades), [allTrades]);
  const exitReasons = useMemo(() => computeExitReasons(allTrades), [allTrades]);
  const longShort = useMemo(() => computeLongShort(allTrades), [allTrades]);

  const obs0 = runs.data?.['0']?.obs ?? [];
  const fvgCount = obs0.filter((o) => o.quality_fvg).length;
  const fvgPct = obs0.length > 0 ? (fvgCount / obs0.length) * 100 : 0;

  const fullBaseline = overview[0];
  const top3Combined = overview[overview.length - 1];

  if (trades.loading || runs.loading) {
    return <div className="stats-tab">Loading trade data...</div>;
  }
  if (trades.error) {
    return (
      <div className="stats-tab" role="alert">
        Failed to load /api/trades: {trades.error.message}
      </div>
    );
  }

  return (
    <div className="stats-tab">
      <div className="stats-header">
        <h2>Research Statistics & Methodology Synthesis</h2>
        <p>Live statistical test validation compiled directly from the BTCUSDT 4H backtest dataset (2022–2026).</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card full-width">
          <h3>Orthogonal Analysis: Independent 5-Criterion Breakdown</h3>
          <p className="stat-desc">
            Evaluating trade performance and return contribution for each of the 5 criteria independently across the
            N={base.length} baseline trade dataset.
          </p>
          <div className="stat-metrics-flex" style={{ marginBottom: '1.1rem' }}>
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Baseline Strategy Return</span>
              <span className="stat-metric-val">{fullBaseline ? signedPct(fullBaseline.totalPnl) : '--'}</span>
              <span className="stat-metric-sig">
                N = {base.length} Trades ({fullBaseline ? pct(fullBaseline.winRate) : '--'} WR)
              </span>
            </div>
            <div className="stat-metric-badge">
              <span className="stat-metric-label">FVG Population</span>
              <span className="stat-metric-val">{pct(fvgPct, 1)}</span>
              <span className="stat-metric-sig">
                {fvgCount} / {obs0.length} Detected OBs
              </span>
            </div>
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Top 3 Return Concentration</span>
              <span className="stat-metric-val">{top3Combined ? pct(top3Combined.shareOfReturn, 2) : '--'}</span>
              <span className="stat-metric-sig">
                {top3Combined ? signedPct(top3Combined.totalPnl) : '--'} from Top 3 Winners
              </span>
            </div>
          </div>
          <div className="table-container">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Criterion</th>
                  <th>Subgroup</th>
                  <th>Count (N)</th>
                  <th>% of Trades</th>
                  <th>Sum PnL (%)</th>
                  <th>% of Total Return</th>
                  <th>Mean Return (%)</th>
                  <th>Median Return (%)</th>
                  <th>Best Trade PnL (%)</th>
                </tr>
              </thead>
              <tbody>
                {orthogonal.map((row, i) => (
                  <tr key={`${row.label}-${row.subgroup}`} style={i % 2 === 1 ? { borderBottom: '2px solid var(--border-strong)' } : undefined}>
                    {row.subgroup === 'True' && (
                      <td rowSpan={2} style={{ fontWeight: 600, verticalAlign: 'middle' }}>
                        {row.label}
                      </td>
                    )}
                    <td>{row.subgroup}</td>
                    <td>{row.n}</td>
                    <td>{pct(row.pctOfTrades, 1)}</td>
                    <td className={pnlClass(row.sumPnl)}>{signedPct(row.sumPnl)}</td>
                    <td>{pct(row.pctOfTotalReturn, 1)}</td>
                    <td>{signedPct(row.meanReturn)}</td>
                    <td>{signedPct(row.medianReturn)}</td>
                    <td>+{row.bestTrade.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="stat-card full-width">
          <h3>1. Baseline Strategy Overview & Return Concentration</h3>
          <p className="stat-desc">
            Single-dataset baseline performance summary (N = {base.length}) and concentration analysis of top
            historical winning trades.
          </p>
          <div className="table-container">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Trade Rank / Group</th>
                  <th>Trade Count (N)</th>
                  <th>Win Rate (%)</th>
                  <th>Total PnL (%)</th>
                  <th>Share of Total Return (%)</th>
                  <th>Avg Return / Trade (%)</th>
                  <th>Std Dev (%)</th>
                </tr>
              </thead>
              <tbody>
                {overview.map((row, i) => (
                  <tr key={row.label} className={i === 0 || i === overview.length - 1 ? 'emphasis' : undefined}>
                    <td>{row.label}</td>
                    <td>{row.n}</td>
                    <td>{pct(row.winRate)}</td>
                    <td className={pnlClass(row.totalPnl)}>{signedPct(row.totalPnl)}</td>
                    <td>{pct(row.shareOfReturn, 1)}</td>
                    <td>{signedPct(row.avgReturn)}</td>
                    <td>{row.stdDev == null ? '--' : pct(row.stdDev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <QualityEquivalence />
        <AblationStudy />
        <BootstrapAudit />

        <div className="stat-card">
          <h3>5. Hold Duration vs. PnL Return Correlation</h3>
          <p className="stat-desc">
            Evaluating linear and monotonic relationships between trade hold duration (in 4H bars) and PnL percentage
            return.
          </p>
          <div className="math-block">
            r = (N·ΣXY − ΣX·ΣY) / √([N·ΣX² − (ΣX)²][N·ΣY² − (ΣY)²]) = {signedNum(correlations.pearson.r)}
            {correlations.pearson.p < 0.001 ? ' (p < 0.001)' : ` (p = ${correlations.pearson.p.toFixed(4)})`}
          </div>
          <div className="stat-metrics-flex">
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Pearson r</span>
              <span className="stat-metric-val">{signedNum(correlations.pearson.r)}</span>
              <span className="stat-metric-sig">
                {correlations.pearson.p < 0.001 ? 'p < 0.001' : `p = ${correlations.pearson.p.toFixed(4)}`} (t ={' '}
                {correlations.pearson.t.toFixed(2)})
              </span>
            </div>
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Spearman ρ</span>
              <span className="stat-metric-val">{signedNum(correlations.spearman.rho)}</span>
              <span className="stat-metric-sig">
                {correlations.spearman.p < 0.001 ? 'p < 0.001' : `p = ${correlations.spearman.p.toFixed(4)}`}
              </span>
            </div>
          </div>
        </div>

        <div className="stat-card">
          <h3>6. Exit Reason Distribution (Baseline Dataset N = {base.length})</h3>
          <p className="stat-desc">
            Summary of hold times and trade performance grouped by closing event triggers across the full baseline
            dataset.
          </p>
          <div className="table-container">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Exit Reason</th>
                  <th>Count (N)</th>
                  <th>Percentage (%)</th>
                  <th>Avg PnL (%)</th>
                  <th>Win Rate (%)</th>
                </tr>
              </thead>
              <tbody>
                {exitReasons.map((row) => (
                  <tr key={row.reason}>
                    <td style={{ fontWeight: 600 }}>{row.reason}</td>
                    <td>{row.n}</td>
                    <td>{pct(row.pct)}</td>
                    <td className={pnlClass(row.avgPnl)}>{signedPct(row.avgPnl)}</td>
                    <td>{pct(row.winRate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="stat-card full-width">
          <h3>7. Directional Long vs. Short Breakdown</h3>
          <p className="stat-desc">Comparison of long versus short trade performance across the baseline backtest history.</p>
          <div className="table-container">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Direction</th>
                  <th>Count (N)</th>
                  <th>Win Rate (%)</th>
                  <th>Total Return (%)</th>
                  <th>Avg Return (%)</th>
                  <th>Std Dev (%)</th>
                </tr>
              </thead>
              <tbody>
                {longShort.map((row) => (
                  <tr key={row.side}>
                    <td style={{ fontWeight: 600 }}>{row.side}</td>
                    <td>{row.n}</td>
                    <td>{pct(row.winRate)}</td>
                    <td className={pnlClass(row.total)}>{signedPct(row.total)}</td>
                    <td>{signedPct(row.avg)}</td>
                    <td>{pct(row.sd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <MethodologySynthesis />
      </div>
    </div>
  );
}

/**
 * Sections 2-4 below are static reference text in gui.js too (renderQualityEquivalence,
 * renderAblationStudy, renderBootstrapAudit -- gui.js:2166-2260 -- take a `trades` param
 * but never read it). They describe specific named historical trades and the locked
 * ablation/bootstrap results from CLAUDE.md, not a live recomputation.
 */
function QualityEquivalence() {
  return (
    <div className="stat-card full-width">
      <h3>2. Order Block Quality Equivalence & Methodological Caution</h3>
      <p className="stat-desc">
        Methodological analysis evaluating trade quality score equivalence between top winners and losses, and
        co-occurrence multi-counting cautions.
      </p>
      <div className="callout-grid">
        <div className="callout-card win">
          <div className="callout-title">🥇 Single Best Winning Trade (+6.69% PnL)</div>
          <div>
            <strong>Entry Bar 359 (SHORT)</strong> — Composite Score: <strong>4 / 5</strong>
            <br />
            Satisfies: <code>LargeBar</code>, <code>FVG</code>, <code>LiqSweep</code>, <code>VolExpansion</code>.
            <br />
            Exit Reason: <code>ATR MOVE EXIT</code>
          </div>
        </div>
        <div className="callout-card loss">
          <div className="callout-title">🔻 Single Worst Loss Trade (-4.65% PnL)</div>
          <div>
            <strong>Entry Bar 2624 (SHORT)</strong> — Composite Score: <strong>4 / 5</strong>
            <br />
            Satisfies: <code>LargeBar</code>, <code>FVG</code>, <code>LiqSweep</code>, <code>VolExpansion</code>.
            <br />
            Exit Reason: <code>HIT STOP LOSS</code>
          </div>
        </div>
      </div>
      <div className="warning-box">
        <div className="warning-title">⚠️ Methodological Caution: Multi-Criteria Co-occurrence</div>
        <div>
          The +6.69% top trade PnL reported across <code>LargeBar</code>, <code>FVG</code>, <code>LiqSweep</code>,
          and <code>VolExpansion</code> in the orthogonal reference table represents a single shared trade (Entry Bar
          359) that satisfied four criteria simultaneously, NOT four independent positive confirmations. Out of all 5
          criteria, only <code>Displacement</code> featured a distinct top contributor (+1.63% PnL, Bar 6991). High
          composite quality score (Score 4) does not prevent stop-outs, as demonstrated by the worst loss (-4.65%
          PnL at Bar 2624) sharing the exact same 4-criterion footprint.
        </div>
      </div>
    </div>
  );
}

function AblationStudy() {
  const rows = [
    { variant: 'Arm 1: Full Strategy (OB-Gated Baseline)', anchor: "OB Boundary (ob['bottom'] - 0.5*ATR)", n: 27, wr: 70.37, total: 30.31, avg: 1.12, sd: 2.41, emphasis: true },
    { variant: 'Arm 2: Flat-ATR Indicators-Only', anchor: 'Entry Volatility Offset (close - 1.5*ATR)', n: 140, wr: 60.0, total: -14.63, avg: -0.1, sd: 2.35, emphasis: false },
    { variant: 'Arm 3: Swing-Anchored Indicators-Only', anchor: '5-Bar Swing Extreme (pivot - 0.5*ATR)', n: 138, wr: 55.07, total: -25.5, avg: -0.18, sd: 2.52, emphasis: false },
  ];
  return (
    <div className="stat-card full-width">
      <h3>3. 3-Arm Controlled Ablation Study (Isolating the Order Block Structural Gate)</h3>
      <p className="stat-desc">
        Comparing the full OB-gated strategy against indicator-only entry triggers (flat ATR stop vs. 5-bar
        swing-pivot stop) to test whether the OB gate adds measurable value independent of indicators.
      </p>
      <div className="table-container">
        <table className="stats-table">
          <thead>
            <tr>
              <th>Strategy Variant</th>
              <th>Risk Placement Anchoring</th>
              <th>Count (N)</th>
              <th>Win Rate (%)</th>
              <th>Total Net Return (%)</th>
              <th>Avg Return / Trade (%)</th>
              <th>Std Dev (%)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.variant} className={r.emphasis ? 'emphasis' : undefined}>
                <td>{r.variant}</td>
                <td>{r.anchor}</td>
                <td>{r.n}</td>
                <td>{pct(r.wr)}</td>
                <td className={pnlClass(r.total)}>{signedPct(r.total)}</td>
                <td>{signedPct(r.avg)}</td>
                <td>{pct(r.sd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BootstrapAudit() {
  return (
    <div className="stat-card full-width">
      <h3>4. Bootstrap Resampling Audit (B = 2,000) & Entry-Bar Overlap Audit</h3>
      <p className="stat-desc">
        Resampling n=27 trades from the 138-trade indicators-only pool over 2,000 iterations to control for sample
        size disparity, alongside entry-bar overlap analysis.
      </p>
      <div className="callout-grid">
        <div className="callout-card">
          <div className="callout-title">Bootstrap Resampling (B = 2,000, n = 27)</div>
          <div className="stat-metric-val" style={{ color: 'var(--good)' }}>
            Empirical p = 0.0020
          </div>
          <div style={{ color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Resampled n=27 Mean Return Percentiles:
            <br />
            2.5th%: -1.17% | 50th%: -0.17% | 97.5th%: +0.70%
          </div>
        </div>
        <div className="callout-card">
          <div className="callout-title">Entry-Bar Overlap Audit</div>
          <div className="stat-metric-val" style={{ color: 'var(--good)' }}>
            92.59% (25 / 27 Entries)
          </div>
          <div style={{ color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            25 out of 27 baseline OB entry bars coincide exactly with valid raw indicator triggers, proving the OB
            gate selects a high-conviction subset.
          </div>
        </div>
      </div>
    </div>
  );
}

function MethodologySynthesis() {
  return (
    <div className="stat-card full-width">
      <h3>8. Research Methodology Synthesis & Conclusions</h3>
      <p className="stat-desc">
        Summary of structural revisions, collinearity resolution, and key takeaways from the backtest evaluation.
      </p>
      <div className="prose">
        <p>
          <strong>1. Retirement of Composite Score Sweeps:</strong> The original 0–5 composite quality score sweep
          created nested subsets where higher threshold trade sets were strict subsets of lower ones (Q3 ⊂ Q2 ⊂ Q1 ⊂
          Q0), confounding statistical comparison. The strategy is now evaluated as a single un-truncated baseline
          (N=27, WR=70.37%, Return=+30.31%).
        </p>
        <p>
          <strong>2. Independent Orthogonal Criteria:</strong> Evaluating each of the 5 criteria independently shows
          that no single Order Block annotation drives statistically significant performance disparity. The core
          trading edge is derived from the MACD histogram momentum alignment, KDJ acceleration, ATR regime filter,
          and Risk-Reward structure.
        </p>
        <p>
          <strong>3. Indispensability of the OB Gate:</strong> Controlled ablation demonstrates that removing the OB
          spatial gate increases trade volume by 5.2x (N=140) but degrades net return to -14.63% (flat ATR stop) and
          -25.50% (swing pivot stop). The OB structural gate is indispensable for spatial entry selection, filtering
          out low-conviction indicator triggers during market consolidation.
        </p>
      </div>
    </div>
  );
}
