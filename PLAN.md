# Full codebase audit: backend correctness, dashboard display, cleanup candidates

## Context

This is the ISEF research codebase (BTC/USDT rule-based strategy backtest,
consolidated into research_analysis.py as of commit 7154d43). It carries a
set of locked results in CLAUDE.md that must never silently drift, a
regression harness (scratch/regression.py) that must pass unchanged, and an
explicit rule that a genuinely new correctness bug must be reported, not
fixed. The user wants a comprehensive audit: every number the dashboard
displays traced back to its source and verified correct, the backend/stats
pipeline re-verified against the locked results (via blind independent
recomputation, not by reading docs and nodding along), and a cleanup-candidate
list for redundant/stale docs, scratch scripts, and artifacts (report only,
no deletion this session).

Uncommitted working-tree state (already understood, not part of this audit's
target): research_analysis.py's diff is a documentation-only comment block
(a ruled-out TP/exit-mechanics investigation) plus one whitespace fix; the
modified artifacts/* files reflect a routine regeneration (new
kdj_exit_window export column added to trades_default_view.csv, hence a
changed trades_hash with an unchanged stats_hash in
verification_report.json — not a discrepancy, just a schema addition to an
already-regenerated file).

## Explicit non-goals

- Not re-litigating the two disclosed bugs in CLAUDE.md's "Known bugs"
  section (composite 0–5 quality score non-orthogonality; the FVG
  3-candle/no-lookahead confirmation-bar fix). Treated as settled.
- Not re-litigating the DCA-vs-strategy exposure-time framing decision in the
  benchmark-vs-passive section. Treated as settled.
- No fixes applied to anything found, of any severity. Report-only.
- No files deleted or moved this session (workstream C output is a report).

## Step 0 — Playwright install (background, non-blocking)

Kick off in the background immediately, in parallel with everything else —
nothing else waits on it:
- npm install -g playwright then npx playwright install --with-deps chromium;
  on error, retry once with plain playwright install chromium (no --with-deps,
  since that flag can be unreliable on Windows).
- Verify with a trivial script: launch Chromium, screenshot about:blank,
  confirm a PNG is written.
- If it still fails after the one retry/fallback: stop trying, mark A2 as
  skipped, and note in the final report that dashboard screenshots are
  unavailable in this environment and would need to be supplied manually.
  This must not delay or block A1, B, or C.

## Shared setup — locked-results extract (before B/C fork)

Read CLAUDE.md's "Locked results" section once and copy it verbatim into
scratch/audit_locked_results_extract.md. Workstreams B and C reference this
extract instead of each independently re-reading the full CLAUDE.md.

## Workstreams (run in parallel: A1, B, C start immediately; A2 starts once Playwright is confirmed working)

All workstreams write findings incrementally, append-only, to their own
scratch file as they go — do not hold the running report in context and
rewrite it repeatedly:
- scratch/audit_A1_findings.md
- scratch/audit_A2_findings.md
- scratch/audit_B_findings.md
- scratch/audit_C_findings.md

## A1 — Static value-trace audit (no browser required)

For every numeric/statistical value the dashboard renders (win rate, total
return, trade count, Sharpe/Sortino/MaxDD, p-values, bootstrap CIs, per-trade
table fields, SolutionsTab derivation steps, benchmark-vs-passive figures):
1. Grep for the specific field/variable name across dashboard-v2/src and
   research_analysis.py first. Only open full files when grep context is
   insufficient to resolve the trace.
2. Trace: rendered value → dashboard-v2/src/api/client.ts / hooks.ts
   fetch → which artifacts/*.json or /api/... endpoint in
   research_analysis.py → which computation function. Confirm units/
   formatting (%, $, decimal places) aren't silently wrong, confirm nothing
   is stale-cached or hardcoded that should be computed.
3. Run npm run typecheck and npm run lint (oxlint) in dashboard-v2/.
   On pass: log "PASS" with a one-line summary only. On failure: capture
   full output (only case where the detail is actionable).
4. Append each traced value's result (file:line chain, match/mismatch) to
   scratch/audit_A1_findings.md as you go.

## A2 — Dashboard screenshots (gated on Step 0 succeeding)

1. Start the stack: npm run dev from dashboard-v2/ (auto-starts
   research_analysis.py --serve --no-browser on :8765 and Vite, per
   dashboard-v2/scripts/dev.mjs).
2. Playwright script visits each tab in dashboard-v2/src/components/tabs/
   (ChartTab, StatsTab, SolutionsTab, SandboxTab) and SettingsPanel,
   screenshotting each, cycling any controls that change displayed data
   (OB quality threshold selector, date range/symbol controls if present).
3. Save screenshots to the scratchpad dir. Append filename + tab/state
   label to scratch/audit_A2_findings.md — do not transcribe screenshot
   contents in prose; numeric verification is A1's job.

## B — Backend/statistics blind recomputation

1. Run scratch/regression.py (read-only — never --generate). On pass:
   log "PASS" with a one-line summary. On failure: capture full output and
   flag immediately as material (per bug-severity tagging below).
2. Blind recompute first: directly from artifacts/candles.csv,
   independently compute the headline stats (27 trades / win rate / total
   return / SD, Sharpe/Sortino, the q≥1 significance flip, 761 OBs / FVG
   count) and the Ablation A/B figures and the benchmark-vs-passive
   figures (strategy/DCA/lump-sum, gross + fee-adjusted, both windows).
   Write every recomputed number to scratch/audit_B_recompute.md BEFORE
   opening scratch/audit_locked_results_extract.md or any doc containing
   the locked values — do not anchor the computation toward the expected
   answer.
3. Only after that file is written, open scratch/audit_locked_results_extract.md
   and the live research_analysis.py output, and diff each recomputed figure
   against both. Append the diff result per figure to
   scratch/audit_B_findings.md.
4. Verify artifact self-consistency: manifest.json,
   verification_report.json hashes, trades_default_view.csv,
   runs_by_threshold.json agree with each other and with a fresh run.
5. Spot-check (do not re-derive from scratch) that the two disclosed-bug
   fixes are still reflected in current code — confirming no silent
   regression, not re-litigating them.
6. Any genuinely new discrepancy (not one of the two disclosed bugs, not
   the known uncommitted diff): capture full evidence (function, inputs,
   expected vs actual) and tag severity per the scheme below. Do not chase
   a fix.

## C — Docs / scratch / artifacts inventory (report only)

One line per file, fixed format, no prose paragraphs:
filename | classification | one-line reason

1. Every file in docs/ (16 files): current/authoritative vs. superseded
   draft vs. one-off audit already folded into CLAUDE.md.
2. Every script/file in scratch/ (20+): still-useful ad hoc tool vs.
   one-shot investigation already resolved vs. generated-output that
   doesn't need tracking.
3. Every file in artifacts/: regenerable via research_analysis.py --serve
   (build output) vs. anything hand-edited or sole-copy.
4. Cross-check numeric claims inside docs/*.md against
   scratch/audit_locked_results_extract.md for drift.
5. Append each line to scratch/audit_C_findings.md.

## Bug severity tagging

Any newly found discrepancy (excluding the two disclosed bugs and the known
uncommitted diff) gets tagged on the way into its findings file:
- (a) cosmetic/formatting only
- (b) real but doesn't affect any locked conclusion
- (c) material — could change a locked number or a paper claim
  Still report-only in all three cases — no fixes.

## Deliverable

Assemble docs/AUDIT_REPORT_2026-08-20.md once, at the end, by concatenating
and lightly editing the four scratch findings files (audit_A1_findings.md,
audit_A2_findings.md, audit_B_findings.md, audit_C_findings.md) — do not
regenerate from scratch. Report section order: dashboard trace results (A1,
any mismatches called out first) with screenshot references if A2 succeeded
→ backend/statistics re-verification results and regression pass/fail (B) →
any newly found bugs with full evidence and severity tag, explicitly marked
"reported, not fixed" → cleanup-candidate list (C). End the chat turn with a
short summary pointing to the report file path.

## Verification

- scratch/regression.py passes (no fixture regeneration).
- npm run typecheck / npm run lint clean, or failures explicitly logged.
- Every locked figure is independently reproduced from artifacts/candles.csv
  via blind recompute-then-diff, not read back from existing docs.
- If Playwright install succeeded: screenshots exist for every tab +
  threshold variant, referenced by filename from the report. If it failed:
  report explicitly says so instead of silently omitting the section.
