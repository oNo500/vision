'use client'

import { useEffect, useRef, useState } from 'react'

import { Button } from '@workspace/ui/components/button'
import { toast } from '@workspace/ui/components/sonner'
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon, ChevronUpIcon } from 'lucide-react'

import { env } from '@/config/env'
import type { ScriptState } from '@/features/live/hooks/use-live-stream'
import type { LivePlan } from '@/features/live/hooks/use-plan'

async function postScriptNav(direction: 'next' | 'prev'): Promise<void> {
  const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/script/${direction}`, { method: 'POST' })
  if (!res.ok) throw new Error(`script nav failed: ${res.status}`)
}

interface PlanSidebarProps {
  plan: LivePlan
  scriptState: ScriptState | null
  running: boolean
}

export function PlanSidebar({ plan, scriptState, running }: PlanSidebarProps) {
  const [navLoading, setNavLoading] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const currentRef = useRef<HTMLDivElement>(null)

  const currentSegId = scriptState?.segment_id ?? null

  // scroll current segment into view when it changes
  useEffect(() => {
    currentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [currentSegId])

  const progress = scriptState && scriptState.segment_duration > 0
    ? Math.max(0, Math.min(100,
        ((scriptState.segment_duration - scriptState.remaining_seconds) / scriptState.segment_duration) * 100,
      ))
    : 0

  const remaining = scriptState
    ? `${Math.floor(scriptState.remaining_seconds / 60)}:${String(Math.floor(scriptState.remaining_seconds % 60)).padStart(2, '0')}`
    : null

  async function handleNav(direction: 'next' | 'prev') {
    if (!running || navLoading) return
    setNavLoading(true)
    try {
      await postScriptNav(direction)
    } catch {
      toast.error('Script navigation failed')
    } finally {
      setNavLoading(false)
    }
  }

  function toggleCollapse(id: string) {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="flex h-full w-64 shrink-0 flex-col overflow-hidden border-r">
      {/* plan meta */}
      <div className="shrink-0 border-b px-3 py-2.5">
        <p className="text-xs font-semibold">{plan.name}</p>
        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
          {plan.product.name}{plan.product.price ? ` · ${plan.product.price}` : ''}
          {' · '}{plan.script.segments.length} 段
        </p>
      </div>

      {/* segments list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {plan.script.segments.map((seg, i) => {
          const isCurrent = seg.id === currentSegId
          const isCollapsed = collapsed.has(seg.id)
          const hasDetail = seg.goal || seg.cue.length > 0 || seg.keywords.length > 0

          return (
            <div
              key={seg.id}
              ref={isCurrent ? currentRef : null}
              className={`rounded-lg border text-xs transition-colors ${
                isCurrent ? 'border-primary/40 bg-primary/5' : 'border-transparent bg-muted/30'
              }`}
            >
              {/* header row — click to collapse */}
              <button
                className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
                onClick={() => toggleCollapse(seg.id)}
              >
                <span className={`flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] font-mono font-semibold ${
                  isCurrent ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                }`}>
                  {i + 1}
                </span>
                <span className={`flex-1 truncate font-medium ${isCurrent ? 'text-primary' : ''}`}>
                  {seg.title || seg.id}
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {isCurrent && remaining ? remaining : seg.duration >= 60 ? `${Math.floor(seg.duration / 60)}m` : `${seg.duration}s`}
                </span>
                {hasDetail && (
                  isCollapsed
                    ? <ChevronDownIcon className="size-3 shrink-0 text-muted-foreground" />
                    : <ChevronUpIcon className="size-3 shrink-0 text-muted-foreground" />
                )}
              </button>

              {/* progress bar — current only */}
              {isCurrent && (
                <div className="h-0.5 w-full bg-primary/20">
                  <div
                    className="h-full bg-primary transition-all duration-1000"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              )}

              {/* detail — hidden when collapsed */}
              {hasDetail && !isCollapsed && (
                <div className="space-y-1.5 border-t border-dashed border-muted-foreground/20 px-2.5 pb-2.5 pt-1.5">
                  {seg.goal && (
                    <p className="leading-relaxed text-muted-foreground">{seg.goal}</p>
                  )}
                  {seg.cue.length > 0 && (
                    <div className="rounded border-l-2 border-primary/50 bg-background/80 py-1.5 pl-2.5 pr-2">
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-primary/70">
                        话术 {seg.must_say ? '· 必说' : '· 融入'}
                      </p>
                      <ul className="space-y-0.5">
                        {seg.cue.map((line, j) => (
                          <li key={j}>{line}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {seg.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {seg.keywords.map((kw, j) => (
                        <span key={j} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{kw}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* nav buttons */}
      <div className="shrink-0 flex gap-2 border-t p-2">
        <Button variant="outline" size="sm" className="flex-1" disabled={!running || navLoading} onClick={() => handleNav('prev')}>
          <ChevronLeftIcon className="mr-1 size-3.5" />
          上一段
        </Button>
        <Button variant="outline" size="sm" className="flex-1" disabled={!running || navLoading} onClick={() => handleNav('next')}>
          下一段
          <ChevronRightIcon className="ml-1 size-3.5" />
        </Button>
      </div>
    </div>
  )
}
