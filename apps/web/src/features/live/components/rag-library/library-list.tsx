'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@workspace/ui/components/button'
import { appPaths } from '@/config/app-paths'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export function LibraryList() {
  const router = useRouter()
  const { libraries, loading, createLibrary, deleteLibrary } = useRagLibraries()
  const [showCreate, setShowCreate] = useState(false)
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')

  async function handleCreate() {
    const ok = await createLibrary(newId, newName)
    if (ok) { setShowCreate(false); setNewId(''); setNewName('') }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">素材库</h1>
        <Button size="sm" onClick={() => setShowCreate(true)} disabled={loading}>
          + 新建素材库
        </Button>
      </div>

      {showCreate && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <input
            className="rounded border px-3 py-1.5 text-sm"
            placeholder="ID（小写字母+连字符，如 dong-yuhui）"
            value={newId}
            onChange={(e) => setNewId(e.target.value)}
          />
          <input
            className="rounded border px-3 py-1.5 text-sm"
            placeholder="显示名称（如 董宇辉）"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreate} disabled={loading || !newId || !newName}>
              创建
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>
              取消
            </Button>
          </div>
        </div>
      )}

      {libraries.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无素材库，点击「新建素材库」开始</p>
      ) : (
        <div className="flex flex-col gap-2">
          {libraries.map((lib) => (
            <div
              key={lib.id}
              className="flex items-center justify-between rounded-lg border p-4 cursor-pointer hover:bg-muted/50"
              onClick={() => router.push(appPaths.dashboard.library(lib.id).href)}
            >
              <div>
                <p className="text-sm font-medium">{lib.name}</p>
                <p className="text-xs text-muted-foreground">{lib.id}</p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="text-destructive hover:text-destructive"
                disabled={loading}
                onClick={(e) => { e.stopPropagation(); deleteLibrary(lib.id) }}
              >
                删除
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
