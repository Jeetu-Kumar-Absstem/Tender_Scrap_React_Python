// server/index.ts
import 'dotenv/config'
import express, { Request, Response } from 'express'
import cors from 'cors'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'
import hospitalRoutes from './routes/hospital'


const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT_DIR  = path.resolve(__dirname, '..')

const app  = express()
const PORT = process.env.PORT ?? 8000

const corsOptions = {
  origin: '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type'],
}

// app.use(cors(corsOptions))
// app.options(/.*/, cors(corsOptions))
// app.use(express.json())

app.use(cors(corsOptions))
app.options(/.*/, cors(corsOptions))
app.use(express.json())

// Hospital routes
app.use('/api/hospitals', hospitalRoutes)

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
        '/opt/render/project/src/venv/bin/python',
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
      return candidate
    }
  }
  return 'python3'
}

const PYTHON_EXE = resolvePython()

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

// ─── Log buffer & SSE clients ────────────────────────────────
interface LogLine {
  ts:   string
  type: 'out' | 'err' | 'sys'
  text: string
}

const MAX_LOG_LINES = 300
let logBuffer: LogLine[] = []
const sseClients: Set<Response> = new Set()

function pushLog(type: LogLine['type'], text: string) {
  const lines = text.split('\n').filter(l => l.trim())
  for (const line of lines) {
    const entry: LogLine = { ts: new Date().toISOString(), type, text: line }
    logBuffer.push(entry)
    if (logBuffer.length > MAX_LOG_LINES) logBuffer.shift()
    // broadcast to all SSE clients
    for (const client of sseClients) {
      client.write(`data: ${JSON.stringify(entry)}\n\n`)
    }
  }
}

// ─── Routes ──────────────────────────────────────────────────

app.get('/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), python: PYTHON_EXE })
})

app.get('/api/status', (_req: Request, res: Response) => {
  res.json(state)
})

// SSE endpoint — streams live logs
app.get('/api/logs', (req: Request, res: Response) => {
  res.setHeader('Content-Type',  'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection',    'keep-alive')
  res.flushHeaders()

  // Send buffered history first
  for (const entry of logBuffer) {
    res.write(`data: ${JSON.stringify(entry)}\n\n`)
  }

  sseClients.add(res)

  req.on('close', () => {
    sseClients.delete(res)
  })
})

app.post('/api/run', (_req: Request, res: Response) => {
  if (state.running) {
    res.status(409).json({ detail: 'Pipeline already running' })
    return
  }

  state.running    = true
  state.started_at = new Date().toISOString()
  state.last_result = null
  logBuffer = [] // clear logs on new run
  pushLog('sys', `▶ Pipeline started at ${state.started_at}`)
  pushLog('sys', `  Python: ${PYTHON_EXE}`)

  activeProcess = spawn(
    PYTHON_EXE,
    ['-m', 'scraper.pipeline'],
    {
      cwd:   ROOT_DIR,
      env: {
        ...process.env,
        PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH ?? '',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  activeProcess.stdout?.on('data', (chunk: Buffer) => {
    const text = chunk.toString()
    process.stdout.write(`[pipeline] ${text}`)
    pushLog('out', text)
  })

  activeProcess.stderr?.on('data', (chunk: Buffer) => {
    const text = chunk.toString()
    process.stderr.write(`[pipeline:err] ${text}`)
    pushLog('err', text)
  })

  activeProcess.on('close', (code: number | null) => {
    const success = code === 0
    console.log(`[server] Pipeline finished. Exit code: ${code}`)
    pushLog('sys', `■ Pipeline finished — exit code ${code}`)
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
    pushLog('err', `Failed to start pipeline: ${err.message}`)
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
  pushLog('sys', '⛔ Pipeline stopped by user')
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
  console.log(`   GET  /api/logs   → SSE log stream`)
  console.log(`   GET  /health     → health check`)
})