'use client'

import { cn } from '@workspace/ui/lib/utils'

type Props = {
  llmGenerating: boolean
  ttsSpeaking: boolean
  pendingCount: number
  synthesizedCount: number
  urgentCount: number
}

export function PipelineHeader({ llmGenerating, ttsSpeaking, pendingCount, synthesizedCount, urgentCount }: Props) {
  return (
    <div className="flex items-center justify-between rounded-t-lg border-b bg-background px-4 py-2 text-xs">
      <div className="flex items-center gap-3">
        {llmGenerating && (
          <span
            data-testid="llm-generating-indicator"
            className="flex items-center gap-1 text-blue-500"
          >
            <span className="size-1.5 animate-pulse rounded-full bg-blue-500" />
            生成中
          </span>
        )}
        <span className={cn('flex items-center gap-1', ttsSpeaking ? 'text-green-500' : 'text-muted-foreground')}>
          <span className={cn('size-1.5 rounded-full', ttsSpeaking ? 'animate-pulse bg-green-500' : 'bg-muted-foreground/30')} />
          {ttsSpeaking ? '播报中' : '播报待机'}
        </span>
      </div>
      <div className="flex items-center gap-3 tabular-nums text-muted-foreground">
        <span>待合成 {pendingCount}</span>
        <span>已合成 {synthesizedCount}</span>
        {urgentCount > 0 && <span className="text-amber-500">紧急 {urgentCount}</span>}
      </div>
    </div>
  )
}
