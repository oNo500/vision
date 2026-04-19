'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Trash2Icon } from 'lucide-react'
import { Button } from '@workspace/ui/components/button'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@workspace/ui/components/collapsible'
import { MarkdownContent } from '@/components/markdown-content'
import { appPaths } from '@/config/app-paths'
import { env } from '@/config/env'
import { apiFetch } from '@/lib/api-fetch'
import { useVideoDetail } from '@/features/video-asr/hooks/use-video-detail'
import { useVideoProgress } from '@/features/video-asr/hooks/use-video-progress'
import { VideoProgress } from '@/features/video-asr/components/video-progress'

type Tab = 'transcript' | 'summary'

type Props = {
  videoId: string
}

export function VideoDetail({ videoId }: Props) {
  const { meta, transcriptMd, summaryMd, loading } = useVideoDetail(videoId)
  const progressState = useVideoProgress(videoId)
  const [tab, setTab] = useState<Tab>('transcript')
  const [deleting, setDeleting] = useState(false)
  const router = useRouter()

  async function handleDelete() {
    if (!confirm('确认删除该视频及所有转录数据？')) return
    setDeleting(true)
    const headers = env.NEXT_PUBLIC_API_KEY ? { 'X-API-Key': env.NEXT_PUBLIC_API_KEY } : undefined
    const res = await apiFetch(`api/intelligence/video-asr/videos/${videoId}`, {
      method: 'DELETE',
      headers,
      fallbackError: '删除失败',
    })
    if (res.ok) {
      router.push(appPaths.dashboard.videoAsr.href)
    } else {
      setDeleting(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-sm text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4">
      <div className="flex items-start justify-between gap-2">
        {meta && (
          <div className="min-w-0 text-sm">
            <h2 className="text-base font-semibold">{meta.title ?? videoId}</h2>
            <div className="mt-1 text-xs text-muted-foreground">
              {meta.uploader} · {meta.source}
              {meta.duration_sec != null ? ` · ${Math.round(meta.duration_sec / 60)} 分钟` : ''}
            </div>
          </div>
        )}
        <Button
          size="sm"
          variant="ghost"
          className="shrink-0 text-muted-foreground hover:text-destructive"
          disabled={deleting}
          onClick={handleDelete}
        >
          <Trash2Icon size={14} />
        </Button>
      </div>

      {!progressState.finished && (
        <Collapsible defaultOpen className="rounded-md border">
          <CollapsibleTrigger className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
            <span>处理进度</span>
            <div className="flex items-center gap-3 tabular-nums">
              {meta?.duration_sec != null && (
                <span>{Math.floor(meta.duration_sec / 60)}:{String(Math.floor(meta.duration_sec % 60)).padStart(2, '0')}</span>
              )}
              {meta?.source && <span>{meta.source}</span>}
              <span className="select-none">▾</span>
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="border-t px-3 pb-3 pt-2">
              <VideoProgress state={progressState} />
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      <div className="flex gap-2">
        <Button
          size="sm"
          variant={tab === 'transcript' ? 'default' : 'outline'}
          onClick={() => setTab('transcript')}
        >
          转录
        </Button>
        <Button
          size="sm"
          variant={tab === 'summary' ? 'default' : 'outline'}
          onClick={() => setTab('summary')}
        >
          摘要
        </Button>
      </div>

      <div className="flex-1 overflow-auto rounded-md border p-4 text-sm">
        {tab === 'transcript' && (
          transcriptMd
            ? <MarkdownContent>{transcriptMd}</MarkdownContent>
            : <div className="text-muted-foreground">转录尚未完成</div>
        )}
        {tab === 'summary' && (
          summaryMd
            ? <MarkdownContent>{summaryMd}</MarkdownContent>
            : <div className="text-muted-foreground">摘要尚未完成</div>
        )}
      </div>
    </div>
  )
}
