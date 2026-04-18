'use client'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

export function NowPlayingCard({ item }: { item: PipelineItem | null }) {
  return (
    <div className="border-y bg-primary/5 p-3">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="size-1.5 animate-pulse rounded-full bg-primary" />
        <span className="text-[10px] font-medium text-primary">正在播</span>
      </div>
      {item ? (
        <>
          <p className="text-sm leading-relaxed">{item.content}</p>
          {item.speech_prompt && (
            <p className="mt-0.5 text-[10px] text-muted-foreground">{item.speech_prompt}</p>
          )}
        </>
      ) : (
        <p className="text-xs text-muted-foreground">等待 AI 输出…</p>
      )}
    </div>
  )
}
