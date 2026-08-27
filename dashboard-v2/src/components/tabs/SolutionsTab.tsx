import { useMemo } from 'react';
import './SolutionsTab.css';
import { useCandles, useTrades } from '../../api/hooks';
import { baselineProvenance, baselineTrades, computeOwnBootstrapCI } from '../stats/statsCompute';
import { binomialTailTerms, binomialTestGreater, computeCorrelationPearson, computeCorrelationSpearman } from '../stats/statMath';
import { dcaArm, lumpSumArm, strategyArm } from '../stats/benchmarkMath';
import {
  binomialDerivation,
  bootstrapDerivation,
  dcaArmDerivation,
  lumpSumArmDerivation,
  pearsonDerivation,
  spearmanDerivation,
  strategyArmDerivation,
} from '../stats/derivationSteps';
import { DerivationCard } from '../stats/DerivationCard';

const STARTING_CAPITAL = 10000;
const STRATEGY_ROUND_TRIP_DRAG_PCT = 0.2; // matches analysis/benchmark_vs_passive.py's ROUND_TRIP_DRAG_PCT

/**
 * Full step-by-step derivation of every statistic on the Stats tab --
 * every intermediate value (means, variances, standard errors, degrees of
 * freedom, percentile brackets, rank tables, term-by-term enumerations...)
 * shown as its own numbered step, not asserted. Calls the exact same
 * statsCompute.ts/statMath.ts functions StatsTab.tsx calls, on the same
 * /api/trades data, so these numbers can never drift from what Stats shows.
 */
export function SolutionsTab() {
  const trades = useTrades();
  const candles = useCandles();
  const allTrades = trades.data ?? [];
  const allCandles = candles.data ?? [];

  const base = useMemo(() => baselineTrades(allTrades), [allTrades]);
  const prov = useMemo(() => baselineProvenance(allTrades), [allTrades]);
  const ownBootstrap = useMemo(() => computeOwnBootstrapCI(allTrades), [allTrades]);

  const baseWins = base.filter((t) => t.pnl_pct > 0).length;
  const binomP = base.length > 0 ? binomialTestGreater(base.length, baseWins, 0.5) : NaN;
  const binomTerms = useMemo(() => (base.length > 0 ? binomialTailTerms(base.length, baseWins, 0.5) : []), [base.length, baseWins]);

  // Same hold_bars/pnl_pct pair, and the same computeCorrelationPearson/
  // computeCorrelationSpearman functions, statsCompute.ts's own
  // computeCorrelations() calls internally -- calling them directly here
  // (rather than through computeCorrelations, whose CorrelationSummary type
  // drops Spearman's `t`) is not a second source of truth, just the same
  // pure function on the same inputs. Wrapped in useMemo (previously built
  // via a bare .map() outside useMemo, which gave a new array identity every
  // render and silently defeated the useMemo below it).
  const holdBars = useMemo(() => base.map((t) => t.hold_bars), [base]);
  const pnl = useMemo(() => base.map((t) => t.pnl_pct), [base]);
  const pearson = useMemo(() => computeCorrelationPearson(holdBars, pnl), [holdBars, pnl]);
  const spearman = useMemo(() => computeCorrelationSpearman(holdBars, pnl), [holdBars, pnl]);

  // Independent JS re-derivation of the Sharpe/Sortino/MaxDD benchmark
  // comparison -- computed here (not in benchmarkMath.ts/derivationSteps.ts,
  // which only build/format) from the same /artifacts/candles.json +
  // /api/trades data every other section on this page uses. See
  // benchmarkMath.ts's module doc for why this never imports Python's
  // precomputed benchmark_vs_passive.json.
  const strategyResult = useMemo(
    () => (allCandles.length > 0 && base.length > 0 ? strategyArm(allCandles, base, STARTING_CAPITAL) : null),
    [allCandles, base],
  );
  const strategyFeeAdjResult = useMemo(
    () => (allCandles.length > 0 && base.length > 0 ? strategyArm(allCandles, base, STARTING_CAPITAL, STRATEGY_ROUND_TRIP_DRAG_PCT) : null),
    [allCandles, base],
  );
  const dcaResult = useMemo(() => (allCandles.length > 0 ? dcaArm(allCandles, STARTING_CAPITAL) : null), [allCandles]);
  const lumpSumResult = useMemo(() => (allCandles.length > 0 ? lumpSumArm(allCandles, STARTING_CAPITAL) : null), [allCandles]);

  if (trades.loading || candles.loading) return <div className="stats-tab-loading">Loading trade and candle data...</div>;
  if (trades.error) {
    return (
      <div className="stats-tab-loading" role="alert">
        Failed to load /api/trades: {trades.error.message}
      </div>
    );
  }
  if (candles.error) {
    return (
      <div className="stats-tab-loading" role="alert">
        Failed to load /artifacts/candles.json: {candles.error.message}
      </div>
    );
  }

  return (
    <div className="stats-tab solutions-tab">
      <p className="stats-legend text-muted">
        Full worked solution for every statistic on the Stats tab: every intermediate value is its own numbered
        step, not asserted. Computed from the same live /api/trades data and the same <code>statsCompute.ts</code>/
        <code>statMath.ts</code> functions Stats uses -- these numbers cannot drift from what Stats shows. Values
        shown in substitutions are rounded for readability (to at least 4 decimal places, 6 for probability tables);
        every final result is the unrounded computed value, never re-derived by summing the rounded display digits.
      </p>

      <section className="stat-card panel">
        <h3>1. Baseline Win Rate Significance</h3>
        <DerivationCard step={binomialDerivation(prov, baseWins, 0.5, binomP, binomTerms)} />
      </section>

      <section className="stat-card panel">
        <h3>2. Percentile Bootstrap CI</h3>
        <DerivationCard step={bootstrapDerivation(ownBootstrap, pnl)} />
      </section>

      <section className="stat-card panel">
        <h3>3. Correlation: Hold Duration vs. PnL</h3>
        <div className="derivation-grid">
          <DerivationCard step={pearsonDerivation(holdBars, pnl, pearson)} />
          <DerivationCard step={spearmanDerivation(holdBars, pnl, spearman)} />
        </div>
      </section>

      <section className="stat-card panel">
        <h3>4. Risk-Adjusted &amp; Benchmark Metrics</h3>
        <p className="stats-legend text-muted">
          Sharpe, Sortino and Max Drawdown for the OB-gated strategy vs. weekly DCA into BTC vs. lump-sum
          buy-and-hold, at $10,000 notional starting capital, over the same locked 2022-2026 window
          (8,767 bars). This is a genuine independent re-derivation from <code>/artifacts/candles.json</code> and{' '}
          <code>/api/trades</code> (see <code>benchmarkMath.ts</code>) -- it never imports from or fetches
          Python's precomputed <code>benchmark_vs_passive.json</code>. Each card's last step cross-checks
          against the CLAUDE.md-locked Python figures as an explicit, labelled comparison; a mismatch would be
          reported here, not silently tuned away.
        </p>
        <div className="derivation-grid">
          {strategyResult && strategyFeeAdjResult && <DerivationCard step={strategyArmDerivation(strategyResult, strategyFeeAdjResult)} />}
          {dcaResult && <DerivationCard step={dcaArmDerivation(dcaResult)} />}
          {lumpSumResult && <DerivationCard step={lumpSumArmDerivation(lumpSumResult)} />}
        </div>
      </section>
    </div>
  );
}
