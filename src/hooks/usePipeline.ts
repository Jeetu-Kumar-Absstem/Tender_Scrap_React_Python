// src/hooks/usePipeline.ts
import { useState, useEffect, useCallback } from 'react'
import { triggerPipeline, getPipelineStatus, type PipelineStatus } from '../lib/pipelineApi'

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

  const trigger = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await triggerPipeline()
      await fetchStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [fetchStatus])

  return {
    status,
    error,
    loading,
    isRunning: status?.running ?? false,
    trigger,
  }
}
