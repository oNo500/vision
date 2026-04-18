import { SidebarInset, SidebarProvider } from '@workspace/ui/components/sidebar'

import { AppSidebar } from '@/components/app-sidebar'
import { DashboardHeader } from '@/components/dashboard-header'
import { PageHeaderProvider } from '@/components/page-header'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider defaultOpen={false} className="h-svh overflow-hidden">
      <AppSidebar />
      <SidebarInset>
        <PageHeaderProvider>
          <DashboardHeader />
          <main id="main-content" className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {children}
          </main>
        </PageHeaderProvider>
      </SidebarInset>
    </SidebarProvider>
  )
}
