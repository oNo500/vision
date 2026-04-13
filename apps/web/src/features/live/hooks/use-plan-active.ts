'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'
import type { LivePlan } from '@/features/live/hooks/use-plan'

export function usePlanActive(): LivePlan | null {
  const [plan, setPlan] = useState<LivePlan | null>(null)

  const fetchActive = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans/active`)
      if (res.ok) {
        const data = await res.json()
        setPlan(data.plan ?? null)
      }
    } catch { /* backend unreachable */ }
  }, [])

  useEffect(() => { fetchActive() }, [fetchActive])

  return plan
}
