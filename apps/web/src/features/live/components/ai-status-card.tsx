import { cn } from '@workspace/ui/lib/utils'

import type { AiOutput } from '../hooks/use-live-stream'

const SOURCE_CFG = {
  script: { label: 'script', cls: 'bg-blue-500/15 text-blue-600 dark:text-blue-400' },
  agent:  { label: 'agent',  cls: 'bg-violet-500/15 text-violet-600 dark:text-violet-400' },
  inject: { label: 'inject', cls: 'bg-orange-500/15 text-orange-600 dark:text-orange-400' },
} as const

interface AiStatusCardProps {
  latest: AiOutput | null
  queueDepth: number
}

export function AiStatusCard({ latest, queueDepth }: AiStatusCardProps) {
  const sourceCfg = latest ? SOURCE_CFG[latest.source] : null

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
            <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
            {sourceCfg && (
              <span className={cn('rounded px-1.5 py-px text-[10px] font-medium leading-none', sourceCfg.cls)}>
                {sourceCfg.label}
              </span>
            )}
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
