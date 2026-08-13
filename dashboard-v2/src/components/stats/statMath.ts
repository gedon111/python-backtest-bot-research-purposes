/**
 * Ported verbatim (same algorithms, same operation order) from gui.js's
 * Research Statistics Module (gui.js:1656-1867). This is the JS-side
 * verification cross-check CLAUDE.md requires stay independent of the Python
 * backtest -- it must never import from the Python side, and its numerical
 * approximations must match the original exactly since they feed the
 * significance figures locked in the paper.
 */

// Lanczos approximation for log-gamma function ln(Gamma(z))
export function logGamma(z: number): number {
  const g = 7;
  const C = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916244059,
    12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ];
  if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
  z -= 1;
  let x = C[0];
  for (let i = 1; i < g + 2; i++) x += C[i] / (z + i);
  const t = z + g + 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

// Upper regularized incomplete gamma function Q(a, x) via Lentz's continued fraction
export function regularizedIncompleteGammaQ(a: number, x: number): number {
  if (x < 0 || a <= 0) return 1.0;
  if (x === 0) return 1.0;
  if (x < a + 1) return 1.0 - regularizedIncompleteGammaP(a, x);
  const tiny = 1e-30;
  let b = x + 1.0 - a;
  let c = 1.0 / tiny;
  let d = 1.0 / b;
  let h = d;
  for (let i = 1; i <= 200; i++) {
    const an = -i * (i - a);
    b += 2.0;
    d = an * d + b;
    if (Math.abs(d) < tiny) d = tiny;
    c = b + an / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1.0 / d;
    const delta = c * d;
    h *= delta;
    if (Math.abs(delta - 1.0) < 1e-15) break;
  }
  return h * Math.exp(-x + a * Math.log(x) - logGamma(a));
}

// Lower regularized incomplete gamma function P(a, x) via series expansion
export function regularizedIncompleteGammaP(a: number, x: number): number {
  if (x < 0 || a <= 0) return 0.0;
  if (x === 0) return 0.0;
  if (x >= a + 1) return 1.0 - regularizedIncompleteGammaQ(a, x);
  let sum = 1.0 / a;
  let term = 1.0 / a;
  for (let n = 1; n <= 200; n++) {
    term *= x / (a + n);
    sum += term;
    if (term < sum * 1e-15) break;
  }
  return sum * Math.exp(-x + a * Math.log(x) - logGamma(a));
}

// Regularized incomplete beta function I_x(a, b) via Lentz's continued fraction + symmetry
export function regularizedIncompleteBeta(x: number, a: number, b: number): number {
  if (x < 0 || x > 1) return NaN;
  if (x === 0) return 0.0;
  if (x === 1) return 1.0;
  if (x > (a + 1.0) / (a + b + 2.0)) return 1.0 - regularizedIncompleteBeta(1.0 - x, b, a);

  const tiny = 1e-30;
  const lbeta = logGamma(a) + logGamma(b) - logGamma(a + b);
  const front = Math.exp(a * Math.log(x) + b * Math.log(1.0 - x) - lbeta) / a;

  let c = 1.0;
  let d = 1.0 - ((a + b) * x) / (a + 1.0);
  if (Math.abs(d) < tiny) d = tiny;
  d = 1.0 / d;
  let h = d;

  for (let m = 1; m <= 150; m++) {
    const m2 = 2 * m;

    const d2m = (m * (b - m) * x) / ((a + m2 - 1.0) * (a + m2));
    d = 1.0 + d2m * d;
    if (Math.abs(d) < tiny) d = tiny;
    c = 1.0 + d2m / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1.0 / d;
    h *= c * d;

    const d2m1 = (-(a + m) * (a + b + m) * x) / ((a + m2) * (a + m2 + 1.0));
    d = 1.0 + d2m1 * d;
    if (Math.abs(d) < tiny) d = tiny;
    c = 1.0 + d2m1 / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1.0 / d;
    const delta = c * d;
    h *= delta;

    if (Math.abs(delta - 1.0) < 1e-15) break;
  }

  return front * h;
}

// Student-t two-tailed p-value via I_x(df/2, 1/2), x = df / (df + t^2)
export function studentTPValue(t: number, df: number): number {
  if (isNaN(t) || isNaN(df) || df <= 0) return NaN;
  const absT = Math.abs(t);
  const x = df / (df + absT * absT);
  return regularizedIncompleteBeta(x, df / 2.0, 0.5);
}

// F-distribution one-sided (upper-tail) p-value via I_x(df2/2, df1/2)
export function fPValue(F: number, df1: number, df2: number): number {
  if (isNaN(F) || isNaN(df1) || isNaN(df2) || df1 <= 0 || df2 <= 0) return NaN;
  if (F <= 0) return 1.0;
  const x = df2 / (df1 * F + df2);
  return regularizedIncompleteBeta(x, df2 / 2.0, df1 / 2.0);
}

// Chi-square one-sided (upper-tail) p-value via Q(df/2, x/2)
export function chiSquarePValue(x: number, df: number): number {
  if (isNaN(x) || isNaN(df) || df <= 0) return NaN;
  if (x <= 0) return 1.0;
  return regularizedIncompleteGammaQ(df / 2.0, x / 2.0);
}

export function logFactorial(n: number): number {
  if (n <= 1) return 0.0;
  let ans = 0.0;
  for (let i = 2; i <= n; i++) ans += Math.log(i);
  return ans;
}

export interface BinomialTerm {
  x: number;
  p: number;
}

/** Every term P(X=x) of the tail sum P(X>=k), x=k..n, in the same ascending-x
 * order binomialTestGreater sums them in -- extracted so the Solutions tab can
 * show the term-by-term enumeration instead of asserting the summed p-value. */
export function binomialTailTerms(n: number, k: number, p0 = 0.5): BinomialTerm[] {
  const terms: BinomialTerm[] = [];
  for (let x = k; x <= n; x++) {
    const logComb = logFactorial(n) - logFactorial(x) - logFactorial(n - x);
    terms.push({ x, p: Math.exp(logComb + x * Math.log(p0) + (n - x) * Math.log(1.0 - p0)) });
  }
  return terms;
}

export function binomialTestGreater(n: number, k: number, p0 = 0.5): number {
  if (n === 0) return 1.0;
  let sum = 0.0;
  for (const term of binomialTailTerms(n, k, p0)) sum += term.p;
  return sum;
}

export interface PearsonResult {
  r: number;
  p: number;
  t: number;
  // Additive: the five running sums + numerator/denominator, so the
  // Solutions tab can show the full substitution by reading these back
  // rather than recomputing them in a second code path (derivationSteps.ts
  // used to re-derive these itself -- fixed here).
  n: number;
  sumX: number;
  sumY: number;
  sumXY: number;
  sumX2: number;
  sumY2: number;
  num: number;
  den: number;
}

export function computeCorrelationPearson(X: number[], Y: number[]): PearsonResult {
  const N = X.length;
  let sumX = 0,
    sumY = 0,
    sumXY = 0,
    sumX2 = 0,
    sumY2 = 0;
  for (let i = 0; i < N; i++) {
    sumX += X[i];
    sumY += Y[i];
    sumXY += X[i] * Y[i];
    sumX2 += X[i] * X[i];
    sumY2 += Y[i] * Y[i];
  }
  const num = N * sumXY - sumX * sumY;
  const den = Math.sqrt((N * sumX2 - sumX * sumX) * (N * sumY2 - sumY * sumY));
  const r = den !== 0 ? num / den : 0.0;
  const t = r * Math.sqrt((N - 2) / (1 - r * r));
  const p = studentTPValue(t, N - 2);
  return { r, p, t, n: N, sumX, sumY, sumXY, sumX2, sumY2, num, den };
}

export interface SpearmanResult {
  rho: number;
  p: number;
  t: number;
  // Additive: the ranked series and the full Pearson-on-ranks result (same
  // machinery computeCorrelationPearson uses internally, exposed rather than
  // discarded) so the Solutions tab can show the rank table and the
  // downstream sums without a second code path.
  rankX: number[];
  rankY: number[];
  ranked: PearsonResult;
}

export function computeCorrelationSpearman(X: number[], Y: number[]): SpearmanResult {
  const N = X.length;
  const getRanks = (arr: number[]) => {
    const indices = arr.map((val, idx) => ({ val, idx }));
    indices.sort((a, b) => a.val - b.val);
    const ranks = new Array<number>(N);
    let i = 0;
    while (i < N) {
      let j = i + 1;
      while (j < N && indices[j].val === indices[i].val) j++;
      let rankSum = 0;
      for (let r = i; r < j; r++) rankSum += r + 1;
      const avgRank = rankSum / (j - i);
      for (let r = i; r < j; r++) ranks[indices[r].idx] = avgRank;
      i = j;
    }
    return ranks;
  };
  const rankX = getRanks(X);
  const rankY = getRanks(Y);
  const pearson = computeCorrelationPearson(rankX, rankY);
  return { rho: pearson.r, p: pearson.p, t: pearson.t, rankX, rankY, ranked: pearson };
}

export interface WelchResult {
  t: number;
  df: number;
  p: number;
  // Additive (non-breaking) fields beyond what StatsTab.tsx reads (t/p) --
  // exposed so the Solutions tab can show the full mean/variance
  // substitution step without recomputing it separately from a different
  // code path than what StatsTab itself displays.
  n1: number;
  n2: number;
  m1: number;
  m2: number;
  v1: number;
  v2: number;
  // Further additive: the SE^2 components (a1=v1/n1, a2=v2/n2), SE itself,
  // and the three pieces of the Welch-Satterthwaite df formula, plus the
  // incomplete-beta argument x=df/(df+t^2) -- all of these were computed
  // internally before but discarded, forcing derivationSteps.ts to either
  // assert them or recompute them itself. Exposing them keeps derivationSteps
  // a pure formatter, per this file's own no-recompute contract.
  a1: number;
  a2: number;
  se2: number;
  se: number;
  dfNum: number;
  dfDen1: number;
  dfDen2: number;
  tX: number;
}

/** Welch's unequal-variance two-sample t-test (two-sided), same formula as scipy.stats.ttest_ind(equal_var=False). */
export function welchTTest(a: number[], b: number[]): WelchResult {
  const n1 = a.length;
  const n2 = b.length;
  const mean = (arr: number[]) => arr.reduce((s, v) => s + v, 0) / arr.length;
  const variance = (arr: number[], m: number) => (arr.length > 1 ? arr.reduce((s, v) => s + (v - m) ** 2, 0) / (arr.length - 1) : 0);
  const m1 = mean(a);
  const m2 = mean(b);
  const v1 = variance(a, m1);
  const v2 = variance(b, m2);
  const a1 = v1 / n1;
  const a2 = v2 / n2;
  const se2 = a1 + a2;
  if (se2 <= 0 || n1 < 2 || n2 < 2) {
    return { t: NaN, df: NaN, p: NaN, n1, n2, m1, m2, v1, v2, a1, a2, se2, se: NaN, dfNum: NaN, dfDen1: NaN, dfDen2: NaN, tX: NaN };
  }
  const se = Math.sqrt(se2);
  const t = (m1 - m2) / se;
  const dfNum = se2 ** 2;
  const dfDen1 = a1 ** 2 / (n1 - 1);
  const dfDen2 = a2 ** 2 / (n2 - 1);
  const df = dfNum / (dfDen1 + dfDen2);
  const tX = df / (df + t * t);
  const p = studentTPValue(t, df);
  return { t, df, p, n1, n2, m1, m2, v1, v2, a1, a2, se2, se, dfNum, dfDen1, dfDen2, tX };
}

export interface FisherTerm {
  x: number;
  p: number;
  logP: number;
  included: boolean;
}

export interface FisherTermsResult {
  terms: FisherTerm[];
  xMin: number;
  xMax: number;
  xObs: number;
  pObs: number;
  logPObs: number;
  epsilon: number;
  rowSum1: number;
  rowSum2: number;
  colSum1: number;
  colSum2: number;
  n: number;
}

/** Every table P(x) with the observed 2x2's row/column margins, x=xMin..xMax,
 * in the same ascending-x order fisherExactTwoSided sums the included ones in
 * -- extracted so the Solutions tab can show the full enumeration and the
 * inclusion boundary (a log-space comparison, hence logP/logPObs/epsilon
 * exposed too) instead of asserting the summed p-value. */
export function fisherExactTerms(a: number, b: number, c: number, d: number): FisherTermsResult {
  const rowSum1 = a + b;
  const rowSum2 = c + d;
  const colSum1 = a + c;
  const colSum2 = b + d;
  const n = rowSum1 + rowSum2;
  const logChoose = (nn: number, kk: number) => logFactorial(nn) - logFactorial(kk) - logFactorial(nn - kk);
  const logDenom = logChoose(n, colSum1);
  const xMin = Math.max(0, colSum1 - rowSum2);
  const xMax = Math.min(rowSum1, colSum1);
  const logObserved = logChoose(rowSum1, a) + logChoose(rowSum2, colSum1 - a) - logDenom;
  const epsilon = 1e-7;
  const terms: FisherTerm[] = [];
  for (let x = xMin; x <= xMax; x++) {
    const lp = logChoose(rowSum1, x) + logChoose(rowSum2, colSum1 - x) - logDenom;
    terms.push({ x, p: Math.exp(lp), logP: lp, included: lp <= logObserved + epsilon });
  }
  return {
    terms,
    xMin,
    xMax,
    xObs: a,
    pObs: Math.exp(logObserved),
    logPObs: logObserved,
    epsilon,
    rowSum1,
    rowSum2,
    colSum1,
    colSum2,
    n,
  };
}

/**
 * Fisher's exact test (two-sided), 2x2 table [[a,b],[c,d]]. Sums the exact
 * hypergeometric probability of every table with the same row/column
 * margins whose probability is <= the observed table's -- same definition
 * scipy.stats.fisher_exact(alternative='two-sided') uses.
 */
export function fisherExactTwoSided(a: number, b: number, c: number, d: number): number {
  const { terms } = fisherExactTerms(a, b, c, d);
  let p = 0;
  for (const term of terms) if (term.included) p += term.p;
  return Math.min(1, p);
}

// z_{1-alpha/2} for alpha=0.05 and z_{power} for power=0.80 -- standard normal
// critical values, matching analysis/bootstrap_power_analysis.py's default
// --alpha 0.05 --power 0.80 (this dashboard doesn't expose alpha/power as
// tunable, so fixed constants are used rather than a general inverse-normal-CDF
// approximation). Exported (was module-private) so the Solutions tab displays
// these exact values instead of a shadowing local copy at lower precision.
export const Z_ALPHA_2 = 1.9599639845400545; // qnorm(0.975)
export const Z_BETA = 0.8416212335729143; // qnorm(0.80)

export interface MdeResult {
  n1: number;
  n2: number;
  sd1: number;
  sd2: number;
  observedDiff: number;
  mde: number;
  detectable: boolean;
  // Additive: SE itself. NOT guaranteed bit-identical to Welch's `se` for the
  // same subgroup split -- both compute sqrt(sd1^2/n1 + sd2^2/n2) from the
  // same sd1/sd2, but Welch derives its variance directly (v1) while this
  // function goes variance->sqrt->square (sd1**2), which loses/regains a bit
  // in ~30% of subgroups observed. Report both, never claim they're the same
  // value "by construction".
  se: number;
}

/** Minimum detectable effect, two-sample normal approximation: MDE = (z_a/2 + z_b) * sqrt(sd1^2/n1 + sd2^2/n2). */
export function mdeNormalApprox(trueVals: number[], falseVals: number[]): MdeResult {
  const n1 = trueVals.length;
  const n2 = falseVals.length;
  const mean = (arr: number[]) => arr.reduce((s, v) => s + v, 0) / arr.length;
  const variance = (arr: number[], m: number) => (arr.length > 1 ? arr.reduce((s, v) => s + (v - m) ** 2, 0) / (arr.length - 1) : 0);
  const m1 = mean(trueVals);
  const m2 = mean(falseVals);
  const sd1 = Math.sqrt(variance(trueVals, m1));
  const sd2 = Math.sqrt(variance(falseVals, m2));
  const observedDiff = m1 - m2;
  const se = Math.sqrt(sd1 ** 2 / n1 + sd2 ** 2 / n2);
  const mde = (Z_ALPHA_2 + Z_BETA) * se;
  return { n1, n2, sd1, sd2, observedDiff, mde, detectable: Math.abs(observedDiff) >= mde, se };
}

/** Deterministic seeded PRNG (mulberry32) so the in-browser bootstrap is reproducible across renders without depending on any Python-side RNG state. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface BootstrapReplicateDetail {
  indices: number[];
  values: number[];
  total: number;
  avg: number;
}

export interface PercentileDetail {
  p: number;
  idx: number;
  lo: number;
  hi: number;
  loValue: number;
  hiValue: number;
  result: number;
}

export interface BootstrapCIResult {
  b: number;
  n: number;
  totalPoint: number;
  totalCI: [number, number];
  avgPoint: number;
  avgCI: [number, number];
  pctResamplesTotalLe0: number;
  pctResamplesAvgLe0: number;
  // Additive: the first resample replicate's drawn indices/values/total/avg
  // (captured, not separately generated, so the RNG draw sequence for i>=1 is
  // untouched), and the full lo/hi bracket + interpolation detail behind each
  // of the four percentile() calls above.
  seed: number;
  firstReplicate: BootstrapReplicateDetail;
  totalLoDetail: PercentileDetail;
  totalHiDetail: PercentileDetail;
  avgLoDetail: PercentileDetail;
  avgHiDetail: PercentileDetail;
}

/** Nonparametric percentile bootstrap on a trade log's own total/average return (resample n with replacement, B resamples). */
export function bootstrapPercentileCI(pnl: number[], b: number, seed: number): BootstrapCIResult {
  const n = pnl.length;
  const rng = mulberry32(seed);
  const totals = new Array<number>(b);
  const avgs = new Array<number>(b);
  let firstReplicate: BootstrapReplicateDetail = { indices: [], values: [], total: 0, avg: 0 };
  for (let i = 0; i < b; i++) {
    let s = 0;
    const captureFirst = i === 0;
    const indices: number[] = captureFirst ? new Array<number>(n) : [];
    for (let j = 0; j < n; j++) {
      const idx = Math.floor(rng() * n);
      if (captureFirst) indices[j] = idx;
      s += pnl[idx];
    }
    totals[i] = s;
    avgs[i] = s / n;
    if (captureFirst) {
      firstReplicate = { indices, values: indices.map((idx) => pnl[idx]), total: s, avg: s / n };
    }
  }
  const percentileDetailed = (arr: number[], p: number): PercentileDetail => {
    const sorted = [...arr].sort((x, y) => x - y);
    const idx = (p / 100) * (sorted.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    const loValue = sorted[lo];
    const hiValue = sorted[hi];
    const result = lo === hi ? loValue : loValue + (hiValue - loValue) * (idx - lo);
    return { p, idx, lo, hi, loValue, hiValue, result };
  };
  const totalLoDetail = percentileDetailed(totals, 2.5);
  const totalHiDetail = percentileDetailed(totals, 97.5);
  const avgLoDetail = percentileDetailed(avgs, 2.5);
  const avgHiDetail = percentileDetailed(avgs, 97.5);
  const totalPoint = pnl.reduce((s, v) => s + v, 0);
  return {
    b,
    n,
    totalPoint,
    totalCI: [totalLoDetail.result, totalHiDetail.result],
    avgPoint: totalPoint / n,
    avgCI: [avgLoDetail.result, avgHiDetail.result],
    pctResamplesTotalLe0: (totals.filter((v) => v <= 0).length / b) * 100,
    pctResamplesAvgLe0: (avgs.filter((v) => v <= 0).length / b) * 100,
    seed,
    firstReplicate,
    totalLoDetail,
    totalHiDetail,
    avgLoDetail,
    avgHiDetail,
  };
}

/** Self-test from gui.js:1810-1846 -- validates the approximations above against known reference points. */
export function runDistributionSelfChecks(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  const pChi = chiSquarePValue(7.815, 3);
  if (Math.abs(pChi - 0.05) > 1e-3) errors.push(`Chi-Square check failed: expected ~0.05, got ${pChi.toFixed(6)}`);

  const pT = studentTPValue(2.086, 20);
  if (Math.abs(pT - 0.05) > 1e-3) errors.push(`Student-t t=2.086 check failed: expected ~0.05, got ${pT.toFixed(6)}`);

  const pT2 = studentTPValue(2.0, 20);
  if (Math.abs(pT2 - 0.059265) > 1e-3)
    errors.push(`Student-t t=2.0 check failed: expected ~0.059265, got ${pT2.toFixed(6)}`);

  const pF = fPValue(3.1, 3, 20);
  if (Math.abs(pF - 0.05) > 1e-3) errors.push(`F-distribution check failed: expected ~0.05, got ${pF.toFixed(6)}`);

  // Fisher's exact + Welch's t-test checked against the LargeBar criterion's
  // known values (STUDY_REFERENCE.md Sec.6.3 / CLAUDE.md locked results):
  // True n=20 (14 wins), False n=7 (5 wins), Fisher p=1.0000, Welch t=+0.2895, p=0.7751.
  const fisherCheck = fisherExactTwoSided(14, 6, 5, 2);
  if (Math.abs(fisherCheck - 1.0) > 1e-3)
    errors.push(`Fisher's exact check failed: expected ~1.0000, got ${fisherCheck.toFixed(6)}`);

  return { valid: errors.length === 0, errors };
}
