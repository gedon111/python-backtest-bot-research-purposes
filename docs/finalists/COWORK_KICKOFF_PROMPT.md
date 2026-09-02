# Kickoff prompt for Claude Cowork

Paste everything below the line into Cowork as the first message, after
attaching the files listed in "Files I am attaching".

---

You are helping me finish an ISEF (International Science and Engineering Fair)
science-fair project. I need three things produced, and I want you to **plan
them first and interview me before you write anything.**

## Files I am attaching

1. `HEDGE_Paper_Rebuild_Handoff.md` — a complete, self-contained build
   specification for the research paper. Every number in it has been
   independently recomputed and verified. It is the authority on content,
   structure, statistics, and what is forbidden.
2. `HEDGE_Research_Paper.md` — the current draft. Use it **only** as a source
   for the figure images (base64 blocks at the end) and for prose I may ask you
   to reuse. Where it disagrees with the handoff, the handoff wins.
3. My old research paper from a previous year — the exemplar for **title page
   layout, section formatting, front matter, and general house style.** Match
   its look. Do not copy its content.

## The three deliverables

**A. The research paper.** Built to `HEDGE_Paper_Rebuild_Handoff.md`, in APA
7th edition, formatted to match my old paper's layout conventions.

**B. The ISEF Research Plan / Project Summary.** The separate document that
attaches to the ISEF student forms. It is not the paper and it is not an
abstract — it is its own document with its own required sections. Note the
tense and framing problem and solve it deliberately: the Research Plan is
written as the plan for the investigation, while the paper reports what
happened. The two must describe the same study without contradicting each
other.

**C. A formatting and submission conformance pass.** APA 7th throughout,
plus whatever the current ISEF rules require of these documents.

## Phase 1 — Interview me first. Do not plan silently.

Before you produce the plan, **ask me questions about everything you intend to
do.** I want the plan to reflect my actual idea, not your best guess at it.

Rules for the interview:

- Ask in **grouped batches**, numbered, so I can answer in one pass. Do not
  drip one question at a time.
- For every question, state **your recommended answer and why**, so I can reply
  "defaults" to a whole batch and still get a good result.
- Where a choice would change the shape of the documents, say so explicitly.
- If something is already fixed by the handoff, do not ask me about it — the
  handoff is settled. Ask only about what it leaves open.
- Do not begin drafting any deliverable until I have answered and approved the
  plan.

Cover at minimum these areas, and add any others you find:

**About the fair and the forms**
- Which ISEF category and sub-category I am entering, and whether the plan
  should be tailored to it.
- Whether this is a **continuation / research progression** of my old paper or
  an unrelated new project — this changes which forms I need, so ask directly
  rather than inferring it from the fact that I have an old paper.
- Which affiliated fair I am going through, and whether it imposes rules on top
  of ISEF's (page limits, its own cover sheet, its own deadlines).
- Whether human participants, vertebrate animals, or hazardous biological
  agents are involved. (They are not — this is a computational study on public
  market data — but confirm it with me and then say plainly which forms that
  eliminates and which remain.)
- Whether I need the abstract in the fair's own word-limited form, and what
  that limit is.

**About the Research Plan document**
- What the current ISEF rules require in it, section by section, and how you
  intend to fill each section from this project.
- How to handle the fact that the strategy parameters were **fixed and
  pre-registered before testing** — I think this is a strength and want it
  stated, but tell me where it belongs.
- How the risk-and-safety section should read for a project with no physical,
  biological, or human-subject risk.
- The bibliography requirement and which of the paper's references satisfy it.

**About the paper**
- Anything in the handoff you find ambiguous, underspecified, or internally
  inconsistent — list it before you start, not while drafting.
- How figures should be handled. The handoff says to emit
  `[Figure N placeholder — caption]`; ask me whether I want the actual images
  lifted from `HEDGE_Research_Paper.md` and re-embedded instead.
- How the appendices should be laid out, especially the 27-row trade log.
- Whether the paper and the Research Plan should share wording where they
  overlap, or be written independently.

**About formatting**
- Which specific conventions from my old paper you plan to carry over — title
  page fields, heading levels, spacing, table and figure numbering, running
  head, page numbering, front matter such as acknowledgements or an abstract
  page. List them and let me correct the list.
- Where my old paper's house style conflicts with APA 7th, and which one should
  win in each case. Ask me; do not resolve it on your own.
- Output format: a single document, or paper and Research Plan as separate
  files, and in what file format.

## Phase 2 — Produce the plan

After I answer, give me one written plan covering:

1. The exact section-by-section outline of each deliverable.
2. Every decision my answers settled, stated as a decision.
3. Every open question that remains, with what it blocks.
4. A build order, and what you will hand me at each step.
5. A verification checklist — how you will confirm, before handing anything
   over, that every number matches the handoff, that no prohibited item
   appears, and that the formatting matches my old paper.

Then stop and wait for my approval.

## Hard constraints — these are not negotiable and are not up for discussion

- **Every number comes from `HEDGE_Paper_Rebuild_Handoff.md`, reproduced to the
  decimal places shown.** Do not round, recompute, adjust, or "clean up" any
  figure. If a number looks wrong to you, flag it to me — do not change it.
- **Do not invent data.** If something is not in the handoff, you do not have
  it. Ask me.
- **Honour the prohibition list in the handoff's §18 exactly.** Nothing on it
  may appear in either document, in any form, including as something
  "considered and rejected."
- **Do not add any statistic** beyond the six the handoff names.
- **Do not soften, omit, or reframe any unfavourable result.** The handoff has
  a section listing the results that must be reported plainly — DCA beating the
  strategy on final value, the win-rate significance not surviving realistic
  costs, the negative forward test, the concentration of return in three
  trades. These are load-bearing and stay exactly as stated.
- **Do not change any strategy rule, threshold, parameter, or formula.**
- **Verify ISEF requirements against the current official rules** for the year
  I am competing in, rather than from memory. Rules and form numbers change
  annually. Tell me what you verified and what you are assuming.
