import { useTrades } from '../../api/hooks';

/**
 * Structural stub for gui.html's stats-tab ("Research Statistics & Methodology
 * Synthesis", gui.html:328+). All of its subsections — including the ones
 * covering bootstrap/DCA/regime-breakdown analysis — are computed client-side
 * from /api/trades plus the 4 core artifacts (see e.g. renderOrthogonalCriteria,
 * gui.js:2009+), NOT from separate analysis/*.json files; analysis/*.py scripts
 * produce stdout-only reports, no JSON. Real computation/rendering is Phase 4.
 *
 * Note for whoever ports this tab's content: gui.html's hardcoded "Corrected FVG
 * Population" badge still shows the pre-fix 47.57% / 362 figure. CLAUDE.md's
 * Known Bug #3 discloses the corrected 33.2% / 253 (commit cb4ed93) — update the
 * number when porting, don't carry the stale one forward.
 */
export function StatsTab() {
  const trades = useTrades();

  return (
    <section id="stats-tab" className="tab-pane">
      <h2>Research Statistics & Methodology Synthesis (stub)</h2>
      {trades.loading && <p>Loading trades...</p>}
      {trades.error && <p role="alert">/api/trades: {trades.error.message}</p>}
      {trades.data && <p>{trades.data.length} trades fetched from /api/trades.</p>}
    </section>
  );
}
