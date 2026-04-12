'use client'

import { useState } from 'react'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'

import { env } from '@/config/env'
import type { ScriptState } from '../hooks/use-live-stream'

interface ScriptCardProps {
  scriptState: ScriptState | null
  running: boolean
}

async function postScriptNav(direction: 'next' | 'prev'): Promise<void> {
  await fetch(`${env.NEXT_PUBLIC_API_URL}/live/script/${direction}`, { method: 'POST' })
}

export function ScriptCard({ scriptState, running }: ScriptCardProps) {
  const [loading, setLoading] = useState(false)

  async function handleNav(direction: 'next' | 'prev') {
    if (!running || loading) return
    setLoading(true)
    try {
      await postScriptNav(direction)
    } finally {
      setLoading(false)
    }
  }

  const progress =
    scriptState && scriptState.segment_duration > 0
      ? ((scriptState.segment_duration - scriptState.remaining_seconds) / scriptState.segment_duration) * 100
      : 0

  const remaining = scriptState
    ? `${Math.floor(scriptState.remaining_seconds / 60)}:${String(Math.floor(scriptState.remaining_seconds % 60)).padStart(2, '0')}`
    : '--:--'

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">脚本进度</span>
        {scriptState?.segment_id && (
          <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-foreground">
            {scriptState.segment_id}
          </span>
        )}
      </div>

      {/* progress bar */}
      <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-1000"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mb-3 text-right text-xs tabular-nums text-muted-foreground">剩余 {remaining}</div>

      {/* segment text */}
      <p className={cn(
        'mb-4 line-clamp-2 text-sm leading-relaxed text-foreground',
        !scriptState && 'text-muted-foreground',
      )}>
        {scriptState?.segment_id ? '（脚本运行中）' : '未开始'}
      </p>

      {/* nav buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={!running || loading}
          onClick={() => handleNav('prev')}
        >
          <ChevronLeftIcon className="mr-1 size-3.5" />
          上一段
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={!running || loading}
          onClick={() => handleNav('next')}
        >
          下一段
          <ChevronRightIcon className="ml-1 size-3.5" />
        </Button>
      </div>
    </div>
  )
}
