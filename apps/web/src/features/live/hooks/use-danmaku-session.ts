'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

type DanmakuSessionState = {
  running: boolean
  buffer_size?: number
}

export function useDanmakuSession() {
  const [state, setState] = useState<DanmakuSessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    const res = await apiFetch<DanmakuSessionState>('live/danmaku/state', { silent: true })
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
        const res = await apiFetch<DanmakuSessionState>(path, {
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

  const start = useCallback(() => transition('live/danmaku/start', 'Failed to start danmaku', {}), [transition])
  const stop = useCallback(() => transition('live/danmaku/stop', 'Failed to stop danmaku'), [transition])

  return { state, loading, error, start, stop }
}
