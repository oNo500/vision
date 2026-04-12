'use client'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { CircleStopIcon, RadioIcon } from 'lucide-react'

import type { useLiveSession } from '../hooks/use-live-session'

type Props = ReturnType<typeof useLiveSession>

export function SessionControls({ state, loading, error, start, stop }: Props) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-background p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'size-2 rounded-full',
              state.running ? 'animate-pulse bg-green-500' : 'bg-muted-foreground',
            )}
          />
          <span className="text-sm font-medium">
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

      {state.running && (
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          {state.segment_id && (
            <div>
              <span className="font-medium text-foreground">段落</span>
              <span className="ml-1">{state.segment_id}</span>
            </div>
          )}
          {state.remaining_seconds !== undefined && (
            <div>
              <span className="font-medium text-foreground">剩余</span>
              <span className="ml-1">{state.remaining_seconds}s</span>
            </div>
          )}
          {state.queue_depth !== undefined && (
            <div>
              <span className="font-medium text-foreground">队列</span>
              <span className="ml-1">{state.queue_depth}</span>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
