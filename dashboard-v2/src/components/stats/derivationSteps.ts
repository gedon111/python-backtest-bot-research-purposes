/**
 * Full step-by-step derivations for the Solutions tab, for every hypothesis
 * test/estimator the Stats tab computes. Deliberately takes ALREADY COMPUTED
 * result objects from statsCompute.ts/statMath.ts (never raw trades) as input
 * -- these functions only format, they never recompute -- so Solutions can
 * never numerically drift from what StatsTab.tsx displays. The one exception
 * is the Spearman card's illustrative (never-used) tie-shortcut number,
 * which is computed locally and clearly labelled as not the real result --
 * see spearmanDerivation.
 *
 * A DerivationStep is an ordered list of DerivationLine "steps", each an
 * ordered list of DerivationBlock. Blocks (not fixed formula/table/note
 * fields) exist because different derivations need different internal
 * orderings: the bootstrap's replicate step wants its raw-draws TABLE before
 * the sum/mean FORMULA, while the binomial's enumeration step wants the
 * general FORMULA before its term TABLE.
 *
 * Every `tex` value handed to <Latex> stays an author-constant template with
 * only numeric leaves interpolated, per Latex.tsx's contract. Field names
 * (e.g. "quality_fvg", "pnl_pct") and anything that could contain a raw "_"
 * only ever appear in plain-text label/description/note strings, never
 * inside a formulaTex/substitutedTex/resultTex string -- an underscore
 * inside \text{...} is a KaTeX subscript operator, not a literal character.
 * Table cells are plain text for the same reason, and so KaTeX only ever
 * parses ~190 formula strings on this page, not one per data cell.
 */
import type { BinomialTerm, BootstrapCIResult, PearsonResult, SpearmanResult } from './statMath';
import type { BaselineProvenance } from './statsCompute';
import type { ArmResult, DcaArmResult } from './benchmarkMath';

export interface DerivationVariable {
  symbol: string;
  description: string;
  value: string;
}

export interface DerivationTableRow {
  cells: string[];
  emphasis?: 'observed' | 'excluded' | 'bracket';
}

export interface DerivationTable {
  caption: string;
  headers: string[];
  rows: DerivationTableRow[];
  /** Defaults to collapsed (rendered inside a <details>) -- every table on
   * this page is raw enumeration/data, not the derivation's algebra itself,
   * so nothing about the derivation is hidden, only bulk rows behind one
   * click. Pass false to force a table open by default. */
  collapsed?: boolean;
}

export type DerivationBlock =
  | { kind: 'values'; items: DerivationVariable[] }
  | { kind: 'algebra'; formulaTex: string; substitutedTex?: string; resultTex?: string }
  | { kind: 'table'; table: DerivationTable }
  | { kind: 'note'; text: string; tone?: 'plain' | 'caveat' }
  | { kind: 'crosscheck'; label: string; jsValue: string; pyValue: string; source: string; match: boolean };

export interface DerivationLine {
  label: string;
  description?: string;
  blocks: DerivationBlock[];
}

export interface DerivationStep {
  id: string;
  title: string;
  steps: DerivationLine[];
  resultTex: string;
  prose: string;
}

// ─── Formatters ─────────────────────────────────────────────────────────────
// Rounded substitution, exact result: every substitutedTex/table cell shows
// values rounded for readability, but every resultTex/`result` field is the
// already-computed value handed in, never re-derived by summing the rounded
// display digits. Probability-term tables use 6dp (not 4dp) because at 4dp
// several of the tables below visibly fail to reconcile with their own
// stated sum (e.g. the binomial's 9 displayed terms sum to 0.0260 against a
// 4dp-stated 0.0261; at 6dp both reconcile exactly).
const n2 = (v: number) => (Number.isNaN(v) ? '\\text{NaN}' : v.toFixed(2));
const n4 = (v: number) => (Number.isNaN(v) ? '\\text{NaN}' : v.toFixed(4));
const s2 = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;
/** Locale-independent thousands separator (not toLocaleString(), whose
 * output depends on the reader's browser locale -- "2,000" in en-US is
 * "2.000" in de-DE, making a `tex` string non-author-constant). */
const commaInt = (v: number) => Math.trunc(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
/** Locale-independent thousands separator with a fixed decimal tail (dollar amounts), same reasoning as commaInt. */
const commaFixed = (v: number, decimals = 2) => {
  const sign = v < 0 ? '-' : '';
  const [intPart, decPart] = Math.abs(v).toFixed(decimals).split('.');
  return sign + intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (decPart ? '.' + decPart : '');
};
/** UTC calendar date for a Candle/trade unix-second timestamp -- not toLocaleDateString(), whose output depends on the reader's browser locale. */
const fmtDate = (timeSec: number) => new Date(timeSec * 1000).toISOString().slice(0, 10);
/** Plain-text probability formatter for TABLE CELLS ONLY -- exponential
 * notation ("7.4506e-9") is safe as plain text but would render wrong inside
 * KaTeX (the "e" would typeset as an italic variable, not "x10^-9"). */
const pFmtTable = (v: number) => (v === 0 ? '0.000000' : Math.abs(v) < 1e-6 ? v.toExponential(4) : v.toFixed(6));
/** Probability formatter for TEX substitution strings only -- always fixed
 * notation, so it stays a valid bare numeral inside a LaTeX string. */
const pFmtTex = (v: number) => (Number.isNaN(v) ? '\\text{NaN}' : v.toFixed(6));

const INCOMPLETE_BETA_NOTE =
  'The p-value above is not evaluated by a closed-form substitution: it is the regularized incomplete ' +
  'beta function I_x(a,b), computed via a modified Lentz continued-fraction expansion (tolerance 1e-15, ' +
  'capped at 150 iterations), a verbatim port of the original gui.js Research Statistics Module. That is ' +
  'not something a term-by-term table can show by hand. What CAN be shown, and is shown above, is the ' +
  'exact closed-form identity being evaluated and the two numeric arguments (a, b) passed into it. The ' +
  "approximation's correctness is validated on startup against known reference points (chi-square(7.815,3)" +
  '=0.05, t(2.086,20)=0.05, t(2.0,20)=0.059265, F(3.1,3,20)=0.05) by runDistributionSelfChecks(), called ' +
  'from the Stats tab on every load.';

// ─── Small block-builder helpers ───────────────────────────────────────────
function values(items: DerivationVariable[]): DerivationBlock {
  return { kind: 'values', items };
}
function algebra(formulaTex: string, substitutedTex?: string, resultTex?: string): DerivationBlock {
  return { kind: 'algebra', formulaTex, substitutedTex, resultTex };
}
function table(t: DerivationTable): DerivationBlock {
  return { kind: 'table', table: t };
}
function note(text: string, tone?: 'caveat'): DerivationBlock {
  return { kind: 'note', text, tone };
}
function crosscheck(label: string, jsValue: string, pyValue: string, source: string, match: boolean): DerivationBlock {
  return { kind: 'crosscheck', label, jsValue, pyValue, source, match };
}

function valuesTable(description: string, values2: number[]): DerivationBlock {
  return table({
    caption: `${description}: all ${values2.length} values`,
    headers: ['#', 'pnl_pct'],
    rows: values2.map((v, i) => ({ cells: [String(i + 1), s2(v) + '%'] })),
  });
}

// ─── 1. One-sided exact binomial test ──────────────────────────────────────
export function binomialDerivation(prov: BaselineProvenance, k: number, p0: number, p: number, terms: BinomialTerm[]): DerivationStep {
  const n = prov.n;
  return {
    id: 'binomial',
    title: 'One-Sided Exact Binomial Test',
    steps: [
      {
        label: 'State the hypotheses',
        blocks: [
          note(
            'H0 (null, "zero edge"): the true win probability is 0.5. H1 (alternative, pre-registered ' +
              "directional hypothesis): the true win probability exceeds 0.5. One-sided because the " +
              'pre-registered claim is directional, not merely that the win rate differs from 50% in ' +
              'either direction (STUDY_REFERENCE.md Sec.5).',
          ),
        ],
      },
      {
        label: 'Where n and k come from',
        blocks: [
          values([
            { symbol: 'n', description: 'baseline trades (min_ob_quality = 0)', value: String(n) },
            { symbol: 'k', description: 'wins (pnl_pct > 0)', value: String(k) },
            { symbol: 'p_0', description: 'null-hypothesis win probability', value: p0.toFixed(1) },
          ]),
          note(
            prov.fallbackUsed
              ? `The min_ob_quality=0 filter matched 0 of ${prov.totalTrades} /api/trades rows, so the ` +
                  `documented empty-filter fallback used all ${prov.totalTrades} trades instead.`
              : `Filtering /api/trades to min_ob_quality=0 matches ${prov.matchedByFilter} of ` +
                  `${prov.totalTrades} total trade rows -- these ${prov.matchedByFilter} rows are n. k counts ` +
                  'how many of those n rows have pnl_pct strictly greater than 0; a pnl_pct of exactly 0 would ' +
                  'count as a loss under this rule (no baseline trade currently has pnl_pct = 0).',
          ),
        ],
      },
      {
        label: 'General formula, and the form actually evaluated',
        blocks: [
          algebra('P(X \\geq k) = \\sum_{x=k}^{n} \\binom{n}{x}\\, p_0^{x} (1-p_0)^{n-x}'),
          note(
            'Evaluated in log-space to avoid factorial overflow at n~25-30: P(X=x) = exp[ ln(n!) - ln(x!) - ' +
              'ln((n-x)!) + x*ln(p0) + (n-x)*ln(1-p0) ], each ln(m!) itself a running sum of ln(2)..ln(m).',
          ),
        ],
      },
      {
        label: `Enumerate every term, x = ${k}..${n}`,
        blocks: [
          table({
            caption: `All ${terms.length} terms of the tail sum, P(X=x)`,
            headers: ['x', 'P(X = x)'],
            rows: terms.map((t) => ({ cells: [String(t.x), pFmtTable(t.p)] })),
          }),
        ],
      },
      {
        label: 'Sum the tail',
        blocks: [
          algebra(
            'P(X \\geq k) = \\sum_{x=k}^{n} P(X=x)',
            `P(X \\geq ${k}) = ${terms.map((t) => pFmtTex(t.p)).join(' + ')}`,
            `P(X \\geq ${k}) = ${n4(p)}`,
          ),
        ],
      },
      {
        label: 'Compare to alpha = 0.05',
        blocks: [
          note(
            `${n4(p)} ${p < 0.05 ? '<' : '>='} 0.05, so this one-sided result is ` +
              `${p < 0.05 ? 'significant' : 'not significant'} at alpha=0.05.`,
          ),
          crosscheck(
            'One-sided p (rounded)',
            n4(p),
            '0.026',
            'CLAUDE.md locked results (also reports a two-sided figure of 0.052, a doubling convention from ' +
              'the original analysis -- not independently recomputed here since the pre-registered ' +
              'hypothesis is one-sided)',
            Math.abs(p - 0.026) < 0.001,
          ),
        ],
      },
    ],
    resultTex: `P(X \\geq ${k}) = ${n4(p)}`,
    prose:
      "One-sided because the pre-registered hypothesis is directional -- that the strategy's win rate " +
      'exceeds the 50% zero-edge null, not merely that it differs from 50% in either direction.',
  };
}

// ─── 5. Percentile bootstrap CI ────────────────────────────────────────────
export function bootstrapDerivation(result: BootstrapCIResult, pnl: number[]): DerivationStep {
  const percentileStep = (label: string, symbol: string, p: number, d: BootstrapCIResult['totalLoDetail']): DerivationLine => ({
    label,
    blocks: [
      algebra(
        `i = (p/100)(B-1)`,
        `i = (${p}/100)(${result.b}-1)`,
        `i = ${d.idx.toFixed(3)}`,
      ),
      algebra(
        `${symbol} = \\text{sorted}[\\lfloor i \\rfloor] + (\\text{sorted}[\\lceil i \\rceil]-\\text{sorted}[\\lfloor i \\rfloor])(i-\\lfloor i \\rfloor)`,
        `${symbol} = ${s2(d.loValue)} + (${s2(d.hiValue)} - (${s2(d.loValue)}))(${d.idx.toFixed(3)} - ${d.lo})`,
        `${symbol} = ${s2(d.result)}\\%`,
      ),
    ],
  });

  return {
    id: 'bootstrap',
    title: 'Percentile Bootstrap CI (Total & Avg Return)',
    steps: [
      {
        label: 'Input data and point estimate',
        blocks: [
          valuesTable('baseline pnl_pct', pnl),
          values([
            { symbol: 'n', description: 'baseline trades', value: String(result.n) },
            { symbol: 'B', description: 'resamples', value: commaInt(result.b) },
            { symbol: '\\text{seed}', description: 'mulberry32 PRNG seed', value: String(result.seed) },
            { symbol: '\\hat\\theta(\\text{total})', description: 'point estimate, total return = sum(pnl_pct)', value: s2(result.totalPoint) + '%' },
            { symbol: '\\hat\\theta(\\text{avg})', description: 'point estimate, avg return/trade = total/n', value: s2(result.avgPoint) + '%' },
          ]),
        ],
      },
      {
        label: 'The resampling rule',
        blocks: [
          algebra('\\hat\\theta^*_b = f(X_1^*,\\dots,X_n^*),\\; X_i^* \\sim \\text{Uniform}(X_1,\\dots,X_n)'),
          note(
            'mulberry32(seed) is a deterministic seeded PRNG returning a uniform value in [0, 1) on each call. ' +
              'Each drawn index is idx = floor(u * n), which maps uniformly onto {0, 1, ..., n-1} -- i.e. one ' +
              'baseline trade drawn "with replacement". n such draws make one resample; summing/averaging its ' +
              'pnl_pct values makes one replicate of theta-hat.',
          ),
        ],
      },
      {
        label: 'Replicate #1, worked in full',
        blocks: [
          table({
            caption: `All ${result.firstReplicate.indices.length} draws of the first resample`,
            headers: ['Draw j', 'Index drawn', 'pnl_pct'],
            rows: result.firstReplicate.indices.map((idx, j) => ({ cells: [String(j + 1), String(idx), s2(result.firstReplicate.values[j]) + '%'] })),
          }),
          algebra(
            's_1 = \\sum_{j=1}^{n} X^*_j, \\quad \\bar{X}^*_1 = s_1/n',
            undefined,
            `s_1 = ${s2(result.firstReplicate.total)}\\%, \\quad \\bar{X}^*_1 = ${s2(result.firstReplicate.avg)}\\%`,
          ),
          note('Repeated indices are expected and correct -- this is sampling WITH replacement, not a reshuffle.'),
        ],
      },
      {
        label: `Repeat for all B = ${commaInt(result.b)} replicates`,
        blocks: [
          note(
            `Steps 2-3 repeat independently ${commaInt(result.b)} times, each drawing n=${result.n} indices from the ` +
              'SAME ongoing PRNG stream (never reseeded), producing one total-return value and one avg-return ' +
              'value per replicate.',
          ),
        ],
      },
      percentileStep('2.5th percentile of the total-return distribution', '\\text{Total}_{2.5}', 2.5, result.totalLoDetail),
      percentileStep('97.5th percentile of the total-return distribution', '\\text{Total}_{97.5}', 97.5, result.totalHiDetail),
      percentileStep('2.5th percentile of the avg-return distribution', '\\text{Avg}_{2.5}', 2.5, result.avgLoDetail),
      percentileStep('97.5th percentile of the avg-return distribution', '\\text{Avg}_{97.5}', 97.5, result.avgHiDetail),
      {
        label: '95% confidence intervals',
        blocks: [
          algebra(
            '\\text{CI}_{95\\%} = [\\text{percentile}_{2.5},\\ \\text{percentile}_{97.5}]',
            undefined,
            `\\text{Total } 95\\%\\ \\text{CI} = [${s2(result.totalCI[0])}\\%,\\ ${s2(result.totalCI[1])}\\%], \\quad \\text{Avg } 95\\%\\ \\text{CI} = [${s2(result.avgCI[0])}\\%,\\ ${s2(result.avgCI[1])}\\%]`,
          ),
          note(
            `Diagnostic: ${n2(result.pctResamplesTotalLe0)}% of the ${commaInt(result.b)} total-return replicates were ` +
              `<= 0%; ${n2(result.pctResamplesAvgLe0)}% of avg-return replicates were <= 0%.`,
          ),
          crosscheck(
            'Total return 95% CI',
            `[${s2(result.totalCI[0])}%, ${s2(result.totalCI[1])}%] (B=${commaInt(result.b)})`,
            '[+5.99%, +54.99%] (B=10,000)',
            'analysis/bootstrap_power_analysis.py, CLAUDE.md Paper reporting corrections #2 -- root cause is the ' +
              'B mismatch alone (verified by porting mulberry32 to Python and reproducing the JS figure exactly ' +
              'at B=2,000); the two are disclosed separately by design, not unified',
            false,
          ),
        ],
      },
    ],
    resultTex: `\\text{Total } 95\\%\\ \\text{CI} = [${s2(result.totalCI[0])}\\%,\\ ${s2(result.totalCI[1])}\\%], \\quad \\text{Avg } 95\\%\\ \\text{CI} = [${s2(result.avgCI[0])}\\%,\\ ${s2(result.avgCI[1])}\\%]`,
    prose:
      'Nonparametric percentile bootstrap on the baseline\'s own total and average return -- no distributional ' +
      'assumption about pnl_pct. Uses a seeded mulberry32 PRNG so the resample set, and therefore the CI, is ' +
      'reproducible across renders and machines.',
  };
}

// ─── 6/7. Pearson & Spearman correlation (hold duration vs PnL) ───────────
function pairTable(X: number[], Y: number[]): DerivationBlock {
  return table({
    caption: `All ${X.length} (hold_bars, pnl_pct) pairs`,
    headers: ['#', 'hold_bars (X)', 'pnl_pct (Y)'],
    rows: X.map((x, i) => ({ cells: [String(i + 1), String(x), s2(Y[i]) + '%'] })),
  });
}

export function pearsonDerivation(X: number[], Y: number[], result: PearsonResult): DerivationStep {
  return {
    id: 'pearson',
    title: 'Pearson Correlation -- Hold Duration vs. PnL',
    steps: [
      {
        label: 'Pair up the data',
        blocks: [pairTable(X, Y), note('X = hold_bars (bars a trade was held open), Y = pnl_pct (per-trade return), over the baseline trades.')],
      },
      {
        label: 'Running sums',
        blocks: [
          values([
            { symbol: 'N', description: 'baseline trades', value: String(result.n) },
            { symbol: '\\sum X', description: 'sum of hold_bars', value: n2(result.sumX) },
            { symbol: '\\sum Y', description: 'sum of pnl_pct', value: n2(result.sumY) + '%' },
            { symbol: '\\sum XY', description: 'sum of cross products', value: n2(result.sumXY) },
            { symbol: '\\sum X^2', description: 'sum of hold_bars squared', value: n2(result.sumX2) },
            { symbol: '\\sum Y^2', description: 'sum of pnl_pct squared', value: n2(result.sumY2) },
          ]),
        ],
      },
      {
        label: 'Numerator and denominator',
        blocks: [
          algebra(
            '\\text{num} = N\\sum XY - \\sum X \\sum Y',
            `\\text{num} = ${result.n}(${n2(result.sumXY)}) - (${n2(result.sumX)})(${n2(result.sumY)})`,
            `\\text{num} = ${n2(result.num)}`,
          ),
          algebra(
            '\\text{den} = \\sqrt{[N\\sum X^2-(\\sum X)^2][N\\sum Y^2-(\\sum Y)^2]}',
            `\\text{den} = \\sqrt{[${result.n}(${n2(result.sumX2)})-(${n2(result.sumX)})^2][${result.n}(${n2(result.sumY2)})-(${n2(result.sumY)})^2]}`,
            `\\text{den} = ${n2(result.den)}`,
          ),
        ],
      },
      {
        label: 'Correlation coefficient',
        blocks: [algebra('r = \\text{num}/\\text{den}', `r = ${n2(result.num)}/${n2(result.den)}`, `r = ${n4(result.r)}`)],
      },
      {
        label: 't statistic',
        blocks: [
          algebra(
            't = r\\sqrt{\\dfrac{N-2}{1-r^2}}',
            `t = ${n4(result.r)}\\sqrt{\\dfrac{${result.n}-2}{1-(${n4(result.r)})^2}}`,
            `t = ${n2(result.t)}`,
          ),
        ],
      },
      {
        label: 'p-value',
        blocks: [
          algebra(
            'x = \\dfrac{N-2}{(N-2)+t^2}',
            `x = \\dfrac{${result.n}-2}{(${result.n}-2)+(${n2(result.t)})^2}`,
          ),
          algebra('p = I_x((N-2)/2,\\, 1/2)', undefined, `p = ${n4(result.p)}`),
          note(INCOMPLETE_BETA_NOTE),
          crosscheck(
            'p-value',
            n4(result.p),
            '~0.0094',
            'docs/paper_full_update_2026-08-08.md and docs/backtest_methodology_defense_walkthrough.md were ' +
              'corrected from an earlier "p < 0.001" to this figure in a 2026-08-08 audit (CLAUDE.md Paper ' +
              'reporting corrections #1; STUDY_REFERENCE.md never contained the "p < 0.001" claim -- an earlier ' +
              'audit pass mis-attributed it there and that was itself corrected)',
            Math.abs(result.p - 0.0094) < 0.001,
          ),
        ],
      },
    ],
    resultTex: `r = ${n4(result.r)}, \\quad t = ${n2(result.t)}, \\quad p = ${n4(result.p)}`,
    prose: 'Tests whether trades held longer tend to return more (or less) -- a monotone-in-magnitude relationship, not a claim about causation.',
  };
}

export function spearmanDerivation(X: number[], Y: number[], result: SpearmanResult): DerivationStep {
  const tieGroups = (raw: number[], ranks: number[]) => {
    const groups = new Map<number, { rank: number; count: number }>();
    raw.forEach((v, i) => {
      const g = groups.get(v);
      if (g) g.count += 1;
      else groups.set(v, { rank: ranks[i], count: 1 });
    });
    return [...groups.entries()].sort((p, q) => p[0] - q[0]);
  };
  const xGroups = tieGroups(X, result.rankX);
  const yGroups = tieGroups(Y, result.rankY);
  const xTiedCount = X.length - xGroups.length;
  const yTiedCount = Y.length - yGroups.length;

  // Illustrative-only: the tie-corrected Pearson-on-ranks r above IS the real
  // result; the classic shortcut rho = 1 - 6*sum(d^2)/(n(n^2-1)) assumes no
  // ties and is invalid here. Computed ONLY to demonstrate that bias -- never
  // exported from statMath.ts, never used as an actual result anywhere.
  const n = X.length;
  const sumD2 = result.rankX.reduce((s, rx, i) => s + (rx - result.rankY[i]) ** 2, 0);
  const shortcutRho = 1 - (6 * sumD2) / (n * (n * n - 1));

  return {
    id: 'spearman',
    title: 'Spearman Rank Correlation -- Hold Duration vs. PnL',
    steps: [
      {
        label: 'Why ranks, not raw values',
        blocks: [
          note(
            "Pearson's r on the raw values above is sensitive to the handful of large outlier winning trades. " +
              'Replacing each value with its rank (position when sorted, ties given the average of their tied ' +
              "positions) makes the measure robust to that -- it tests whether the relationship is monotone, " +
              'not linear.',
          ),
        ],
      },
      {
        label: 'Rank X (hold_bars), tie-averaged',
        blocks: [
          table({
            caption: `Distinct hold_bars values (${xGroups.length} distinct, ${xTiedCount} of ${X.length} values in a tie group)`,
            headers: ['hold_bars', 'count', 'rank assigned'],
            rows: xGroups.map(([v, g]) => ({ cells: [String(v), String(g.count), n2(g.rank)], emphasis: g.count > 1 ? 'bracket' : undefined })),
          }),
          note(
            xTiedCount > 0
              ? `${xTiedCount} of ${X.length} hold_bars values fall into a tied group; each tied group is assigned the ` +
                'AVERAGE of the ranks it would occupy (e.g. two values tied for ranks 3 and 4 both get rank 3.5).'
              : 'No ties in hold_bars -- every value gets a unique rank.',
          ),
        ],
      },
      {
        label: 'Rank Y (pnl_pct), tie-averaged',
        blocks: [
          table({
            caption: `Distinct pnl_pct values (${yGroups.length} distinct, ${yTiedCount} of ${Y.length} values in a tie group)`,
            headers: ['pnl_pct', 'count', 'rank assigned'],
            rows: yGroups.map(([v, g]) => ({ cells: [s2(v) + '%', String(g.count), n2(g.rank)], emphasis: g.count > 1 ? 'bracket' : undefined })),
          }),
          note(yTiedCount > 0 ? `${yTiedCount} of ${Y.length} pnl_pct values are tied.` : 'No ties in pnl_pct -- every value gets a unique rank.'),
        ],
      },
      {
        label: "Apply Pearson's formula to the rank pairs",
        blocks: [
          values([
            { symbol: '\\sum X_{\\text{rank}}', description: 'sum of X ranks', value: n2(result.ranked.sumX) },
            { symbol: '\\sum Y_{\\text{rank}}', description: 'sum of Y ranks', value: n2(result.ranked.sumY) },
            { symbol: '\\sum X_{\\text{rank}}Y_{\\text{rank}}', description: 'sum of rank cross products', value: n2(result.ranked.sumXY) },
          ]),
          algebra(
            '\\rho = r(\\text{rank}(X), \\text{rank}(Y))',
            `\\rho = \\dfrac{${result.ranked.n}(${n2(result.ranked.sumXY)}) - (${n2(result.ranked.sumX)})(${n2(result.ranked.sumY)})}{${n2(result.ranked.den)}}`,
            `\\rho = ${n4(result.rho)}`,
          ),
        ],
      },
      {
        label: 't and p, on the rank correlation',
        blocks: [
          algebra('t = \\rho\\sqrt{\\dfrac{N-2}{1-\\rho^2}}', `t = ${n4(result.rho)}\\sqrt{\\dfrac{${n}-2}{1-(${n4(result.rho)})^2}}`, `t = ${n2(result.t)}`),
          algebra('p = I_x((N-2)/2,\\, 1/2)', undefined, `p = ${n4(result.p)}`),
          note(INCOMPLETE_BETA_NOTE),
          crosscheck(
            'p-value',
            n4(result.p),
            '~0.0113',
            'CLAUDE.md Paper reporting corrections #1, same 2026-08-08 audit as the Pearson figure above',
            Math.abs(result.p - 0.0113) < 0.001,
          ),
        ],
      },
      {
        label: 'Why the textbook shortcut formula would be wrong here',
        blocks: [
          algebra(
            '\\rho_{\\text{shortcut}} = 1 - \\dfrac{6\\sum d_i^2}{n(n^2-1)}, \\quad d_i = \\text{rank}(X_i)-\\text{rank}(Y_i)',
            `\\rho_{\\text{shortcut}} = 1 - \\dfrac{6(${n2(sumD2)})}{${n}(${n}^2-1)}`,
            `\\rho_{\\text{shortcut}} = ${n4(shortcutRho)}`,
          ),
          note(
            `NOT USED as a result anywhere on this page -- shown only to demonstrate the tie bias. This shortcut ` +
              'assumes no ties in either series; with 22 of 27 hold_bars values tied, it disagrees with the exact ' +
              `Pearson-on-ranks value above (${n4(shortcutRho)} vs. ${n4(result.rho)}). The Pearson-on-ranks ` +
              'computation above is the actual result.',
            'caveat',
          ),
        ],
      },
    ],
    resultTex: `\\rho = ${n4(result.rho)}, \\quad t = ${n2(result.t)}, \\quad p = ${n4(result.p)}`,
    prose:
      'Rank-based, so robust to the outlier winning trades that dominate the raw Pearson sums above -- each ' +
      'value is replaced by its rank (ties averaged) before applying the same Pearson formula.',
  };
}

// ─── 8. Risk-adjusted & benchmark metrics (Sharpe, Sortino, Max Drawdown) ──
// benchmarkMath.ts independently re-derives these from /artifacts/candles.json
// + /api/trades -- it never imports from or fetches Python's precomputed
// benchmark_vs_passive.json. The PY_* constants below are only the CLAUDE.md
// locked comparison figures, rendered as a labelled crosscheck row, exactly
// like the bootstrap B=2,000-vs-10,000 disclosure above -- if the two
// disagree, that's reported, not reconciled away.
const CROSSCHECK_SOURCE =
  'analysis/benchmark_vs_passive.py output, CLAUDE.md Locked results (benchmark-vs-passive block, ' +
  '2022-2026 window, $10,000 notional, gross unless stated)';

const PY_STRATEGY_GROSS = { totalReturnPct: 30.31, finalCapital: 13417.77, sharpe: 1.114, sortino: 2.727, maxDrawdownPct: -6.46, timeInMarketPct: 2.63 };
const PY_STRATEGY_FEE_ADJ = { totalReturnPct: 24.91, finalCapital: 12719.01 };
const PY_DCA = { totalReturnPct: 123.13, finalCapital: 22312.94, sharpe: 0.556, sortino: null as number | null, maxDrawdownPct: -27.85, timeInMarketPct: 100 };
const PY_LUMP = { totalReturnPct: 90.07, finalCapital: 19007.32, sharpe: 0.564, sortino: null as number | null, maxDrawdownPct: -67.21, timeInMarketPct: 100 };

/** Fractional-return formatter (Sharpe/Sortino inputs are pct_change() fractions, e.g. 0.0012, not pnl_pct-style already-percent values). */
const pct4 = (v: number) => (Number.isNaN(v) ? '\\text{NaN}' : `${(v * 100).toFixed(4)}\\%`);
const num3 = (v: number) => (Number.isNaN(v) ? '\\text{NaN}' : v.toFixed(3));

function equitySampleTable(result: ArmResult, valueLabel: string): DerivationBlock {
  return table({
    caption: `First ${result.equitySample.length} ${valueLabel} points`,
    headers: ['Bar', 'Date (UTC)', valueLabel],
    rows: result.equitySample.map((p) => ({ cells: [String(p.index), fmtDate(p.time), '$' + commaFixed(p.equity)] })),
    collapsed: false,
  });
}

function sharpeSortinoSteps(result: ArmResult, periodLabel: string): DerivationLine[] {
  const r = result.returns;
  const P = result.periodsPerYear.toFixed(1);
  return [
    {
      label: `${periodLabel} returns: mean and standard deviation`,
      blocks: [
        note(
          `N = ${commaInt(r.n)} ${periodLabel} returns, each computed as (E_i - E_{i-1})/E_{i-1} from the equity ` +
            `series constructed above -- too many to enumerate individually (unlike the 27-trade tables ` +
            'elsewhere on this page), so only the construction rule and the resulting mean/SD are shown.',
        ),
        values([
          { symbol: 'N', description: `${periodLabel} returns`, value: commaInt(r.n) },
          { symbol: '\\bar r', description: 'mean return per period', value: pct4(r.meanR) },
          { symbol: 's_r', description: 'sample standard deviation of returns (ddof=1)', value: pct4(r.stdR) },
        ]),
      ],
    },
    {
      label: 'Sharpe ratio',
      blocks: [
        algebra(
          '\\text{Sharpe} = \\dfrac{\\bar r}{s_r}\\sqrt{P}',
          `\\text{Sharpe} = \\dfrac{${pct4(r.meanR)}}{${pct4(r.stdR)}}\\sqrt{${P}}`,
          `\\text{Sharpe} = ${num3(r.sharpe)}`,
        ),
        note(`Risk-free rate = 0. P = periods/year = ${P} (annualization factor for this arm's sampling frequency).`),
      ],
    },
    {
      label: 'Sortino ratio',
      blocks: [
        algebra(
          '\\sigma_d = \\sqrt{\\dfrac{1}{N}\\sum_{i=1}^{N} \\min(r_i, 0)^2}',
          undefined,
          `\\sigma_d = ${pct4(r.downsideDev)}`,
        ),
        note(
          'The downside deviation divides by N (population, ddof=0) over ALL N returns, not just the negative ' +
            'ones -- every non-negative period still contributes a 0 to the sum. Matches ' +
            'benchmark_dca_analysis.py:82-84 exactly: np.sqrt((np.minimum(r,0)**2).mean()).',
        ),
        algebra(
          '\\text{Sortino} = \\dfrac{\\bar r}{\\sigma_d}\\sqrt{P}',
          `\\text{Sortino} = \\dfrac{${pct4(r.meanR)}}{${pct4(r.downsideDev)}}\\sqrt{${P}}`,
          `\\text{Sortino} = ${num3(r.sortino)}`,
        ),
      ],
    },
  ];
}

function maxDrawdownStep(result: ArmResult): DerivationLine {
  const tp = result.troughPoint;
  return {
    label: 'Maximum drawdown',
    blocks: [
      algebra('DD_t = \\dfrac{E_t - \\max_{s \\leq t} E_s}{\\max_{s \\leq t} E_s}\\times 100, \\qquad DD_{\\min} = \\min_t DD_t'),
      note(
        `Worst point: bar ${tp.index} (${fmtDate(tp.time)}) -- equity there = $${commaFixed(tp.equity)}, running ` +
          `max at that point = $${commaFixed(tp.runningMax)}.`,
      ),
      algebra(
        'DD_{\\min} = \\dfrac{E_{t^*} - \\text{RunningMax}_{t^*}}{\\text{RunningMax}_{t^*}}\\times 100',
        `DD_{\\min} = \\dfrac{${commaFixed(tp.equity)} - ${commaFixed(tp.runningMax)}}{${commaFixed(tp.runningMax)}}\\times 100`,
        `DD_{\\min} = ${n2(result.maxDrawdownPct)}\\%`,
      ),
    ],
  };
}

function benchmarkCrosscheckStep(
  result: ArmResult,
  py: { totalReturnPct: number; finalCapital: number; sharpe: number; sortino: number | null; maxDrawdownPct: number; timeInMarketPct: number },
  exposureCaveat: boolean,
): DerivationLine {
  // crosscheck's jsValue/pyValue render as plain React text, NOT through
  // <Latex> (see DerivationCard.tsx's 'crosscheck' case) -- unlike every
  // other block kind on this page, these must be plain strings, never
  // LaTeX-escaped (\%, \$); a literal "%"/"$" is correct here.
  const close = (a: number, b: number, tol: number) => Math.abs(a - b) < tol;
  const blocks: DerivationBlock[] = [
    crosscheck('Total return', `${s2(result.totalReturnPct)}%`, `${s2(py.totalReturnPct)}%`, CROSSCHECK_SOURCE, close(result.totalReturnPct, py.totalReturnPct, 0.1)),
    crosscheck('Final capital', `$${commaFixed(result.finalCapital)}`, `$${commaFixed(py.finalCapital)}`, CROSSCHECK_SOURCE, close(result.finalCapital, py.finalCapital, 10)),
    crosscheck('Sharpe', num3(result.returns.sharpe), py.sharpe.toFixed(3), CROSSCHECK_SOURCE, close(result.returns.sharpe, py.sharpe, 0.02)),
  ];
  if (py.sortino != null) {
    blocks.push(crosscheck('Sortino', num3(result.returns.sortino), py.sortino.toFixed(3), CROSSCHECK_SOURCE, close(result.returns.sortino, py.sortino, 0.02)));
  } else {
    blocks.push(note("CLAUDE.md's locked comparison does not disclose a Sortino figure for this arm -- only Sharpe and MaxDD -- so this row has no Python value to check against."));
  }
  blocks.push(
    crosscheck('Max drawdown', `${n2(result.maxDrawdownPct)}%`, `${py.maxDrawdownPct.toFixed(2)}%`, CROSSCHECK_SOURCE, close(result.maxDrawdownPct, py.maxDrawdownPct, 0.1)),
    crosscheck('Time in market', `${n2(result.timeInMarketPct)}%`, `${py.timeInMarketPct.toFixed(2)}%`, CROSSCHECK_SOURCE, close(result.timeInMarketPct, py.timeInMarketPct, 0.1)),
  );
  if (exposureCaveat) {
    blocks.push(
      note(
        "This arm holds 100% of its window's bars, against the strategy's 2.63% time-in-market -- a materially " +
          'different risk exposure. Per CLAUDE.md, a higher raw return here must never be stated without this ' +
          'exposure-time caveat in the same breath.',
        'caveat',
      ),
    );
  }
  return { label: 'Cross-check vs. the Python benchmark script', blocks };
}

export function strategyArmDerivation(result: ArmResult, feeAdjResult: ArmResult): DerivationStep {
  return {
    id: 'benchmark-strategy',
    title: 'OB-Gated Strategy -- Equity Curve, Sharpe, Sortino, Max Drawdown',
    steps: [
      {
        label: 'Capital and construction rule',
        blocks: [
          values([
            { symbol: 'C_0', description: 'starting capital', value: `\\$${commaInt(result.startingCapital)}` },
            { symbol: 'n_{\\text{bars}}', description: '4h bars in the locked window', value: commaInt(result.nBars) },
          ]),
          note(
            "Capital sits idle between trades and compounds multiplicatively by (1+pnl_pct/100) only at each " +
              "trade's own exit bar -- valid because trades never overlap (simulate_trades() only opens a new " +
              'position once the prior one is flat).',
          ),
          algebra(
            'E_0 = C_0, \\qquad E_i = \\begin{cases} E_{i-1}(1+\\text{pnl\\_pct}_i/100) & \\text{bar } i \\text{ is a trade exit} \\\\ E_{i-1} & \\text{otherwise} \\end{cases}',
          ),
          equitySampleTable(result, 'Equity ($)'),
        ],
      },
      ...sharpeSortinoSteps(result, '4h-bar'),
      maxDrawdownStep(result),
      {
        label: 'Total return, final capital, and time in market',
        blocks: [
          algebra('\\text{Total return} = \\sum_i \\text{pnl\\_pct}_i', undefined, `\\text{Total return} = ${s2(result.totalReturnPct)}\\%`),
          note(
            "This is a simple SUM of each trade's pnl_pct -- the same convention as the locked +30.31% headline " +
              "figure -- which differs very slightly from the compounded equity curve's own final value below; " +
              'both are shown, not reconciled away (benchmark_vs_passive.py:238-244 documents the same split ' +
              'deliberately, on the Python side).',
          ),
          algebra('\\text{Final capital} = E_{n_{\\text{bars}}-1}', undefined, `\\text{Final capital} = \\$${commaFixed(result.finalCapital)}`),
          algebra(
            '\\text{Time in market} = \\dfrac{\\sum_i \\text{hold\\_bars}_i}{n_{\\text{bars}}}\\times 100',
            undefined,
            `\\text{Time in market} = ${n2(result.timeInMarketPct)}\\%`,
          ),
        ],
      },
      benchmarkCrosscheckStep(result, PY_STRATEGY_GROSS, false),
      {
        label: 'Fee-adjusted variant (0.20% round-trip drag per trade)',
        blocks: [
          note(
            'Matches fee_slippage_analysis.py\'s confirmed primary scenario (5bps/side taker + 5bps/side ' +
              'slippage, round-tripped): each trade\'s pnl_pct is reduced by 0.20% before summing/compounding.',
          ),
          crosscheck(
            'Total return (fee-adjusted)',
            `${s2(feeAdjResult.totalReturnPct)}%`,
            `${s2(PY_STRATEGY_FEE_ADJ.totalReturnPct)}%`,
            CROSSCHECK_SOURCE,
            Math.abs(feeAdjResult.totalReturnPct - PY_STRATEGY_FEE_ADJ.totalReturnPct) < 0.1,
          ),
          crosscheck(
            'Final capital (fee-adjusted)',
            `$${commaFixed(feeAdjResult.finalCapital)}`,
            `$${commaFixed(PY_STRATEGY_FEE_ADJ.finalCapital)}`,
            CROSSCHECK_SOURCE,
            Math.abs(feeAdjResult.finalCapital - PY_STRATEGY_FEE_ADJ.finalCapital) < 10,
          ),
        ],
      },
    ],
    resultTex: `\\text{Sharpe} = ${num3(result.returns.sharpe)}, \\quad \\text{Sortino} = ${num3(result.returns.sortino)}, \\quad \\text{Max DD} = ${n2(result.maxDrawdownPct)}\\%`,
    prose:
      'Event-driven equity curve on the same 27-trade baseline used throughout this page -- Sharpe/Sortino ' +
      "annualized on 4h-bar returns, matching analysis/benchmark_vs_passive.py's strategy_arm().",
  };
}

export function dcaArmDerivation(result: DcaArmResult): DerivationStep {
  return {
    id: 'benchmark-dca',
    title: 'Weekly DCA into BTC -- Equity Curve, Sharpe, Sortino, Max Drawdown',
    steps: [
      {
        label: 'Capital and contribution schedule',
        blocks: [
          values([
            { symbol: 'C_0', description: 'starting capital', value: `\\$${commaInt(result.startingCapital)}` },
            { symbol: 'W', description: 'ISO calendar weeks in the window', value: commaInt(result.nContributions) },
            { symbol: 'c', description: 'contribution per week, C_0/W', value: `\\$${commaFixed(result.contributionPerWeek)}` },
          ]),
          note(
            'One contribution at the first bar of every ISO-8601 calendar week (Monday-Thursday rule), bought at ' +
              "that bar's CLOSE price -- same timing convention as benchmark_dca_analysis.py's Section 2.",
          ),
          algebra('\\text{units} \\mathrel{+}= \\dfrac{c}{\\text{close}_i}\\ \\text{at each contribution bar } i, \\qquad V_i = \\text{units}\\times\\text{close}_i'),
          equitySampleTable(result, 'Portfolio value ($)'),
        ],
      },
      ...sharpeSortinoSteps(result, 'weekly'),
      maxDrawdownStep(result),
      {
        label: 'Total return',
        blocks: [
          values([{ symbol: '\\text{Contributed}', description: 'W x c', value: `\\$${commaFixed(result.startingCapital)}` }]),
          algebra(
            '\\text{Total return} = \\dfrac{V_{\\text{final}} - \\text{Contributed}}{\\text{Contributed}}\\times 100',
            `\\text{Total return} = \\dfrac{${commaFixed(result.finalCapital)} - ${commaFixed(result.startingCapital)}}{${commaFixed(result.startingCapital)}}\\times 100`,
            `\\text{Total return} = ${s2(result.totalReturnPct)}\\%`,
          ),
        ],
      },
      benchmarkCrosscheckStep(result, PY_DCA, true),
    ],
    resultTex: `\\text{Sharpe} = ${num3(result.returns.sharpe)}, \\quad \\text{Max DD} = ${n2(result.maxDrawdownPct)}\\%`,
    prose:
      "Weekly-sampled equity curve -- Sharpe/Sortino/MaxDD use the W weekly value samples, not every 4h bar, " +
      "matching analysis/benchmark_vs_passive.py's dca_arm() exactly.",
  };
}

export function lumpSumArmDerivation(result: ArmResult): DerivationStep {
  return {
    id: 'benchmark-lumpsum',
    title: 'Lump-Sum Buy-and-Hold -- Equity Curve, Sharpe, Sortino, Max Drawdown',
    steps: [
      {
        label: 'Capital and construction rule',
        blocks: [
          values([{ symbol: 'C_0', description: 'starting capital', value: `\\$${commaInt(result.startingCapital)}` }]),
          note("All capital deployed at the window's very first bar's OPEN price -- a deliberately different anchor than the DCA arm's per-contribution CLOSE price, flagged explicitly in benchmark_vs_passive.py's module docstring."),
          algebra('\\text{units} = \\dfrac{C_0}{\\text{open}_0}, \\qquad E_i = \\text{units}\\times\\text{close}_i'),
          equitySampleTable(result, 'Equity ($)'),
        ],
      },
      ...sharpeSortinoSteps(result, '4h-bar'),
      maxDrawdownStep(result),
      {
        label: 'Total return',
        blocks: [
          algebra(
            '\\text{Total return} = \\dfrac{E_{\\text{final}} - C_0}{C_0}\\times 100',
            `\\text{Total return} = \\dfrac{${commaFixed(result.finalCapital)} - ${commaFixed(result.startingCapital)}}{${commaFixed(result.startingCapital)}}\\times 100`,
            `\\text{Total return} = ${s2(result.totalReturnPct)}\\%`,
          ),
        ],
      },
      benchmarkCrosscheckStep(result, PY_LUMP, true),
    ],
    resultTex: `\\text{Sharpe} = ${num3(result.returns.sharpe)}, \\quad \\text{Max DD} = ${n2(result.maxDrawdownPct)}\\%`,
    prose:
      "Single all-in purchase at the window's first open, held to the last close -- Sharpe/Sortino annualized on " +
      "4h-bar returns, matching analysis/benchmark_vs_passive.py's lump_sum_arm().",
  };
}
