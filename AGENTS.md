# Agent instructions

**The instructions for this repository live in [`CLAUDE.md`](./CLAUDE.md). Read
that file. This one holds no rules of its own.**

This file used to be a hand-maintained *copy* of `CLAUDE.md`, and it drifted, as
duplicated instructions do. By 2026-09-21 it was carrying three statements that
had already been verified false and corrected in `CLAUDE.md`:

- that the 40-column trade schema written to Google Sheets includes the numeric
  OB-criteria diagnostics alongside the booleans (11 of those columns are empty
  on the current in-process path);
- that `push_all_thresholds_to_gsheet` is "left defined in Section 3B but no
  longer called" (the function is absent from the codebase entirely);
- that its stale "Quality N" sheets are "actively deleted from the live workbook
  on every push" (there is no `del_worksheet` call anywhere in the repo).

It also had no mention of Section 3C at all. An agent that read this file
instead of `CLAUDE.md` got a wrong picture of the pipeline it was about to
touch, which is worse than having no second file.

So this is now a pointer, deliberately. Do not restore prose here, and do not
copy `CLAUDE.md`'s contents back into it: a second copy cannot be kept in sync
by hand and its only achievement was to be wrong. Put repository instructions
in `CLAUDE.md` alone.
