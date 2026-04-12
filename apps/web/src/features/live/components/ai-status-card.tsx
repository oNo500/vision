import { cn } from '@workspace/ui/lib/utils'

import type { AiOutput } from '../hooks/use-live-stream'

const SOURCE_CFG = {
  script: { label: 'script', cls: 'bg-primary/15 text-primary' },
  agent:  { label: 'agent',  cls: 'bg-secondary text-secondary-foreground' },
  inject: { label: 'inject', cls: 'bg-muted text-muted-foreground' },
} as const

interface AiStatusCardProps {
  latest: AiOutput | null
  queueDepth: number
}

export function AiStatusCard({ latest, queueDepth }: AiStatusCardProps) {

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">AI 状态</span>
        <span className={cn(
          'text-xs tabular-nums',
          queueDepth > 0 ? 'text-foreground' : 'text-muted-foreground',
        )}>
          队列 {queueDepth} 句
        </span>
      </div>

      {latest ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="size-1.5 shrink-0 rounded-full bg-primary" />
            <span className={cn('rounded px-1.5 py-px text-[10px] font-medium leading-none', SOURCE_CFG[latest.source].cls)}>
              {SOURCE_CFG[latest.source].label}
            </span>
          </div>
          <p className="line-clamp-2 text-sm leading-relaxed text-foreground">
            {latest.content}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">等待 AI 输出…</p>
      )}
    </div>
  )
}
