'use client'

import { useEffect, useRef } from 'react'

import { cn } from '@workspace/ui/lib/utils'

import type { LiveEvent } from '../hooks/use-live-stream'

const TYPE_BADGE: Record<string, { label: string; cls: string }> = {
  gift:     { label: '礼物',   cls: 'bg-yellow-500/15 text-yellow-600 dark:text-yellow-400' },
  enter:    { label: '进场',   cls: 'bg-blue-500/15 text-blue-600 dark:text-blue-400' },
  follow:   { label: '关注',   cls: 'bg-green-500/15 text-green-600 dark:text-green-400' },
  share:    { label: '分享',   cls: 'bg-purple-500/15 text-purple-600 dark:text-purple-400' },
  fansclub: { label: '粉丝团', cls: 'bg-orange-500/15 text-orange-600 dark:text-orange-400' },
  like:     { label: '赞',     cls: 'bg-pink-500/15 text-pink-600 dark:text-pink-400' },
}

function EventRow({ event }: { event: LiveEvent }) {
  const badge = TYPE_BADGE[event.type]
  const isLike = event.type === 'like'

  const body = (() => {
    if (event.type === 'danmaku' || event.type === 'fansclub') return event.text
    if (event.type === 'gift')   return `${event.gift}${event.value > 0 ? ` ×${event.value}` : ''}`
    if (event.type === 'enter')  return '进入直播间'
    if (event.type === 'follow') return '关注了主播'
    if (event.type === 'share')  return '分享了直播间'
    if (event.type === 'like')   return `+${event.value}`
    return null
  })()

  return (
    <div className={cn('flex items-baseline gap-1.5 px-3 py-1 text-xs', isLike && 'opacity-35')}>
      {badge && (
        <span className={cn('shrink-0 rounded px-1 py-0.5 text-[10px] font-medium leading-none', badge.cls)}>
          {badge.label}
        </span>
      )}
      <span className="shrink-0 font-medium text-foreground">{event.user}</span>
      {body && <span className="min-w-0 truncate text-muted-foreground">{body}</span>}
    </div>
  )
}

interface DanmakuFeedProps {
  events: LiveEvent[]
  connected: boolean
  onlineCount: number | null
}

export function DanmakuFeed({ events, connected, onlineCount }: DanmakuFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-background">
      <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">互动</span>
          {onlineCount != null && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
              在线 {onlineCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className={cn('size-1.5 rounded-full', connected ? 'bg-green-500' : 'bg-muted-foreground/50')} />
          <span className="text-xs text-muted-foreground">{connected ? '实时' : '未连接'}</span>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col-reverse overflow-y-auto py-1">
        <div ref={bottomRef} />
        {events.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            {connected ? '等待互动…' : '请先启动监听'}
          </p>
        ) : (
          events.map((event, i) => <EventRow key={`${event.ts}-${i}`} event={event} />)
        )}
      </div>
    </div>
  )
}
