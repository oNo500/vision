'use client'

import { useCallback, useEffect, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { apiFetch } from '@/lib/api-fetch'

export type RagLibrary = {
  id: string
  name: string
  created_at: string
}

const BASE = 'api/intelligence/rag-libraries'

export function useRagLibraries() {
  const [libraries, setLibraries] = useState<RagLibrary[]>([])
  const [loading, setLoading] = useState(false)

  const refetch = useCallback(async () => {
    const res = await apiFetch<RagLibrary[]>(`${BASE}/`, { silent: true })
    if (res.ok) setLibraries(res.data)
  }, [])

  useEffect(() => { refetch() }, [refetch])

  const createLibrary = useCallback(async (id: string, name: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<RagLibrary>(`${BASE}/`, {
        method: 'POST',
        body: { id, name },
        fallbackError: '创建失败',
      })
      if (res.ok) {
        toast.success(`已创建RAG ${name}`)
        await refetch()
      }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [refetch])

  const deleteLibrary = useCallback(async (id: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`${BASE}/${id}`, {
        method: 'DELETE',
        fallbackError: '删除失败',
      })
      if (res.ok) {
        toast.success('已删除RAG')
        await refetch()
      }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [refetch])

  return { libraries, loading, createLibrary, deleteLibrary, refetch }
}
