'use client'

import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const { events, connected } = useLiveStream()

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Live</h1>
        <p className="text-sm text-muted-foreground">直播控场面板</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
          控场面板（待开发）
        </div>
        <DanmakuFeed events={events} connected={connected} />
      </div>
    </div>
  )
}
