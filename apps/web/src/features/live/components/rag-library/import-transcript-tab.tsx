'use client'

import { useEffect, useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { apiFetch } from '@/lib/api-fetch'

type VideoSummary = {
  video_id: string
  title: string | null
  source: string
  duration_sec: number | null
}

export function ImportTranscriptTab({
  onImport,
}: {
  onImport: (videoId: string) => Promise<boolean>
}) {
  const [videos, setVideos] = useState<VideoSummary[]>([])
  const [imported, setImported] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiFetch<VideoSummary[]>('api/intelligence/video-asr/videos', { silent: true }).then(
      (res) => { if (res.ok) setVideos(res.data) },
    )
  }, [])

  async function handleImport(videoId: string) {
    setLoading(true)
    try {
      const ok = await onImport(videoId)
      if (ok) setImported((prev) => new Set([...prev, videoId]))
    } finally {
      setLoading(false)
    }
  }

  if (videos.length === 0) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        暂无已完成的转录视频。先运行ASR流程。
      </div>
    )
  }

  return (
    <div className="flex flex-col divide-y">
      {videos.map((v) => {
        const isImported = imported.has(v.video_id)
        const durationMin = v.duration_sec ? Math.round(v.duration_sec / 60) : null
        return (
          <div key={v.video_id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-sm">{v.title ?? v.video_id}</span>
              <span className="text-xs text-muted-foreground">
                {v.source}{durationMin ? ` · ${durationMin}分钟` : ''}
              </span>
            </div>
            <Button
              size="sm"
              variant={isImported ? 'outline' : 'default'}
              disabled={loading}
              onClick={() => handleImport(v.video_id)}
            >
              {isImported ? '已导入' : '导入'}
            </Button>
          </div>
        )
      })}
    </div>
  )
}
