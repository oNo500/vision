'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'

export type Strategy = 'immediate' | 'intelligent'

export function useStrategy() {
  const [strategy, setStrategyState] = useState<Strategy>('immediate')

  useEffect(() => {
    fetch(`${env.NEXT_PUBLIC_API_URL}/live/strategy`)
      .then((r) => r.json())
      .then((d: { strategy: Strategy }) => setStrategyState(d.strategy))
      .catch(() => {})
  }, [])

  const setStrategy = useCallback(async (s: Strategy) => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/strategy`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ strategy: s }),
      })
      if (res.ok) {
        const data = await res.json() as { strategy: Strategy }
        setStrategyState(data.strategy)
      }
    } catch { /* ignore */ }
  }, [])

  return { strategy, setStrategy }
}
