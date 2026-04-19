'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { apiFetch } from '@/lib/api-fetch'

export type RagSource = {
  rel_path: string
  category: RagCategory
  chunks: number
  sha256: string
  indexed: boolean
}

export type RagStatus = {
  indexed: boolean
  dirty: boolean
  chunk_count: number
  build_time: string | null
  file_count: number
  sources: RagSource[]
}

export type RagBuildStatus = {
  running: boolean
  last_build_time: string | null
  last_error: string | null
}

export const RAG_CATEGORIES = [
  'scripts',
  'competitor_clips',
  'product_manual',
  'qa_log',
] as const

export type RagCategory = (typeof RAG_CATEGORIES)[number]

export const CATEGORY_LABELS: Record<RagCategory, string> = {
  scripts: '脚本',
  competitor_clips: '爆款片段',
  product_manual: '产品手册',
  qa_log: '社群问答',
}

const BASE = (libId: string) => `api/intelligence/rag-libraries/${libId}`
const BUILD_POLL_MS = 1500

export function useRagLibrary(libId: string) {
  const [status, setStatus] = useState<RagStatus | null>(null)
  const [buildStatus, setBuildStatus] = useState<RagBuildStatus>({
    running: false,
    last_build_time: null,
    last_error: null,
  })
  const [loading, setLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refetch = useCallback(async () => {
    const res = await apiFetch<RagStatus>(`${BASE(libId)}/status`, { silent: true })
    if (res.ok) setStatus(res.data)
  }, [libId])

  const refetchBuild = useCallback(async () => {
    const res = await apiFetch<RagBuildStatus>(`${BASE(libId)}/rebuild/status`, { silent: true })
    if (!res.ok) return null
    const next = res.data
    setBuildStatus(prev =>
      prev.running === next.running && prev.last_build_time === next.last_build_time && prev.last_error === next.last_error
        ? prev : next,
    )
    return next
  }, [libId])

  useEffect(() => { Promise.all([refetch(), refetchBuild()]) }, [refetch, refetchBuild])

  useEffect(() => {
    if (!buildStatus.running) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return
    }
    pollRef.current = setInterval(async () => {
      const next = await refetchBuild()
      if (next && !next.running) {
        await refetch()
        if (next.last_error) toast.error(`构建失败: ${next.last_error.split('\n')[0]}`)
        else toast.success('索引已重建')
      }
    }, BUILD_POLL_MS)
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  }, [buildStatus.running, refetch, refetchBuild])

  const upload = useCallback(async (files: File[], category: RagCategory): Promise<boolean[]> => {
    setLoading(true)
    try {
      const results = await Promise.all(files.map(async (file) => {
        const form = new FormData()
        form.append('category', category)
        form.append('file', file)
        const res = await apiFetch<{ overwritten: boolean; rel_path: string }>(
          `${BASE(libId)}/files`,
          { method: 'POST', body: form, fallbackError: `上传失败: ${file.name}` },
        )
        if (res.ok) toast.success(res.data.overwritten ? `已覆盖 ${res.data.rel_path}` : `已上传 ${res.data.rel_path}`)
        return res.ok
      }))
      await refetch()
      return results
    } finally {
      setLoading(false)
    }
  }, [libId, refetch])

  const remove = useCallback(async (category: RagCategory, filename: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(
        `${BASE(libId)}/files/${category}/${encodeURIComponent(filename)}`,
        { method: 'DELETE', fallbackError: '删除失败' },
      )
      if (res.ok) { toast.success(`已删除 ${category}/${filename}`); await refetch() }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [libId, refetch])

  const rebuild = useCallback(async (): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`${BASE(libId)}/rebuild`, { method: 'POST', silent: true })
      if (!res.ok) {
        if (res.status === 409) toast.info('构建已在进行中')
        else toast.error('启动构建失败')
        return false
      }
      setBuildStatus(prev => ({ ...prev, running: true, last_error: null }))
      return true
    } finally {
      setLoading(false)
    }
  }, [libId])

  const importTranscript = useCallback(async (videoId: string): Promise<boolean> => {
    setLoading(true)
    try {
      const res = await apiFetch<{ imported: string[]; video_id: string }>(
        `${BASE(libId)}/import-transcript`,
        { method: 'POST', body: { video_id: videoId }, fallbackError: '导入失败' },
      )
      if (res.ok) {
        toast.success(`已导入 ${res.data.imported.length} 个文件`)
        await refetch()
      }
      return res.ok
    } finally {
      setLoading(false)
    }
  }, [libId, refetch])

  return { status, buildStatus, loading, upload, remove, rebuild, importTranscript, refetch }
}
