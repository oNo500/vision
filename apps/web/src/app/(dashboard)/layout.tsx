import { SidebarInset, SidebarProvider } from '@workspace/ui/components/sidebar'

import { AppSidebar } from '@/components/app-sidebar'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <main id="main-content" className="flex min-h-0 flex-1 flex-col">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
