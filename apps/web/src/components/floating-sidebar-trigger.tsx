'use client'

import { SidebarTrigger, useSidebar } from '@workspace/ui/components/sidebar'

export function FloatingSidebarTrigger() {
  const { state, isMobile } = useSidebar()
  if (!isMobile && state === 'expanded') return null
  return <SidebarTrigger />
}
