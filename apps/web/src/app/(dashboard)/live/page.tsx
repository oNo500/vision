'use client'

import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { SessionControls } from '@/features/live/components/session-controls'
import { useLiveSession } from '@/features/live/hooks/use-live-session'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const session = useLiveSession()
  const { events, connected } = useLiveStream()

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Live</h1>
        <p className="text-sm text-muted-foreground">直播控场面板</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <SessionControls {...session} />
        <DanmakuFeed events={events} connected={connected} />
      </div>
    </div>
  )
}
