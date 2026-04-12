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
    <div className="flex flex-col gap-4 rounded-lg border bg-background p-4">
      {/* status row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'size-2 rounded-full',
              state.running ? 'animate-pulse bg-green-500' : 'bg-muted-foreground/40',
            )}
          />
          <span className="text-sm font-semibold">
            {state.running ? '直播中' : '未开始'}
          </span>
        </div>

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

      {/* stats grid */}
      {state.running && (
        <div className="grid grid-cols-3 divide-x rounded-md border text-center text-xs">
          <div className="px-3 py-2">
            <p className="text-muted-foreground">段落</p>
            <p className="mt-0.5 font-medium text-foreground truncate">{state.segment_id ?? '—'}</p>
          </div>
          <div className="px-3 py-2">
            <p className="text-muted-foreground">剩余</p>
            <p className="mt-0.5 font-medium tabular-nums text-foreground">
              {state.remaining_seconds != null ? formatSeconds(state.remaining_seconds) : '—'}
            </p>
          </div>
          <div className="px-3 py-2">
            <p className="text-muted-foreground">TTS 队列</p>
            <p className="mt-0.5 font-medium tabular-nums text-foreground">{state.queue_depth ?? 0}</p>
          </div>
        </div>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
