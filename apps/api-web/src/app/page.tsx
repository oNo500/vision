import { redirect } from 'next/navigation'

import { appPaths } from '@/config/app-paths'

export default function RootPage() {
  redirect(appPaths.dashboard.live.href)
}
