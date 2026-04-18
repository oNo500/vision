'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

import type { LivePlan } from '@/features/live/hooks/use-plan'

export function usePlanActive(): LivePlan | null {
  const [plan, setPlan] = useState<LivePlan | null>(null)

  const fetchActive = useCallback(async () => {
    const res = await apiFetch<{ plan: LivePlan | null }>('live/plans/active', { silent: true })
    if (res.ok) setPlan(res.data.plan ?? null)
  }, [])

  useEffect(() => { fetchActive() }, [fetchActive])

  return plan
}
