import { useEffect, useMemo } from 'react';
import './StatsTab.css';
import { useRunsByThreshold, useTrades } from '../../api/hooks';
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
import { SectionTag } from '../common/SectionTag';

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
  const criteriaTests = useMemo(() => computeCriteriaTests(allTrades), [allTrades]);
  const overview = useMemo(() => computeBaselineOverview(allTrades), [allTrades]);
  const correlations = useMemo(() => computeCorrelations(allTrades), [allTrades]);
  const exitReasons = useMemo(() => computeExitReasons(allTrades), [allTrades]);
  const longShort = useMemo(() => computeLongShort(allTrades), [allTrades]);
  const ownBootstrap = useMemo(() => computeOwnBootstrapCI(allTrades), [allTrades]);

  const obs0 = runs.data?.['0']?.obs ?? [];
  const fvgCount = obs0.filter((o) => o.quality_fvg).length;
  const fvgPct = obs0.length > 0 ? (fvgCount / obs0.length) * 100 : 0;

  const fullBaseline = overview[0];
  const top3Combined = overview[overview.length - 1];

  const baseWins = base.filter((t) => t.pnl_pct > 0).length;
  const binomP = base.length > 0 ? binomialTestGreater(base.length, baseWins, 0.5) : NaN;
  const baseSqSum = fullBaseline?.stdDev != null ? fullBaseline.stdDev ** 2 * (base.length - 1) : 0;

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
        <p>
          Every figure below shows its formula and inputs. <span className="section-tag live">Live</span> sections
          are computed in your browser from /api/trades; <span className="section-tag reference">Reference</span>{' '}
          sections come from separate offline backtest runs whose per-trade data isn't exposed via the API, cited
          in each card.
        </p>
      </div>

      <div className="stats-grid">
        <div className="stat-card full-width">
          <h3>
            Orthogonal Analysis: Independent 5-Criterion Breakdown <SectionTag kind="live" />
          </h3>
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
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Statistical Significance</span>
              <span className="stat-metric-val">p = {isNaN(binomP) ? '--' : binomP.toFixed(4)}</span>
              <span className="stat-metric-sig">One-sided binomial, H0: p=0.5</span>
            </div>
          </div>
          <div className="method-block">
            <span className="method-label">Method — one-sided exact binomial test</span>
            <Latex
              block
              className="method-latex"
              tex="P(X \geq k) = \sum_{x=k}^{n} \binom{n}{x} 0.5^{x} \, 0.5^{\,n-x}"
            />
            <div className="method-line">
              n = {base.length} trades, k = {baseWins} wins → P(X ≥ {baseWins}) ={' '}
              <strong>{isNaN(binomP) ? '--' : binomP.toFixed(4)}</strong>
            </div>
          </div>
          <div className="method-block">
            <span className="method-label">Method — Fisher's exact test (win/loss × criterion True/False, two-sided)</span>
            <Latex
              block
              className="method-latex"
              tex="p = \sum_{\substack{x:\, P(x) \,\leq\, P(x_{\text{obs}})}} P(x), \quad P(x) = \dfrac{\binom{a+b}{x}\binom{c+d}{(a+c)-x}}{\binom{n}{a+c}}"
            />
            <div className="method-line">
              2×2 contingency table (wins, losses) × (criterion True, criterion False) per row below; sums the exact
              hypergeometric probability of every table with the same margins that is no more likely than the observed one.
            </div>
            <span className="method-label" style={{ marginTop: '0.6rem', display: 'block' }}>
              Method — Welch's unequal-variance t-test (pnl_pct, True vs. False)
            </span>
            <Latex
              block
              className="method-latex"
              tex="t = \dfrac{\overline{X}_1 - \overline{X}_2}{\sqrt{s_1^2/n_1 + s_2^2/n_2}}, \quad df = \dfrac{(s_1^2/n_1 + s_2^2/n_2)^2}{\frac{(s_1^2/n_1)^2}{n_1-1} + \frac{(s_2^2/n_2)^2}{n_2-1}}"
            />
            <div className="method-line">Two-sided p-value from the Student-t CDF at the Welch-Satterthwaite df above (not assumed equal-variance).</div>
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
                  <th>Fisher's Exact p</th>
                  <th>Welch's t (p)</th>
                </tr>
              </thead>
              <tbody>
                {orthogonal.map((row, i) => {
                  const test = criteriaTests[Math.floor(i / 2)];
                  return (
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
                      {row.subgroup === 'True' && (
                        <>
                          <td rowSpan={2} style={{ verticalAlign: 'middle' }}>
                            {test ? test.fisherP.toFixed(4) : '--'}
                          </td>
                          <td rowSpan={2} style={{ verticalAlign: 'middle' }}>
                            {test && !isNaN(test.welch.t) ? `${signedNum(test.welch.t, 3)} (${test.welch.p.toFixed(4)})` : 'n < 2'}
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="stat-card full-width">
          <h3>
            1. Baseline Strategy Overview & Return Concentration <SectionTag kind="live" />
          </h3>
          <p className="stat-desc">
            Single-dataset baseline performance summary (N = {base.length}) and concentration analysis of top
            historical winning trades.
          </p>
          <div className="method-block">
            <span className="method-label">Method</span>
            <Latex block className="method-latex" tex="\text{Win Rate} = \dfrac{\text{wins}}{N} \times 100" />
            <div className="method-line">
              = {baseWins} / {base.length} × 100 = <strong>{fullBaseline ? pct(fullBaseline.winRate) : '--'}</strong>
            </div>
            <Latex
              block
              className="method-latex"
              tex="\sigma = \sqrt{\dfrac{\sum (\text{pnl}_i - \overline{\text{pnl}})^2}{N-1}}"
            />
            <div className="method-line">
              = √({baseSqSum.toFixed(2)} / {base.length - 1}) ={' '}
              <strong>{fullBaseline?.stdDev != null ? pct(fullBaseline.stdDev) : '--'}</strong>
            </div>
            <Latex
              block
              className="method-latex"
              tex="\text{Share of Return} = \dfrac{\text{trade PnL}}{\text{total PnL}} \times 100"
            />
          </div>
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

        <div className="stat-card">
          <h3>
            2. Bootstrap Resampling (Own N = {ownBootstrap.n} Trades) <SectionTag kind="live" />
          </h3>
          <p className="stat-desc">
            Nonparametric percentile bootstrap on the baseline's own trade log: resample n = {ownBootstrap.n} returns
            with replacement, {ownBootstrap.b.toLocaleString()} times, to estimate a 95% CI on total and average
            return without assuming a parametric distribution.
          </p>
          <div className="method-block">
            <span className="method-label">Method — percentile bootstrap</span>
            <Latex
              block
              className="method-latex"
              tex="\hat{\theta}^{*}_b = f(X_1^{*}, \dots, X_n^{*}), \; X_i^{*} \sim \text{Uniform}(X_1,\dots,X_n) \text{ w/ replacement}, \; b = 1,\dots,B"
            />
            <div className="method-line">
              95% CI = [2.5th percentile, 97.5th percentile] of {'{'}θ̂*<sub>b</sub>{'}'}, B = {ownBootstrap.b.toLocaleString()}
            </div>
          </div>
          <div className="stat-metrics-flex">
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Total Return 95% CI</span>
              <span className="stat-metric-val">{signedPct(ownBootstrap.totalPoint)}</span>
              <span className="stat-metric-sig">
                [{signedPct(ownBootstrap.totalCI[0])}, {signedPct(ownBootstrap.totalCI[1])}]
              </span>
            </div>
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Avg Return/Trade 95% CI</span>
              <span className="stat-metric-val">{signedPct(ownBootstrap.avgPoint)}</span>
              <span className="stat-metric-sig">
                [{signedPct(ownBootstrap.avgCI[0])}, {signedPct(ownBootstrap.avgCI[1])}]
              </span>
            </div>
            <div className="stat-metric-badge">
              <span className="stat-metric-label">Resamples with Total ≤ 0%</span>
              <span className="stat-metric-val">{pct(ownBootstrap.pctResamplesTotalLe0, 2)}</span>
              <span className="stat-metric-sig">of {ownBootstrap.b.toLocaleString()} resamples</span>
            </div>
          </div>
          <div className="provenance-note">
            <span className="provenance-tag">Scope</span>
            <span>
              Resamples FROM the baseline's own {ownBootstrap.n} trades (a within-arm design) -- distinct from the
              between-arms ablation bootstrap in card 6 below, which resamples from a separate indicators-only trade
              pool not exposed via /api/trades.
            </span>
          </div>
        </div>

        <div className="stat-card">
          <h3>
            3. Minimum Detectable Effect / Power Analysis <SectionTag kind="live" />
          </h3>
          <p className="stat-desc">
            Given each criterion's observed True/False subgroup sizes and standard deviations, the smallest true
            mean-return gap this sample size could detect 80% of the time at α = 0.05.
          </p>
          <div className="method-block">
            <span className="method-label">Method — two-sample normal-approximation MDE</span>
            <Latex block className="method-latex" tex="\text{MDE} = (z_{\alpha/2} + z_{\beta}) \sqrt{\dfrac{s_1^2}{n_1} + \dfrac{s_2^2}{n_2}}" />
            <div className="method-line">
              z<sub>0.025</sub> = 1.9600, z<sub>0.80</sub> = 0.8416 (α = 0.05, power = 0.80). Where |observed diff| &lt;
              MDE, a non-significant test reads as "underpowered to rule out a gap up to ≈±MDE," not "no gap exists."
            </div>
          </div>
          <div className="table-container">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Criterion</th>
                  <th>n (True)</th>
                  <th>SD (True)</th>
                  <th>n (False)</th>
                  <th>SD (False)</th>
                  <th>Observed Diff (%)</th>
                  <th>MDE (%)</th>
                  <th>Detectable?</th>
                </tr>
              </thead>
              <tbody>
                {criteriaTests.map((row) => (
                  <tr key={row.label}>
                    <td style={{ fontWeight: 600 }}>{row.label}</td>
                    <td>{row.mde.n1}</td>
                    <td>{row.mde.sd1.toFixed(4)}</td>
                    <td>{row.mde.n2}</td>
                    <td>{row.mde.sd2.toFixed(4)}</td>
                    <td className={pnlClass(row.mde.observedDiff)}>{signedPct(row.mde.observedDiff, 4)}</td>
                    <td>{pct(row.mde.mde, 4)}</td>
                    <td className={row.mde.detectable ? 'pnl-pos' : undefined}>
                      {row.mde.detectable ? 'yes' : 'NO (underpowered)'}
                    </td>
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
          <h3>
            7. Hold Duration vs. PnL Return Correlation <SectionTag kind="live" />
          </h3>
          <p className="stat-desc">
            Evaluating linear and monotonic relationships between trade hold duration (in 4H bars) and PnL percentage
            return.
          </p>
          <div className="method-block">
            <span className="method-label">Method — Pearson product-moment correlation</span>
            <Latex
              block
              className="method-latex"
              tex="r = \dfrac{N\sum XY - \sum X \sum Y}{\sqrt{[N\sum X^2 - (\sum X)^2][N\sum Y^2 - (\sum Y)^2]}}"
            />
            <div className="method-line">
              = <strong>{signedNum(correlations.pearson.r)}</strong>,{' '}
              t = r·√((N−2)/(1−r²)) = {correlations.pearson.t.toFixed(3)} →{' '}
              {correlations.pearson.p < 0.001 ? 'p < 0.001' : `p = ${correlations.pearson.p.toFixed(4)}`} (Student-t,
              df = {correlations.n - 2})
            </div>
            <span className="method-label" style={{ marginTop: '0.6rem', display: 'block' }}>
              Method — Spearman rank correlation
            </span>
            <Latex
              block
              className="method-latex"
              tex="\rho = r_{\text{Pearson}}(\operatorname{rank}(X), \operatorname{rank}(Y))"
            />
            <div className="method-line">
              Average ranks assigned for ties, then Pearson r computed on the rank-transformed series. ={' '}
              <strong>{signedNum(correlations.spearman.rho)}</strong>,{' '}
              {correlations.spearman.p < 0.001 ? 'p < 0.001' : `p = ${correlations.spearman.p.toFixed(4)}`}
            </div>
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
          <h3>
            8. Exit Reason Distribution (Baseline Dataset N = {base.length}) <SectionTag kind="live" />
          </h3>
          <p className="stat-desc">
            Summary of hold times and trade performance grouped by closing event triggers across the full baseline
            dataset.
          </p>
          <div className="method-block">
            <span className="method-label">Method — grouped by exit_reason</span>
            <Latex
              block
              className="method-latex"
              tex="\overline{\text{PnL}}_r = \dfrac{\sum_{t \,\in\, r} \text{pnl}_t}{N_r}, \quad \text{WinRate}_r = \dfrac{\text{wins}_r}{N_r} \times 100"
            />
          </div>
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
          <h3>
            9. Directional Long vs. Short Breakdown <SectionTag kind="live" />
          </h3>
          <p className="stat-desc">Comparison of long versus short trade performance across the baseline backtest history.</p>
          <div className="method-block">
            <span className="method-label">Method — same Win Rate / Std Dev formulas as section 1, grouped by side</span>
            <Latex
              block
              className="method-latex"
              tex="\text{WinRate}_{\text{side}} = \dfrac{\text{wins}_{\text{side}}}{N_{\text{side}}} \times 100, \quad \sigma_{\text{side}} = \sqrt{\dfrac{\sum (\text{pnl}_i - \overline{\text{pnl}})^2}{N_{\text{side}}-1}}"
            />
          </div>
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
      <h3>
        4. Order Block Quality Equivalence & Methodological Caution <SectionTag kind="reference" />
      </h3>
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
      <div className="provenance-note">
        <span className="provenance-tag">Source</span>
        <span>
          Entry Bar 359 / 2624 details are read directly from their trade and Order Block records, not derived from a
          formula -- this card is a factual lookup, not a live statistical computation.
        </span>
      </div>
    </div>
  );
}

function AblationStudy() {
  const rows = [
    { variant: 'Arm 1: Full Strategy (OB-Gated Baseline)', anchor: "OB Boundary (ob['bottom'] - 0.5*ATR)", n: 27, wr: 70.37, total: 30.31, avg: 1.12, sd: 2.41, emphasis: true },
    { variant: 'Arm 2: Flat-ATR Indicators-Only (locked)', anchor: 'Entry Volatility Offset (close - 1.5*ATR)', n: 140, wr: 60.0, total: -14.63, avg: -0.1, sd: 2.35, emphasis: false },
    { variant: 'Arm 2: Flat-ATR Indicators-Only (this session’s reconstruction)', anchor: 'Entry Volatility Offset (close - 1.5*ATR)', n: 140, wr: 47.14, total: -13.72, avg: -0.1, sd: 2.81, emphasis: false, reconstructed: true },
    { variant: 'Arm 3: Swing-Anchored Indicators-Only (locked)', anchor: '5-Bar Swing Extreme (pivot - 0.5*ATR)', n: 138, wr: 55.07, total: -25.5, avg: -0.18, sd: 2.52, emphasis: false },
    { variant: 'Arm 3: Swing-Anchored Indicators-Only (this session’s reconstruction)', anchor: '5-Bar Swing Extreme (pivot - 0.5*ATR)', n: 138, wr: 43.48, total: -23.85, avg: -0.17, sd: 2.8, emphasis: false, reconstructed: true },
  ];
  return (
    <div className="stat-card full-width">
      <h3>
        5. 3-Arm Controlled Ablation Study (Isolating the Order Block Structural Gate) <SectionTag kind="reference" />
      </h3>
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
              <tr key={r.variant} className={r.emphasis ? 'emphasis' : undefined} style={r.reconstructed ? { fontStyle: 'italic', color: 'var(--text-muted)' } : undefined}>
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
      <div className="warning-box">
        <div className="warning-title">⚠️ Reconstruction-Fidelity Finding: Trade Counts Match, Win Rate Diverges</div>
        <div>
          The original script that produced Arms 2/3's per-trade pools was never committed to this repository
          (STUDY_REFERENCE.md Sec.6.4/7). <code>analysis/ablation_reconstruction.py</code> is a fresh, best-faith
          reconstruction from the documented ablation design, run this session: it reproduces the locked trade
          counts <strong>exactly</strong> (140 and 138) and lands close on total return, but its win rate is ~13 and
          ~11.6 points lower than the locked figures. The exact N match is evidence the entry-side logic (indicator
          conditions minus the OB touch requirement) is faithfully reconstructed; the divergence is isolated to
          exit/take-profit mechanics -- most plausibly this reconstruction's fixed-2R take-profit vs. a possible
          structural/OB-anchored TP in the original uncommitted script. Reported as a finding, not resolved: the
          locked figures above are unchanged.
        </div>
      </div>
      <div className="provenance-note">
        <span className="provenance-tag">Source</span>
        <span>
          Locked rows: separate backtest runs cited from CLAUDE.md, whose original trade sets aren't recomputable
          in-browser (only Arm 1's trades are exposed via /api/trades). Reconstructed rows:{' '}
          <code>analysis/ablation_reconstruction.py</code>, this session, also offline (not live in the browser).
        </span>
      </div>
    </div>
  );
}

function BootstrapAudit() {
  return (
    <div className="stat-card full-width">
      <h3>
        6. Ablation-Arm Bootstrap Resampling Audit (B = 2,000) & Entry-Bar Overlap Audit <SectionTag kind="reference" />
      </h3>
      <p className="stat-desc">
        Resampling n=27 trades from the 138-trade indicators-only pool over 2,000 iterations to control for sample
        size disparity, alongside entry-bar overlap analysis.
      </p>
      <div className="callout-grid">
        <div className="callout-card">
          <div className="callout-title">Bootstrap Resampling (locked, B = 2,000, n = 27)</div>
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
          <div className="callout-title">Entry-Bar Overlap Audit (locked)</div>
          <div className="stat-metric-val" style={{ color: 'var(--good)' }}>
            92.59% (25 / 27 Entries)
          </div>
          <div style={{ color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            25 out of 27 baseline OB entry bars coincide exactly with valid raw indicator triggers, proving the OB
            gate selects a high-conviction subset.
          </div>
        </div>
        <div className="callout-card" style={{ fontStyle: 'italic' }}>
          <div className="callout-title">Bootstrap vs. this session's Arm 3 reconstruction (B = 2,000, n = 27)</div>
          <div className="stat-metric-val" style={{ color: 'var(--text-muted)' }}>
            Empirical p = 0.0090 (avg return) / 0.0040 (win rate)
          </div>
          <div style={{ color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Resampled n=27 Avg Return Percentiles: 2.5th%: -1.26% | 50th%: -0.18% | 97.5th%: +0.89%
            <br />
            Still significant (baseline avg return clears the 97.5th percentile of both the locked and reconstructed
            pools), despite the reconstructed pool's lower win rate -- see card 5's divergence note.
          </div>
        </div>
      </div>
      <div className="provenance-note">
        <span className="provenance-tag">Source</span>
        <span>
          Locked cards: 2,000 resamples with replacement of n=27 from the 138-trade indicators-only pool (Ablation
          Arm 3's original trade set), cited from CLAUDE.md/docs -- that pool isn't exposed via /api/trades, so this
          can't be recomputed in-browser. Reconstructed card: same bootstrap procedure run this session against{' '}
          <code>analysis/ablation_reconstruction.py</code>'s Arm 3 pool instead (also offline, not live in-browser) --
          see card 5's reconstruction-fidelity finding before treating this as a replacement for the locked figure.
        </span>
      </div>
    </div>
  );
}

function MethodologySynthesis() {
  return (
    <div className="stat-card full-width">
      <h3>
        10. Research Methodology Synthesis & Conclusions <SectionTag kind="reference" />
      </h3>
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
