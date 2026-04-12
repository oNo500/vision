'use client'

import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@workspace/ui/components/sidebar'
import { RadioIcon, Settings2Icon } from 'lucide-react'
import * as React from 'react'

import { NavMain } from '@/components/nav-main'
import { appPaths } from '@/config/app-paths'

const navItems = [
  {
    title: 'Live',
    url: appPaths.dashboard.live.href,
    icon: <RadioIcon />,
    isActive: true,
    items: [],
  },
  {
    title: 'Settings',
    url: '#',
    icon: <Settings2Icon />,
    items: [],
  },
]

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<a href={appPaths.home.href} />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <RadioIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">Vision</span>
                <span className="truncate text-xs">直播控场</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navItems} />
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
