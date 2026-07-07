// src/hooks/usePipeline.ts
import { useState, useEffect, useCallback } from 'react'
import {
  triggerPipeline,
  getPipelineStatus,
  stopPipeline,
  PipelineAlreadyRunningError,
  type PipelineStatus,
} from '../lib/pipelineApi'

const KEEP_ALIVE_INTERVAL_MS = 10 * 60 * 1000 // 10 minutes — prevents Render free tier from sleeping

export function usePipeline() {
  const [status, setStatus]   = useState<PipelineStatus | null>(null)
  const [error, setError]     = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // True once the first status fetch has resolved (success or failure).
  // Until then we don't know if a pipeline run is already in progress, so
  // trigger() must refuse to fire — otherwise a click (or any caller) during
  // that initial window can race ahead of isRunning and hit a 409.
  const [statusLoaded, setStatusLoaded] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getPipelineStatus()
      setStatus(s)
    } catch {
      // API server not running — show offline state
      setStatus(null)
    } finally {
      setStatusLoaded(true)
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

  const isRunning = status?.running ?? false

  const trigger = useCallback(async () => {
    // Guard at the call site: refuse to fire if status hasn't loaded yet
    // (we don't know real running state), or if we already know it's
    // running/loading (e.g. double click before the disabled prop re-renders).
    if (!statusLoaded || isRunning || loading) return

    setLoading(true)
    setError(null)
    try {
      await triggerPipeline()
      await fetchStatus()
    } catch (e: any) {
      if (e instanceof PipelineAlreadyRunningError) {
        setError('Pipeline is already running.')
        await fetchStatus() // resync so isRunning reflects backend truth
      } else if (e.name === 'AbortError') {
        setError('Server is waking up, please try again in a moment.')
      } else {
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }, [fetchStatus, isRunning, loading, statusLoaded])

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
    isRunning,
    statusLoaded,
    trigger,
    stop,
  }
}