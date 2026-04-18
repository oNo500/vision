'use client'

import { FloatingSidebarTrigger } from '@/components/floating-sidebar-trigger'
import { usePageHeaderSlot } from '@/components/page-header'

export function DashboardHeader() {
  const slot = usePageHeaderSlot()
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b px-3">
      <FloatingSidebarTrigger />
      <div className="flex min-w-0 flex-1 items-center gap-3">{slot}</div>
    </header>
  )
}
