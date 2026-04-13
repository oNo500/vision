import { cn } from '@workspace/ui/lib/utils'

import type { AiOutput } from '../hooks/use-live-stream'

const SOURCE_CFG = {
  script: { label: 'script', cls: 'bg-primary/15 text-primary' },
  agent:  { label: 'agent',  cls: 'bg-secondary text-secondary-foreground' },
  inject: { label: 'inject', cls: 'bg-muted text-muted-foreground' },
} as const

interface AiStatusCardProps {
  nowPlaying: AiOutput | null
  latest: AiOutput | null
  ttsQueueDepth: number
  urgentQueueDepth: number
}

export function AiStatusCard({ nowPlaying, latest, ttsQueueDepth, urgentQueueDepth }: AiStatusCardProps) {

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">AI 状态</span>
        <div className="flex items-center gap-3">
          <span className={cn(
            'text-xs tabular-nums',
            urgentQueueDepth > 0 ? 'text-amber-500' : 'text-muted-foreground',
          )}>
            紧急 {urgentQueueDepth}
          </span>
          <span className={cn(
            'text-xs tabular-nums',
            ttsQueueDepth > 0 ? 'text-foreground' : 'text-muted-foreground',
          )}>
            TTS {ttsQueueDepth} 句
          </span>
        </div>
      </div>

      {/* Now playing */}
      {nowPlaying ? (
        <div className="mb-3 rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            <span className="text-[10px] font-medium text-primary">正在播</span>
          </div>
          <p className="text-sm leading-relaxed text-foreground">{nowPlaying.content}</p>
          {nowPlaying.speech_prompt && (
            <p className="mt-0.5 text-[10px] text-muted-foreground">{nowPlaying.speech_prompt}</p>
          )}
        </div>
      ) : null}

      {/* Latest queued */}
      {latest ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground">最新生成</span>
            <span className={cn('rounded px-1.5 py-px text-[10px] font-medium leading-none', SOURCE_CFG[latest.source].cls)}>
              {SOURCE_CFG[latest.source].label}
            </span>
          </div>
          <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
            {latest.content}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">等待 AI 输出…</p>
      )}
    </div>
  )
}
