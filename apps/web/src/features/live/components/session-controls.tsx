'use client'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { CircleStopIcon, RadioIcon } from 'lucide-react'

import type { useAiSession } from '../hooks/use-ai-session'
import type { useDanmakuSession } from '../hooks/use-danmaku-session'
import type { Strategy, useStrategy } from '../hooks/use-strategy'

interface Props {
  aiSession: ReturnType<typeof useAiSession>
  danmakuSession: ReturnType<typeof useDanmakuSession>
  strategy: ReturnType<typeof useStrategy>
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span
      className={cn(
        'size-2 shrink-0 rounded-full',
        active ? 'animate-pulse bg-primary' : 'bg-muted-foreground/30',
      )}
    />
  )
}

export function SessionControls({ aiSession, danmakuSession, strategy }: Props) {
  return (
    <div className="flex items-center gap-6">
      {/* AI session row */}
      <div className="flex items-center gap-2">
        <StatusDot active={aiSession.state.running} />
        <span
          className={cn(
            'text-sm font-medium',
            aiSession.state.running ? 'text-foreground' : 'text-muted-foreground',
          )}
        >
          AI 主播
        </span>
        {aiSession.state.running ? (
          <Button variant="destructive" size="sm" disabled={aiSession.loading} onClick={aiSession.stop}>
            <CircleStopIcon className="mr-1.5 size-3.5" />
            停止
          </Button>
        ) : (
          <Button size="sm" disabled={aiSession.loading} onClick={aiSession.start}>
            <RadioIcon className="mr-1.5 size-3.5" />
            启动
          </Button>
        )}
      </div>

      <div className="h-4 w-px bg-border" />

      {/* Danmaku row */}
      <div className="flex items-center gap-2">
        <StatusDot active={danmakuSession.state.running} />
        <span
          className={cn(
            'text-sm font-medium',
            danmakuSession.state.running ? 'text-foreground' : 'text-muted-foreground',
          )}
        >
          弹幕采集
        </span>
        {danmakuSession.state.running ? (
          <Button variant="destructive" size="sm" disabled={danmakuSession.loading} onClick={danmakuSession.stop}>
            <CircleStopIcon className="mr-1.5 size-3.5" />
            停止
          </Button>
        ) : (
          <Button size="sm" disabled={danmakuSession.loading} onClick={danmakuSession.start}>
            <RadioIcon className="mr-1.5 size-3.5" />
            开启
          </Button>
        )}
      </div>

      <div className="h-4 w-px bg-border" />

      {/* Strategy toggle */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">插队</span>
        {(['immediate', 'intelligent'] as Strategy[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => { void strategy.setStrategy(s) }}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium transition-colors',
              strategy.strategy === s
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground',
            )}
          >
            {s === 'immediate' ? '及时' : '智能'}
          </button>
        ))}
      </div>

      {/* Errors */}
      {(aiSession.error ?? danmakuSession.error) && (
        <span className="text-xs text-destructive">
          {aiSession.error ?? danmakuSession.error}
        </span>
      )}
    </div>
  )
}
