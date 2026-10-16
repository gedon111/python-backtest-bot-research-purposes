# Workstream A1 — Static + live value-trace audit

## A1-3 — Build gates

- `npm run typecheck` (`tsc -b --noEmit`): **PASS**, clean, no output.
- `npm run lint` (oxlint): **PASS with 21 warnings, 0 errors.**
  Breakdown: 16 x `react-hooks(exhaustive-deps)` (memo deps that change
  every render, in StatsTab/SolutionsTab/ChartTab), 1 x
  `react-hooks(exhaustive-deps)` setState-without-deps in `api/hooks.ts:24`,
  1 x `react(only-export-components)` in `theme/ThemeContext.tsx:89`,
  1 x `eslint(no-loss-of-precision)` in `stats/statMath.ts:14`.
  None are errors; none affect a displayed value.

## A1-1/A1-2 — Data-flow trace

Two distinct data paths feed the dashboard, and they are correctly kept
separate (CLAUDE.md's independence rule is upheld — nothing in
`dashboard-v2/src` imports from or reads a Python-computed statistic as its
own source of truth):

| Rendered surface | Fetch (client.ts) | Server route / artifact | Python producer |
|---|---|---|---|
| Chart candles | `getCandles` | `/artifacts/candles.json` | `export_dashboard_artifacts()` §6 |
| Chart full-history toggle | `getCandlesExtended` (lazy) | `/artifacts/candles_extended.json` | committed snapshot |
| Verification badge | `getVerificationReport` | `/artifacts/verification_report.json` | `build_verification_report()` :4510 |
| Manifest / symbol / bars | `getManifest` | `/artifacts/manifest.json` | `build_artifact_manifest()` :4495 |
| Per-threshold OB/trade sets | `getRunsByThreshold` | `/artifacts/runs_by_threshold.json` | `run_quality_sweep()` :1638 |
| All Stats/Solutions statistics | `getTrades(q)` | `/api/trades[?min_ob_quality=N]` (live DB) | `DashboardRequestHandler.handle_get_trades` :4943 |
| Ablation table | `getAblationReconstruction` | `/artifacts/ablation_reconstruction.json` | `run_ablation_study()` :2682 |
| Theme | `getTheme`/`saveTheme` | `/api/get_theme`, `/api/save_theme` | `chart_theme.json` |

Statistics are recomputed in-browser from `/api/trades` by
`stats/statMath.ts` + `stats/statsCompute.ts` + `stats/benchmarkMath.ts`.
`benchmarkMath.ts:1-18` states the independence contract explicitly. Verified:
no `import` in `dashboard-v2/src` pulls a precomputed Python statistic as a
value source; Python figures appear only as labelled comparison strings.

`/api/trades` was verified live: 89 rows, split 27/25/23/14 across
`min_ob_quality` 0/1/2/3 — matching `runs_by_threshold.json` exactly.
`baselineTrades()` (`statsCompute.ts:16-19`) filters to `min_ob_quality===0`,
yielding the 27-trade baseline the whole tab is built on. Correct.

## A1-4 — Live rendered-value verification

Captured from the running dashboard (`http://127.0.0.1:8765/dashboard/`).
The Solutions tab renders its own JS-vs-Python cross-check verdict per
figure; every one below was ALSO independently confirmed against this
audit's own Python recompute (workstream B), so this is a three-way
agreement, not two surfaces agreeing with each other.

| Figure | JS (rendered) | Python (rendered label) | This audit's recompute | Verdict |
|---|---|---|---|---|
| One-sided binomial p | 0.0261 | 0.026 | 0.026119 | MATCH |
| Pearson p | 0.0094 | ~0.0094 | 0.009356 | MATCH |
| Spearman p | 0.0113 | ~0.0113 | 0.011335 | MATCH |
| Strategy total return | +30.31% | +30.31% | +30.3065% | MATCH |
| Strategy final capital | $13,417.77 | $13,417.77 | $13,417.77 | MATCH |
| Strategy Sharpe | 1.114 | 1.114 | 1.1142 | MATCH |
| Strategy MaxDD | -6.46% | -6.46% | -6.4619% | MATCH |
| Strategy time-in-market | 2.63% | 2.63% | 2.6349% | MATCH |
| Strategy fee-adjusted return | +24.91% | +24.91% | +24.9065% | MATCH |
| Strategy fee-adj final capital | $12,719.01 | $12,719.01 | $12,719.01 | MATCH |
| DCA return / capital | +123.13% / $22,312.94 | same | +123.1294% / $22,312.94 | MATCH |
| DCA Sharpe / MaxDD / TIM | 0.556 / -27.85% / 100.00% | same | 0.5559 / -27.8493% / 100% | MATCH |
| Lump-sum return / capital | +90.07% / $19,007.32 | same | +90.0732% / $19,007.32 | MATCH |
| Lump-sum Sharpe / MaxDD / TIM | 0.564 / -67.21% / 100.00% | same | 0.5642 / -67.2139% / 100% | MATCH |
| Bootstrap 95% CI total return | [+7.48%, +54.46%] (B=2,000) | [+5.99%, +54.99%] (B=10,000) | [+5.99%, +54.99%] @B=10,000 | **MISMATCH — pre-disclosed** |

The single MISMATCH is the one CLAUDE.md already documents ("Paper
reporting corrections" #2): the JS surface uses B=2,000 with a mulberry32
PRNG, Python uses B=10,000. The dashboard labels it MISMATCH on-screen and
states both B values — i.e. it is disclosed in the UI, not hidden. Correct
behaviour, no action.

Unit/formatting spot-checks: `pct()`/`spct()`/`snum()`
(`StatsTab.tsx:17-19`) apply `%` and signed prefixes consistently; currency
figures are rendered with `$` and 2dp; p-values at 4dp with a `<0.001`
floor (`StatsTab.tsx:205,212`). No hardcoded statistic was found where a
computed one is claimed — every LIVE-tagged number traces to a
`/api/trades`-derived computation.

Chart tab MIN QUALITY selector (Q0/Q1/Q2/Q3) was cycled; all four renders
differ (distinct PNG hashes), confirming the control actually re-filters
displayed Order Blocks/trades rather than being inert.

## A1 — Findings

### A1-F1 — Stats tab crashes and unmounts the entire dashboard
**Severity: (b) real, does not affect any locked conclusion — but
high-impact: the Stats tab is 100% unusable and takes the whole SPA down
with it.**

Reproduction: load `http://127.0.0.1:8765/dashboard/`, click **STATS**.
Result: `TypeError: Cannot read properties of undefined (reading 'toFixed')`,
`#root` innerHTML drops to 0 bytes (blank black page). There is no error
boundary, so the crash unmounts App, not just the tab. Confirmed
reproducibly in a clean browser context; the other four surfaces (Chart,
Sandbox, Solutions, Settings) render with zero console errors.

Root cause — a schema mismatch between the artifact and its TypeScript type:

- Python writes the locked block as `win_rate_pct` / `total_return_pct`
  (`research_analysis.py:163-164`, `LOCKED_ABLATION_ARMS`), and
  `artifacts/ablation_reconstruction.json` contains exactly
  `"locked": {"n": 140, "win_rate_pct": 60.0, "total_return_pct": -14.63}`.
- The TS type declares the other names:
  `dashboard-v2/src/types/artifacts.ts:227` —
  `locked: { n: number; win_rate: number; total_return: number };`
- `StatsTab.tsx:337-338` therefore reads `arm.locked.win_rate` and
  `arm.locked.total_return`, both `undefined` at runtime, and passes them to
  `pct()` / `spct()` (`StatsTab.tsx:17-18`), which call `.toFixed()` on
  `undefined`.

The stack trace matches exactly: the throw is inside the
`(['flat_atr','swing_pivot'] as const).map(...)` in `AblationSection`
(`StatsTab.tsx:331`). `tsc` cannot catch this because the interface is a
hand-written declaration that was never validated against the emitted JSON.

Note the neighbouring reads are fine: `data.baseline.win_rate` /
`.total_return` (`StatsTab.tsx:327-328`) and `arm.reconstructed.win_rate` /
`.total_return` (`:342-343`) DO match the JSON, which is produced by
`summarize_trade_pool()` (`research_analysis.py:2612-2616`) with those exact
key names. Only the `locked` sub-object diverges.

**Reported, not fixed** (per this audit's report-only scope).

### A1-F2 — Comment references to files retired by the consolidation
**Severity: (a) cosmetic — comments only, no runtime effect.**
53 comment references across 16 files in `dashboard-v2/src` still cite paths
retired by the 2026-08-13/14 single-file consolidation:
`export_gui_data.py` (7), `db_manager.py` (1), `analysis/*.py` (14),
`src/Binance backtest bot.py` (1), and `gui.js` (30, the dashboard-v1
frontend). Representative: `api/client.ts:20,38,56`,
`stats/benchmarkMath.ts:3-4,14,16`, `types/artifacts.ts:5,121,126-127`,
`chart/obQualityVerification.ts:13`. For a codebase whose stated priority is
auditability, these comments are the provenance trail a reviewer follows, so
they are worth correcting — but nothing executes them. Reported, not fixed.

### A1-F3 — Server exposes the whole repository over HTTP
**Severity: (b) real, no effect on any figure.**
`DashboardRequestHandler.translate_path` (`research_analysis.py:4910-4924`)
special-cases `/dashboard/` and `/api/*`, then falls through to
`SimpleHTTPRequestHandler`'s default, which serves the process CWD — the
repo root — with directory listings enabled. Verified live: `GET /` returns
a browsable index including `.git/`, `.env.example`, and `SERVICE KEY/`
(the Google service-account key directory). Mitigating: the default bind is
`127.0.0.1` (`run_dashboard_server`, `:5120-5121`), so a native run is
loopback-only. Not mitigating: the shipped `Dockerfile` sets
`DASHBOARD_HOST=0.0.0.0` (documented at `:5113-5115`), so a containerised
run exposes the same listing on every interface the container publishes.
Reported, not fixed.
