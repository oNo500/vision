'use client'

import { AiOutputLog } from '@/features/live/components/ai-output-log'
import { AiStatusCard } from '@/features/live/components/ai-status-card'
import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { ScriptCard } from '@/features/live/components/script-card'
import { SessionControls } from '@/features/live/components/session-controls'
import { useLiveSession } from '@/features/live/hooks/use-live-session'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const session = useLiveSession()
  const { events, connected, onlineCount, aiOutputs, scriptState } = useLiveStream()

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* top bar */}
      <div className="shrink-0 border-b px-5 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold">直播控场</h1>
          <div className="flex-1">
            <SessionControls {...session} />
          </div>
        </div>
      </div>

      {/* body */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* left col */}
        <div className="flex w-80 shrink-0 flex-col gap-3 overflow-hidden border-r p-3">
          <ScriptCard scriptState={scriptState} connected={connected} />
        </div>

        {/* center col */}
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-3">
          <div className="shrink-0">
            <AiStatusCard latest={aiOutputs[0] ?? null} queueDepth={session.state.queue_depth ?? 0} />
          </div>
          <div className="min-h-0 flex-1">
            <AiOutputLog outputs={aiOutputs} />
          </div>
        </div>

        {/* right col: danmaku feed */}
        <div className="flex w-96 shrink-0 flex-col overflow-hidden border-l p-3">
          <DanmakuFeed events={events} connected={connected} onlineCount={onlineCount} />
        </div>
      </div>
    </div>
  )
}
