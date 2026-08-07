import { Fragment, useEffect, useMemo } from 'react';
import './StatsTab.css';
import { useAblationReconstruction, useTrades } from '../../api/hooks';
import {
  baselineTrades,
  computeBaselineOverview,
  computeCorrelations,
  computeCriteriaTests,
  computeExitReasons,
  computeLongShort,
  computeOrthogonalCriteria,
  computeOwnBootstrapCI,
} from '../stats/statsCompute';
import { binomialTestGreater, runDistributionSelfChecks } from '../stats/statMath';
import { Latex } from '../common/Latex';

const pct = (v: number, d = 2) => `${v.toFixed(d)}%`;
const spct = (v: number, d = 2) => `${v > 0 ? '+' : ''}${v.toFixed(d)}%`;
const snum = (v: number, d = 4) => `${v > 0 ? '+' : ''}${v.toFixed(d)}`;
const pnlClass = (v: number) => (v >= 0 ? 'pnl-pos' : 'pnl-neg');

export function StatsTab() {
  const trades = useTrades();
  const ablation = useAblationReconstruction();

  useEffect(() => {
    const check = runDistributionSelfChecks();
    if (!check.valid) console.error('[Stats Engine] Numerical self-check FAILED:', check.errors);
  }, []);

  const allTrades = trades.data ?? [];
  const base = useMemo(() => baselineTrades(allTrades), [allTrades]);
  const overview = useMemo(() => computeBaselineOverview(allTrades), [allTrades]);
  const orthogonal = useMemo(() => computeOrthogonalCriteria(allTrades), [allTrades]);
  const criteriaTests = useMemo(() => computeCriteriaTests(allTrades), [allTrades]);
  const ownBootstrap = useMemo(() => computeOwnBootstrapCI(allTrades), [allTrades]);
  const correlations = useMemo(() => computeCorrelations(allTrades), [allTrades]);
  const exitReasons = useMemo(() => computeExitReasons(allTrades), [allTrades]);
  const longShort = useMemo(() => computeLongShort(allTrades), [allTrades]);

  const fullBaseline = overview[0];
  const baseWins = base.filter((t) => t.pnl_pct > 0).length;
  const binomP = base.length > 0 ? binomialTestGreater(base.length, baseWins, 0.5) : NaN;

  if (trades.loading) return <div className="stats-tab-loading">Loading trade data...</div>;
  if (trades.error) {
    return (
      <div className="stats-tab-loading" role="alert">
        Failed to load /api/trades: {trades.error.message}
      </div>
    );
  }

  return (
    <div className="stats-tab">
      <p className="stats-legend text-muted">
        <span className="tag tag-live">LIVE</span> sections are computed in your browser from /api/trades, independent
        of the Python backend. <span className="tag tag-ref">REF</span> sections cite a separate offline artifact
        whose per-trade data isn't exposed via the API.
      </p>

      <section className="stat-card panel">
        <h3>
          Baseline Overview <span className="tag tag-live">LIVE</span>
        </h3>
        <div className="method-block">
          <Latex block tex="\text{Win Rate} = \dfrac{\text{wins}}{N} \times 100" />
          <div className="method-line">
            = {baseWins} / {base.length} × 100 = <strong>{fullBaseline ? pct(fullBaseline.winRate) : '--'}</strong>
          </div>
          <Latex block tex="P(X \geq k) = \sum_{x=k}^{n} \binom{n}{x} 0.5^{x} 0.5^{n-x}" />
          <div className="method-line">
            One-sided exact binomial, n={base.length}, k={baseWins} → P(X≥{baseWins}) = <strong>{fmt4(binomP)}</strong>
          </div>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Group</th>
                <th>N</th>
                <th>Win Rate</th>
                <th>Total PnL</th>
                <th>Share of Return</th>
                <th>Avg Return</th>
                <th>SD</th>
              </tr>
            </thead>
            <tbody>
              {overview.map((row, i) => (
                <tr key={row.label} className={i === 0 || i === overview.length - 1 ? 'emphasis' : undefined}>
                  <td>{row.label}</td>
                  <td>{row.n}</td>
                  <td>{pct(row.winRate)}</td>
                  <td className={pnlClass(row.totalPnl)}>{spct(row.totalPnl)}</td>
                  <td>{pct(row.shareOfReturn, 1)}</td>
                  <td>{spct(row.avgReturn)}</td>
                  <td>{row.stdDev == null ? '--' : pct(row.stdDev)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="stat-card panel">
        <h3>
          Orthogonal Criteria: Fisher's Exact + Welch's t-test + MDE <span className="tag tag-live">LIVE</span>
        </h3>
        <div className="method-block">
          <Latex
            block
            tex="p = \sum_{x:\,P(x)\leq P(x_{\text{obs}})} P(x), \quad P(x) = \dfrac{\binom{a+b}{x}\binom{c+d}{(a+c)-x}}{\binom{n}{a+c}}"
          />
          <div className="method-line">Fisher's exact test (two-sided), win/loss × criterion True/False.</div>
          <Latex
            block
            tex="t = \dfrac{\bar{X}_1-\bar{X}_2}{\sqrt{s_1^2/n_1+s_2^2/n_2}}, \quad \text{MDE} = (z_{\alpha/2}+z_\beta)\sqrt{s_1^2/n_1+s_2^2/n_2}"
          />
          <div className="method-line">Welch's t-test on pnl_pct; MDE at α=0.05, power=0.80 (z=1.9600, z=0.8416).</div>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Criterion</th>
                <th>Subgroup</th>
                <th>N</th>
                <th>Mean Return</th>
                <th>Best Trade</th>
                <th>Fisher p</th>
                <th>Welch t (p)</th>
                <th>MDE</th>
              </tr>
            </thead>
            <tbody>
              {orthogonal.map((row, i) => {
                const test = criteriaTests[Math.floor(i / 2)];
                return (
                  <tr key={`${row.label}-${row.subgroup}`}>
                    {row.subgroup === 'True' && (
                      <td rowSpan={2} className="row-label">
                        {row.label}
                      </td>
                    )}
                    <td>{row.subgroup}</td>
                    <td>{row.n}</td>
                    <td>{spct(row.meanReturn)}</td>
                    <td className="pnl-pos">+{row.bestTrade.toFixed(2)}%</td>
                    {row.subgroup === 'True' && (
                      <>
                        <td rowSpan={2}>{test ? test.fisherP.toFixed(4) : '--'}</td>
                        <td rowSpan={2}>
                          {test && !isNaN(test.welch.t) ? `${snum(test.welch.t, 3)} (${test.welch.p.toFixed(4)})` : 'n<2'}
                        </td>
                        <td rowSpan={2}>
                          {test ? `${pct(test.mde.mde, 2)} ${test.mde.detectable ? '' : '(underpowered)'}` : '--'}
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div className="stat-card-row">
        <section className="stat-card panel">
          <h3>
            Bootstrap CI (Own N={ownBootstrap.n}) <span className="tag tag-live">LIVE</span>
          </h3>
          <div className="method-block">
            <Latex block tex="\hat\theta^*_b = f(X_1^*,\dots,X_n^*),\; X_i^* \sim \text{Uniform}(X_1,\dots,X_n)" />
            <div className="method-line">Percentile bootstrap, B={ownBootstrap.b.toLocaleString()}.</div>
          </div>
          <div className="stat-metrics">
            <div className="stat-metric">
              <span className="text-muted">Total Return 95% CI</span>
              <strong>
                [{spct(ownBootstrap.totalCI[0])}, {spct(ownBootstrap.totalCI[1])}]
              </strong>
            </div>
            <div className="stat-metric">
              <span className="text-muted">Avg Return/Trade 95% CI</span>
              <strong>
                [{spct(ownBootstrap.avgCI[0])}, {spct(ownBootstrap.avgCI[1])}]
              </strong>
            </div>
          </div>
        </section>

        <section className="stat-card panel">
          <h3>
            Correlation: Hold Duration vs PnL <span className="tag tag-live">LIVE</span>
          </h3>
          <div className="method-block">
            <Latex block tex="r = \dfrac{N\sum XY - \sum X \sum Y}{\sqrt{[N\sum X^2-(\sum X)^2][N\sum Y^2-(\sum Y)^2]}}" />
          </div>
          <div className="stat-metrics">
            <div className="stat-metric">
              <span className="text-muted">Pearson r</span>
              <strong>
                {snum(correlations.pearson.r)} (p={correlations.pearson.p < 0.001 ? '<0.001' : correlations.pearson.p.toFixed(4)})
              </strong>
            </div>
            <div className="stat-metric">
              <span className="text-muted">Spearman ρ</span>
              <strong>
                {snum(correlations.spearman.rho)} (p=
                {correlations.spearman.p < 0.001 ? '<0.001' : correlations.spearman.p.toFixed(4)})
              </strong>
            </div>
          </div>
        </section>
      </div>

      <div className="stat-card-row">
        <section className="stat-card panel">
          <h3>
            Exit Reason Distribution <span className="tag tag-live">LIVE</span>
          </h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>N</th>
                  <th>%</th>
                  <th>Avg PnL</th>
                  <th>Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {exitReasons.map((r) => (
                  <tr key={r.reason}>
                    <td>{r.reason}</td>
                    <td>{r.n}</td>
                    <td>{pct(r.pct)}</td>
                    <td className={pnlClass(r.avgPnl)}>{spct(r.avgPnl)}</td>
                    <td>{pct(r.winRate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="stat-card panel">
          <h3>
            Long vs Short <span className="tag tag-live">LIVE</span>
          </h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Side</th>
                  <th>N</th>
                  <th>Win Rate</th>
                  <th>Total</th>
                  <th>Avg</th>
                  <th>SD</th>
                </tr>
              </thead>
              <tbody>
                {longShort.map((r) => (
                  <tr key={r.side}>
                    <td>{r.side}</td>
                    <td>{r.n}</td>
                    <td>{pct(r.winRate)}</td>
                    <td className={pnlClass(r.total)}>{spct(r.total)}</td>
                    <td>{spct(r.avg)}</td>
                    <td>{pct(r.sd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <AblationSection data={ablation.data} loading={ablation.loading} error={ablation.error} />
    </div>
  );
}

function fmt4(v: number) {
  return isNaN(v) ? '--' : v.toFixed(4);
}

function AblationSection({
  data,
  loading,
  error,
}: {
  data: ReturnType<typeof useAblationReconstruction>['data'];
  loading: boolean;
  error: Error | null;
}) {
  return (
    <section className="stat-card panel">
      <h3>
        Ablation Study: OB Gate vs Indicators-Only <span className="tag tag-ref">REF</span>
      </h3>
      <p className="stat-desc text-muted">
        Comparing the full OB-gated strategy against two indicators-only configurations. Sourced from{' '}
        <code>artifacts/ablation_reconstruction.json</code> -- not recomputable in-browser, since only the OB-gated
        baseline's trades are exposed via /api/trades.
      </p>
      {loading && <p className="text-muted">Loading...</p>}
      {error && <p className="text-critical">Failed to load: {error.message}</p>}
      {data && (
        <>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Configuration</th>
                  <th>N</th>
                  <th>Win Rate</th>
                  <th>Total Return</th>
                </tr>
              </thead>
              <tbody>
                <tr className="emphasis">
                  <td>Full Strategy (OB-gated baseline)</td>
                  <td>{data.baseline.n}</td>
                  <td>{pct(data.baseline.win_rate)}</td>
                  <td className={pnlClass(data.baseline.total_return)}>{spct(data.baseline.total_return)}</td>
                </tr>
                {(['flat_atr', 'swing_pivot'] as const).map((key) => {
                  const arm = data.arms[key];
                  return (
                    <Fragment key={key}>
                      <tr>
                        <td>{arm.label} (locked)</td>
                        <td>{arm.locked.n}</td>
                        <td>{pct(arm.locked.win_rate)}</td>
                        <td className={pnlClass(arm.locked.total_return)}>{spct(arm.locked.total_return)}</td>
                      </tr>
                      <tr className="row-muted">
                        <td>{arm.label} (this session's reconstruction)</td>
                        <td>{arm.reconstructed.n}</td>
                        <td>{pct(arm.reconstructed.win_rate)}</td>
                        <td className={pnlClass(arm.reconstructed.total_return)}>{spct(arm.reconstructed.total_return)}</td>
                      </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="rail rail-warning ablation-note">
            Trade counts match the locked figures exactly (140, 138); win rate diverges (~13 / ~11.6 points lower).
            The original script that produced the locked per-trade pools was never committed --{' '}
            <code>analysis/ablation_reconstruction.py</code> is a best-faith reconstruction from the documented
            design, reported as a finding, not a replacement for the locked figures.
          </div>
        </>
      )}
    </section>
  );
}
