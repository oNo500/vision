'use client'

import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from '@workspace/ui/components/sidebar'
import { BookOpenIcon, DatabaseIcon, RadioIcon, Settings2Icon } from 'lucide-react'
import Link from 'next/link'
import * as React from 'react'

import { NavMain } from '@/components/nav-main'
import { appPaths } from '@/config/app-paths'

const navItems = [
  {
    title: 'Live',
    url: appPaths.dashboard.live.href,
    icon: <RadioIcon />,
    items: [],
  },
  {
    title: '方案库',
    url: appPaths.dashboard.plans.href,
    icon: <BookOpenIcon />,
    items: [],
  },
  {
    title: '素材库',
    url: appPaths.dashboard.libraries.href,
    icon: <DatabaseIcon />,
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
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem className="flex items-center gap-2">
            <SidebarMenuButton size="lg" render={<Link href={appPaths.home.href} />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <RadioIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">Vision</span>
                <span className="truncate text-xs">直播控场</span>
              </div>
            </SidebarMenuButton>
            <SidebarTrigger className="shrink-0" />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navItems} />
      </SidebarContent>
    </Sidebar>
  )
}
