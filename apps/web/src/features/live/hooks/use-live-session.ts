'use client'

import { useCallback, useEffect, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { env } from '@/config/env'

type SessionState = {
  running: boolean
  queue_depth?: number
  segment_id?: string
  remaining_seconds?: number
}

export function useLiveSession() {
  const [state, setState] = useState<SessionState>({ running: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/state`)
      if (res.ok) {
        setState(await res.json())
      }
    } catch {
      // backend not yet reachable
    }
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
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/start`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = (data as { detail?: unknown }).detail
        const msg = typeof detail === 'string' ? detail : 'Failed to start'
        setError(msg)
        toast.error(msg)
      } else {
        setState(data)
      }
    } catch {
      setError('Cannot reach backend')
      toast.error('Cannot reach backend')
    } finally {
      setLoading(false)
    }
  }, [])

  const stop = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/stop`, {
        method: 'POST',
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = (data as { detail?: unknown }).detail
        const msg = typeof detail === 'string' ? detail : 'Failed to stop'
        setError(msg)
        toast.error(msg)
      } else {
        setState(data)
      }
    } catch {
      setError('Cannot reach backend')
      toast.error('Cannot reach backend')
    } finally {
      setLoading(false)
    }
  }, [])

  return { state, loading, error, start, stop }
}
