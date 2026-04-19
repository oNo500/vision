'use client'

import Link from 'next/link'
import { appPaths } from '@/config/app-paths'
import type { VideoItem } from '@/features/video-asr/hooks/use-videos'

function formatDuration(sec: number | null): string {
  if (sec === null) return '--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`
}

type Props = {
  videos: VideoItem[]
  loading: boolean
}

export function VideoList({ videos, loading }: Props) {
  if (loading) {
    return <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">加载中...</div>
  }
  if (videos.length === 0) {
    return <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">暂无视频，点击右上角提交任务</div>
  }
  return (
    <div className="divide-y">
      {videos.map((v) => (
        <Link
          key={v.video_id}
          href={appPaths.dashboard.videoAsrDetail(v.video_id).href}
          className="flex items-center gap-4 px-4 py-3 text-sm hover:bg-muted/50 transition-colors"
        >
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{v.title ?? v.video_id}</div>
            <div className="truncate text-xs text-muted-foreground">
              {[v.uploader, v.source].filter(Boolean).join(' · ')}
            </div>
          </div>
          <div className="shrink-0 tabular-nums text-xs text-muted-foreground">{formatDuration(v.duration_sec)}</div>
          <div className="shrink-0 text-xs text-muted-foreground">{v.processed_at ? new Date(v.processed_at).toLocaleDateString('zh-CN') : ''}</div>
        </Link>
      ))}
    </div>
  )
}
