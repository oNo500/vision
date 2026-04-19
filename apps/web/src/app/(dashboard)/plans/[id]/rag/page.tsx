'use client'

import { use } from 'react'
import { useRouter } from 'next/navigation'

import { appPaths } from '@/config/app-paths'
import { PlanRagLibraries } from '@/features/live/components/plan-rag-libraries'

export default function PlanRagPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b px-6 py-3">
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => router.push(appPaths.dashboard.plan(id).href)}
        >
          ← 方案编辑
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <PlanRagLibraries planId={id} />
      </div>
    </div>
  )
}
