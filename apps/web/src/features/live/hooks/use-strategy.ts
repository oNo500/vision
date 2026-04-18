'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

export type Strategy = 'immediate' | 'intelligent'

export function useStrategy() {
  const [strategy, setStrategyState] = useState<Strategy>('immediate')

  useEffect(() => {
    let cancelled = false
    apiFetch<{ strategy: Strategy }>('live/strategy', { silent: true }).then((res) => {
      if (!cancelled && res.ok) setStrategyState(res.data.strategy)
    })
    return () => { cancelled = true }
  }, [])

  const setStrategy = useCallback(async (s: Strategy) => {
    const res = await apiFetch<{ strategy: Strategy }>('live/strategy', {
      method: 'POST',
      body: { strategy: s },
      fallbackError: 'Strategy update failed',
    })
    if (res.ok) setStrategyState(res.data.strategy)
  }, [])

  return { strategy, setStrategy }
}
