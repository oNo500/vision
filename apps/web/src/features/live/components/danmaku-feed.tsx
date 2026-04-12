'use client'

import { useEffect, useRef } from 'react'

import { cn } from '@workspace/ui/lib/utils'

import type { LiveEvent } from '../hooks/use-live-stream'

const EVENT_LABELS: Record<string, string> = {
  danmaku: '弹幕',
  gift: '礼物',
  enter: '进场',
  like: '点赞',
  follow: '关注',
  share: '分享',
  fansclub: '粉丝团',
  stats: '统计',
}

const EVENT_COLORS: Record<string, string> = {
  danmaku: 'text-foreground',
  gift: 'text-yellow-500',
  enter: 'text-blue-500',
  like: 'text-pink-500',
  follow: 'text-green-500',
  share: 'text-purple-500',
  fansclub: 'text-orange-500',
}

function EventRow({ event }: { event: LiveEvent }) {
  const label = EVENT_LABELS[event.type] ?? event.type
  const color = EVENT_COLORS[event.type] ?? 'text-muted-foreground'

  const content = (() => {
    if (event.type === 'danmaku' || event.type === 'fansclub') {
      return event.text
    }
    if (event.type === 'gift') {
      return `${event.gift}${event.value > 0 ? ` ×${event.value}` : ''}`
    }
    if (event.type === 'like') {
      return `+${event.value}`
    }
    if (event.type === 'stats') {
      return `在线 ${event.value}`
    }
    return null
  })()

  return (
    <div className="flex items-baseline gap-2 px-3 py-1.5 text-sm hover:bg-muted/40">
      <span className={cn('shrink-0 text-xs font-medium', color)}>{label}</span>
      {event.user && (
        <span className="shrink-0 font-medium text-foreground">{event.user}</span>
      )}
      {content && (
        <span className="min-w-0 truncate text-muted-foreground">{content}</span>
      )}
    </div>
  )
}

interface DanmakuFeedProps {
  events: LiveEvent[]
  connected: boolean
}

export function DanmakuFeed({ events, connected }: DanmakuFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div className="flex flex-col rounded-lg border bg-background">
      {/* header */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-medium">弹幕</span>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'size-2 rounded-full',
              connected ? 'bg-green-500' : 'bg-muted-foreground',
            )}
          />
          <span className="text-xs text-muted-foreground">
            {connected ? '已连接' : '未连接'}
          </span>
        </div>
      </div>

      {/* feed — newest at bottom */}
      <div className="flex max-h-[480px] flex-col-reverse overflow-y-auto">
        <div ref={bottomRef} />
        {events.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {connected ? '等待弹幕…' : '未连接到直播后端'}
          </p>
        ) : (
          events.map((event, i) => <EventRow key={`${event.ts}-${i}`} event={event} />)
        )}
      </div>
    </div>
  )
}
