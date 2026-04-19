'use client'

import { useCallback, useEffect, useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { toast } from '@workspace/ui/components/sonner'
import { apiFetch } from '@/lib/api-fetch'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export function PlanRagLibraries({ planId }: { planId: string }) {
  const { libraries } = useRagLibraries()
  const [selected, setSelected] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiFetch<{ rag_library_ids: string[] }>(`live/plans/${planId}`, { silent: true }).then((res) => {
      if (res.ok) setSelected(res.data.rag_library_ids ?? [])
    })
  }, [planId])

  const toggle = useCallback((id: string) => {
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }, [])

  const save = useCallback(async () => {
    setSaving(true)
    try {
      const res = await apiFetch(`live/plans/${planId}/rag-libraries`, {
        method: 'PUT',
        body: { library_ids: selected },
        fallbackError: '保存失败',
      })
      if (res.ok) toast.success('已保存关联RAG')
    } finally {
      setSaving(false)
    }
  }, [planId, selected])

  if (libraries.length === 0) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        暂无RAG。请先在「RAG」页面创建。
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h2 className="text-base font-semibold">关联RAG</h2>
      <p className="text-sm text-muted-foreground">勾选后点击保存，直播时 AI 导播将从这些库中检索话术参考。</p>
      <div className="flex flex-col gap-2">
        {libraries.map((lib) => (
          <label key={lib.id} className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/50">
            <input
              type="checkbox"
              checked={selected.includes(lib.id)}
              onChange={() => toggle(lib.id)}
            />
            <div>
              <p className="text-sm font-medium">{lib.name}</p>
              <p className="text-xs text-muted-foreground">{lib.id}</p>
            </div>
          </label>
        ))}
      </div>
      <Button size="sm" onClick={save} disabled={saving}>
        {saving ? '保存中…' : '保存'}
      </Button>
    </div>
  )
}
