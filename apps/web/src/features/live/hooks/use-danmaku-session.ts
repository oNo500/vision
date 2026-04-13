'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'

type DanmakuSessionState = {
  running: boolean
  buffer_size?: number
}

export function useDanmakuSession() {
  const [state, setState] = useState<DanmakuSessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/danmaku/state`)
      if (res.ok) setState(await res.json())
    } catch { /* backend unreachable */ }
  }, [])

  useEffect(() => {
    fetchState()
    const id = setInterval(fetchState, 5000)
    return () => clearInterval(id)
  }, [fetchState])

  const start = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/danmaku/start`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      if (!res.ok) setError((data as { detail?: string }).detail ?? 'Failed to start danmaku')
      else setState(data as DanmakuSessionState)
    } catch { setError('Cannot reach backend') }
    finally { setLoading(false) }
  }, [])

  const stop = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/danmaku/stop`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) setError((data as { detail?: string }).detail ?? 'Failed to stop danmaku')
      else setState(data as DanmakuSessionState)
    } catch { setError('Cannot reach backend') }
    finally { setLoading(false) }
  }, [])

  return { state, loading, error, start, stop }
}
