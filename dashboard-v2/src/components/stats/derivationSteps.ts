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
 * orderings: Welch's mean step wants its raw-value TABLE before the mean
 * FORMULA, while Fisher's enumeration step wants the hypergeometric FORMULA
 * before its term TABLE.
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
import type {
  BinomialTerm,
  BootstrapCIResult,
  FisherTermsResult,
  MdeResult,
  PearsonResult,
  SpearmanResult,
  WelchResult,
} from './statMath';
import { Z_ALPHA_2, Z_BETA } from './statMath';
import type { BaselineProvenance, CriterionTestRow } from './statsCompute';

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
const n6 = (v: number) => (Number.isNaN(v) ? '\\text{NaN}' : v.toFixed(6));
const s2 = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;
/** A single value as a signed LaTeX term, negatives parenthesized so a
 * following " + " reads unambiguously (e.g. "0.78 + (-1.23)"). */
const term = (v: number) => (v < 0 ? `(${v.toFixed(2)})` : v.toFixed(2));
/** Locale-independent thousands separator (not toLocaleString(), whose
 * output depends on the reader's browser locale -- "2,000" in en-US is
 * "2.000" in de-DE, making a `tex` string non-author-constant). */
const commaInt = (v: number) => Math.trunc(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
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

/** Mean sub-derivation as a full DerivationLine: raw-values table, then the
 * general formula, the expanded sum, and the (already-computed) result. */
function meanLine(symbol: string, description: string, vals: number[], resultValue: number): DerivationLine {
  const n = vals.length;
  const sumTex = vals.map(term).join(' + ');
  return {
    label: `Mean, ${description}`,
    blocks: [
      valuesTable(description, vals),
      algebra('\\bar{X} = \\dfrac{1}{n}\\sum_{i=1}^{n} X_i', `${symbol} = \\dfrac{${sumTex}}{${n}}`, `${symbol} = ${s2(resultValue)}\\%`),
    ],
  };
}

/** Sample-variance (Bessel-corrected) sub-derivation. `showTable` controls
 * whether the raw values are re-listed -- skipped when the same subgroup's
 * table was already shown in an adjacent step (e.g. the mean step directly
 * above), so the page doesn't repeat a 20+ row table twice in a row. */
function varianceLine(
  symbol: string,
  description: string,
  vals: number[],
  meanValue: number,
  resultValue: number,
  opts: { asSd: boolean; showTable: boolean },
): DerivationLine {
  const n = vals.length;
  const meanStr = s2(meanValue);
  const devTex = vals.map((v) => `(${term(v)} - ${meanStr})^2`).join(' + ');
  const formulaTex = opts.asSd
    ? 's = \\sqrt{\\dfrac{1}{n-1}\\sum_{i=1}^{n} (X_i-\\bar{X})^2}'
    : 's^2 = \\dfrac{1}{n-1}\\sum_{i=1}^{n} (X_i-\\bar{X})^2';
  const substitutedTex = opts.asSd
    ? `${symbol} = \\sqrt{\\dfrac{${devTex}}{${n}-1}}`
    : `${symbol} = \\dfrac{${devTex}}{${n}-1}`;
  const blocks: DerivationBlock[] = [];
  if (opts.showTable) blocks.push(valuesTable(description, vals));
  blocks.push(algebra(formulaTex, substitutedTex, `${symbol} = ${n4(resultValue)}`));
  return { label: `${opts.asSd ? 'Standard deviation' : 'Sample variance'}, ${description}`, blocks };
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

// ─── 2. Fisher's exact test (per orthogonal criterion) ─────────────────────
export function fisherDerivation(row: CriterionTestRow, terms: FisherTermsResult): DerivationStep {
  const a = row.trueWins;
  const b = row.trueN - row.trueWins;
  const c = row.falseWins;
  const d = row.falseN - row.falseWins;
  return {
    id: `fisher-${row.label}`,
    title: `Fisher's Exact Test -- ${row.label}`,
    steps: [
      {
        label: `Build the 2x2 table from ${row.field}`,
        blocks: [
          values([
            { symbol: 'a', description: `${row.label}=True, win`, value: String(a) },
            { symbol: 'b', description: `${row.label}=True, loss`, value: String(b) },
            { symbol: 'c', description: `${row.label}=False, win`, value: String(c) },
            { symbol: 'd', description: `${row.label}=False, loss`, value: String(d) },
          ]),
          algebra(`\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}`, `\\begin{bmatrix} ${a} & ${b} \\\\ ${c} & ${d} \\end{bmatrix}`),
          note(`a,b,c,d partition the N=${terms.n} baseline trades by win/loss (pnl_pct > 0) crossed with whether the ${row.field} field is true.`),
        ],
      },
      {
        label: 'Row/column margins and total',
        blocks: [
          algebra(
            'n_1 = a+b, \\quad n_2 = c+d, \\quad m_1 = a+c, \\quad m_2 = b+d, \\quad n = n_1+n_2',
            `n_1 = ${a}+${b}, \\; n_2 = ${c}+${d}, \\; m_1 = ${a}+${c}, \\; m_2 = ${b}+${d}, \\; n = ${terms.n}`,
            `n_1 = ${terms.rowSum1}, \\; n_2 = ${terms.rowSum2}, \\; m_1 = ${terms.colSum1}, \\; m_2 = ${terms.colSum2}, \\; n = ${terms.n}`,
          ),
        ],
      },
      {
        label: 'Hypergeometric probability of any table with these margins',
        blocks: [
          algebra('P(x) = \\dfrac{\\binom{n_1}{x}\\binom{n_2}{m_1-x}}{\\binom{n}{m_1}}'),
          note('x is the (a)-cell count -- the number of True&Win trades -- ranging over every table sharing these same row/column margins.'),
        ],
      },
      {
        label: 'Probability of the observed table',
        blocks: [
          algebra(
            `P(x_{\\text{obs}}) = \\dfrac{\\binom{${terms.rowSum1}}{${terms.xObs}}\\binom{${terms.rowSum2}}{${terms.colSum1}-${terms.xObs}}}{\\binom{${terms.n}}{${terms.colSum1}}}`,
            undefined,
            `P(x_{\\text{obs}}) = ${pFmtTex(terms.pObs)}`,
          ),
          note(
            `A table is included in the two-sided sum if its probability is <= P(x_obs) plus a small floating-point ` +
              `tolerance (epsilon = ${terms.epsilon.toExponential(0)}); the comparison is actually done in log-probability ` +
              'space (log P(x) <= log P(x_obs) + epsilon), which is why the enumeration table below also lists log P(x).',
          ),
        ],
      },
      {
        label: `Enumerate every table with these margins, x = ${terms.xMin}..${terms.xMax}`,
        blocks: [
          table({
            caption: `All ${terms.terms.length} tables, P(x) and inclusion in the two-sided sum`,
            headers: ['x', 'P(x)', 'log P(x)', 'Included?'],
            rows: terms.terms.map((t) => ({
              cells: [String(t.x), pFmtTable(t.p), t.logP.toFixed(4), t.included ? 'yes' : 'no -- more likely than observed'],
              emphasis: t.x === terms.xObs ? 'observed' : t.included ? undefined : 'excluded',
            })),
          }),
        ],
      },
      {
        label: 'Sum the included tables',
        blocks: [
          algebra(
            'p = \\sum_{x:\\, P(x) \\leq P(x_{\\text{obs}})+\\epsilon} P(x)',
            `p = ${terms.terms
              .filter((t) => t.included)
              .map((t) => pFmtTex(t.p))
              .join(' + ')}`,
            `p = ${n4(row.fisherP)}`,
          ),
        ],
      },
      {
        label: 'Compare to alpha = 0.05',
        blocks: [
          note(
            `${n4(row.fisherP)} ${row.fisherP < 0.05 ? '<' : '>='} 0.05, so the association between ${row.label} and ` +
              `win/loss is ${row.fisherP < 0.05 ? 'significant' : 'not significant'} at alpha=0.05.`,
          ),
        ],
      },
    ],
    resultTex: `p = ${n4(row.fisherP)}`,
    prose:
      'Two-sided exact test on the 2x2 win/loss x criterion-True/False contingency table, over the baseline. ' +
      "Sums the exact hypergeometric probability of every table with the same row/column margins whose " +
      "probability is <= the observed table's -- matches scipy.stats.fisher_exact(alternative='two-sided').",
  };
}

// ─── 3. Welch's t-test (per orthogonal criterion) ───────────────────────────
export function welchDerivation(row: CriterionTestRow): DerivationStep {
  const w: WelchResult = row.welch;
  return {
    id: `welch-${row.label}`,
    title: `Welch's t-test -- ${row.label}`,
    steps: [
      {
        label: `Partition the baseline by ${row.field}`,
        blocks: [
          values([
            { symbol: 'n_1', description: `${row.label}=True subgroup size`, value: String(w.n1) },
            { symbol: 'n_2', description: `${row.label}=False subgroup size`, value: String(w.n2) },
          ]),
        ],
      },
      meanLine('\\bar{X}_1', `${row.label}=True`, row.trueValues, w.m1),
      meanLine('\\bar{X}_2', `${row.label}=False`, row.falseValues, w.m2),
      varianceLine('s_1^2', `${row.label}=True`, row.trueValues, w.m1, w.v1, { asSd: false, showTable: false }),
      varianceLine('s_2^2', `${row.label}=False`, row.falseValues, w.m2, w.v2, { asSd: false, showTable: false }),
      {
        label: 'Standard error',
        blocks: [
          algebra('a_1 = s_1^2/n_1', `a_1 = ${n4(w.v1)}/${w.n1}`, `a_1 = ${n4(w.a1)}`),
          algebra('a_2 = s_2^2/n_2', `a_2 = ${n4(w.v2)}/${w.n2}`, `a_2 = ${n4(w.a2)}`),
          algebra('SE^2 = a_1 + a_2', `SE^2 = ${n4(w.a1)} + ${n4(w.a2)}`, `SE^2 = ${n4(w.se2)}`),
          algebra('SE = \\sqrt{SE^2}', `SE = \\sqrt{${n4(w.se2)}}`, `SE = ${n4(w.se)}`),
        ],
      },
      {
        label: 't statistic',
        blocks: [algebra('t = \\dfrac{\\bar{X}_1-\\bar{X}_2}{SE}', `t = \\dfrac{${s2(w.m1)} - (${s2(w.m2)})}{${n4(w.se)}}`, `t = ${s2(w.t)}`)],
      },
      {
        label: 'Welch-Satterthwaite degrees of freedom',
        blocks: [
          algebra('\\text{df}_{\\text{num}} = (SE^2)^2', `(${n4(w.se2)})^2`, `\\text{df}_{\\text{num}} = ${n4(w.dfNum)}`),
          algebra(
            '\\text{df}_{\\text{den}} = \\dfrac{a_1^2}{n_1-1} + \\dfrac{a_2^2}{n_2-1}',
            `\\dfrac{${n4(w.a1)}^2}{${w.n1}-1} + \\dfrac{${n4(w.a2)}^2}{${w.n2}-1}`,
            `\\text{df}_{\\text{den}} = ${n6(w.dfDen1 + w.dfDen2)}`,
          ),
          algebra(
            '\\text{df} = \\dfrac{\\text{df}_{\\text{num}}}{\\text{df}_{\\text{den}}}',
            `\\text{df} = \\dfrac{${n4(w.dfNum)}}{${n6(w.dfDen1 + w.dfDen2)}}`,
            `\\text{df} = ${n2(w.df)}`,
          ),
        ],
      },
      {
        label: 'p-value',
        blocks: [
          algebra('x = \\dfrac{\\text{df}}{\\text{df}+t^2}', `x = \\dfrac{${n2(w.df)}}{${n2(w.df)}+(${s2(w.t)})^2}`, `x = ${n4(w.tX)}`),
          algebra('p = I_x(\\text{df}/2,\\, 1/2)', `p = I_{${n4(w.tX)}}(${n2(w.df / 2)},\\, 0.5)`, `p = ${n4(w.p)}`),
          note(INCOMPLETE_BETA_NOTE),
        ],
      },
      {
        label: 'Compare to alpha = 0.05',
        blocks: [
          note(
            `${n4(w.p)} ${w.p < 0.05 ? '<' : '>='} 0.05, so the mean-return difference between ${row.label}=True and ` +
              `${row.label}=False is ${w.p < 0.05 ? 'significant' : 'not significant'} at alpha=0.05.`,
          ),
        ],
      },
    ],
    resultTex: `t = ${s2(w.t)}, \\; \\text{df} = ${n2(w.df)}, \\; p = ${n4(w.p)}`,
    prose:
      "Unequal-variance (Welch's, not Student's) two-sample t-test on pnl_pct, True vs. False subgroups. " +
      "Welch's form is used because subgroup sizes and variances are unequal and small -- matches " +
      'scipy.stats.ttest_ind(equal_var=False).',
  };
}

// ─── 4. Minimum Detectable Effect (per orthogonal criterion) ───────────────
export function mdeDerivation(row: CriterionTestRow): DerivationStep {
  const m: MdeResult = row.mde;
  return {
    id: `mde-${row.label}`,
    title: `Minimum Detectable Effect -- ${row.label}`,
    steps: [
      {
        label: 'Reuse the True/False subgroups',
        blocks: [
          note(
            `Same ${row.field}=True/False partition of the baseline as the Welch's t-test card above -- see ` +
              'its first step for the raw pnl_pct values behind each subgroup.',
          ),
        ],
      },
      varianceLine('s_1', `${row.label}=True`, row.trueValues, row.welch.m1, m.sd1, { asSd: true, showTable: false }),
      varianceLine('s_2', `${row.label}=False`, row.falseValues, row.welch.m2, m.sd2, { asSd: true, showTable: false }),
      {
        label: 'Where the critical values come from',
        blocks: [
          values([
            { symbol: 'z_{\\alpha/2}', description: 'two-sided critical value, alpha=0.05', value: n4(Z_ALPHA_2) },
            { symbol: 'z_\\beta', description: 'critical value, power=0.80', value: n4(Z_BETA) },
          ]),
          note(
            'These are the standard-normal quantiles Phi^-1(0.975) and Phi^-1(0.80). They are NOT evaluated by an ' +
              'inverse-normal-CDF routine in this browser -- they are fixed constants, hardcoded to match ' +
              "analysis/bootstrap_power_analysis.py's own defaults (--alpha 0.05 --power 0.80), since this " +
              'dashboard does not expose alpha/power as tunable inputs.',
          ),
        ],
      },
      {
        label: 'Standard error',
        blocks: [
          algebra(
            'SE = \\sqrt{s_1^2/n_1 + s_2^2/n_2}',
            `SE = \\sqrt{${n4(m.sd1)}^2/${m.n1} + ${n4(m.sd2)}^2/${m.n2}}`,
            `SE = ${n4(m.se)}`,
          ),
          note(
            "This SE is the same formula as Welch's SE above, but computed independently here from s (this " +
              "card's own sd -> square path) rather than Welch's s^2 (its variance directly). The two are " +
              'numerically equal for this data but are not guaranteed bit-identical in general, since ' +
              'sqrt(v)**2 does not always equal v exactly in floating point.',
          ),
        ],
      },
      {
        label: 'Minimum detectable effect',
        blocks: [
          algebra(
            '\\text{MDE} = (z_{\\alpha/2}+z_\\beta)\\, SE',
            `\\text{MDE} = (${n4(Z_ALPHA_2)} + ${n4(Z_BETA)}) \\times ${n4(m.se)}`,
            `\\text{MDE} = ${n2(m.mde)}\\%`,
          ),
        ],
      },
      {
        label: 'Compare to the observed difference',
        blocks: [
          algebra(
            '|\\bar{X}_1-\\bar{X}_2|\\ \\text{vs.}\\ \\text{MDE}',
            `${n2(Math.abs(m.observedDiff))}\\%\\ \\text{vs.}\\ ${n2(m.mde)}\\%`,
            `\\text{${m.detectable ? 'detectable' : 'underpowered'}}`,
          ),
          note(
            m.detectable
              ? 'The observed difference exceeds the MDE: this sample size could reliably detect an effect of this size.'
              : 'The observed difference is SMALLER than the MDE: this sample size cannot reliably distinguish an effect ' +
                'of this size from noise. Reported plainly, not softened -- this is the case for all 5 orthogonal criteria.',
          ),
        ],
      },
    ],
    resultTex: `\\text{MDE} = ${n2(m.mde)}\\%, \\quad |\\bar{X}_1-\\bar{X}_2| = ${n2(Math.abs(m.observedDiff))}\\%\\ (${m.detectable ? 'detectable' : 'underpowered'})`,
    prose:
      'Two-sample normal-approximation MDE at alpha=0.05, power=0.80 -- the smallest true mean difference ' +
      "this subgroup split could reliably detect at these sample sizes.",
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
