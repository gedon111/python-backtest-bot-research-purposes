// Orchestrator for `npm run dev`: makes sure the Python backend
// (research_analysis.py --serve) is up on 127.0.0.1:8765 before starting Vite, so the
// dev-server proxy in vite.config.ts always has something to talk to.
//
// - If a backend is already reachable (started separately, e.g. via
//   `python research_analysis.py --serve` or `Run_All.py`), it is left alone and
//   never killed on exit.
// - Otherwise this spawns `python research_analysis.py --serve --no-browser` from the
//   repo root, waits for it to become reachable, and kills it on exit.
// - `npm run dev:vite-only` bypasses all of this and runs plain `vite`, for
//   anyone actively iterating on the backend separately.
import { spawn, spawnSync } from 'node:child_process'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dashboardDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = path.resolve(dashboardDir, '..')
const BACKEND_URL = 'http://127.0.0.1:8765/artifacts/manifest.json'
const POLL_INTERVAL_MS = 500
const POLL_TIMEOUT_MS = 180_000

let backendChild = null
let viteChild = null
let cleanedUp = false

function killChild(label, child) {
  if (!child || child.exitCode !== null) return
  console.log(`[dev] stopping ${label}...`)
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'])
  } else {
    child.kill('SIGTERM')
  }
}

function probeBackend(timeoutMs = 1000) {
  return new Promise((resolve) => {
    const req = http.get(BACKEND_URL, { timeout: timeoutMs }, (res) => {
      res.resume()
      resolve(res.statusCode < 400)
    })
    req.on('timeout', () => req.destroy())
    req.on('error', () => resolve(false))
  })
}

function resolvePython() {
  const candidates = process.env.PYTHON ? [process.env.PYTHON] : ['python', 'python3']
  for (const cmd of candidates) {
    const result = spawnSync(cmd, ['--version'], { shell: false })
    if (result.status === 0) return cmd
  }
  return null
}

function startBackend(pythonCmd) {
  console.log(`[dev] starting backend: ${pythonCmd} research_analysis.py --serve --no-browser`)
  const child = spawn(pythonCmd, ['research_analysis.py', '--serve', '--no-browser'], {
    cwd: repoRoot,
    shell: false,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  const prefix = (data) =>
    data
      .toString()
      .split(/\r?\n/)
      .filter(Boolean)
      .forEach((line) => console.log(`[backend] ${line}`))
  child.stdout.on('data', prefix)
  child.stderr.on('data', prefix)
  return child
}

function waitForBackend(deadlineMs) {
  const start = Date.now()
  let lastLog = start
  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (backendChild && backendChild.exitCode !== null) {
        reject(new Error(`backend process exited early with code ${backendChild.exitCode}`))
        return
      }
      if (await probeBackend()) {
        resolve()
        return
      }
      const now = Date.now()
      if (now - start > deadlineMs) {
        reject(new Error(`backend did not become ready within ${Math.round(deadlineMs / 1000)}s`))
        return
      }
      if (now - lastLog > 5000) {
        console.log(`[dev] waiting for backend... (${Math.round((now - start) / 1000)}s)`)
        lastLog = now
      }
      setTimeout(tick, POLL_INTERVAL_MS)
    }
    tick()
  })
}

function cleanup() {
  if (cleanedUp) return
  cleanedUp = true
  // Vite is always ours to stop. The backend is only ours if we spawned it
  // (backendChild stays null when an already-running backend was detected).
  killChild('vite', viteChild)
  killChild('backend', backendChild)
}

function runVite() {
  const viteBin = path.join(dashboardDir, 'node_modules', 'vite', 'bin', 'vite.js')
  const extraArgs = process.argv.slice(2)
  viteChild = spawn(process.execPath, [viteBin, ...extraArgs], {
    cwd: dashboardDir,
    stdio: 'inherit',
  })
  viteChild.on('exit', (code) => {
    cleanup()
    process.exit(code ?? 0)
  })
}

async function main() {
  if (await probeBackend()) {
    console.log('[dev] backend already running on :8765 (not managed by this process)')
    runVite()
    return
  }

  const pythonCmd = resolvePython()
  if (!pythonCmd) {
    console.error(
      '[dev] could not find a working `python`/`python3` on PATH. Set the PYTHON env var to your interpreter, ' +
        'or start the backend yourself and use `npm run dev:vite-only`.',
    )
    process.exit(1)
  }

  backendChild = startBackend(pythonCmd)

  try {
    await waitForBackend(POLL_TIMEOUT_MS)
  } catch (err) {
    console.error(`[dev] ${err.message}`)
    console.error('[dev] aborting. You can also run `npm run dev:vite-only` against a manually-started backend.')
    cleanup()
    process.exit(1)
  }

  console.log('[dev] backend ready')
  runVite()
}

process.on('SIGINT', () => {
  cleanup()
  process.exit(0)
})
process.on('SIGTERM', () => {
  cleanup()
  process.exit(0)
})
process.on('uncaughtException', (err) => {
  console.error(err)
  cleanup()
  process.exit(1)
})
process.on('exit', cleanup)

main()
