'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

import { ChevronDownIcon, ChevronRightIcon } from 'lucide-react'

import { appPaths } from '@/config/app-paths'
import { env } from '@/config/env'
import type { LivePlan } from '@/features/live/hooks/use-plan'

export function PlanPanel() {
  const router = useRouter()
  const [plan, setPlan] = useState<LivePlan | null>(null)
  const [open, setOpen] = useState(true)

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

  if (!plan) {
    return (
      <div className="border-b px-5 py-2 text-sm text-muted-foreground">
        未加载方案 —{' '}
        <button
          className="underline"
          onClick={() => router.push(appPaths.dashboard.livePlans.href)}
        >
          前往方案库
        </button>
      </div>
    )
  }

  return (
    <div className="border-b px-5 py-2 text-sm">
      <button
        className="flex items-center gap-2 font-medium"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
        当前方案：{plan.name}
        <span className="ml-2 font-normal text-muted-foreground text-xs">
          <button
            className="underline"
            onClick={(e) => { e.stopPropagation(); router.push(appPaths.dashboard.livePlans.href) }}
          >
            切换方案 ↗
          </button>
        </span>
      </button>
      {open && (
        <div className="mt-1.5 flex gap-6 text-muted-foreground text-xs pl-6">
          <span>产品：{plan.product.name}{plan.product.price ? ` · ¥${plan.product.price}` : ''}</span>
          <span>人设：{plan.persona.name}{plan.persona.style ? ` · ${plan.persona.style}` : ''}</span>
          <span>脚本：{plan.script.segments.length} 个段落</span>
        </div>
      )}
    </div>
  )
}
