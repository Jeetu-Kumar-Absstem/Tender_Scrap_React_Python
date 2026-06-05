// server/index.ts
import express, { Request, Response } from 'express'
import cors from 'cors'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT_DIR  = path.resolve(__dirname, '..')

const app  = express()
const PORT = process.env.PORT ?? 8000

// ─── CORS — allow all origins (safe for this app, no auth cookies) ────────────
app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type'],
}))

app.options('*', cors()) // handle preflight for all routes

app.use(express.json())

// ─── Run state (in-memory) ───────────────────────────────────
interface RunState {
  running:     boolean
  started_at:  string | null
  last_result: {
    success:     boolean
    finished_at: string
    exit_code:   number
    status:      'completed' | 'failed' | 'interrupted'
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

app.get('/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() })
})

app.get('/api/status', (_req: Request, res: Response) => {
  res.json(state)
})

app.post('/api/run', (_req: Request, res: Response) => {
  if (state.running) {
    res.status(409).json({ detail: 'Pipeline already running' })
    return
  }

  state.running    = true
  state.started_at = new Date().toISOString()
  state.last_result = null

  const isWindows  = process.platform === 'win32'
  const venvPython = isWindows
    ? path.join(ROOT_DIR, 'venv', 'Scripts', 'python.exe')
    : path.join(ROOT_DIR, 'venv', 'bin', 'python')

  const pythonExe = (() => {
    try {
      const fs = require('fs')
      return fs.existsSync(venvPython) ? venvPython : (isWindows ? 'python' : 'python3')
    } catch {
      return isWindows ? 'python' : 'python3'
    }
  })()

  console.log(`[server] Starting pipeline with: ${pythonExe}`)
  console.log(`[server] Working dir: ${ROOT_DIR}`)

  activeProcess = spawn(
    pythonExe,
    ['-m', 'scraper.pipeline'],
    {
      cwd:   ROOT_DIR,
      env:   process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  activeProcess.stdout?.on('data', (chunk: Buffer) => {
    process.stdout.write(`[pipeline] ${chunk.toString()}`)
  })
  activeProcess.stderr?.on('data', (chunk: Buffer) => {
    process.stderr.write(`[pipeline:err] ${chunk.toString()}`)
  })

  activeProcess.on('close', (code: number | null) => {
    const success = code === 0
    console.log(`[server] Pipeline finished. Exit code: ${code}`)
    state.running     = false
    state.last_result = {
      success,
      exit_code:   code ?? -1,
      finished_at: new Date().toISOString(),
      status:      success ? 'completed' : 'failed',
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
      status:      'failed',
      error:       err.message,
    }
    activeProcess = null
  })

  res.json({
    message:    'Pipeline started',
    started_at: state.started_at,
    python:     pythonExe,
  })
})

app.post('/api/stop', (_req: Request, res: Response) => {
  if (!state.running || !activeProcess) {
    res.status(400).json({ detail: 'No pipeline running' })
    return
  }
  activeProcess.kill('SIGTERM')
  state.running = false
  state.last_result = {
    success:     false,
    exit_code:   -1,
    finished_at: new Date().toISOString(),
    status:      'interrupted',
  }
  res.json({ message: 'Pipeline interrupted' })
})

app.listen(PORT, () => {
  console.log(`✅ TenderPulse server running at http://localhost:${PORT}`)
  console.log(`   POST /api/run    → trigger pipeline`)
  console.log(`   GET  /api/status → check status`)
  console.log(`   GET  /health     → health check`)
})