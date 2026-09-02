# Full Codebase Audit — 2026-08-20

Scope: every number the dashboard displays traced to its source and verified;
the backend/statistics pipeline re-verified against CLAUDE.md's locked
results by independent recomputation; and a cleanup-candidate inventory of
`docs/`, `scratch/`, and `artifacts/`.

**Report-only. Nothing was fixed, deleted, or moved.** Branch: `development`.
Plan of record: `PLAN.md`.

## Executive summary

- **Regression harness: PASS.** `scratch/regression.py` reports an exact
  match against the golden-master fixtures across all bars, indicators, and
  all 27 baseline trades. Run read-only; `--generate` never invoked.
- **Every locked figure reproduced.** All 20 headline figures — trade count,
  win rate, total/avg return, SD, both binomial p-values, the q>=1
  significance flip, 761 OBs, the FVG count, the full OB quality
  distribution, and all 14 benchmark-vs-passive figures across both windows,
  gross and fee-adjusted — were independently recomputed and matched.
- **The dashboard's live JS re-derivations agree with Python** on every
  cross-checked figure, and with this audit's own third recomputation. The
  single on-screen MISMATCH (bootstrap CI) is the pre-disclosed
  B=2,000-vs-B=10,000 gap, correctly labelled in the UI.
- **Typecheck clean; lint clean** (0 errors, 21 warnings).
- **One new, previously unreported bug: the Stats tab crashes and unmounts
  the entire dashboard** (A1-F1). Severity (b) — it corrupts no figure, but
  the tab is 100% unusable. Root cause is a field-name mismatch between
  `artifacts/ablation_reconstruction.json` and its hand-written TypeScript
  interface.
- **No new correctness bug was found in the backend or statistics
  pipeline.** The CLAUDE.md "THIRD bug — STOP and report" rule is therefore
  not triggered: the one new defect is a frontend rendering bug that changes
  no claim the paper makes. Both previously disclosed engine bugs are still
  correctly fixed in current code, with their no-lookahead assertions live.
- **Two pre-disclosed divergences were re-confirmed as pre-disclosed**, not
  rediscovered as new: the Ablation A/B reconstruction gap, and the
  bootstrap-CI B mismatch.
- **Cleanup candidates:** 4 self-labelled superseded docs, 1 broken scratch
  script (`run_export_offline.py`, imports a retired module), 12 finished
  one-off scripts, and 7 orphaned artifacts (~16 MB, of which
  `export_candles_for_gsheet.json` alone is 15 MB).

### New findings at a glance

| ID | Finding | Severity |
|---|---|---|
| A1-F1 | Stats tab throws `TypeError` and unmounts the whole SPA | (b) real, high-impact |
| A1-F2 | 53 comment references to files retired by the consolidation | (a) cosmetic |
| A1-F3 | HTTP server directory-lists the whole repo, incl. `SERVICE KEY/` | (b) real |
| B6-2 | `manifest.json` start/end are requested args, not realised bounds | (a) cosmetic |

### Pre-disclosed, re-confirmed (NOT new findings)

| ID | Item | Status |
|---|---|---|
| B6-1 | Ablation A/B win rate diverges from locked figures | disclosed in `research_analysis.py` §4, printed at runtime, stored as `"DIVERGE"` in the artifact |
| A1-4 | Bootstrap CI JS [+7.48%, +54.46%] vs Python [+5.99%, +54.99%] | disclosed in CLAUDE.md; labelled MISMATCH on-screen with both B values shown |
| C4 | Welch p-range "0.38–0.90" should read "0.38–0.78" | still PENDING in the paper, exactly as CLAUDE.md states; independently confirmed here as 0.3775–0.7751 |

---

# Part 1 — Dashboard value trace (A1)


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
| Strategy Sortino | 2.727 | 2.727 | 2.7273 | MATCH |
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

---

# Part 2 — Dashboard screenshots (A2)


Step 0 (Playwright install) **succeeded**, but not on the first attempt:
`npm install -g playwright` + `npx playwright install chromium` completed
(exit 0), yet a global install is not resolvable from an ESM `import` in a
scratch script (`ERR_MODULE_NOT_FOUND`). Resolved with the plan's one
permitted retry: a local `npm install playwright` in the scratchpad. Smoke
test then passed — Chromium launched, `about:blank` screenshotted, PNG
written (`PLAYWRIGHT_OK`, 4,254 bytes).

Stack: `python research_analysis.py --serve --no-browser --levels 0,1,2,3`
on `:8765`. Note the dashboard is served at **`/dashboard/`**, not `/`
(`translate_path`, `research_analysis.py:4910-4913`); `/` returns a
directory listing (see A1-F3).

Each capture used a **fresh browser context and page load**, so a crash on
one tab could not suppress the others.

Screenshot directory:
`C:\Users\Gideon\AppData\Local\Temp\claude\E--PROGRAMMING-git-projects-Binance-Backtest-Bot-Package--compliance-ver-\70595acf-ec73-4f7a-a5c6-d3ce87dd9180\scratchpad\shots\`

| File | Tab / state | Rendered | Console errors |
|---|---|---|---|
| `01_chart_default.png` | Chart (default, Q0) | YES | 0 |
| `02_sandbox.png` | Sandbox | YES | 0 |
| `03_stats.png` | Stats | **NO — React tree unmounted, blank page** | 1 (`TypeError ... 'toFixed'`) |
| `04_solutions.png` | Solutions | YES | 0 |
| `05_settings.png` | Settings panel (over Chart) | YES | 0 |
| `06_chart_Q0.png` | Chart, MIN QUALITY = Q0 (baseline) | YES | 0 |
| `06_chart_Q1.png` | Chart, MIN QUALITY = Q1 | YES | 0 |
| `06_chart_Q2.png` | Chart, MIN QUALITY = Q2 | YES | 0 |
| `06_chart_Q3.png` | Chart, MIN QUALITY = Q3 | YES | 0 |

Alongside each PNG, the page's full `innerText` was saved as `<name>.txt`
for A1's value trace; `_index.txt` holds the table above verbatim.

The four Q-threshold captures have four distinct MD5 hashes
(`f83f6ecc…`, `f374a17a…`, `81bf4ed6…`, `da2d1a28…`), confirming the
selector re-renders real data rather than being inert.

`03_stats.png` is a genuine capture of the failure state (a blank black
page), not a missing screenshot — see A1-F1 for the root cause. All other
controls exercised on the Chart tab (LEVEL, STRUCTURE, OB ZONES, OB FILTER,
TRADE ZONES, AUTO FIT, FULL HISTORY) rendered without error.

---

# Part 3 — Backend / statistics re-verification (B)


Method note (scope, stated honestly): the strategy ENGINE
(`compute_indicators` / `compute_smc` / `simulate_trades`) was not
re-implemented from scratch — it is validated independently by
`scratch/regression.py` against golden-master fixtures. What IS
independently recomputed below is the whole DOWNSTREAM STATISTICS LAYER:
every summary statistic, significance test, risk ratio and benchmark arm
was recomputed from raw trade-level / bar-level output using scipy/numpy
primitives written for this audit, NOT by calling `research_analysis.py`'s
own stats functions. Raw output: `scratch/audit_B_recompute.md`.

Anchoring caveat: CLAUDE.md's locked-results block is loaded into this
session's context automatically (project instructions), so a literally
"blind" recompute was not achievable. Mitigation: the recompute script
contains no expected values and no reference to the locked figures; it
emits whatever it computes, and the diff was performed only afterwards.

## B1 — Regression harness

**PASS.** `python scratch/regression.py` -> "Fresh run matches golden-master
fixture EXACTLY across all bars, indicators, and 27 trades!" (exit 0). Run
read-only; `--generate` never invoked.

## B2/B3 — Recomputed vs locked, figure by figure

| Figure | Locked (CLAUDE.md) | Independently recomputed | Verdict |
|---|---|---|---|
| Dataset bars | 8,767 | 8,767 (2022-01-01 08:00 -> 2026-01-01 08:00) | MATCH |
| Baseline trades | 27 | 27 (19 wins) | MATCH |
| Baseline win rate | 70.37% | 70.3704% | MATCH |
| Baseline total net return | +30.31% | +30.3065% | MATCH |
| Baseline avg return/trade | +1.12% | +1.1225% | MATCH |
| Baseline SD | 2.41% | 2.4101% (ddof=1) | MATCH |
| Binomial one-sided p (q>=0) | 0.026 | 0.026119 | MATCH |
| Binomial two-sided p (q>=0) | 0.052 | 0.052239 | MATCH |
| q>=1 trades (post-fix) | 25 | 25 (17 wins, 68.00%) | MATCH |
| q>=1 one-sided p (post-fix) | 0.054 | 0.053876 | MATCH |
| Order Blocks detected | 761 | 761 | MATCH |
| FVG criterion true | 253 (33.2%) | 253 (33.2%) | MATCH |
| Displacement criterion true | 107 | 107 | MATCH |
| OB quality distribution | 93/154/206/197/90/21 | 93/154/206/197/90/21 | MATCH |
| Ablation A (flat-ATR) N | 140 | 140 | MATCH |
| Ablation A win rate | 60.00% | 47.14% (66/140) | **DIVERGE — pre-disclosed, see B6-1** |
| Ablation A total return | -14.63% | -13.72% | **DIVERGE — pre-disclosed** |
| Ablation B (swing-pivot) N | 138 | 138 | MATCH |
| Ablation B win rate | 55.07% | 43.48% (60/138) | **DIVERGE — pre-disclosed** |
| Ablation B total return | -25.50% | -23.85% | **DIVERGE — pre-disclosed** |

### Benchmark vs passive — 2022-2026 window (gross, $10,000)

| Arm | Locked | Recomputed | Verdict |
|---|---|---|---|
| Strategy return / final | +30.31% / $13,417.77 | +30.3065% / $13,417.77 | MATCH |
| Strategy Sharpe / Sortino / MaxDD | 1.114 / 2.727 / -6.46% | 1.1142 / 2.7273 / -6.4619% | MATCH |
| Strategy time-in-market | 2.63% | 2.6349% | MATCH |
| DCA return / final | +123.13% / $22,312.94 | +123.1294% / $22,312.94 | MATCH |
| DCA Sharpe / MaxDD | 0.556 / -27.85% | 0.5559 / -27.8493% | MATCH |
| Lump-sum return / final | +90.07% / $19,007.32 | +90.0732% / $19,007.32 | MATCH |
| Lump-sum Sharpe / MaxDD | 0.564 / -67.21% | 0.5642 / -67.2139% | MATCH |
| Fee-adjusted strategy | +24.91% / $12,719.01 | +24.9065% / $12,719.01 | MATCH |

### Benchmark vs passive — 2018-2022 formulation window (NOT out-of-sample)

| Arm | Locked | Recomputed | Verdict |
|---|---|---|---|
| Strategy | +21.82% / $12,282.53 | +21.8246% / $12,282.53 | MATCH |
| DCA | +439.88% / $53,987.55 | +439.8755% / $53,987.55 | MATCH |
| Lump-sum | +236.96% / $33,696.49 | +236.9649% / $33,696.49 | MATCH |

### Other statistics independently reproduced

- Pearson (hold_bars vs pnl_pct, n=27): r=+0.4907, t=2.8158, df=25,
  p=0.009356 -> confirms CLAUDE.md's "Paper reporting corrections" #1
  (p~=0.0094, NOT "p<0.001"). MATCH.
- Spearman: rho=+0.4797, p=0.011335 -> confirms p~=0.0113. MATCH.
- Bootstrap CI on total return (B=10,000, seed=42): recomputed
  [+5.99%, +54.99%]; artifact reports [+5.9866%, +54.9866%]. MATCH
  (the paper's canonical Python figure).
- Welch's t-test across the 5 orthogonal criteria: p = 0.3775
  (Displacement), 0.7751 (LargeBar), 0.5996 (FVG), 0.4204 (LiqSweep),
  0.3864 (VolExpansion). Range **0.38–0.78**, max = LargeBar. This
  independently confirms the still-PENDING paper correction noted in
  CLAUDE.md Known bugs #3 (the narrative should read "0.38-0.78", not
  "0.38-0.90"). Still pending in the paper — not actioned here.

## B4 — Artifact self-consistency

**PASS, all checks.** Recomputing `build_verification_report()` from the
committed `manifest.json` + `candles.json` + `runs_by_threshold.json`
reproduces every stored hash byte-identically:

- `snapshot_hashes.ohlc_hash`, `snapshot_hashes.indicator_hash` — OK
- levels 0/1/2/3 x `orderblocks_hash` / `trades_hash` / `stats_hash` — 12/12 OK
- all 5 `source_checks` fields — OK
- `manifest.candle_count` 8,767 == `len(candles.json)` 8,767 — OK
- `orderblocks_default_view.csv` 761 rows == per-level `obs` count 761 — OK
- `trades_default_view.csv` 25 rows == level-1 trade count 25 — OK
  (consistent: the exported "default view" is `default_view_quality=1`,
  i.e. the q>=1 view, NOT the 27-trade q>=0 baseline — by design, but see
  the C-stream note)
- `kdj_exit_window` column present in `trades_default_view.csv` — confirms
  the working-tree schema addition described in the plan's context section;
  a changed `trades_hash` with an unchanged `stats_hash` is explained by it.

Per-level stats read back from `runs_by_threshold.json`:
q0 = 27 trades / 70.370% / +30.306%; q1 = 25 / 68.000% / +28.307%;
q2 = 23 / 65.217% / +23.276%; q3 = 14 / 57.143% / +6.593%.

### B4b — Cross-run determinism (added after a second full pipeline run)

`python research_analysis.py --serve --no-browser --levels 0,1,2,3` was run
during this audit, regenerating `artifacts/`. Re-running the self-consistency
check afterwards still gives **PASS, 14/14 hashes**, and the regenerated
level-0 stats are bit-identical (27 / 70.37037037037037% /
30.306456356031937%). The only field that moved between the pre-run and
post-run artifact set is `manifest.generated_at_utc`. The pipeline is
therefore deterministic across runs.

Diffing the regenerated set against `HEAD` isolates the change to exactly
four `trades_hash` values (levels 0/1/2/3) with `ohlc_hash`,
`indicator_hash`, all four `orderblocks_hash` and all four `stats_hash`
unchanged — precisely the signature of the `kdj_exit_window` export-column
addition described in the plan's context section, and confirmation that no
computed statistic moved with it.

## B5 — Disclosed-bug fixes still present (spot-check, not re-litigated)

- Bug #2 (FVG 3-candle definition): `research_analysis.py:849,852` use
  `lows[j+2] > highs[j]` / `highs[j+2] < lows[j]`. Present.
- Bug #3 (no-lookahead confirmation-bar bound): `research_analysis.py:842`
  bounds the forward search by `min(confirmation_bar - 1, ob_bar_index + 3)`
  and `:843` carries a live `assert j + 2 <= confirmation_bar`. The
  displacement check carries the equivalent assertion at `:813`. Present
  and actively enforced (no assertion fired during any run in this audit).
- Bug #1 (non-orthogonal composite score): the 5 `quality_*` booleans are
  evaluated independently at `:886-890`; the composite `quality` integer is
  still computed at `:891` but is used only as the `min_ob_quality` sweep
  threshold, as documented. Present.

## B6 — Discrepancies found

### B6-1 — Ablation A/B win rate and return diverge from locked figures
**Severity: not a new finding — PRE-DISCLOSED in-repo.**
Recomputation gives 140 / 47.14% / -13.72% and 138 / 43.48% / -23.85%
against locked 140 / 60.00% / -14.63% and 138 / 55.07% / -25.50%. Trade
counts match exactly; win rates differ by ~12 points.

Already known and documented at length: `research_analysis.py` Section 4's
header (lines 2277-2372) discloses that the original script producing those
pools was never committed, that this is a best-faith reconstruction, and
that a DIVERGE verdict is expected. `run_ablation_study()` prints the
DIVERGE banner at runtime (lines 2725-2734), and
`artifacts/ablation_reconstruction.json` stores
`"status_vs_locked": "DIVERGE"` for both arms. This audit's independent
recomputation reproduces the repo's reconstruction figures exactly (66/140
and 60/138 wins), which confirms the reconstruction code is internally
correct — the gap is between the reconstruction and the lost original,
exactly as disclosed. **No action. Not counted toward the "THIRD bug" rule.**

### B6-2 — `manifest.json` start/end vs actual first/last candle
**Severity: (a) cosmetic.**
`manifest.json` reports `start_time: "2022-01-01 00:00:00"` /
`end_time: "2026-01-01 00:00:00"`, but the actual first/last bars are at
`08:00:00` (correctly reported by `verification_report.json`'s
`source_checks`). The manifest fields carry
`export_dashboard_artifacts()`'s *requested window arguments* (its defaults
at `research_analysis.py:4561-4562`), not the realised data bounds. No
computed figure depends on them. Reported, not fixed.

**No new correctness bug of category (c) was found in the backend or
statistics pipeline.**

---

# Part 4 — Cleanup candidates (C)


Format: `filename | classification | one-line reason`

Classifications: **CURRENT** (authoritative, keep) · **SUPERSEDED**
(self-labelled or content-overtaken) · **ONE-OFF** (finished investigation,
conclusion already folded into CLAUDE.md/CHANGELOG) · **GENERATED**
(rebuildable build output) · **BROKEN** (references something that no longer
exists) · **ORPHANED** (no current producer in the codebase).

## C1 — `docs/` (15 files)

```
ablation_study_indicators_only.md            | CURRENT    | source-of-record for the Ablation A design; cited by research_analysis.py Section 4's reconstruction docstring
ablation_unconfounding_analysis.md           | CURRENT    | source-of-record for the Ablation B swing-pivot arm; same citation path
backtest_methodology_defense_walkthrough.md  | CURRENT    | panel-defense walkthrough; carries the corrected Pearson/Spearman p-values (verified this audit)
change_log_2026-08-08.md                     | CURRENT    | traceability record for the 2026-08-08 reporting-correction pass; the "p<0.001" hits in it are quoted-error context, not live claims
license_verification.md                      | CURRENT    | untracked, new; dependency-license audit, 8 PASS / 3 FLAGGED — no overlap with any other doc
limitations_section_draft.md                 | SUPERSEDED | self-labelled "draft, not yet inserted"; its Leverage subsection was consolidated into paper_FINAL_for_docx_handoff.md
MATH_CORRECTNESS_AND_COMPREHENSION.md        | CURRENT    | untracked, new; line-by-line formula check of the 5 custom-math functions
order_block_criteria_per_trade_reference.md  | CURRENT    | post-Bug-#3 OB criteria code trace; matches current code (spot-verified in workstream B5)
orthogonal_criteria_reference.md             | SUPERSEDED | self-labelled "Superseded 2026-08-01"; its Section 1 N counts predate the Bug #3 fix
paper_FINAL_for_docx_handoff.md              | CURRENT    | the standalone consolidated paper draft — the handoff artifact
paper_full_update_2026-08-08.md              | SUPERSEDED | self-labelled "draft, not yet inserted"; consolidated into paper_FINAL_for_docx_handoff.md, but still the only home of the pending-corrections checklist (§742-755)
PROVENANCE_VERDICT.md                        | CURRENT    | untracked, new; statistical-provenance defense report
research_statistics_reference.md             | SUPERSEDED | self-labelled "Superseded 2026-08-01"; its sweep table matches neither pre- nor post-fix values — keep only for formula explanations
results_section_addition_draft.md            | SUPERSEDED | self-labelled "draft for review"; content folded into paper_full_update / paper_FINAL
backtest_revision_ledger_2026-08-18.xlsx     | CURRENT    | untracked, new; binary revision ledger, no markdown equivalent
```

Note: all four SUPERSEDED markdown files carry their own explicit
superseded/draft banner at the top. None is silently stale, so deleting them
is optional cleanup, not a correctness need — and
`paper_full_update_2026-08-08.md` should NOT be deleted while it is the only
place holding the open pending-corrections list.

## C2 — `scratch/` (16 scripts + 7 data/report files + fixtures)

```
regression.py                          | CURRENT   | the golden-master harness CLAUDE.md mandates; correctly repointed to research_analysis.py (PASS this audit)
fixtures/baseline_bars.parquet         | CURRENT   | regression golden master — do not touch
fixtures/baseline_trades.json          | CURRENT   | regression golden master — do not touch
run_export_offline.py                  | BROKEN    | `import export_gui_data as egd` (line 23) — that module is retired to legacy_pre_consolidation/; this script cannot run
02_benchmark_and_risk.py               | ONE-OFF   | superseded by research_analysis.py's run_benchmark_vs_passive(); still cited as independent corroboration of the ablation gap, so keep the file
bootstrap_power_audit.py               | ONE-OFF   | promoted into run_bootstrap_ci()/run_mde_power_report()
calculate_all_qualities.py             | ONE-OFF   | OB quality tally; superseded by orderblocks_default_view.csv + the sweep
calculate_paper_metrics.py             | ONE-OFF   | ad-hoc sqlite metric pull; superseded by the stats pipeline
dca_blend_audit.py                     | ONE-OFF   | promoted into run_dca_blend_analysis()
eightyr_backfill_audit.py              | ONE-OFF   | self-labelled "ONE-TIME"; produced the 2018-2026 extended history
fee_slippage_audit.py                  | ONE-OFF   | promoted into run_fee_slippage_sensitivity()
inspect_max_min_trades.py              | ONE-OFF   | ad-hoc sqlite inspection helper
inspect_raw_signals.py                 | CURRENT   | small offline signal-inspection tool, correctly loads research_analysis.py
kdj_exit_window_counterfactual.py      | ONE-OFF   | the KDJ-w investigation; conclusion is now CLAUDE.md's "KDJ architecture" section
kdj_exit_window_trade_detail.py        | ONE-OFF   | companion per-trade detail for the same investigation
no_lookahead_atr_kdj_check.py          | CURRENT   | part of the CLAUDE.md-mandated no-lookahead final step; still re-runnable
no_lookahead_fvg_scope_audit.py        | CURRENT   | the Bug #3 audit tool; keep as the evidence trail for a disclosed correction
oos_live_pull_2026_08.py               | ONE-OFF   | self-labelled ONE-TIME; makes a live API call by disclosed exception
regime_breakdown_audit.py              | ONE-OFF   | promoted into run_regime_breakdown()
full_sweep_q0_q5_live.json             | GENERATED | q0-q5 sweep output, regenerable
kdj_exit_window_counterfactual_results.json | GENERATED | output of the same-named script
kdj_exit_window_trade_detail_results.json   | GENERATED | output of the same-named script
oos_extended_candles_2018_2026.csv     | GENERATED | 1.6 MB; superseded by artifacts/candles_extended.json
oos_extended_candles_2026_08.csv       | GENERATED | 880 KB; one-time live-pull snapshot
audit_locked_results_extract.md        | GENERATED | this audit's own working file
audit_B_recompute.md                   | GENERATED | this audit's own raw recompute log
audit_{A1,A2,B,C}_findings.md          | GENERATED | this audit's own working files (folded into docs/AUDIT_REPORT_2026-08-20.md)
__pycache__/                           | GENERATED | build residue
```

**The one actionable item here is `run_export_offline.py`** — it is not
merely stale, it is non-executable: its only entrypoint imports a module
that no longer exists. Every other ONE-OFF still runs.

## C3 — `artifacts/` (23 files, all git-tracked)

Written by the current pipeline (`research_analysis.py --serve` /
`write_statistical_artifacts()`) — all GENERATED, all safely rebuildable:

```
manifest.json, candles.json, candles.csv, threshold_runs.json,
threshold_runs.csv, runs_by_threshold.json, verification_report.json,
trades_default_view.csv, orderblocks_default_view.csv, paper_sync_report.md,
bootstrap_power_analysis.json, fee_slippage_analysis.json,
ablation_reconstruction.json, benchmark_vs_passive.json
```

Read as INPUT by the current pipeline — must NOT be treated as disposable:

```
candles.csv                    | CURRENT (sole-copy input) | the locked 8,767-bar dataset; every locked figure derives from it — CLAUDE.md says do not trim
candles_extended.json          | CURRENT (sole-copy input) | 2018-2026 history; load_formulation_period_window() asserts on its segment boundary
oos_validation_analysis.json   | CURRENT (sole-copy input) | read by reconcile_formulation_window_trades() as the published cross-check baseline
```

No current producer found in `research_analysis.py` — ORPHANED outputs of
the retired `analysis/*.py` scripts:

```
benchmark_dca_analysis.json           | ORPHANED | run_dca_blend_analysis() exists but does not write this path
regime_breakdown_analysis.json        | ORPHANED | run_regime_breakdown() exists but does not write this path
benchmark_vs_passive_2018_2022.csv    | ORPHANED | CSV companion to benchmark_vs_passive.json; only the JSON is written now
benchmark_vs_passive_2022_2026.csv    | ORPHANED | same
export_trades_and_results.json        | ORPHANED | gsheet staging file; the push is computed in-process now
export_candles_for_gsheet.json        | ORPHANED | 15 MB (largest file in the repo); gsheet staging, computed in-process now
candles_extended_manifest.json        | ORPHANED | manifest for the extended history; not read by the loader, which reads the JSON directly
```

`export_candles_for_gsheet.json` at 15 MB is the single largest cleanup win
in the repo. **Verify each ORPHANED file is genuinely unreferenced before
deleting** — several are still cited by name in docs and comments, so
deleting them would break those citations even though no code reads them.

## C4 — Numeric drift check, docs vs locked results

Cross-checked `docs/*.md` and root `*.md` against
`scratch/audit_locked_results_extract.md`. **No drift found.** Specifically:

- `p < 0.001`: 13 hits, ALL inside correction/change-log context that quotes
  the old wrong value while stating the corrected one. No file asserts it as
  a live claim.
- `8,760`: 4 hits, all explicitly rejecting it in favour of 8,767.
- `0.038` (pre-fix q>=1 p-value): 6 hits, all inside the disclosed
  0.038 -> 0.054 significance-flip narrative.
- `"0.38–0.90"` (stale Welch range): 2 hits —
  `docs/paper_full_update_2026-08-08.md:749` and `CLAUDE.md:150`. Both are
  inside a *pending-corrections checklist* that instructs the reader to
  change it to "0.38–0.78". `STUDY_REFERENCE.md:395` already states the
  corrected range. `docs/paper_FINAL_for_docx_handoff.md` does not carry the
  claim at all. Workstream B independently recomputed the true range as
  0.3775–0.7751, confirming "0.38–0.78" is the correct target. The
  correction remains PENDING in the paper itself, exactly as CLAUDE.md
  Known bugs #3 states — this audit did not action it.
