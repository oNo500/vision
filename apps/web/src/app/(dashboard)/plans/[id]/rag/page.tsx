'use client'

import { use } from 'react'
import { useRouter } from 'next/navigation'

import { appPaths } from '@/config/app-paths'
import { PlanRagLibraries } from '@/features/live/components/plan-rag-libraries'
import { ImportToLibraryPanel } from '@/features/live/components/rag-library/import-to-library-panel'

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
      <div className="flex-1 divide-y overflow-y-auto">
        <PlanRagLibraries planId={id} />
        <div className="flex flex-col gap-3 p-6">
          <h2 className="text-base font-semibold">从视频导入到素材库</h2>
          <p className="text-sm text-muted-foreground">
            选择目标素材库，再选择视频，将主播话术片段导入供检索使用。
          </p>
          <ImportToLibraryPanel />
        </div>
      </div>
    </div>
  )
}
