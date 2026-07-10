// src/hooks/useTypeC.ts
import { useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

interface TypeCRunStatus {
  running: boolean
  started_at: string | null
  last_result: {
    success: boolean
    finished_at: string
    exit_code: number
    status: 'completed' | 'failed' | 'interrupted'
    error?: string
  } | null
}

interface TypeCStatusResponse {
  typeD?: TypeCRunStatus
  typeC?: TypeCRunStatus
  pipeline?: TypeCRunStatus
}

async function fetchTypeCStatus(): Promise<TypeCStatusResponse> {
  const res = await fetch('/api/status')
  if (!res.ok) throw new Error('Failed to fetch status')
  return res.json()
}

export function useTypeC() {
  const queryClient = useQueryClient()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['type-c-status'],
    queryFn: fetchTypeCStatus,
    refetchInterval: (query) => {
      // Refetch every 2 seconds while running
      const data = (query as any).state?.data as TypeCStatusResponse | undefined
      if (data?.typeC?.running) {
        return 2000
      }
      return false
    },
  })

  const isRunning = status?.typeC?.running ?? false

  const trigger = useCallback(async () => {
    if (isRunning) {
      setError('Type C scraper is already running')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/run-type-c', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || data.message || 'Failed to start Type C scraper')
      }

      // Refetch status immediately
      await refetchStatus()

      // Poll for completion
      const pollInterval = setInterval(async () => {
        const statusRes = await fetch('/api/status')
        if (statusRes.ok) {
          const data = await statusRes.json()
          if (!data.typeC?.running) {
            clearInterval(pollInterval)
            setLoading(false)
            // Invalidate cache so data refreshes
            queryClient.invalidateQueries({ queryKey: ['gem-tenders'] })
          }
        }
      }, 3000)

      // Safety: clear interval after 5 minutes
      setTimeout(() => clearInterval(pollInterval), 300000)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setLoading(false)
    }
  }, [isRunning, refetchStatus, queryClient])

  const stop = useCallback(async () => {
    try {
      const res = await fetch('/api/stop-type-c', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || data.message || 'Failed to stop Type C scraper')
      }

      await refetchStatus()
      setLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop scraper')
    }
  }, [refetchStatus])

  return {
    isRunning,
    loading,
    error,
    status: status?.typeC ?? null,
    trigger,
    stop,
    refetchStatus,
  }
}