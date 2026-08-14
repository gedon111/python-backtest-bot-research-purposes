# dashboard-v2

React + TypeScript + Vite frontend for the project's terminal-style
backtest dashboard. Talks to the Python backend (`research_analysis.py
--serve` at the repo root) via `/api/*` and `/artifacts/*`, proxied through
Vite in dev mode (see `vite.config.ts`). See the root `README.md` for the
full pipeline (data fetch -> indicators -> SMC order blocks -> trade
simulation -> artifact export).

## Dev mode (hot reload)

```bash
npm install
npm run dev
```

This starts the Python backend automatically (`research_analysis.py --serve
--no-browser`, from the repo root) if one isn't already listening on
`127.0.0.1:8765`, waits for it to be ready, then starts Vite at
`http://localhost:5173` with hot reload. Ctrl+C stops both. The orchestration
lives in `scripts/dev.mjs`.

If you already have a backend running yourself (e.g. `python Run_All.py` or
`python research_analysis.py --serve` in another terminal, or you're
iterating on backend code and don't want it restarted), use:

```bash
npm run dev:vite-only
```

which just runs Vite against whatever backend is already up.

## Build

```bash
npm run build
```

Type-checks (`tsc -b`) then builds to `dist/`, served by
`research_analysis.py`'s `DashboardRequestHandler` under `/dashboard/` in
production (`python Run_All.py` builds this automatically if stale).

## Other scripts

- `npm run typecheck` -- `tsc -b --noEmit`
- `npm run lint` -- `oxlint`
- `npm run preview` -- preview a production build locally
