// src/lib/pipelineApi.ts
// Calls the FastAPI backend to trigger/check pipeline

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface PipelineStatus {
  running: boolean
  started_at: string | null
  last_result: {
    exit_code: number
    finished_at: string
    success: boolean
    status?: 'completed' | 'failed' | 'interrupted'
    error?: string
  } | null
}

// Custom error for 409 — pipeline already running
export class PipelineAlreadyRunningError extends Error {
  constructor() {
    super('Pipeline is already running')
    this.name = 'PipelineAlreadyRunningError'
  }
}

// Helper: fetch with explicit timeout (avoids browser's ~2s default on slow servers)
async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 60000): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    return res
  } finally {
    clearTimeout(timer)
  }
}

// Trigger the pipeline — 60s timeout to allow Render free tier cold start (~30-50s)
export async function triggerPipeline(): Promise<{ message: string; started_at: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/run`, { method: 'POST' }, 60000)
  if (res.status === 409) throw new PipelineAlreadyRunningError()
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// Status check — 10s is plenty once the server is awake
export async function getPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetchWithTimeout(`${API_BASE}/api/status`, {}, 10000)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// Stop the pipeline — 10s timeout
export async function stopPipeline(): Promise<{ message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/stop`, { method: 'POST' }, 10000)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}