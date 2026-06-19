// src/hooks/useTypeD.ts
import { useState, useEffect, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

interface TypeDStatus {
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

export function useTypeD() {
  const [isRunning, setIsRunning] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<TypeDStatus | null>(null)
  const queryClient = useQueryClient()

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`)
      if (!res.ok) {
        console.error('Status fetch failed:', res.status, res.statusText)
        return
      }
      const data = await res.json()
      
      const typeDStatus = data?.typeD || { running: false, started_at: null, last_result: null }
      setStatus(typeDStatus)
      setIsRunning(typeDStatus.running || false)
    } catch (err) {
      console.error('Error fetching Type D status:', err)
      setStatus({ running: false, started_at: null, last_result: null })
      setIsRunning(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const trigger = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('[useTypeD] Triggering scraper...')
      const res = await fetch(`${API_BASE}/api/run-type-d`, { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      })
      
      console.log('[useTypeD] Response status:', res.status)
      
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || `Server error: ${res.status}`)
      }
      
      const data = await res.json()
      console.log('[useTypeD] Scraper started:', data)
      await fetchStatus()
      queryClient.invalidateQueries({ queryKey: ['tender18-tenders'] })
    } catch (err) {
      console.error('[useTypeD] Error:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchStatus, queryClient])

  const stop = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stop-type-d`, { method: 'POST' })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to stop Type D scraper')
      }
      await fetchStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }, [fetchStatus])

  return { isRunning, loading, error, status, trigger, stop, refetch: fetchStatus }
}