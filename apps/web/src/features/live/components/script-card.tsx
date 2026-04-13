'use client'

import { useState } from 'react'

import { Button } from '@workspace/ui/components/button'
import { toast } from '@workspace/ui/components/sonner'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'

import { env } from '@/config/env'
import type { ScriptState } from '../hooks/use-live-stream'

interface ScriptCardProps {
  scriptState: ScriptState | null
  running: boolean
}

async function postScriptNav(direction: 'next' | 'prev'): Promise<void> {
  const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/script/${direction}`, { method: 'POST' })
  if (!res.ok) throw new Error(`script nav failed: ${res.status}`)
}

export function ScriptCard({ scriptState, running }: ScriptCardProps) {
  const [loading, setLoading] = useState(false)

  async function handleNav(direction: 'next' | 'prev') {
    if (!running || loading) return
    setLoading(true)
    try {
      await postScriptNav(direction)
    } catch {
      toast.error('Script navigation failed')
    } finally {
      setLoading(false)
    }
  }

  const progress =
    scriptState && scriptState.segment_duration > 0
      ? Math.max(0, Math.min(100,
          ((scriptState.segment_duration - scriptState.remaining_seconds) / scriptState.segment_duration) * 100,
        ))
      : 0

  const remaining = scriptState
    ? `${Math.floor(scriptState.remaining_seconds / 60)}:${String(Math.floor(scriptState.remaining_seconds % 60)).padStart(2, '0')}`
    : '--:--'

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      {/* progress */}
      <div>
        <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>{scriptState?.title ?? '未开始'}</span>
          <span className="tabular-nums">{remaining}</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all duration-1000"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* goal */}
      {scriptState?.goal && (
        <p className="text-xs leading-relaxed text-muted-foreground">{scriptState.goal}</p>
      )}

      {/* cue */}
      {scriptState?.cue && scriptState.cue.length > 0 && (
        <div className="rounded-lg border-l-2 border-primary/50 bg-primary/5 py-2 pl-3 pr-2">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary/70">
            话术 · {scriptState.must_say ? '必说' : '融入'}
          </p>
          <ul className="space-y-1">
            {scriptState.cue.map((line, i) => (
              <li key={i} className="text-xs leading-relaxed">{line}</li>
            ))}
          </ul>
        </div>
      )}

      {!scriptState && (
        <p className="text-xs text-muted-foreground">直播开始后显示当前阶段</p>
      )}

      {/* nav */}
      <div className="mt-auto flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={!running || loading}
          onClick={() => handleNav('prev')}
        >
          <ChevronLeftIcon className="mr-1 size-3.5" />
          上一段
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={!running || loading}
          onClick={() => handleNav('next')}
        >
          下一段
          <ChevronRightIcon className="ml-1 size-3.5" />
        </Button>
      </div>
    </div>
  )
}
