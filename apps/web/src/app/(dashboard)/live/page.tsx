'use client'

import { useEffect, useState } from 'react'

import { AiOutputLog } from '@/features/live/components/ai-output-log'
import { AiStatusCard } from '@/features/live/components/ai-status-card'
import { DanmakuFeed } from '@/features/live/components/danmaku-feed'
import { PlanPanel } from '@/features/live/components/plan-panel'
import { ScriptCard } from '@/features/live/components/script-card'
import { SessionControls } from '@/features/live/components/session-controls'
import { useAiSession } from '@/features/live/hooks/use-ai-session'
import { useDanmakuSession } from '@/features/live/hooks/use-danmaku-session'
import { useStrategy } from '@/features/live/hooks/use-strategy'
import { useLiveStream } from '@/features/live/hooks/use-live-stream'

export default function LivePage() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const aiSession = useAiSession()
  const danmakuSession = useDanmakuSession()
  const strategy = useStrategy()
  const { events, connected, onlineCount, aiOutputs, scriptState } = useLiveStream()

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* plan panel */}
      <PlanPanel />

      {/* top bar */}
      <div className="shrink-0 border-b px-5 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold">直播控场</h1>
          <div className="flex-1">
            <SessionControls aiSession={aiSession} danmakuSession={danmakuSession} strategy={strategy} />
          </div>
        </div>
      </div>

      {/* body — client-only to avoid SSR hydration mismatch */}
      {mounted && (
        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* left col: script progress */}
          <div className="flex w-64 shrink-0 flex-col overflow-hidden border-r">
            <ScriptCard scriptState={scriptState} running={aiSession.state.running} />
          </div>

          {/* center col */}
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-3">
            <div className="shrink-0">
              <AiStatusCard
                latest={aiOutputs[aiOutputs.length - 1] ?? null}
                queueDepth={aiSession.state.queue_depth ?? 0}
              />
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
      )}
    </div>
  )
}
