'use client'

import Link from 'next/link'

import { appPaths } from '@/config/app-paths'
import { usePlanActive } from '@/features/live/hooks/use-plan-active'

export function PlanPanel() {
  const plan = usePlanActive()

  if (!plan) {
    return (
      <div className="px-4 text-center text-xs text-muted-foreground">
        未加载方案 —{' '}
        <Link href={appPaths.dashboard.livePlans.href} className="underline">
          前往方案库
        </Link>
      </div>
    )
  }

  return (
    <div className="px-4 text-center text-xs text-muted-foreground">
      {plan.name}
    </div>
  )
}
