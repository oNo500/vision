'use client'

import { Tooltip } from '@base-ui/react/tooltip'
import { InfoIcon } from 'lucide-react'
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

const STAGE_LABELS: Record<string, string> = {
  ingest: '下载',
  preprocess: '预处理',
  transcribe: '转录',
  merge: '合并',
  render: '渲染',
  analyze: '分析',
  load: '入库',
}

const STAGE_TIPS: Record<string, string> = {
  ingest: '通过 yt-dlp 下载视频及元数据',
  preprocess: '分离人声、切分音频片段',
  transcribe: '并发调用 Gemini / FunASR 识别各片段。Gemini 失败时自动重试最多 2 次（首次等 15s，第二次等 30s），可重试错误包括：429 限流、5xx 错误、截断响应。',
  merge: '合并片段结果、去重、清洗文本',
  render: '生成 .md 转录稿和 .srt 字幕文件',
  analyze: '用 LLM 生成摘要与风格分析',
  load: '将结果写入数据库',
}

type Props = {
  state: VideoProgressState
}

function formatElapsed(sec: number): string {
  if (sec < 60) return `${sec.toFixed(0)}s`
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function VideoProgress({ state }: Props) {
  const stageMap = new Map(state.stages.map((s) => [s.stage, s]))
  const { done, total, chunks } = state.transcribeProgress

  return (
    <div className="space-y-3 font-mono text-sm">
      {STAGE_ORDER.map((name) => {
        const s = stageMap.get(name)
        const status = s?.status ?? 'pending'

        let elapsed: string = ''
        if (s?.duration_sec != null) {
          elapsed = `${s.duration_sec.toFixed(1)}s`
        } else if (status === 'running' && s?.started_at) {
          const sec = (state.now - new Date(s.started_at).getTime()) / 1000
          elapsed = formatElapsed(sec)
        }

        return (
          <div key={name} className="flex items-center gap-3">
            <span className={`w-4 text-center ${STATUS_COLOR[status] ?? 'text-muted-foreground'}`}>
              {STATUS_ICON[status] ?? '○'}
            </span>
            <span className="flex w-20 items-center gap-1 text-muted-foreground">
              {STAGE_LABELS[name] ?? name}
              <Tooltip.Root>
                <Tooltip.Trigger
                  delay={300}
                  className="flex cursor-default items-center text-muted-foreground/40 hover:text-muted-foreground transition-colors"
                  render={<span />}
                >
                  <InfoIcon size={11} />
                </Tooltip.Trigger>
                <Tooltip.Portal>
                  <Tooltip.Positioner side="right" sideOffset={8}>
                    <Tooltip.Popup className="z-50 max-w-[200px] rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background">
                      {STAGE_TIPS[name]}
                    </Tooltip.Popup>
                  </Tooltip.Positioner>
                </Tooltip.Portal>
              </Tooltip.Root>
            </span>
            <span className={`w-16 tabular-nums text-xs ${status === 'running' ? 'text-blue-500' : 'text-muted-foreground'}`}>
              {elapsed}
            </span>
            {name === 'transcribe' && status !== 'pending' && (
              <span className="text-xs text-muted-foreground">
                {done} / {total ?? '?'}
                {state.transcribeProgress.retrying.length > 0 && (
                  <span className="ml-2 text-yellow-500">
                    重试 {state.transcribeProgress.retrying.map(r => `#${r.id}(${r.attempt}次)`).join(' ')}
                  </span>
                )}
              </span>
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
