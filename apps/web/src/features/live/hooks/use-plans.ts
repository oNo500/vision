'use client'

import { useCallback, useEffect, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { env } from '@/config/env'

export type PlanSummary = {
  id: string
  name: string
  updated_at: string
}

export function usePlans() {
  const [plans, setPlans] = useState<PlanSummary[]>([])
  const [loading, setLoading] = useState(false)

  const fetchPlans = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans`)
      if (res.ok) setPlans(await res.json())
    } catch { /* backend unreachable */ }
  }, [])

  useEffect(() => {
    fetchPlans()
  }, [fetchPlans])

  const deletePlan = useCallback(
    async (id: string) => {
      setLoading(true)
      try {
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans/${id}`, {
          method: 'DELETE',
        })
        if (!res.ok) {
          toast.error('Failed to delete plan')
        } else {
          await fetchPlans()
        }
      } catch {
        toast.error('Cannot reach backend')
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
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans/${id}/load`, {
          method: 'POST',
        })
        if (!res.ok) {
          const data = await res.json()
          toast.error((data as { detail?: string }).detail ?? 'Failed to load plan')
          return false
        }
        return true
      } catch {
        toast.error('Cannot reach backend')
        return false
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  return { plans, loading, fetchPlans, deletePlan, loadPlan }
}
