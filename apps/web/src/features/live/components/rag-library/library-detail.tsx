'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { useRagLibrary } from '@/features/live/hooks/use-rag-library'
import { FileList } from '@/features/live/components/rag-panel/file-list'
import { RagStatusCard } from '@/features/live/components/rag-panel/rag-status-card'
import { UploadDropzone } from '@/features/live/components/rag-panel/upload-dropzone'
import { ImportTranscriptTab } from './import-transcript-tab'

type Tab = 'files' | 'import'

export function LibraryDetail({ libId, libName }: { libId: string; libName: string }) {
  const { status, buildStatus, loading, upload, remove, rebuild, importTranscript } =
    useRagLibrary(libId)
  const [tab, setTab] = useState<Tab>('files')

  if (!status) {
    return <div className="p-6 text-sm text-muted-foreground">加载中…</div>
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{libName}</h2>
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

      <div className="flex gap-2 border-b">
        <button
          type="button"
          className={`pb-2 text-sm ${tab === 'files' ? 'border-b-2 border-foreground font-medium' : 'text-muted-foreground'}`}
          onClick={() => setTab('files')}
        >
          文件
        </button>
        <button
          type="button"
          className={`pb-2 text-sm ${tab === 'import' ? 'border-b-2 border-foreground font-medium' : 'text-muted-foreground'}`}
          onClick={() => setTab('import')}
        >
          从转录导入
        </button>
      </div>

      {tab === 'files' && (
        <>
          <UploadDropzone onUpload={upload} disabled={loading || buildStatus.running} />
          <FileList sources={status.sources} onDelete={remove} disabled={loading || buildStatus.running} />
        </>
      )}

      {tab === 'import' && (
        <ImportTranscriptTab onImport={importTranscript} />
      )}

      {buildStatus.last_error && !buildStatus.running && (
        <div className="rounded border border-destructive bg-destructive/10 p-3 text-xs text-destructive whitespace-pre-wrap">
          上次构建失败: {buildStatus.last_error.split('\n')[0]}
        </div>
      )}
    </div>
  )
}
