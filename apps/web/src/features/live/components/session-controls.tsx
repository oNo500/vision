'use client'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { CircleStopIcon, RadioIcon } from 'lucide-react'

import type { useLiveSession } from '../hooks/use-live-session'

type Props = ReturnType<typeof useLiveSession>

function formatSeconds(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

export function SessionControls({ state, loading, error, start, stop }: Props) {
  return (
    <div className="flex items-center gap-3">
      {/* status indicator */}
      <div className="flex items-center gap-2">
        <span className={cn(
          'size-2 rounded-full',
          state.running ? 'animate-pulse bg-emerald-500' : 'bg-muted-foreground/30',
        )} />
        <span className={cn(
          'text-sm font-medium',
          state.running ? 'text-foreground' : 'text-muted-foreground',
        )}>
          {state.running ? '直播中' : '未开始'}
        </span>
      </div>

      {/* meta: segment / remaining / queue */}
      {state.running && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {state.segment_id && (
            <span className="rounded-md bg-muted px-2 py-0.5 font-mono font-medium text-foreground">
              {state.segment_id}
            </span>
          )}
          {state.remaining_seconds != null && (
            <span>剩余 <span className="tabular-nums font-medium text-foreground">{formatSeconds(state.remaining_seconds)}</span></span>
          )}
          {state.queue_depth != null && (
            <span>队列 <span className="tabular-nums font-medium text-foreground">{state.queue_depth}</span></span>
          )}
        </div>
      )}

      {/* action button */}
      <div className="ml-auto">
        {state.running ? (
          <Button variant="destructive" size="sm" disabled={loading} onClick={stop}>
            <CircleStopIcon className="mr-1.5 size-3.5" />
            停止
          </Button>
        ) : (
          <Button size="sm" disabled={loading} onClick={start}>
            <RadioIcon className="mr-1.5 size-3.5" />
            开始监听
          </Button>
        )}
      </div>

      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  )
}
