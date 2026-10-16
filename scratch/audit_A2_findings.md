# Workstream A2 — Dashboard screenshots

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
