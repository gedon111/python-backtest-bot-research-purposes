# Change Log — Paper Draft Fixes, 2026-08-08

Every edit below traces to either **Part 1** (framing decisions from the
separate Claude.ai conversation) or **Part 2** (findings from this repo's
own prior audit session) of the context-handoff prompt that requested this
work. No independent judgment calls were made beyond what those two sources
already decided, except where explicitly flagged as a recommendation for
your review (see "Open items — my recommendation" at the end).

**One correction to my own prior audit, caught while making these edits:**
Part 2(b) stated the `p<0.001` error appeared in three files including
`STUDY_REFERENCE.md`. On re-checking that file directly (`grep` for
"Pearson", "Spearman", "correlation") to make the precise edit, **it does
not appear there at all** — `STUDY_REFERENCE.md` contains no Pearson/Spearman
correlation content. The error actually appears in only two files:
`docs/backtest_methodology_defense_walkthrough.md` and
`docs/paper_full_update_2026-08-08.md`. Both are fixed below;
`STUDY_REFERENCE.md` was left untouched since it never needed the fix.

---

## Edit 1 — Pearson/Spearman p-value correction

**File:** `docs/backtest_methodology_defense_walkthrough.md`, lines 224–225

**Before:**
```
$$Pearson \, r = +0.4907 \quad (p < 0.001, t = 2.82)$$
$$Spearman \, \rho = +0.4797 \quad (p < 0.001)$$
```

**After:**
```
$$Pearson \, r = +0.4907 \quad (p \approx 0.0094, t = 2.82)$$
$$Spearman \, \rho = +0.4797 \quad (p \approx 0.0113)$$
```
Plus an added parenthetical explaining the correction and the sanity check
(critical $t$ for $p=0.01$ at $df=25$ is $\approx2.79$; observed $t=2.82$ is
just past it, so $p\approx0.01$ is expected — $p<0.001$ would require
$t\approx3.73$).

**Justification:** Part 2(b) — confirmed wrong via independent
`scipy.stats.pearsonr`/`spearmanr` recomputation in the prior audit session;
Part 3 item 1 instructed the fix using the exact recomputed values.

---

## Edit 2 — Pearson/Spearman p-value correction (paper draft)

**File:** `docs/paper_full_update_2026-08-08.md`, §2.6 "Correlation" paragraph

**Before:**
> Pearson $r=+0.4907$ ($t=2.82$, $p<0.001$) and Spearman $\rho=+0.4797$
> ($p<0.001$) between hold duration and `pnl_pct` across the 27 baseline
> trades — longer-held trades tend to realize larger gains, a moderate,
> statistically significant positive association.

**After:**
> Pearson $r=+0.4907$ ($t=2.82$, $p\approx0.0094$) and Spearman
> $\rho=+0.4797$ ($p\approx0.0113$) between hold duration and `pnl_pct`
> across the 27 baseline trades. In plain terms: trades that stay open
> longer tend to realize larger gains, a moderate positive association that
> is statistically significant at the conventional $\alpha=0.05$ threshold
> (and at $\alpha=0.01$). *(These $p$-values were corrected during a
> 2026-08-08 numerical audit — both were previously misreported as
> "$p<0.001$" here and in a supporting walkthrough document; see §1.8.)*

**Justification:** Part 2(b) + Part 3 item 1 (same fix as Edit 1, applied to
the paper draft itself, plus Part 1 point 7's "plain language first"
instruction for the added explanatory sentence).

---

## Edit 3 — Bootstrap B/seed disclosure

**File:** `docs/paper_full_update_2026-08-08.md`, §2.5 "Bootstrap CI on the
core return finding"

**Before:** Reported only the $B=10{,}000$ figure, [+5.99%, +54.99%], with
no mention that another figure existed anywhere else.

**After:** Same figure kept as the canonical result, with an added sentence
disclosing the website's $B=2{,}000$ figure, [+7.48%, +54.46%], and
explaining the gap is attributable to resample count alone (same seed,
same trade data, same algorithm family — the two implementations use
different RNGs by design, but that is not what's driving this specific gap;
the B mismatch is).

**Justification:** Part 2(a) (root cause already diagnosed in the prior
audit) + Part 3 item 2, which explicitly recommended this exact resolution
("report B=10,000 as canonical... add one explicit sentence... do not
silently pick one and delete the other") — followed as specified, not
altered.

---

## Edit 4 — Benchmark-vs-passive integration (new content)

**File:** `docs/paper_full_update_2026-08-08.md`, §2.6, two new paragraphs +
two new tables appended after the existing DCA-blend content

**Before:** No mention of `analysis/benchmark_vs_passive.py`'s results
anywhere in the paper draft (the feature did not exist when the draft was
written).

**After:** Added:
- A head-to-head 2022–2026 table (strategy / weekly DCA / lump-sum B&H,
  each from \$10,000 notional capital) with Total Return, Final Capital,
  Sharpe, Sortino, Max Drawdown, % Time In-Market.
- A plain-language paragraph stating, without hedging, that DCA
  outperformed the strategy in raw terminal value (\$22,312.94 vs.
  \$13,417.77), paired with the risk-adjusted/exposure-time caveat
  (Sharpe 1.114 vs. 0.564, but only 2.63% time in market) and an explicit
  statement that the blended-sleeve model (already in the draft) is the
  more decision-relevant framing.
- A second table + paragraph for the 2018–2022 formulation-period arm,
  labeled not-out-of-sample, with the same structure.

**Justification:** Part 2(c) (the gap) + Part 3 item 3 (the instruction to
add it, extending §2.6) + **Part 1 point 5, followed exactly**: the "DCA
outperformed" fact is stated plainly rather than buried, and every mention
of the strategy's better risk-adjusted profile is paired with the
2.63%-vs-100% exposure caveat in the same breath, never standing alone.

---

## Edit 5 — Reporting-layer corrections narrative (new content)

**File:** `docs/paper_full_update_2026-08-08.md`, §1.8, new paragraph
inserted after the three code-level bugs, before the no-lookahead-proof
paragraph

**Before:** §1.8 discussed only the three code-level bugs (non-orthogonal
score, FVG 2- vs 3-candle, lookahead boundary).

**After:** Added a paragraph explicitly naming the bootstrap-B mismatch and
the $p<0.001$ overclaim as a *fourth and fifth* disclosed correction,
explicitly distinguished from the three code-level bugs ("reporting-layer,"
not backtest-engine), framed as evidence the self-audit discipline extends
to the paper's own numbers.

Also added one cross-referencing sentence to the Discussion section's
existing "Self-correction as a feature of the methodology" paragraph,
pointing back to this new §1.8 material.

**Justification:** Part 1 point 6, explicit: "Same treatment for the
newly-found reporting bugs below (Part 2) — the fact that a final audit
caught them IS the story, not something to downplay." This edit exists
specifically to satisfy that instruction; nothing here reports a new
finding, it only narrates the two already-fixed items (Edits 1–3) as
methodology.

---

## Items explicitly NOT touched (per Part 3 items 4–5)

- Baseline 27-trade numbers, all 5 Fisher's exact values, all 5 Welch's
  t/p values, all 5 MDE values, fee-sensitivity table, ablation three-arm
  table, OOS test, 8-year backfill, Google Sheets "Benchmark 2022-2026"
  tab — **zero edits**, per the "Confirmed correct, do not touch" list.
- **190-signal denominator (item d):** left exactly as-is, still stated as
  open/unresolved in §3 and §4 of the paper draft. Not re-derived.
- **Welch range wording tension (item f):** left exactly as-is in §2.3 —
  both framings ("0.38–0.78" all-five-criteria vs. "0.39–0.78"
  four-criteria) still presented side by side, un-adjudicated.

## Open items — my recommendation, not acted on

You asked for my recommendation on (d) and (f) without acting on either.

- **(f) Welch range wording:** I'd report the **four-criteria framing
  ("0.39–0.78")** as the paper's primary number, with the all-five figure
  in a footnote. Reasoning: the paper's own stated methodology already
  treats Displacement's $n=4$ true-subgroup as too thin to test formally
  (this is stated explicitly elsewhere in the draft), so a summary range
  that silently reintroduces it via the *min* of a Welch $p$-range is
  inconsistent with the paper's own stated inclusion criteria. This is a
  wording-consistency argument, not a new calculation — nothing about the
  underlying five $p$-values changes either way.
- **(d) 190-signal denominator:** I don't have enough information to
  recommend re-deriving it right now — doing so correctly requires
  re-running the indicators-only signal count under the OB-gated strategy's
  *own* risk rules (stop distance, R:R filter), which is a real piece of
  new analysis, not a five-minute fix, and per your instruction I have not
  attempted it. If you want it resolved, that should be scoped as its own
  task with its own verification pass, not folded into this edit round.

---

## Consolidation into the final handoff file

Once Edits 1–5 above were made and verified in
`docs/paper_full_update_2026-08-08.md`, that file (plus the Leverage
subsection from `docs/limitations_section_draft.md`, and newly-drafted
Abstract/Introduction/Limitations-framing/References sections that did not
exist anywhere in this repository before) were consolidated into
`docs/paper_FINAL_for_docx_handoff.md` — the full, standalone paper. See
that file's own header comment and the accompanying chat summary for what
was newly drafted versus what was carried over verbatim.
