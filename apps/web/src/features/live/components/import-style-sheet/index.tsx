'use client'

import { useEffect, useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@workspace/ui/components/sheet'
import { apiFetch } from '@/lib/api-fetch'

type VideoSummary = {
  video_id: string
  title: string | null
  source: string
  duration_sec: number | null
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImport: (videoId: string) => Promise<boolean>
}

export function ImportStyleSheet({ open, onOpenChange, onImport }: Props) {
  const [videos, setVideos] = useState<VideoSummary[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) {
      setVideos([])
      return
    }
    apiFetch<VideoSummary[]>('api/intelligence/video-asr/videos', { silent: true }).then(
      (res) => { if (res.ok) setVideos(res.data) },
    )
  }, [open])

  async function handleImport(videoId: string) {
    setLoading(true)
    try {
      const ok = await onImport(videoId)
      if (ok) {
        onOpenChange(false)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>从视频导入风格</SheetTitle>
        </SheetHeader>
        <p className="mt-2 text-sm text-muted-foreground">
          选择一个已转录的视频，将其口头禅、开场话术、行动号召模式导入当前方案的人设与脚本。
        </p>
        {videos.length === 0 ? (
          <div className="mt-6 text-sm text-muted-foreground">暂无已完成的转录视频。</div>
        ) : (
          <div className="mt-4 flex flex-col divide-y">
            {videos.map((v) => {
              const durationMin = v.duration_sec ? Math.round(v.duration_sec / 60) : null
              return (
                <div key={v.video_id} className="flex items-center justify-between gap-3 py-3">
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-sm">{v.title ?? v.video_id}</span>
                    <span className="text-xs text-muted-foreground">
                      {v.source}{durationMin ? ` · ${durationMin}分钟` : ''}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="default"
                    disabled={loading}
                    onClick={() => handleImport(v.video_id)}
                  >
                    {'导入'}
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
