// server/index.ts
// ─────────────────────────────────────────────────────────────
// Express server that replaces FastAPI.
// Triggers python -m scraper.pipeline as a child process.
// Runs in the same Node.js ecosystem as your React/TS app.
//
// Start:  npm run server
// ─────────────────────────────────────────────────────────────

import express, { Request, Response } from 'express'
import cors from 'cors'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT_DIR  = path.resolve(__dirname, '..')   // tenderpulse/

const app  = express()
const PORT = process.env.PORT ?? 8000

// ─── CORS — allow dev & production origins ────────────────────
const allowedOrigins = [
  'http://localhost:5173',
  'http://localhost:5174',
  'http://localhost:5175',
  'http://localhost:4173',
  process.env.FRONTEND_URL || 'https://tender-scrap-react-python.vercel.app',
]

app.use(cors({
  origin: allowedOrigins,
  credentials: true,
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type'],
}))

app.use(express.json())

// ─── Run state (in-memory) ───────────────────────────────────
interface RunState {
  running:     boolean
  started_at:  string | null
  last_result: {
    success:     boolean
    finished_at: string
    exit_code:   number
    error?:      string
  } | null
}

const state: RunState = {
  running:     false,
  started_at:  null,
  last_result: null,
}

let activeProcess: ChildProcess | null = null

// ─── Routes ──────────────────────────────────────────────────

// Health check
app.get('/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() })
})

// Get current pipeline status
app.get('/api/status', (_req: Request, res: Response) => {
  res.json(state)
})

// Trigger pipeline
app.post('/api/run', (_req: Request, res: Response) => {
  if (state.running) {
    res.status(409).json({ detail: 'Pipeline already running' })
    return
  }

  state.running    = true
  state.started_at = new Date().toISOString()
  state.last_result = null

  // Detect Python executable (venv or system)
  const isWindows = process.platform === 'win32'
  const venvPython = isWindows
    ? path.join(ROOT_DIR, 'venv', 'Scripts', 'python.exe')
    : path.join(ROOT_DIR, 'venv', 'bin', 'python')

  // Use venv python if it exists, otherwise fall back to system python
  const pythonExe = (() => {
    try {
      const fs = require('fs')    // eslint-disable-line @typescript-eslint/no-require-imports
      return fs.existsSync(venvPython) ? venvPython : (isWindows ? 'python' : 'python3')
    } catch {
      return isWindows ? 'python' : 'python3'
    }
  })()

  console.log(`[server] Starting pipeline with: ${pythonExe}`)
  console.log(`[server] Working dir: ${ROOT_DIR}`)

  // Spawn pipeline as child process
  activeProcess = spawn(
    pythonExe,
    ['-m', 'scraper.pipeline'],
    {
      cwd:   ROOT_DIR,      // must run from project root
      env:   process.env,   // inherits .env loaded by dotenv
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  // Stream pipeline logs to server console
  activeProcess.stdout?.on('data', (chunk: Buffer) => {
    process.stdout.write(`[pipeline] ${chunk.toString()}`)
  })
  activeProcess.stderr?.on('data', (chunk: Buffer) => {
    process.stderr.write(`[pipeline:err] ${chunk.toString()}`)
  })

  // On finish — update state
  activeProcess.on('close', (code: number | null) => {
    const success = code === 0
    console.log(`[server] Pipeline finished. Exit code: ${code}`)
    state.running     = false
    state.last_result = {
      success,
      exit_code:   code ?? -1,
      finished_at: new Date().toISOString(),
    }
    activeProcess = null
  })

  activeProcess.on('error', (err: Error) => {
    console.error(`[server] Failed to start pipeline: ${err.message}`)
    state.running     = false
    state.last_result = {
      success:     false,
      exit_code:   -1,
      finished_at: new Date().toISOString(),
      error:       err.message,
    }
    activeProcess = null
  })

  // Respond immediately — pipeline runs in background
  res.json({
    message:    'Pipeline started',
    started_at: state.started_at,
    python:     pythonExe,
  })
})

// Kill running pipeline (emergency stop)
app.post('/api/stop', (_req: Request, res: Response) => {
  if (!state.running || !activeProcess) {
    res.status(400).json({ detail: 'No pipeline running' })
    return
  }
  activeProcess.kill('SIGTERM')
  state.running = false
  res.json({ message: 'Pipeline stopped' })
})

// ─── Start ───────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`✅ TenderPulse server running at http://localhost:${PORT}`)
  console.log(`   POST /api/run    → trigger pipeline`)
  console.log(`   GET  /api/status → check status`)
  console.log(`   GET  /health     → health check`)
})
