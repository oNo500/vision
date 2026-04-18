'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

export type PlanSummary = {
  id: string
  name: string
  updated_at: string
}

export function usePlans() {
  const [plans, setPlans] = useState<PlanSummary[]>([])
  const [loading, setLoading] = useState(false)

  const fetchPlans = useCallback(async () => {
    const res = await apiFetch<PlanSummary[]>('live/plans', { silent: true })
    if (res.ok) setPlans(res.data)
  }, [])

  useEffect(() => {
    fetchPlans()
  }, [fetchPlans])

  const deletePlan = useCallback(
    async (id: string) => {
      setLoading(true)
      try {
        const res = await apiFetch<unknown>(`live/plans/${id}`, {
          method: 'DELETE',
          fallbackError: 'Failed to delete plan',
        })
        if (res.ok) await fetchPlans()
      } finally {
        setLoading(false)
      }
    },
    [fetchPlans],
  )

  const loadPlan = useCallback(
    async (id: string): Promise<boolean> => {
      setLoading(true)
      try {
        const res = await apiFetch<unknown>(`live/plans/${id}/load`, {
          method: 'POST',
          fallbackError: 'Failed to load plan',
        })
        return res.ok
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  return { plans, loading, fetchPlans, deletePlan, loadPlan }
}
