// src/hooks/useLogs.ts
import { useState, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface LogLine {
  ts:   string
  type: 'out' | 'err' | 'sys'
  text: string
}

export function useLogs(enabled: boolean) {
  const [logs, setLogs] = useState<LogLine[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!enabled) return

    const es = new EventSource(`${API_BASE}/api/logs`)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const line: LogLine = JSON.parse(e.data)
        setLogs(prev => {
          // clear on new run signal
          if (line.type === 'sys' && line.text.startsWith('▶ Pipeline started')) {
            return [line]
          }
          return [...prev.slice(-299), line]
        })
      } catch {}
    }

    es.onerror = () => {
      // SSE auto-reconnects; ignore transient errors
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [enabled])

  const clear = () => setLogs([])

  return { logs, clear }
}