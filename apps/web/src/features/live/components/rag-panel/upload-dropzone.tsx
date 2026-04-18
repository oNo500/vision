'use client'

import { useRef, useState, type DragEvent } from 'react'

import { Button } from '@workspace/ui/components/button'

import {
  RAG_CATEGORIES,
  type RagCategory,
} from '@/features/live/hooks/use-rag'

const CATEGORY_LABELS: Record<RagCategory, string> = {
  scripts: '脚本',
  competitor_clips: '爆款片段',
  product_manual: '产品手册',
  qa_log: '社群问答',
}

export function UploadDropzone({
  onUpload,
  disabled = false,
}: {
  onUpload: (file: File, category: RagCategory) => Promise<boolean>
  disabled?: boolean
}) {
  const [category, setCategory] = useState<RagCategory>('scripts')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    for (const file of Array.from(files)) {
      await onUpload(file, category)
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div
      className={`flex flex-col gap-3 rounded-lg border-2 border-dashed p-4 transition-colors ${
        dragging ? 'border-primary bg-muted' : 'border-border'
      } ${disabled ? 'opacity-50 pointer-events-none' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">类别</span>
        <select
          className="rounded border px-2 py-1 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value as RagCategory)}
          disabled={disabled}
        >
          {RAG_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABELS[c]}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept=".md,.txt"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          选择文件
        </Button>
        <span className="text-xs text-muted-foreground">
          支持 .md / .txt,单文件最大 5MB,可拖入此区域
        </span>
      </div>
    </div>
  )
}
