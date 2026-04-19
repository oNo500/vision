'use client'

import type { VideoProgressState } from '@/features/video-asr/hooks/use-video-progress'

const STATUS_ICON: Record<string, string> = {
  done: '●',
  running: '◎',
  failed: '✗',
  pending: '○',
}

const STATUS_COLOR: Record<string, string> = {
  done: 'text-green-500',
  running: 'text-blue-500 animate-pulse',
  failed: 'text-red-500',
  pending: 'text-muted-foreground',
}

const STAGE_ORDER = ['ingest', 'preprocess', 'transcribe', 'merge', 'render', 'analyze', 'load']

type Props = {
  state: VideoProgressState
}

export function VideoProgress({ state }: Props) {
  const stageMap = new Map(state.stages.map((s) => [s.stage, s]))
  const { done, total, chunks } = state.transcribeProgress

  return (
    <div className="space-y-3 font-mono text-sm">
      {STAGE_ORDER.map((name) => {
        const s = stageMap.get(name)
        const status = s?.status ?? 'pending'
        return (
          <div key={name} className="flex items-center gap-3">
            <span className={`w-4 text-center ${STATUS_COLOR[status] ?? 'text-muted-foreground'}`}>
              {STATUS_ICON[status] ?? '○'}
            </span>
            <span className="w-20 text-muted-foreground">{name}</span>
            <span className="w-16 tabular-nums text-xs text-muted-foreground">
              {s?.duration_sec != null ? `${s.duration_sec.toFixed(1)}s` : ''}
            </span>
            {name === 'transcribe' && status === 'running' && (
              <span className="text-xs text-muted-foreground">{done} / {total ?? '?'}</span>
            )}
          </div>
        )
      })}

      {chunks.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {chunks.map((c) => (
            <span
              key={c.id}
              title={c.engine}
              className={`rounded px-1.5 py-0.5 text-xs ${
                c.engine.startsWith('funasr')
                  ? 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300'
                  : 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
              }`}
            >
              {c.engine.startsWith('funasr') ? 'F' : 'G'}
            </span>
          ))}
        </div>
      )}

      {state.costUsd > 0 && (
        <div className="pt-2 text-xs text-muted-foreground">
          费用: ${state.costUsd.toFixed(4)}
        </div>
      )}
    </div>
  )
}
