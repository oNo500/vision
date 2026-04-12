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
    <div className="flex h-full flex-col gap-3 rounded-lg border bg-background p-4">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className={cn('size-2 rounded-full', state.running ? 'animate-pulse bg-green-500' : 'bg-muted-foreground/40')} />
          <span className="text-sm font-semibold">{state.running ? '直播中' : '未开始'}</span>
        </div>

        {state.running && (
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {state.segment_id && (
              <span>段落 <span className="font-medium text-foreground">{state.segment_id}</span></span>
            )}
            {state.remaining_seconds != null && (
              <span>剩余 <span className="tabular-nums font-medium text-foreground">{formatSeconds(state.remaining_seconds)}</span></span>
            )}
            {state.queue_depth != null && (
              <span>队列 <span className="tabular-nums font-medium text-foreground">{state.queue_depth}</span></span>
            )}
          </div>
        )}

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
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
