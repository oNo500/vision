'use client'

import { cn } from '@workspace/ui/lib/utils'

import type { AiOutput, TtsQueueItem } from '../hooks/use-live-stream'

interface TtsQueuePanelProps {
  nowPlaying: AiOutput | null
  queue: TtsQueueItem[]
}

export function TtsQueuePanel({ nowPlaying, queue }: TtsQueuePanelProps) {
  const totalChars = queue.reduce((sum, item) => sum + item.content.length, 0)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">待播队列</span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {queue.length} 句 · {totalChars} 字
        </span>
      </div>

      {/* Now playing */}
      {nowPlaying && (
        <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            <span className="text-[10px] font-medium text-primary">正在播</span>
          </div>
          <p className="text-sm leading-relaxed">{nowPlaying.content}</p>
          {nowPlaying.speech_prompt && (
            <p className="mt-0.5 text-[10px] text-muted-foreground">{nowPlaying.speech_prompt}</p>
          )}
        </div>
      )}

      {/* Pending queue */}
      {queue.length === 0 && !nowPlaying ? (
        <p className="text-xs text-muted-foreground">队列为空</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {queue.map((item, idx) => (
            <div
              key={item.id}
              className={cn(
                'rounded-md border px-3 py-2',
                idx === 0 ? 'border-border bg-muted/40' : 'border-transparent bg-muted/20',
              )}
            >
              <div className="mb-0.5 flex items-center gap-1.5">
                <span className="text-[10px] tabular-nums text-muted-foreground">#{idx + 1}</span>
                <span className="text-[10px] tabular-nums text-muted-foreground">{item.content.length} 字</span>
              </div>
              <p className="text-sm leading-relaxed">{item.content}</p>
              {item.speech_prompt && (
                <p className="mt-0.5 text-[10px] text-muted-foreground">{item.speech_prompt}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
