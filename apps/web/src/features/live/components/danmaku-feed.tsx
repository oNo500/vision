'use client'

import { useEffect } from 'react'

import { cn } from '@workspace/ui/lib/utils'
import { ArrowDownIcon } from 'lucide-react'

import { useScrollAnchor } from '../hooks/use-scroll-anchor'
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
    <div className={cn('flex items-baseline gap-1.5 px-3 py-1 text-xs', event.type === 'like' && 'opacity-35')}>
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
  const { scrollRef, isAtBottom, unread, scrollToBottom, onNewMessage } = useScrollAnchor()

  useEffect(() => {
    if (events.length > 0) onNewMessage()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events.length])

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-background">
      {/* header */}
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

      {/* feed */}
      <div className="relative min-h-0 flex-1">
        <div ref={scrollRef} className="absolute inset-0 overflow-y-auto py-1">
          {events.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">
              {connected ? '等待互动…' : '请先启动监听'}
            </p>
          ) : (
            events.map((event, i) => <EventRow key={`${event.ts}-${i}`} event={event} />)
          )}
        </div>

        {/* jump-to-bottom button */}
        {!isAtBottom && (
          <button
            onClick={() => scrollToBottom()}
            className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border bg-background/90 px-3 py-1.5 text-xs font-medium shadow-md backdrop-blur-sm transition-opacity hover:bg-muted"
          >
            <ArrowDownIcon className="size-3" />
            {unread > 0 ? `${unread} 条新消息` : '跳到最新'}
          </button>
        )}
      </div>
    </div>
  )
}
