'use client'

import { Button } from '@workspace/ui/components/button'

import { useRag } from '@/features/live/hooks/use-rag'

import { FileList } from './file-list'
import { RagStatusCard } from './rag-status-card'
import { UploadDropzone } from './upload-dropzone'

export function RagPanel({ planId }: { planId: string }) {
  const { status, buildStatus, loading, upload, remove, rebuild } = useRag(planId)

  if (!status) {
    return <div className="p-6 text-sm text-muted-foreground">加载中…</div>
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">话术库</h2>
        <Button
          size="sm"
          variant={status.dirty ? 'default' : 'outline'}
          onClick={rebuild}
          disabled={loading || buildStatus.running}
        >
          {buildStatus.running ? '构建中…' : status.dirty ? '重建索引 (有未索引变更)' : '重建索引'}
        </Button>
      </div>

      <RagStatusCard status={status} />

      <UploadDropzone onUpload={upload} disabled={loading || buildStatus.running} />

      <FileList
        sources={status.sources}
        onDelete={remove}
        disabled={loading || buildStatus.running}
      />

      {buildStatus.last_error && !buildStatus.running && (
        <div className="rounded border border-destructive bg-destructive/10 p-3 text-xs text-destructive whitespace-pre-wrap">
          上次构建失败:{buildStatus.last_error.split('\n')[0]}
        </div>
      )}
    </div>
  )
}
