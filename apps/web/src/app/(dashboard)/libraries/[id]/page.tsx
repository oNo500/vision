'use client'

import { use } from 'react'
import { useRouter } from 'next/navigation'
import { appPaths } from '@/config/app-paths'
import { LibraryDetail } from '@/features/live/components/rag-library/library-detail'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export default function LibraryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { libraries } = useRagLibraries()
  const lib = libraries.find((l) => l.id === id)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b px-6 py-3">
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => router.push(appPaths.dashboard.libraries.href)}
        >
          ← 素材库
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <LibraryDetail libId={id} libName={lib?.name ?? id} />
      </div>
    </div>
  )
}
