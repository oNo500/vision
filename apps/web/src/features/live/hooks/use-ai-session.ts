'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

type AiSessionState = {
  running: boolean
  tts_queue_depth?: number
  urgent_queue_depth?: number
  tts_speaking?: boolean
  llm_generating?: boolean
  segment_id?: string
  remaining_seconds?: number
  strategy?: string
}

export function useAiSession() {
  const [state, setState] = useState<AiSessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    const res = await apiFetch<AiSessionState>('live/session/state', { silent: true })
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
        const res = await apiFetch<AiSessionState>(path, {
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

  const start = useCallback(() => transition('live/session/start', 'Failed to start', {}), [transition])
  const stop = useCallback(() => transition('live/session/stop', 'Failed to stop'), [transition])

  return { state, loading, error, start, stop }
}
