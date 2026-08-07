import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Production builds are served under /dashboard/ by export_gui_data.py's
  // SilentHandler (translate_path maps /dashboard/* to dashboard-v2/dist/*),
  // alongside /artifacts/* and /api/* at the repo root -- so the built asset
  // URLs need that prefix. `npm run dev` stays at root for convenience (it's
  // never what SilentHandler serves).
  base: command === 'build' ? '/dashboard/' : '/',
  server: {
    proxy: {
      // Forward to the existing local dashboard server (export_gui_data.py's
      // SilentHandler, started via `python export_gui_data.py` or
      // Run_Dashboard.py) so `npm run dev` can be verified against real,
      // running data instead of mocks. Static files are served from the repo
      // root by SimpleHTTPRequestHandler, so /artifacts/* resolves directly.
      '/api': 'http://127.0.0.1:8765',
      '/artifacts': 'http://127.0.0.1:8765',
    },
  },
}))
