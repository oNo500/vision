'use client'

import { useCallback, useState } from 'react'

import { apiFetch } from '@/lib/api-fetch'

type EditPatch = { text: string; speech_prompt?: string | null }

const NETWORK_ERROR = '无法连接到后端'

export function useTtsMutations() {
  const [loading, setLoading] = useState(false)

  const remove = useCallback(async (id: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`live/tts/queue/${id}`, {
        method: 'DELETE',
        fallbackError: '删除失败',
        networkError: NETWORK_ERROR,
      })
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [])

  const edit = useCallback(async (id: string, patch: EditPatch): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`live/tts/queue/${id}`, {
        method: 'PATCH',
        body: patch,
        fallbackError: '编辑失败',
        networkError: NETWORK_ERROR,
      })
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [])

  const reorder = useCallback(async (stage: 'pending' | 'synthesized', ids: string[]): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>('live/tts/queue/reorder', {
        method: 'POST',
        body: { stage, ids },
        fallbackError: '顺序已过时，请重试',
        networkError: NETWORK_ERROR,
      })
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [])

  return { remove, edit, reorder, loading }
}
