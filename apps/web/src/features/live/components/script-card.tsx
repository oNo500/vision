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
    <div className="rounded-lg border bg-background p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">脚本进度</span>
        {scriptState?.segment_id && (
          <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-foreground">
            {scriptState.segment_id}
          </span>
        )}
      </div>

      {/* progress bar */}
      <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-1000"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mb-3 text-right text-xs tabular-nums text-muted-foreground">剩余 {remaining}</div>

      {/* segment info */}
      {scriptState?.segment_id ? (
        <div className="mb-4 space-y-2">
          {scriptState.title && (
            <p className="text-sm font-medium text-foreground">{scriptState.title}</p>
          )}
          {scriptState.goal && (
            <p className="text-xs leading-relaxed text-muted-foreground">{scriptState.goal}</p>
          )}
          {scriptState.cue.length > 0 && (
            <div className="rounded border border-dashed border-muted-foreground/40 bg-muted/50 px-3 py-2">
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                话术{scriptState.must_say ? '（必说）' : '（融入）'}
              </p>
              <ul className="space-y-0.5">
                {scriptState.cue.map((line, i) => (
                  <li key={i} className="text-xs text-foreground">· {line}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p className="mb-4 text-sm text-muted-foreground">未开始</p>
      )}

      {/* nav buttons */}
      <div className="flex gap-2">
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
