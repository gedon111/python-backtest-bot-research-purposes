# Mock regional judging: bitcoin (6)

Branch `dev/paper-3rq-2h`, 2026-10-28. Reviewed: `docs/finalists/bitcoin (6).docx` / `.pdf` (76 pages),
`PLAIN_SUMMARY.md` (treated as the display board), `CHANGELOG_REGIONALS.md`.

Four judges worked independently and in parallel; none saw another's report:

| Tag | Judge |
|---|---|
| **[S]** | Agent 1, rigorous statistician |
| **[D]** | Agent 2, non-specialist DepEd panelist |
| **[Q]** | Agent 3, quant trading practitioner |
| **[I]** | Agent 4, integrity and consistency auditor |
| **[H]** | Head judge (checks made while merging) |

This is a critique only. No manuscript, code or data file was changed. Every finding below that
says "verified" was re-checked by the head judge against the file, the code or a recomputation.
No fix below changes a reported number by hand. Any fix that needs a new number says
**recompute**, which means producing the number with code first and logging it in the changelog
as the (6) revision did.

---

## 1. Score

| Rubric row | Max | Score | Reason |
|---|---:|---:|---|
| Research problem & creativity | 20 | **15** | The question ("does a rule system beat weekly buying?") is clear, testable and relevant to ordinary savers. Combining MACD, KDJ and ATR with Order Blocks under frozen rules is a reasonable student contribution. Points lost: the title (CIPHER acronym) hides the question; Order Blocks are practitioner lore, and the SOP still calls them "institutional order flow" as if that were established. |
| Scientific method & design | 25 | **16** | Strong: rules frozen before the test window, an out-of-sample window, a forward test, a one-shot 1h holdout, six cost scenarios and a full funding check. Weak: stops and fills are close-only (trade 2624 lost −4.65% against a 2.68% stop); spot candles stand in for perpetual futures; strategy equity is not marked to market; H₂ has no cash-sleeve control; the H₁ cost basis is not stated with the hypothesis; the pre-registration files call themselves exploratory and are not cited; and Table 1 lists a breakeven rule that can never fire. |
| Data analysis & interpretation | 20 | **13** | Every number the judges recomputed matches the result files: binomial, iid bootstrap, Holm, Pearson/Spearman, Tables 9–16. Interpretation is the problem. "Directionally robust return edge" does not survive the paper's own stationary bootstrap after costs (the CI includes zero). The p-value definition is wrong. "No p-value can be formed for Sharpe" is false. The Spearman 1% sentence is false. There is no power statement. Figure 8 shows superseded Sharpe values. |
| Thoroughness & integrity | 10 | **6** | Nulls and unfavourable results are reported plainly: H₁ not supported after costs, the forward-test loss, the 1h failure, and the disclosed leakage bug. Points lost: there is no AI-use disclosure anywhere, Appendix E is a bare placeholder, the pre-registration's exploratory status and timing are not disclosed, and the DCA end-bar caveat appears only in the Figure 7 caption. |
| Clarity & presentation | 15 | **10** | Good walk-throughs: the coin-flip H₁, "26 in 1,000", and naming the two trades that flip significance. Points lost: the abstract is 328 words with the main result in sentence 7; much jargon is unexplained (short, 1x perpetual, bootstrap, Holm, gate); Figures 6–10 are never called out; and there are small inconsistencies (forward-test end date, "Datc"). |
| Relevance & impact | 10 | **7** | Strong Philippine context (BSP inclusion data) and an honest "the simple habit won" message. Points lost: the board's numbers lean on Sharpe; the gambling question is not met head-on; and the SDG 11 link is decoration. |
| **Total** | **100** | **67** | |

---

## 2. Ranked fix list

Fatal items come first. After that the list is ordered by rubric points gained per hour of work.
Times are rough estimates for the students.

### Fatal

| # | Fix | Where | Raised by | Est. time |
|---|---|---|---|---|
| F1 | **Add an AI-use disclosure.** The PDF and docx contain no mention of AI, Claude or language models (verified with grep: zero hits), yet AI tools were used for code, statistics and editing. Name the tool, what it was used for (code, analysis, audits, wording) and what the students did and checked themselves. Put it in Methods or Acknowledgments **and** in the Research Plan. ISEF rules require it, and Limitation 10 ("verification was internal only") reads as all-student work without it. | new paragraph, Sec B or Acknowledgments; Research Plan | [I] | 30 min |
| F2 | **Insert the real, signed ISEF forms.** Appendix E (p.75) is only "[INSERT SCANNED FORMS HERE]". At minimum include: Checklist for Adult Sponsor (1), Student Checklist (1A), Research Plan/Project Summary, and Approval Form (1B), all dated **before** experimentation. Add Form 7 if this continues earlier work. State that human, vertebrate and hazard forms do not apply. Change Appendix F's placeholder to "[INSERT CVs HERE]". | App. E, F (pp.75–76) | [I] | 1–2 h (signatures) |

### Major

| # | Fix | Where | Raised by | Est. time |
|---|---|---|---|---|
| M1 | **Regenerate Figure 8.** It still shows the superseded weekly-frequency Sharpe values 0.556 / 0.581 / 0.607 / 0.637, while Table 12, the abstract and the board show the daily-close values 0.558 / 0.581 / 0.606 / 0.632. Verified by viewing the embedded image. The (6) revision recomputed Table 12 but missed this figure. Redraw it from `artifacts/benchmark_daily_sharpe.json` (blend) and `artifacts/benchmark_dca_analysis.json` (drawdown), change the "210 weekly contributions" note to "valued at daily closes", and log it in the changelog. | Fig. 8, p.42 | [D] ([I] checked Table 12 but not the image) | 30 min |
| M2 | **Fix the p-value definition.** "the chance of a result at least this strong if the strategy had no edge at all" is wrong. The null is a 50% win rate, not zero edge. Write: "the chance of 19 or more wins out of 27 if each trade were a fair coin flip". Add one sentence: "Win rate alone is not edge; average return per trade is." | Sec F p.30; Table 3 text p.34 | [S] | 10 min |
| M3 | **Fix "no p-value can honestly be formed" for Sharpe/MDD.** It is false: a Sharpe ratio estimated from about 1,461 daily returns has a standard error, and paired Sharpe-difference tests exist (Jobson–Korkie/Memmel; Ledoit & Wolf, 2008). Replace with: "We chose a descriptive standard for H₂. Formal Sharpe-difference tests exist (Ledoit & Wolf, 2008) but were not run." Do **not** run one now unless it is added through code and logged. | H₂ rationale p.14; Limitation 4 p.51 | [S] | 15 min |
| M4 | **Drop "directionally robust return edge".** The paper's own Formula 4 (stationary bootstrap, L = 3, B = 10,000), applied to the 27 trades net of 0.20%, gives a 95% CI of about [−0.05%, +1.85%] on the mean, which includes zero. The judge found this, and the head judge confirmed it independently with seeds 42, 1 and 7 (share ≤ 0 ≈ 0.03). The iid net interval clears zero by only 0.02 points. **Recompute** the stationary-bootstrap net CI with the project's own stationary-bootstrap function and report it next to the iid interval in SOP 1 and Table 15. Then reword: "positive before costs; after costs the dependence-robust interval reaches zero." Also show the net iid CI (the gross CI shifted by exactly −5.40) wherever "excludes zero" is claimed. | Abstract; SOP 1 p.34; Table 15; Summary p.54–55 | [S], [Q] | 1–1.5 h |
| M5 | **Fix the Spearman sentence.** "The pattern holds at both the 5% and 1% thresholds" is false for Spearman (p = 0.0113 > 0.01). Write: "Pearson is significant at 1%, Spearman at 5% only." Add that the link largely reflects the exit design (stops fire early; winners are allowed to run) and is descriptive. | SOP 1, p.37 | [S] | 5 min |
| M6 | **State when 0.20% was fixed as the cost for judging H₁.** H₁ does not say gross or net; the 0.20% row is labelled "primary" only in Table 4. Put the decision rule next to H₁ ("judged at 0.20% round trip") and say honestly when that was decided. If it was fixed after the gross result was known, say so. | H₁ p.14; Sec F; Table 4 | [S] | 15 min |
| M7 | **Disclose the pre-registration honestly.** Name `experimental/PREREGISTRATION.md` (commit 996cf2a) and `PREREGISTRATION_1H.md` (f220b1e) with their dates. Say that both files are headed "Status: EXPLORATORY" (verified), that including them in the paper was decided after the results, that the primary endpoint of that pre-registration was the ML filter (Limitation 13, p = 0.378), and that the runs came minutes after the commits. Use one phrase throughout: "pre-specified before computation, added after the headline result was known." Also cite the earliest dated record of the frozen 4h parameters, or soften "frozen" to "fixed before the 2022 window was run (no dated record survives; see Limitation 3)". | Abstract; Sec A p.11, p.14; App. A; Summary | [I] | 45 min |
| M8 | **Label strategy Sharpe and MDD as realized-equity.** The strategy arm and the blend sleeve change value only at exit bars (verified, Sec E p.26 and code), so open-trade swings never show up. Trade 2624 moved about 4.7% against the position inside one trade. The passive arms are marked every day. Add to the Table 9, 10 and 12 notes: "Strategy and sleeve values are realized at trade exits, not marked to market; their Sharpe and drawdown omit intra-trade swings." A mark-to-market recompute is the full fix, but it is a code change (regression harness before and after) and can wait. | Sec E p.26; notes to Tables 9, 10, 12 | [S], [Q] | 15 min (label); 3–4 h (recompute) |
| M9 | **Add a cash-sleeve control for H₂, or disclose its absence.** The sleeve is in cash about 97% of the time (2.63% time in market). Moving 10–30% of a BTC DCA plan into cash would also make drawdown shallower, whatever the strategy does. The three steps are also re-weightings of the same two series, not three separate confirmations. Full fix: **recompute** "90/10, 80/20, 70/30 BTC/cash" with the same construction and judge H₂ against those rows. Minimum fix: add to Table 12: "This comparison does not separate the strategy's effect from simply holding part of the plan in cash; a cash-only control was not run." Also state Table 12's cost basis (gross or net), and that the table measures smoothness, not ending dollars. | H₂ / Table 12 p.41; Conclusions | [S], [Q], [D] | 15 min (disclose); 2–3 h (recompute) |
| M10 | **Rewrite the abstract to 250 words or fewer, result first.** It is currently 328 words; ISEF's limit is 250. Make sentence 2 the headline: "Over 2022–2026, buying a fixed amount every week ended with more money than the strategy ($22,312.94 vs $13,417.77 from $10,000), although the strategy won 70.37% of its 27 trades." Cut the compounding sentence, the bug sentence and the 4-decimal CI digits. Replace "Costs decide the verdict." with: "Costs decided whether the win rate was significant; weekly buying won on final value either way." Say "in both windows", not "both test windows". | Abstract pp.2–3 | [D], [I] | 1 h |
| M11 | **Describe the stop as a close-based stop and disclose its bias.** Stops are checked and filled only at the candle close (verified in `_check_long/short_exit_conditions`). Wicks through a stop that close back inside never trigger it, which flatters the win rate, and gaps book more than the stop. Trade 2624 is the concrete case: −4.65% on a stop 2.68% away (verified). Disclose this in Sec D and Limitation 1 as a bias in the 27 reported trades, not only as a leverage concern. An intrabar-stop sensitivity is the full fix (new code, harness). | Sec D p.25; Fig. 5; Limitation 1 p.50 | [Q] | 20 min (disclose); 3 h (sensitivity) |
| M12 | **Disclose that the breakeven rule cannot fire.** The 1.8×ATR move exit is checked and returns before the 2.0×ATR breakeven ratchet (verified, `research_analysis.py` lines 1277–1283 and 1322–1328), so any close past 2.0×ATR has already exited. It changes no reported number, but Table 1 and Figure 5 present an inactive rule as active. Do **not** change the logic (frozen rules; CLAUDE.md treats a newly found code issue as needing review). Disclose it in a Table 1 note and annotate Figure 5. Record it in `docs/SCRATCH_RESULTS_METHODS.md`. | Table 1 p.24; Fig. 5; Sec D | [Q] (verified [H]) | 20 min |
| M13 | **Fix the position-sizing contradiction.** The Introduction says ATR sets position size to keep risk steady, "the same logic this study applies" (pp.9–10). Sec E says every trade uses the full amount. Rewrite pp.9–10: in this study ATR sets the stop distance only, and every trade is full notional at 1x. | Intro pp.9–10 | [Q] | 10 min |
| M14 | **State that the prices are spot candles used as a proxy for the perpetual.** The engine pulls spot klines (`client.get_klines`; the 1h data uses `api/v3/klines`; verified), but the paper trades USDT-M perpetuals. Add to Sec B: "Signals and fills use Binance spot BTCUSDT prices as a proxy for the perpetual contract; the two differ by the basis." A perp-candle rerun is optional. | Sec B p.17; Sec E | [Q] | 10 min |
| M15 | **Add a power statement.** With n = 27 and one-sided α = .05 the critical value is 19 wins, so power to detect a true 60–70% win rate is low. The 1h CI cannot rule out a moderate positive mean either. **Recompute** the power values with scipy in a logged script (the judge's 0.18 / 0.36 / 0.58 at 60 / 65 / 70% must not be pasted unverified). Add them to Limitations, plus the 1-in-4 forward-test tail probability. Reword the verdicts to "not supported (inconclusive at this sample size)". | Limitations; H₁ verdict p.33, p.54; Table 7 | [S], [Q] | 45 min |
| M16 | **Fix the Fang et al. (2014) citation.** It is cited for "chart patterns repeat", but that paper finds simple technical rules lose their predictability out of sample, which is the opposite. Cite it as counter-evidence ("but see Fang et al., 2014, who find…"), which helps the paper's honesty. | Intro p.7 (line "People repeat their behavior…") | [I] | 10 min |
| M17 | **Qualify the 4h-vs-1h gate contrast, and the 2018–2022 agreement.** The random-filter control (63.3% pass rate) was run only on 1h, so there is no evidence that the 4h gates beat random selection. The 2018–2022 "same direction" result is in-sample, since the rules were set by eye on it. Reword the SOP 3 answer to "directionally consistent but not significant; the 2018–2022 agreement is in-sample and expected". Remove or qualify "gates help on 4h, chance on 1h" (pp.47, 50). | SOP 3 p.42, p.45; pp.47, 50 | [S] | 20 min |
| M18 | **Explain the jargon on first use, in the body, not the abstract.** Short (betting on a fall), 1x / unlevered, perpetual futures, bootstrap, Holm correction, data leakage, and gate ("one condition that must be true before a trade is allowed"). In Figure 11, gloss "time-scaled ×4" and note the log x-axis. | Sec B/D/F; SOP 3 p.13; Fig. 11 | [D] | 30 min |
| M19 | **Put the responsible-use and "is this gambling?" answer where judges look.** Add two sentences to the Summary (p.54) and the board: not advice, high risk, BSP-regulated VASPs; and "The study tested whether fixed, published rules beat simple saving; it found they did not, which is the opposite of a get-rich claim." Mention that the Philippine SEC also regulates crypto-asset service providers. | Summary p.54; board; p.12 | [D], [I] | 20 min |

### Minor (all quick)

| # | Fix | Raised by |
|---|---|---|
| m1 | Use one forward-test end date. Table 7 has 2026-07-31; p.45 and Table 16 say August / Aug 7. Name the 2026-08-07 lockbox run separately from the forward test. | [S], [D], [I] |
| m2 | Call out Figures 6, 7, 8, 9 and 10 and Table 2 in the body text. | [I] |
| m3 | Figure 7: fix "Datc", use "Combined strategy" in the legend, and say the weekly arm starts near $0 because its $10,000 goes in over 210 weeks. | [D] |
| m4 | DCA end bar. The Figure 7 caption already says the weekly arm's value is measured at its final contribution bar. Repeat that one line in the Table 9 note so it sits beside $22,312.94. This is a disclosure only; the number stays as published (user decision). | [I] (downgraded [H], see §3) |
| m5 | Close the Conclusions with the plain result instead of "historically observed, directionally robust return edge" (follows from M4). | [D], [S] |
| m6 | Board: lead the third box with "Worst drop: −27.85% → −23.18%" and give Sharpe as "smoother ride (0.558 → 0.632)". Fix "each dot switches filters off" (the OB quality ≥1 dot adds one). Give the forward-test −3.45% its own box or line. | [D], [I] |
| m7 | Explain why a Filipino family should care: replace the SDG 11 clause with a financial-literacy line (young investors see trading screenshots; this shows a full system against simple saving). | [D] |
| m8 | Add "Can a Rule-Based Bitcoin Strategy Beat Simply Buying Every Week?" as the subtitle under CIPHER. | [D] |
| m9 | Soften the SOP's "reacts to large institutional order flow" to "price structure that practitioners attribute to large participants". Cite LuxAlgo as "as implemented by LuxAlgo (CC BY-NC-SA)". | [Q], [I] |
| m10 | Fix wording: "+30.3065% vs +30.3064%" are the same quantity (the observed sum vs C1's rounded rows); say so. Round CI bounds to 2 decimals. Print −0.002, not "−0.00". Report funding as 0.175 / 0.287 / 0.112 so the parts add up. | [S], [I] |
| m11 | Fix wording: "exactly nine quantities" → "nine core statistical procedures". "UTC+8 everywhere" → "except the 1-hour data". "after every change to the code" → "after every change to the strategy code". "closest to the full rule" → "closest among the gate removals, by average". | [S], [I] |
| m12 | Tables 5–6: change "edge concentrated in bull" to "observed more often in bull" and state when the 40% / 12% regime thresholds were chosen. Clopper–Pearson CIs are optional (recompute). | [S] |
| m13 | Write "conservative" for slippage or "realistic" for the 0.20% total, not both. Note that 0.05% per side is optimistic for stop exits in fast candles, and that significance needs all-in cost below about 0.12%. Derive that threshold from Table 4's flipped trades, not a new estimate. | [S], [Q] |
| m14 | Explicitly state the fill assumption: entry at the signal candle's close. | [Q] |
| m15 | Tables 13–14: add "assuming independence" to the 1 − 0.95⁹ sentence, and note that the samples share trades so the test is conservative. | [S] |
| m16 | RQ3: in Sec F name the 1h test's H₀: μ_net ≤ 0 and its threshold as "pre-registered test (not a study hypothesis)". The structure is unchanged. | [S] |
| m17 | Rename "share of resample means ≤ 0" to "bootstrap one-sided p (percentile method)". | [S] |
| m18 | Add the Hypotheses heading to the TOC (re-render and re-check pages). Define "SOP" on first use. | [I] |
| m19 | Appendix A: point readers to the 27-trade file (`experimental/results/oos_trades_A0_rules.csv`), not `artifacts/trades_default_view.csv`, which holds the 25-trade OB ≥ 1 view. | [I] |
| m20 | Citations: Nakamoto (2008) cannot support "most traded by value and volume", so add a market-data source. Lv et al. (2017), Díaz & Escribano (2020) and Brolley & Cimon (2020) are weak for the claims they support; reframe them or drop them. Figure 1: add the 1h holdout window. | [I] |

---

## 3. Merges, conflicts and discards

**Merged duplicates.**
- Realized-only equity: [S]5 and [Q]5 → M8.
- Cash-sleeve control: [S]6, [Q]6 and [D]6 → M9.
- Forward-test date: [S]18, [D]10 and [I] → m1.
- Abstract: [D]2 and [I] → M10.
- Power: [S]15 and [Q]13 → M15.
- Bootstrap CI: [S]1 and [Q]11 → M4.
- "Exactly nine": [S]17 and [I] → m11.
- SMC wording: [Q]12 and [I] → m9.
- Responsible use: [D]8 and the SEC note in [I] → M19.

**Conflicts resolved.**
- **Figure 8 / Table 12: [D] said the values mismatch; [I] marked Table 12 PASS.** [D] is right. [I] checked the table against the JSON but not the figure image. The head judge viewed the embedded image and confirmed the stale values (M1).
- **DCA end bar: [I] called it "left silent".** The Figure 7 caption already discloses it ("drawn to its final contribution bar, which is where its reported final value is measured"). Downgraded to minor (m4). The number stays $22,312.94, as the user decided. The fix is one disclosure line, not a change.
- **Clarity vs rigor in the abstract: [D] wants plain glosses; [I] wants ≤250 words.** Glosses go in the body (M18), and the abstract only gets shorter and result-first (M10). Rigor is not traded for clarity.
- **H₁ wording: [D] wants plain language; [S] wants "inconclusive".** Use "not supported (inconclusive at this sample size)". It keeps the stated decision rule, does not imply that no edge exists, and is still plain.
- **Board third box: [D] wants drawdown instead of Sharpe.** Accepted, but both numbers carry M8's realized-equity caveat. The board should not present either as more certain than the table does.
- **[D]'s suggested lines ("the simple habit beat the complicated system", "opposite of a get-rich claim").** Accepted. Both are factual for this window and claim nothing beyond it.
- **[S]4 offered "run a paired Sharpe-difference test".** Only the wording fix is required (M3). A new test would be a new number and must go through code and the changelog. It is optional and not needed for regionals.

**Discarded (one line each).**
- [Q]8, add XIRR/CAGR and an end-date sensitivity: a new set of metrics for a comparison already decisive in both directions. Keep it as an interview answer, not a revision.
- [Q]14, rerun Sharpe with a T-bill risk-free rate: Rf = 0 is already disclosed in Limitation 5. A new rate needs a data source and recompute, and helps little at regionals.
- [S]10, re-bootstrap only the trades admitted by relaxed gates: the current test is conservative, so it cannot overstate the gates. Keep only the wording (m15).
- [S]14, show L = 2 and L = 5 give the same result: low value at regionals once M4 reports the stationary result. Keep the rename (m17).
- [I], renumber Framework subsections to avoid the A–F clash with appendices: many cross-references would change for a cosmetic gain, which risks new errors.
- [I], BSP "15% → 10% investment uptake" unverified: the judge could not check it offline. It is not a finding; the students should simply confirm it against the BSP FIS report.
- [Q]2 severity "major": downgraded in effect. The unreachable breakeven rule changes no number. It stays in the major list (M12) only because Table 1 misdescribes the frozen rules, which a judge will notice.

---

## 4. Top 10 interview questions and model answers

These answers assume the fixes above are made. Where an answer quotes a number that is not yet
in the paper (M4's net stationary CI), the students should say it only after the number has been
recomputed through the project code.

1. **"Your strategy lost to weekly buying. Isn't the project a failure?"** [D]
   *No. The question was whether the rules beat weekly buying, and the honest answer is that they did not: $13,418 against $22,313 from the same $10,000. That is a useful result for an ordinary saver, because on this period the simple habit beat the complicated system.*

2. **"Your win rate is 70%. Why do you say H₁ is not supported?"** [S][D]
   *Before costs, 19 wins out of 27 would happen by coin-flipping only about 26 times in 1,000. After a 0.20% cost per trade, two small winners become losers, and 17 out of 27 is no longer unusual (p = 0.124). We judge H₁ after costs because that is what a real trader keeps.*

3. **"After costs, does your own stationary bootstrap still exclude zero?"** [S]
   *No. Once we allow for trades that cluster in time, the after-cost interval for average return reaches zero. So we only say the trades were positive before costs. We do not claim a proven edge after costs.*

4. **"Isn't the 30% blend better just because 97% of the strategy sleeve is cash?"** [S][Q]
   *That is a fair challenge, and we did not run a cash-only control, so we cannot separate the two. What we can say is that the blend was smoother and fell less in this window. We do not claim the strategy caused that.* (If M9's control is run, answer with its result instead.)

5. **"Your stop is only checked at the close. Trade 2624 lost 4.65% with a stop 2.68% away. Which would you really have lost?"** [Q]
   *With a real stop order resting in the market, the loss would have been near the stop, about 2.7% plus slippage. Our test only checks at the close, so it books the close price. We list this in Limitation 1 as a bias in both directions: price can briefly poke through a stop without stopping us out, and big moves past the stop book bigger losses.*

6. **"Table 1 lists a 2.0×ATR breakeven rule, but the 1.8×ATR exit is checked first. Can it ever fire?"** [Q]
   *No, and we disclose that. The 1.8×ATR exit always closes the trade first, so the breakeven rule never acts. We kept the rule as written because the rules were frozen, and it changes none of our results.*

7. **"What does your p-value actually mean?"** [S]
   *It is the chance of getting 19 or more wins out of 27 if each trade were a fair coin flip. It does not measure profit by itself; the average return per trade does that.*

8. **"With only 27 trades, could you have detected a real edge at all?"** [S][Q]
   *Not easily. With 27 trades our test only had a modest chance of catching a true 60–70% win rate (power figures in Limitations). That is why we say "not supported" means inconclusive, not proof that there is no edge.*

9. **"You used AI tools. What did you do yourselves?"** [I]
   *We used an AI assistant for coding, statistics checks and editing, and we say so in the paper. We designed the question and the rules, chose the tests, checked the results by hand in Appendices C and D, and wrote the conclusions. Every number traces to a named function and result file.*

10. **"This is futures trading and short-selling. How is this not gambling, and could a student legally do it here?"** [D][Q]
    *We did not trade real money; we tested fixed, published rules on past prices to see if they beat simple saving, and they did not. That is the opposite of a get-rich claim. In the Philippines crypto platforms are regulated by the BSP and the SEC; this is not investment advice, and crypto carries a high risk of loss.*

---

## 5. Expected rubric gain if the fixes are made

| Rubric row | Now | After fatal + major fixes | Main fixes |
|---|---:|---:|---|
| Research problem & creativity (20) | 15 | 16 | m8 subtitle, m9 SMC wording |
| Scientific method & design (25) | 16 | 19–21 | M6, M7, M11, M12, M14 (disclosures); +1–2 more if M9's cash control and M8's mark-to-market are recomputed |
| Data analysis & interpretation (20) | 13 | 16–17 | M1, M2, M3, M4, M5, M15, M17 |
| Thoroughness & integrity (10) | 6 | 8–9 | F1, F2, M7, m4 |
| Clarity & presentation (15) | 10 | 12–13 | M10, M18, m1–m3, m6 |
| Relevance & impact (10) | 7 | 8 | M19, m7 |
| **Total** | **67** | **≈79–84** | |

Highest return for the time spent: F1 and F2 (they block judging outright), then M1, M2, M3, M5,
M13, M16 (about an hour together), then M4, M7, M8, M9 (disclosure versions), and M10.

---

## 6. Notes for the project record

- **Newly found code issue (M12), reported, not fixed.** `ATR_MULT_BREAKEVEN = 2.0` can never take
  effect, because `_check_long_exit_conditions()` / `_check_short_exit_conditions()` return on the
  `ATR_MULT_EXIT = 1.8` move exit first. No reported number depends on it. Per CLAUDE.md it needs
  review before anything is changed. The strategy logic must stay as is (frozen rules); the
  expected fix is disclosure only.
- The (6) revision missed Figure 8 when Table 12 was recomputed (M1). The changelog's "no
  superseded values remain" check covered document text and OMML, not text inside images.
- Verified by the head judge: Figure 8 image values; Figure 7 caption; the breakeven ordering;
  trade 2624 (−4.65% vs a 2.68% stop) and 3947; the spot klines source; the PREREGISTRATION
  "Status: EXPLORATORY" header; zero AI mentions; the abstract text; the Spearman sentence; the p-value
  definition; the "single observation" sentence; the Fang et al. usage; the sizing contradiction;
  and the net stationary-bootstrap CI (three seeds).
