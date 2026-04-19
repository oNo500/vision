'use client'

import { use } from 'react'
import Link from 'next/link'
import { ChevronLeftIcon } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { VideoDetail } from '@/features/video-asr/components/video-detail'
import { appPaths } from '@/config/app-paths'

export default function VideoAsrDetailPage({
  params,
}: {
  params: Promise<{ videoId: string }>
}) {
  const { videoId } = use(params)

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <PageHeader>
        <Link
          href={appPaths.dashboard.videoAsr.href}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeftIcon className="size-4" />
          视频转录
        </Link>
        <span className="font-mono text-sm text-muted-foreground">{videoId}</span>
      </PageHeader>
      <VideoDetail videoId={videoId} />
    </div>
  )
}
