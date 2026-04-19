'use client'

import { useState } from 'react'

import { Button } from '@workspace/ui/components/button'

import {
  CATEGORY_LABELS,
  RAG_CATEGORIES,
  type RagCategory,
  type RagSource,
} from '@/features/live/hooks/use-rag-library'

export function FileList({
  sources,
  onDelete,
  disabled = false,
}: {
  sources: RagSource[]
  onDelete: (category: RagCategory, filename: string) => Promise<boolean>
  disabled?: boolean
}) {
  const [pendingDelete, setPendingDelete] = useState<RagSource | null>(null)

  const grouped = RAG_CATEGORIES.map((category) => ({
    category,
    files: sources.filter((s) => s.category === category),
  }))

  if (sources.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">
        尚未上传任何话术文件。上传首个文件后点击「重建索引」即可启用。
      </div>
    )
  }

  return (
    <>
      <div className="flex flex-col gap-4">
        {grouped.map(({ category, files }) => (
          <div key={category}>
            <h3 className="mb-2 text-sm font-medium">
              {CATEGORY_LABELS[category]}
              <span className="ml-2 text-xs text-muted-foreground">({files.length})</span>
            </h3>
            {files.length === 0 ? (
              <div className="rounded border border-dashed p-3 text-xs text-muted-foreground">
                暂无文件
              </div>
            ) : (
              <ul className="flex flex-col divide-y rounded border">
                {files.map((src) => {
                  const filename = src.rel_path.slice(category.length + 1)
                  return (
                    <li
                      key={src.rel_path}
                      className="flex items-center justify-between gap-3 px-3 py-2"
                    >
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate text-sm">{filename}</span>
                        <span className="text-xs text-muted-foreground">
                          {src.indexed ? `${src.chunks} chunks` : '待索引'}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        disabled={disabled}
                        onClick={() => setPendingDelete(src)}
                      >
                        删除
                      </Button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        ))}
      </div>

      {pendingDelete && (
        <ConfirmDialog
          message={`确认删除 ${pendingDelete.rel_path}？删除后需要「重建索引」才能从向量库移除。`}
          onCancel={() => setPendingDelete(null)}
          onConfirm={async () => {
            const filename = pendingDelete.rel_path.slice(
              pendingDelete.category.length + 1,
            )
            await onDelete(pendingDelete.category, filename)
            setPendingDelete(null)
          }}
        />
      )}
    </>
  )
}

function ConfirmDialog({
  message,
  onCancel,
  onConfirm,
}: {
  message: string
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onCancel}
    >
      <div
        className="flex flex-col gap-4 rounded-lg bg-background p-6 shadow-lg max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm">{message}</p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            取消
          </Button>
          <Button variant="destructive" size="sm" onClick={onConfirm}>
            删除
          </Button>
        </div>
      </div>
    </div>
  )
}
