'use client'

import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { SessionControls } from '@/features/live/components/session-controls'
import { useLiveSession } from '@/features/live/hooks/use-live-session'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const session = useLiveSession()
  const { events, connected, onlineCount } = useLiveStream()

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-6 p-6">
      <div className="shrink-0">
        <h1 className="text-2xl font-bold">Live</h1>
        <p className="text-sm text-muted-foreground">直播控场面板</p>
      </div>
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1fr_360px]">
        <SessionControls {...session} />
        <DanmakuFeed events={events} connected={connected} onlineCount={onlineCount} />
      </div>
    </div>
  )
}
