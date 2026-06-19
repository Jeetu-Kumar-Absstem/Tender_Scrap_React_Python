// src/hooks/usePipeline.ts
import { useState, useEffect, useCallback } from 'react'
import { triggerPipeline, getPipelineStatus, stopPipeline, type PipelineStatus } from '../lib/pipelineApi'

const KEEP_ALIVE_INTERVAL_MS = 10 * 60 * 1000 // 10 minutes — prevents Render free tier from sleeping

export function usePipeline() {
  const [status, setStatus]   = useState<PipelineStatus | null>(null)
  const [error, setError]     = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getPipelineStatus()
      setStatus(s)
    } catch {
      // API server not running — show offline state
      setStatus(null)
    }
  }, [])

  // Poll every 5s when running
  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Keep-alive ping every 10 minutes to prevent Render free tier cold starts
  useEffect(() => {
    const keepAlive = setInterval(() => {
      getPipelineStatus().catch(() => {}) // silent — just wake the server
    }, KEEP_ALIVE_INTERVAL_MS)
    return () => clearInterval(keepAlive)
  }, [])

  const trigger = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await triggerPipeline()
      await fetchStatus()
    } catch (e: any) {
      if (e.name === 'AbortError') {
        // Render cold start took too long — ask user to retry
        setError('Server is waking up, please try again in a moment.')
      } else {
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }, [fetchStatus])

  const stop = useCallback(async () => {
    setError(null)
    try {
      await stopPipeline()
      await fetchStatus()
    } catch (e: any) {
      if (e.name === 'AbortError') {
        setError('Request timed out. Please try again.')
      } else {
        setError(e.message)
      }
    }
  }, [fetchStatus])

  return {
    status,
    error,
    loading,
    isRunning: status?.running ?? false,
    trigger,
    stop,
  }
}