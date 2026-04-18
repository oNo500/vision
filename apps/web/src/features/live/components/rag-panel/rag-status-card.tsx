'use client'

import type { RagStatus } from '@/features/live/hooks/use-rag'

function formatBuildTime(iso: string | null): string {
  if (!iso) return '从未构建'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function RagStatusCard({ status }: { status: RagStatus }) {
  return (
    <div className="grid grid-cols-4 gap-4 rounded-lg border p-4">
      <StatusItem label="文件数" value={String(status.file_count)} />
      <StatusItem label="Chunk 数" value={String(status.chunk_count)} />
      <StatusItem
        label="上次构建"
        value={formatBuildTime(status.build_time)}
      />
      <StatusItem
        label="状态"
        value={status.dirty ? '有未索引变更' : status.indexed ? '已同步' : '未构建'}
        tone={status.dirty ? 'warning' : 'default'}
      />
    </div>
  )
}

function StatusItem({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: string
  tone?: 'default' | 'warning'
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={`text-sm font-medium ${tone === 'warning' ? 'text-amber-600' : ''}`}
      >
        {value}
      </span>
    </div>
  )
}
