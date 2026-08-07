import { useMemo } from 'react';
import './SolutionsTab.css';
import { useTrades } from '../../api/hooks';
import { baselineTrades, computeCriteriaTests, computeOwnBootstrapCI } from '../stats/statsCompute';
import { binomialTestGreater, computeCorrelationPearson, computeCorrelationSpearman } from '../stats/statMath';
import {
  binomialDerivation,
  bootstrapDerivation,
  fisherDerivation,
  mdeDerivation,
  pearsonDerivation,
  spearmanDerivation,
  welchDerivation,
} from '../stats/derivationSteps';
import { DerivationCard } from '../stats/DerivationCard';

/**
 * Full step-by-step derivation of every statistic on the Stats tab --
 * variables, then general formula, then substitution, then result, per
 * criterion (not one representative example). Calls the exact same
 * statsCompute.ts/statMath.ts functions StatsTab.tsx calls, on the same
 * /api/trades data, so these numbers can never drift from what Stats shows.
 */
export function SolutionsTab() {
  const trades = useTrades();
  const allTrades = trades.data ?? [];

  const base = useMemo(() => baselineTrades(allTrades), [allTrades]);
  const criteriaTests = useMemo(() => computeCriteriaTests(allTrades), [allTrades]);
  const ownBootstrap = useMemo(() => computeOwnBootstrapCI(allTrades), [allTrades]);

  const baseWins = base.filter((t) => t.pnl_pct > 0).length;
  const binomP = base.length > 0 ? binomialTestGreater(base.length, baseWins, 0.5) : NaN;

  // Same hold_bars/pnl_pct pair, and the same computeCorrelationPearson/
  // computeCorrelationSpearman functions, statsCompute.ts's own
  // computeCorrelations() calls internally -- calling them directly here
  // (rather than through computeCorrelations, whose CorrelationSummary type
  // drops Spearman's `t`) is not a second source of truth, just the same
  // pure function on the same inputs.
  const holdBars = base.map((t) => t.hold_bars);
  const pnl = base.map((t) => t.pnl_pct);
  const pearson = useMemo(() => computeCorrelationPearson(holdBars, pnl), [holdBars, pnl]);
  const spearman = useMemo(() => computeCorrelationSpearman(holdBars, pnl), [holdBars, pnl]);

  if (trades.loading) return <div className="stats-tab-loading">Loading trade data...</div>;
  if (trades.error) {
    return (
      <div className="stats-tab-loading" role="alert">
        Failed to load /api/trades: {trades.error.message}
      </div>
    );
  }

  return (
    <div className="stats-tab solutions-tab">
      <p className="stats-legend text-muted">
        Full worked solution for every statistic on the Stats tab: variables first, then the general formula,
        then the substituted formula, then the result. Computed from the same live /api/trades data and the same{' '}
        <code>statsCompute.ts</code>/<code>statMath.ts</code> functions Stats uses -- these numbers cannot drift
        from what Stats shows.
      </p>

      <section className="stat-card panel">
        <h3>1. Baseline Win Rate Significance</h3>
        <DerivationCard step={binomialDerivation(base.length, baseWins, 0.5, binomP)} />
      </section>

      <section className="stat-card panel">
        <h3>2. Orthogonal Criteria: Fisher&apos;s Exact, Welch&apos;s t-test, MDE (per criterion)</h3>
        {criteriaTests.map((row) => (
          <div key={row.label} className="criterion-group">
            <h4 className="criterion-group-title">{row.label}</h4>
            <div className="derivation-grid">
              <DerivationCard step={fisherDerivation(row)} />
              <DerivationCard step={welchDerivation(row)} />
              <DerivationCard step={mdeDerivation(row)} />
            </div>
          </div>
        ))}
      </section>

      <section className="stat-card panel">
        <h3>3. Percentile Bootstrap CI</h3>
        <DerivationCard step={bootstrapDerivation(ownBootstrap)} />
      </section>

      <section className="stat-card panel">
        <h3>4. Correlation: Hold Duration vs. PnL</h3>
        <div className="derivation-grid">
          <DerivationCard step={pearsonDerivation(holdBars, pnl, pearson)} />
          <DerivationCard step={spearmanDerivation(holdBars, pnl, spearman)} />
        </div>
      </section>
    </div>
  );
}
