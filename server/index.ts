// server/index.ts
import express, { Request, Response } from 'express'
import cors from 'cors'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT_DIR  = path.resolve(__dirname, '..')

const app  = express()
const PORT = process.env.PORT ?? 8000

// ─── CORS — allow all origins ─────────────────────────────────
const corsOptions = {
  origin: '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type'],
}

app.use(cors(corsOptions))
app.options(/.*/, cors(corsOptions))

app.use(express.json())

// ─── Resolve Python executable ───────────────────────────────
// Priority: venv (has all pip packages) → system python3 → python
function resolvePython(): string {
  const isWindows = process.platform === 'win32'

  const candidates = isWindows
    ? [
        path.join(ROOT_DIR, 'venv', 'Scripts', 'python.exe'),
        path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe'),
        'python',
      ]
    : [
        path.join(ROOT_DIR, 'venv', 'bin', 'python'),
        path.join(ROOT_DIR, '.venv', 'bin', 'python'),
        '/opt/render/project/src/venv/bin/python',  // Render venv path
        'python3',
        'python',
      ]

  for (const candidate of candidates) {
    if (candidate.startsWith('/') || candidate.includes('\\')) {
      if (fs.existsSync(candidate)) {
        console.log(`[server] Using python: ${candidate}`)
        return candidate
      }
    } else {
      return candidate // system command, trust it exists
    }
  }
  return 'python3'
}

const PYTHON_EXE = resolvePython()

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
  res.json({ status: 'ok', timestamp: new Date().toISOString(), python: PYTHON_EXE })
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

  console.log(`[server] Starting pipeline with: ${PYTHON_EXE}`)
  console.log(`[server] Working dir: ${ROOT_DIR}`)

  activeProcess = spawn(
    PYTHON_EXE,
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
    python:     PYTHON_EXE,
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
  console.log(`   Python: ${PYTHON_EXE}`)
  console.log(`   POST /api/run    → trigger pipeline`)
  console.log(`   GET  /api/status → check status`)
  console.log(`   GET  /health     → health check`)
})