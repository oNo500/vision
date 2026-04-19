'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
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

  if (loading) {
    return <div className="p-8 text-sm text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4">
      {meta && (
        <div className="text-sm">
          <h2 className="text-base font-semibold">{meta.title ?? videoId}</h2>
          <div className="mt-1 text-xs text-muted-foreground">
            {meta.uploader} · {meta.source}
            {meta.duration_sec != null ? ` · ${Math.round(meta.duration_sec / 60)} 分钟` : ''}
          </div>
        </div>
      )}

      {!progressState.finished && (
        <div className="rounded-md border p-3">
          <VideoProgress state={progressState} />
        </div>
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

      <div className="flex-1 overflow-auto rounded-md border p-4">
        {tab === 'transcript' && (
          transcriptMd
            ? <pre className="whitespace-pre-wrap text-sm">{transcriptMd}</pre>
            : <div className="text-sm text-muted-foreground">转录尚未完成</div>
        )}
        {tab === 'summary' && (
          summaryMd
            ? <pre className="whitespace-pre-wrap text-sm">{summaryMd}</pre>
            : <div className="text-sm text-muted-foreground">摘要尚未完成</div>
        )}
      </div>
    </div>
  )
}
