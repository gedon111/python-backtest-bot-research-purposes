# Workstream B — Backend / statistics re-verification

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
| Strategy Sharpe / MaxDD | 1.114 / -6.46% | 1.1142 / -6.4619% | MATCH |
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
