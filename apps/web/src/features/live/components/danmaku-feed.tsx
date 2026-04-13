'use client'

import { useEffect, useState } from 'react'

import { cn } from '@workspace/ui/lib/utils'
import { ArrowDownIcon } from 'lucide-react'

import type { LiveEvent } from '../hooks/use-live-stream'
import { useScrollAnchor } from '../hooks/use-scroll-anchor'

// ── filter tabs ───────────────────────────────────────────────────────────────

type FilterTab = 'all' | 'danmaku' | 'gift' | 'social'

const TABS: { id: FilterTab; label: string }[] = [
  { id: 'all',     label: '全部' },
  { id: 'danmaku', label: '弹幕' },
  { id: 'gift',    label: '礼物' },
  { id: 'social',  label: '互动' },
]

const SOCIAL_TYPES = new Set(['enter', 'follow', 'share', 'fansclub', 'like'])

function matchTab(event: LiveEvent, tab: FilterTab): boolean {
  if (tab === 'all')     return true
  if (tab === 'danmaku') return event.type === 'danmaku'
  if (tab === 'gift')    return event.type === 'gift'
  if (tab === 'social')  return SOCIAL_TYPES.has(event.type)
  return true
}

// ── per-type config ────────────────────────────────────────────────────────────

type EventCfg = { label: string; bar: string; badge: string }

const TYPE_CFG = new Map<string, EventCfg>([
  ['danmaku',  { label: '弹幕', bar: 'bg-transparent',              badge: '' }],
  ['gift',     { label: '礼物', bar: 'bg-amber-500',                badge: 'bg-amber-500/15 text-amber-600 dark:text-amber-400' }],
  ['enter',    { label: '进场', bar: 'bg-sky-500',                  badge: 'bg-sky-500/15 text-sky-600 dark:text-sky-400' }],
  ['follow',   { label: '关注', bar: 'bg-emerald-500',              badge: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' }],
  ['share',    { label: '分享', bar: 'bg-violet-500',               badge: 'bg-violet-500/15 text-violet-600 dark:text-violet-400' }],
  ['fansclub', { label: '粉团', bar: 'bg-orange-500',               badge: 'bg-orange-500/15 text-orange-600 dark:text-orange-400' }],
  ['like',     { label: '赞',   bar: 'bg-rose-500',                 badge: 'bg-rose-500/15 text-rose-600 dark:text-rose-400' }],
])

const DEFAULT_CFG: EventCfg = { label: '', bar: 'bg-transparent', badge: '' }

function getCfg(type: string): EventCfg {
  return TYPE_CFG.get(type) ?? DEFAULT_CFG
}

// ── helpers ───────────────────────────────────────────────────────────────────

function avatarChar(name: string): string {
  return (name || '?').slice(-1).toUpperCase()
}

function eventBody(event: LiveEvent): string {
  if (event.type === 'danmaku' || event.type === 'fansclub') return event.text ?? ''
  if (event.type === 'gift')   return `送出 ${event.gift ?? ''}${event.value > 0 ? ` ×${event.value}` : ''}`
  if (event.type === 'enter')  return '进入直播间'
  if (event.type === 'follow') return '关注了主播'
  if (event.type === 'share')  return '分享了直播间'
  if (event.type === 'like')   return `点赞 +${event.value}`
  return ''
}

// ── EventRow ──────────────────────────────────────────────────────────────────

function EventRow({ event }: { event: LiveEvent }) {
  const cfg = getCfg(event.type)
  const isDanmaku = event.type === 'danmaku'
  const body = eventBody(event)

  return (
    <div className="group flex items-start gap-2.5 px-3 py-2 transition-colors hover:bg-muted/50">
      {/* left accent bar */}
      <div className={cn('mt-1 w-0.5 self-stretch shrink-0 rounded-full', cfg.bar)} />

      {/* avatar */}
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-bold text-muted-foreground">
        {avatarChar(event.user)}
      </div>

      {/* content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-[13px] font-semibold text-foreground">{event.user}</span>
          {!isDanmaku && cfg.badge && (
            <span className={cn('shrink-0 rounded px-1 py-px text-[10px] font-medium leading-none', cfg.badge)}>
              {cfg.label}
            </span>
          )}
        </div>
        {body && (
          <p className={cn(
            'mt-0.5 text-[13px] leading-snug',
            isDanmaku ? 'text-foreground' : 'text-muted-foreground',
          )}>
            {body}
          </p>
        )}
      </div>
    </div>
  )
}

// ── DanmakuFeed ───────────────────────────────────────────────────────────────

interface DanmakuFeedProps {
  events: LiveEvent[]
  connected: boolean
  onlineCount: number | null
}

export function DanmakuFeed({ events, connected, onlineCount }: DanmakuFeedProps) {
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const { scrollRef, isAtBottom, unread, scrollToBottom, onNewMessage } = useScrollAnchor()

  const filtered = events.filter((e) => matchTab(e, activeTab))

  useEffect(() => {
    if (events.length > 0) onNewMessage()
  }, [events.length, onNewMessage])

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border bg-background">
      {/* ── header ── */}
      <div className="shrink-0 px-3 pt-3">
        <div className="flex items-center justify-between pb-2.5">
          <span className="text-sm font-semibold">互动消息</span>
          <div className="flex items-center gap-1.5">
            <span className={cn(
              'size-1.5 rounded-full',
              connected ? 'bg-emerald-500' : 'bg-muted-foreground/40',
            )} />
            <span className="text-xs text-muted-foreground">{connected ? '实时' : '未连接'}</span>
            {onlineCount != null && (
              <span className="ml-0.5 text-xs tabular-nums text-muted-foreground">
                · {onlineCount.toLocaleString()} 在线
              </span>
            )}
          </div>
        </div>

        {/* filter tabs */}
        <div className="flex gap-0.5 border-b">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'relative px-3 py-1.5 text-xs font-medium transition-colors',
                activeTab === tab.id
                  ? 'text-foreground after:absolute after:inset-x-1 after:bottom-0 after:h-0.5 after:rounded-full after:bg-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── feed ── */}
      <div className="relative min-h-0 flex-1">
        <div ref={scrollRef} className="absolute inset-0 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <span className="text-sm text-muted-foreground">
                {connected ? '等待互动…' : '请先启动监听'}
              </span>
            </div>
          ) : (
            filtered.map((event, i) => (
              <EventRow key={`${event.ts}-${i}`} event={event} />
            ))
          )}
        </div>

        {/* jump-to-bottom */}
        {!isAtBottom && (
          <button
            type="button"
            onClick={() => scrollToBottom()}
            className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border bg-background/95 px-3 py-1.5 text-xs font-medium shadow-lg backdrop-blur-sm transition-all hover:bg-muted active:scale-95"
          >
            <ArrowDownIcon className="size-3" />
            {unread > 0 ? `${unread} 条新消息` : '跳到最新'}
          </button>
        )}
      </div>
    </div>
  )
}
