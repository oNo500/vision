'use client'

import { useCallback, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { env } from '@/config/env'

type EditPatch = { text: string; speech_prompt?: string | null }

export function useTtsMutations() {
  const [loading, setLoading] = useState(false)

  const remove = useCallback(async (id: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/${id}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: unknown }
        toast.error(typeof data.detail === 'string' ? data.detail : '删除失败')
        return false
      }
      return true
    } catch {
      toast.error('无法连接到后端')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const edit = useCallback(async (id: string, patch: EditPatch): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/${id}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(patch),
      })
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: unknown }
        toast.error(typeof data.detail === 'string' ? data.detail : '编辑失败')
        return false
      }
      return true
    } catch {
      toast.error('无法连接到后端')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const reorder = useCallback(async (stage: 'pending' | 'synthesized', ids: string[]): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/tts/queue/reorder`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ stage, ids }),
      })
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: unknown }
        toast.error(typeof data.detail === 'string' ? data.detail : '顺序已过时，请重试')
        return false
      }
      return true
    } catch {
      toast.error('无法连接到后端')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  return { remove, edit, reorder, loading }
}
