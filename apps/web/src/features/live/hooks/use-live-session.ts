'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

type SessionState = {
  running: boolean
  tts_queue_depth?: number
  segment_id?: string
  remaining_seconds?: number
}

export function useLiveSession() {
  const [state, setState] = useState<SessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    const res = await apiFetch<SessionState>('live/state', { silent: true })
    if (res.ok) setState(res.data)
  }, [])

  useEffect(() => {
    fetchState()
    const id = setInterval(fetchState, 5000)
    return () => clearInterval(id)
  }, [fetchState])

  const transition = useCallback(
    async (path: string, fallback: string, body?: Record<string, unknown>) => {
      setLoading(true)
      setError(null)
      try {
        const res = await apiFetch<SessionState>(path, {
          method: 'POST',
          body,
          fallbackError: fallback,
        })
        if (res.ok) {
          setState(res.data)
        } else {
          setError(fallback)
        }
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  const start = useCallback(() => transition('live/start', 'Failed to start', {}), [transition])
  const stop = useCallback(() => transition('live/stop', 'Failed to stop'), [transition])

  return { state, loading, error, start, stop }
}
