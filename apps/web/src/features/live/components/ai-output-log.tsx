'use client'

import { useEffect, useRef } from 'react'

import { cn } from '@workspace/ui/lib/utils'

import type { AiOutput } from '../hooks/use-live-stream'

const SOURCE_CFG = {
  script: { label: 'script', cls: 'bg-primary/15 text-primary' },
  agent:  { label: 'agent',  cls: 'bg-secondary text-secondary-foreground' },
  inject: { label: 'inject', cls: 'bg-muted text-muted-foreground' },
} as const

interface AiOutputLogProps {
  outputs: AiOutput[]
}

function formatTimestamp(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour12: false })
}

export function AiOutputLog({ outputs }: AiOutputLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 32
  }

  useEffect(() => {
    if (isAtBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [outputs.length])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="mb-2 flex items-center gap-2 shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          AI 输出历史
        </span>
        <span className="text-xs text-muted-foreground tabular-nums">({outputs.length})</span>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 min-h-0 overflow-y-auto space-y-2"
      >
        {outputs.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无输出记录</p>
        ) : (
          outputs.map((output) => (
            <div key={output.ts} className="rounded-md border bg-background p-2.5 text-sm">
              <div className="mb-1 flex items-center gap-2">
                <span
                  className={cn(
                    'rounded px-1.5 py-px text-[10px] font-medium leading-none',
                    SOURCE_CFG[output.source].cls,
                  )}
                >
                  {SOURCE_CFG[output.source].label}
                </span>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {formatTimestamp(output.ts)}
                </span>
              </div>
              <p className="leading-relaxed text-foreground">{output.content}</p>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
