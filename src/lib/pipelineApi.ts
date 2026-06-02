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
    error?: string
  } | null
}

export async function triggerPipeline(): Promise<{ message: string; started_at: string }> {
  const res = await fetch(`${API_BASE}/api/run`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetch(`${API_BASE}/api/status`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
