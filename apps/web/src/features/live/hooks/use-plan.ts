'use client'

import { useCallback, useEffect, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { env } from '@/config/env'

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
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans/${id}`)
      if (res.ok) setPlan(await res.json())
    } catch { /* backend unreachable */ }
  }, [id])

  useEffect(() => {
    fetchPlan()
  }, [fetchPlan])

  const savePlan = useCallback(
    async (data: Partial<LivePlan> & { name: string }) => {
      setSaving(true)
      try {
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans/${id}`, {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(data),
        })
        const result = await res.json()
        if (!res.ok) {
          toast.error((result as { detail?: string }).detail ?? 'Failed to save plan')
        } else {
          setPlan(result as LivePlan)
          toast.success('Plan saved')
        }
      } catch {
        toast.error('Cannot reach backend')
      } finally {
        setSaving(false)
      }
    },
    [id],
  )

  return { plan, saving, savePlan, fetchPlan }
}
