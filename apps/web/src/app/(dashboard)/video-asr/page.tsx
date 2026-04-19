'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { PageHeader } from '@/components/page-header'
import { SubmitJobDialog } from '@/features/video-asr/components/submit-job-dialog'
import { VideoList } from '@/features/video-asr/components/video-list'
import { useSubmitJob } from '@/features/video-asr/hooks/use-submit-job'
import { useVideos } from '@/features/video-asr/hooks/use-videos'

export default function VideoAsrPage() {
  const { videos, loading, refresh } = useVideos()
  const { submit, submitting } = useSubmitJob()
  const [dialogOpen, setDialogOpen] = useState(false)

  async function handleSubmit(urls: string[]) {
    const jobId = await submit(urls)
    if (jobId) refresh()
    return jobId
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <PageHeader>
        <h1 className="text-sm font-semibold">视频转录</h1>
        <div className="flex-1" />
        <Button size="sm" onClick={() => setDialogOpen(true)}>提交任务</Button>
      </PageHeader>

      <div className="flex-1 overflow-auto">
        <VideoList videos={videos} loading={loading} />
      </div>

      <SubmitJobDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmit}
        submitting={submitting}
      />
    </div>
  )
}
