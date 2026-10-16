# Workstream C — Docs / scratch / artifacts inventory (REPORT ONLY, nothing deleted)

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
