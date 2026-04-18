'use client'

import { useCallback, useEffect, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { apiFetch } from '@/lib/api-fetch'

export type FaqItem = { question: string; answer: string }

export type Product = {
  name: string
  description: string
  price: string
  highlights: string[]
  faq: FaqItem[]
}

export type Persona = {
  name: string
  style: string
  catchphrases: string[]
  forbidden_words: string[]
}

export type Segment = {
  id: string
  title: string
  goal: string
  duration: number
  cue: string[]
  must_say: boolean
  keywords: string[]
}

export type LivePlan = {
  id: string
  name: string
  created_at: string
  updated_at: string
  product: Product
  persona: Persona
  script: { segments: Segment[] }
}

export function usePlan(id: string) {
  const [plan, setPlan] = useState<LivePlan | null>(null)
  const [saving, setSaving] = useState(false)

  const fetchPlan = useCallback(async () => {
    const res = await apiFetch<LivePlan>(`live/plans/${id}`, { silent: true })
    if (res.ok) setPlan(res.data)
  }, [id])

  useEffect(() => {
    fetchPlan()
  }, [fetchPlan])

  const savePlan = useCallback(
    async (data: Partial<LivePlan> & { name: string }) => {
      setSaving(true)
      try {
        const res = await apiFetch<LivePlan>(`live/plans/${id}`, {
          method: 'PUT',
          body: data,
          fallbackError: 'Failed to save plan',
        })
        if (res.ok) {
          setPlan(res.data)
          toast.success('Plan saved')
        }
      } finally {
        setSaving(false)
      }
    },
    [id],
  )

  return { plan, saving, savePlan, fetchPlan }
}
