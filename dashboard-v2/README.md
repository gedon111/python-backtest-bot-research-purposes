# dashboard-v2

React + TypeScript + Vite frontend for the project's terminal-style
backtest dashboard. Talks to the Python backend (`export_gui_data.py` at the
repo root) via `/api/*` and `/artifacts/*`, proxied through Vite in dev mode
(see `vite.config.ts`). See the root `README.md` for the full pipeline
(data fetch -> indicators -> SMC order blocks -> trade simulation ->
artifact export).

## Dev mode (hot reload)

```bash
npm install
npm run dev
```

This starts the Python backend automatically (`export_gui_data.py
--no-browser`, from the repo root) if one isn't already listening on
`127.0.0.1:8765`, waits for it to be ready, then starts Vite at
`http://localhost:5173` with hot reload. Ctrl+C stops both. The orchestration
lives in `scripts/dev.mjs`.

If you already have a backend running yourself (e.g. `python
Run_Dashboard.py` or `python export_gui_data.py` in another terminal, or
you're iterating on backend code and don't want it restarted), use:

```bash
npm run dev:vite-only
```

which just runs Vite against whatever backend is already up.

## Build

```bash
npm run build
```

Type-checks (`tsc -b`) then builds to `dist/`, served by
`export_gui_data.py`'s `SilentHandler` under `/dashboard/` in production
(`python Run_Dashboard.py` builds this automatically if stale).

## Other scripts

- `npm run typecheck` -- `tsc -b --noEmit`
- `npm run lint` -- `oxlint`
- `npm run preview` -- preview a production build locally
