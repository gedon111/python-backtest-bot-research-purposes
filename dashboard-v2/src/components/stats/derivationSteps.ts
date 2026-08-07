/**
 * Step-by-step derivations for the Solutions tab: variables -> general
 * formula -> substituted formula -> result, for every hypothesis
 * test/estimator the Stats tab computes. Deliberately takes ALREADY
 * COMPUTED result objects from statsCompute.ts/statMath.ts (never raw
 * trades) as input -- these functions only format, they never recompute --
 * so Solutions can never numerically drift from what StatsTab.tsx displays.
 *
 * General-formula LaTeX strings are copied verbatim from StatsTab.tsx's own
 * constants. Substituted-formula/prose text is grounded in
 * STUDY_REFERENCE.md Sec.5 ("Statistical methods") and CLAUDE.md's locked
 * figures -- author-constant strings, cross-checked against locked numbers
 * (e.g. FVG's post-fix Welch t=+0.5360, p=0.5996) before being written here.
 * Every `tex` value handed to <Latex> stays an author-constant template with
 * only numeric leaves interpolated, per Latex.tsx's contract -- never built
 * from arbitrary/unsanitized data.
 */
import type { BootstrapCIResult, PearsonResult, SpearmanResult, WelchResult, MdeResult } from './statMath';
import type { CriterionTestRow } from './statsCompute';

export interface DerivationVariable {
  symbol: string;
  description: string;
  value: string;
}

/** A sub-derivation showing how one "given" variable (e.g. a mean or sample
 * variance) was itself computed from a list of raw per-trade values -- one
 * level deeper than DerivationStep's own formula/substitution/result. */
export interface VariableDerivation {
  symbol: string;
  description: string;
  formulaTex: string;
  substitutedTex: string;
  resultTex: string;
}

export interface DerivationStep {
  id: string;
  title: string;
  variables: DerivationVariable[];
  /** How aggregate variables above (means, variances) were computed from raw
   * per-trade values. Absent for steps whose variables are already primitive
   * (plain counts, or sums already shown as the deepest substitution level). */
  variableDerivations?: VariableDerivation[];
  generalFormulaTex: string;
  substitutedFormulaTex: string;
  resultTex: string;
  prose: string;
}

const n4 = (v: number) => (Number.isNaN(v) ? 'NaN' : v.toFixed(4));
const n2 = (v: number) => (Number.isNaN(v) ? 'NaN' : v.toFixed(2));
const s2 = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;

/** A single value as a signed LaTeX term, negatives parenthesized so a
 * following " + " reads unambiguously (e.g. "0.78 + (-1.23)"). */
const term = (v: number) => (v < 0 ? `(${v.toFixed(2)})` : v.toFixed(2));

/** Mean sub-derivation: shows the raw values, their sum, and the division by n.
 * `resultValue` is the already-computed mean (e.g. WelchResult.m1) -- shown as
 * the result rather than resummed from the rounded display terms, same
 * rounded-substitution-but-exact-result convention the rest of this file uses. */
function meanVariableDerivation(symbol: string, description: string, values: number[], resultValue: number): VariableDerivation {
  const n = values.length;
  const sumTex = values.map(term).join(' + ');
  return {
    symbol,
    description,
    formulaTex: '\\bar{X} = \\dfrac{1}{n}\\sum_{i=1}^{n} X_i',
    substitutedTex: `${symbol} = \\dfrac{${sumTex}}{${n}}`,
    resultTex: `${symbol} = ${s2(resultValue)}\\%`,
  };
}

/** Sample-variance (Bessel-corrected) sub-derivation, reusing the same
 * expanded-deviation form for both the Welch card's s^2 and the MDE card's s
 * (sqrt of the identical variance() computation in statMath.ts -- same inputs,
 * same formula, so v1 and sd1^2 are numerically identical by construction). */
function varianceVariableDerivation(
  symbol: string,
  description: string,
  values: number[],
  meanValue: number,
  resultValue: number,
  asSd: boolean,
): VariableDerivation {
  const n = values.length;
  const meanStr = s2(meanValue);
  const devTex = values.map((v) => `(${term(v)} - ${meanStr})^2`).join(' + ');
  const formulaTex = asSd
    ? 's = \\sqrt{\\dfrac{1}{n-1}\\sum_{i=1}^{n} (X_i-\\bar{X})^2}'
    : 's^2 = \\dfrac{1}{n-1}\\sum_{i=1}^{n} (X_i-\\bar{X})^2';
  const substitutedTex = asSd
    ? `${symbol} = \\sqrt{\\dfrac{${devTex}}{${n}-1}}`
    : `${symbol} = \\dfrac{${devTex}}{${n}-1}`;
  return {
    symbol,
    description,
    formulaTex,
    substitutedTex,
    resultTex: `${symbol} = ${n4(resultValue)}`,
  };
}

// ─── 1. One-sided exact binomial test ──────────────────────────────────────
export function binomialDerivation(n: number, k: number, p0: number, p: number): DerivationStep {
  return {
    id: 'binomial',
    title: "One-Sided Exact Binomial Test",
    variables: [
      { symbol: 'n', description: 'total trades', value: String(n) },
      { symbol: 'k', description: 'wins', value: String(k) },
      { symbol: 'p_0', description: 'null-hypothesis win probability (zero-edge)', value: p0.toFixed(1) },
    ],
    generalFormulaTex: 'P(X \\geq k) = \\sum_{x=k}^{n} \\binom{n}{x}\\, p_0^{x} (1-p_0)^{n-x}',
    substitutedFormulaTex: `P(X \\geq ${k}) = \\sum_{x=${k}}^{${n}} \\binom{${n}}{x}\\, ${p0.toFixed(1)}^{x} ${(1 - p0).toFixed(1)}^{${n}-x}`,
    resultTex: `P(X \\geq ${k}) = ${n4(p)}`,
    prose:
      'One-sided because the pre-registered hypothesis is directional -- that the strategy\'s win rate ' +
      'exceeds the 50% zero-edge null, not merely that it differs from 50% in either direction ' +
      '(STUDY_REFERENCE.md Sec.5). Computed via log-factorial combinatorics to avoid overflow at n~25-30.',
  };
}

// ─── 2. Fisher's exact test (per orthogonal criterion) ─────────────────────
export function fisherDerivation(row: CriterionTestRow): DerivationStep {
  const a = row.trueWins;
  const b = row.trueN - row.trueWins;
  const c = row.falseWins;
  const d = row.falseN - row.falseWins;
  const n = a + b + c + d;
  return {
    id: `fisher-${row.label}`,
    title: `Fisher's Exact Test -- ${row.label}`,
    variables: [
      { symbol: 'a', description: `${row.label}=True, win`, value: String(a) },
      { symbol: 'b', description: `${row.label}=True, loss`, value: String(b) },
      { symbol: 'c', description: `${row.label}=False, win`, value: String(c) },
      { symbol: 'd', description: `${row.label}=False, loss`, value: String(d) },
      { symbol: 'n', description: 'total trades (baseline)', value: String(n) },
    ],
    generalFormulaTex:
      'p = \\sum_{x:\\,P(x)\\leq P(x_{\\text{obs}})} P(x), \\quad P(x) = \\dfrac{\\binom{a+b}{x}\\binom{c+d}{(a+c)-x}}{\\binom{n}{a+c}}',
    substitutedFormulaTex: `\\begin{bmatrix} a=${a} & b=${b} \\\\ c=${c} & d=${d} \\end{bmatrix}, \\quad n=${n}`,
    resultTex: `p = ${n4(row.fisherP)}`,
    prose:
      "Two-sided exact test on the 2x2 win/loss x criterion-True/False contingency table, over the " +
      "N=27 min_ob_quality=0 baseline. Sums the exact hypergeometric probability of every table with the " +
      "same row/column margins whose probability is <= the observed table's -- matches " +
      "scipy.stats.fisher_exact(alternative='two-sided').",
  };
}

// ─── 3. Welch's t-test (per orthogonal criterion) ───────────────────────────
export function welchDerivation(row: CriterionTestRow): DerivationStep {
  const w: WelchResult = row.welch;
  return {
    id: `welch-${row.label}`,
    title: `Welch's t-test -- ${row.label}`,
    variables: [
      { symbol: '\\bar{X}_1', description: `mean return, ${row.label}=True`, value: s2(w.m1) + '%' },
      { symbol: '\\bar{X}_2', description: `mean return, ${row.label}=False`, value: s2(w.m2) + '%' },
      { symbol: 's_1^2', description: 'sample variance, True subgroup', value: n4(w.v1) },
      { symbol: 's_2^2', description: 'sample variance, False subgroup', value: n4(w.v2) },
      { symbol: 'n_1', description: 'True subgroup size', value: String(w.n1) },
      { symbol: 'n_2', description: 'False subgroup size', value: String(w.n2) },
    ],
    variableDerivations: [
      meanVariableDerivation('\\bar{X}_1', `mean return, ${row.label}=True`, row.trueValues, w.m1),
      meanVariableDerivation('\\bar{X}_2', `mean return, ${row.label}=False`, row.falseValues, w.m2),
      varianceVariableDerivation('s_1^2', 'sample variance, True subgroup', row.trueValues, w.m1, w.v1, false),
      varianceVariableDerivation('s_2^2', 'sample variance, False subgroup', row.falseValues, w.m2, w.v2, false),
    ],
    generalFormulaTex: 't = \\dfrac{\\bar{X}_1-\\bar{X}_2}{\\sqrt{s_1^2/n_1+s_2^2/n_2}}',
    substitutedFormulaTex: `t = \\dfrac{${s2(w.m1)} - (${s2(w.m2)})}{\\sqrt{${n4(w.v1)}/${w.n1} + ${n4(w.v2)}/${w.n2}}}`,
    resultTex: `t = ${s2(w.t)}, \\; \\text{df} = ${n2(w.df)}, \\; p = ${n4(w.p)}`,
    prose:
      "Unequal-variance (Welch's, not Student's) two-sample t-test on pnl_pct, True vs. False subgroups. " +
      'Welch\'s form is used because subgroup sizes and variances are unequal and small (subgroup n ranges ' +
      "4-23 across the 5 criteria) -- matches scipy.stats.ttest_ind(equal_var=False). Degrees of freedom via " +
      'the Welch-Satterthwaite equation.',
  };
}

// ─── 4. Minimum Detectable Effect (per orthogonal criterion) ───────────────
export function mdeDerivation(row: CriterionTestRow): DerivationStep {
  const m: MdeResult = row.mde;
  const zAlpha2 = 1.96;
  const zBeta = 0.8416;
  return {
    id: `mde-${row.label}`,
    title: `Minimum Detectable Effect -- ${row.label}`,
    variables: [
      { symbol: 's_1', description: `SD, ${row.label}=True`, value: n4(m.sd1) },
      { symbol: 's_2', description: `SD, ${row.label}=False`, value: n4(m.sd2) },
      { symbol: 'n_1', description: 'True subgroup size', value: String(m.n1) },
      { symbol: 'n_2', description: 'False subgroup size', value: String(m.n2) },
      { symbol: 'z_{\\alpha/2}', description: 'critical value, alpha=0.05', value: zAlpha2.toFixed(4) },
      { symbol: 'z_\\beta', description: 'critical value, power=0.80', value: zBeta.toFixed(4) },
    ],
    // Same variance() computation as Welch's t-test card (identical inputs,
    // identical formula in statMath.ts), just reported as SD here since MDE's
    // own formula uses s1/s2 directly -- reuses row.welch.m1/m2 for the mean
    // rather than recomputing, since MdeResult doesn't carry the mean itself.
    variableDerivations: [
      varianceVariableDerivation('s_1', `SD, ${row.label}=True`, row.trueValues, row.welch.m1, m.sd1, true),
      varianceVariableDerivation('s_2', `SD, ${row.label}=False`, row.falseValues, row.welch.m2, m.sd2, true),
    ],
    generalFormulaTex: '\\text{MDE} = (z_{\\alpha/2}+z_\\beta)\\sqrt{s_1^2/n_1+s_2^2/n_2}',
    substitutedFormulaTex: `\\text{MDE} = (${zAlpha2.toFixed(4)} + ${zBeta.toFixed(4)}) \\sqrt{${n4(m.sd1)}^2/${m.n1} + ${n4(m.sd2)}^2/${m.n2}}`,
    resultTex: `\\text{MDE} = ${n2(m.mde)}\\%, \\quad |\\bar{X}_1-\\bar{X}_2| = ${n2(Math.abs(m.observedDiff))}\\%\\ (${m.detectable ? 'detectable' : 'underpowered'})`,
    prose:
      'Two-sample normal-approximation MDE at alpha=0.05, power=0.80 -- the smallest true mean difference ' +
      "this subgroup split could reliably detect at these sample sizes. 'Underpowered' means the observed " +
      'difference is smaller than the MDE, i.e. this sample size cannot distinguish it from noise.',
  };
}

// ─── 5. Percentile bootstrap CI ────────────────────────────────────────────
export function bootstrapDerivation(result: BootstrapCIResult): DerivationStep {
  return {
    id: 'bootstrap',
    title: 'Percentile Bootstrap CI (Total & Avg Return)',
    variables: [
      { symbol: 'n', description: 'baseline trades', value: String(result.n) },
      { symbol: 'B', description: 'resamples', value: result.b.toLocaleString() },
      { symbol: '\\hat\\theta(\\text{total})', description: 'point estimate, total return', value: s2(result.totalPoint) + '%' },
      { symbol: '\\hat\\theta(\\text{avg})', description: 'point estimate, avg return/trade', value: s2(result.avgPoint) + '%' },
    ],
    generalFormulaTex: '\\hat\\theta^*_b = f(X_1^*,\\dots,X_n^*),\\; X_i^* \\sim \\text{Uniform}(X_1,\\dots,X_n)',
    substitutedFormulaTex:
      `\\text{Resample } n=${result.n} \\text{ trades with replacement, } B=${result.b.toLocaleString()} \\text{ times; ` +
      'take the [2.5, 97.5] percentiles of the resulting distribution of } f(\\cdot)',
    resultTex: `\\text{Total 95\\% CI} = [${s2(result.totalCI[0])}\\%,\\ ${s2(result.totalCI[1])}\\%], \\quad \\text{Avg 95\\% CI} = [${s2(result.avgCI[0])}\\%,\\ ${s2(result.avgCI[1])}\\%]`,
    prose:
      'Nonparametric percentile bootstrap on the baseline\'s own total and average return -- no distributional ' +
      'assumption about pnl_pct. Uses a seeded mulberry32 PRNG (seed=42) so the resample set, and therefore ' +
      'the CI, is reproducible across renders and machines.',
  };
}

// ─── 6/7. Pearson & Spearman correlation (hold duration vs PnL) ───────────
export function pearsonDerivation(X: number[], Y: number[], result: PearsonResult): DerivationStep {
  const N = X.length;
  const sumX = X.reduce((s, v) => s + v, 0);
  const sumY = Y.reduce((s, v) => s + v, 0);
  const sumXY = X.reduce((s, v, i) => s + v * Y[i], 0);
  const sumX2 = X.reduce((s, v) => s + v * v, 0);
  const sumY2 = Y.reduce((s, v) => s + v * v, 0);
  return {
    id: 'pearson',
    title: 'Pearson Correlation -- Hold Duration vs. PnL',
    variables: [
      { symbol: 'N', description: 'baseline trades', value: String(N) },
      { symbol: '\\sum X', description: 'sum of hold_bars', value: n2(sumX) },
      { symbol: '\\sum Y', description: 'sum of pnl_pct', value: n2(sumY) },
      { symbol: '\\sum XY', description: 'sum of cross products', value: n2(sumXY) },
      { symbol: '\\sum X^2', description: 'sum of hold_bars squared', value: n2(sumX2) },
      { symbol: '\\sum Y^2', description: 'sum of pnl_pct squared', value: n2(sumY2) },
    ],
    generalFormulaTex: 'r = \\dfrac{N\\sum XY - \\sum X \\sum Y}{\\sqrt{[N\\sum X^2-(\\sum X)^2][N\\sum Y^2-(\\sum Y)^2]}}',
    substitutedFormulaTex: `r = \\dfrac{${N}(${n2(sumXY)}) - (${n2(sumX)})(${n2(sumY)})}{\\sqrt{[${N}(${n2(sumX2)})-(${n2(sumX)})^2][${N}(${n2(sumY2)})-(${n2(sumY)})^2]}}`,
    resultTex: `r = ${n4(result.r)}, \\quad t = ${n2(result.t)}, \\quad p = ${n4(result.p)}`,
    prose:
      'X = hold_bars (bars held), Y = pnl_pct (per-trade return). Significance via t = r\\sqrt{(N-2)/(1-r^2)}, ' +
      "Student's t p-value with N-2 degrees of freedom.",
  };
}

export function spearmanDerivation(X: number[], _Y: number[], result: SpearmanResult): DerivationStep {
  return {
    id: 'spearman',
    title: 'Spearman Rank Correlation -- Hold Duration vs. PnL',
    variables: [
      { symbol: 'N', description: 'baseline trades', value: String(X.length) },
      { symbol: '\\rho', description: 'Spearman rank correlation', value: n4(result.rho) },
    ],
    generalFormulaTex: '\\rho = r(\\text{rank}(X), \\text{rank}(Y))',
    substitutedFormulaTex:
      'X, Y \\text{ ranked (average rank on ties), then Pearson\'s } r \\text{ applied to the rank pairs}',
    resultTex: `\\rho = ${n4(result.rho)}, \\quad t = ${n2(result.t)}, \\quad p = ${n4(result.p)}`,
    prose:
      'Rank-based, so robust to the outlier winning trades that dominate the raw Pearson sums above -- each ' +
      'value is replaced by its rank (ties averaged) before applying the same Pearson formula.',
  };
}
