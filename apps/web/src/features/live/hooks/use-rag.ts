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

const BUILD_POLL_INTERVAL_MS = 1500

function base(planId: string): string {
  return `live/plans/${planId}/rag`
}

export function useRag(planId: string) {
  const [status, setStatus] = useState<RagStatus | null>(null)
  const [buildStatus, setBuildStatus] = useState<RagBuildStatus>({
    running: false,
    last_build_time: null,
    last_error: null,
  })
  const [loading, setLoading] = useState(false)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refetch = useCallback(async () => {
    const res = await apiFetch<RagStatus>(`${base(planId)}/`, { silent: true })
    if (res.ok) setStatus(res.data)
  }, [planId])

  const refetchBuildStatus = useCallback(async () => {
    const res = await apiFetch<RagBuildStatus>(`${base(planId)}/rebuild/status`, { silent: true })
    if (!res.ok) return null
    const next = res.data
    // Shallow-equal guard: avoid re-renders from 1.5s polling that fetches
    // the same object every tick while nothing is running.
    setBuildStatus((prev) =>
      prev.running === next.running
        && prev.last_build_time === next.last_build_time
        && prev.last_error === next.last_error
        ? prev
        : next,
    )
    return next
  }, [planId])

  useEffect(() => {
    Promise.all([refetch(), refetchBuildStatus()])
  }, [refetch, refetchBuildStatus])

  // Poll build status while running, stop when it flips to idle.
  useEffect(() => {
    if (!buildStatus.running) {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
      return
    }
    pollTimerRef.current = setInterval(async () => {
      const next = await refetchBuildStatus()
      if (next && !next.running) {
        await refetch()
        if (next.last_error) {
          toast.error(`Build failed: ${next.last_error.split('\n')[0]}`)
        } else {
          toast.success('Index rebuilt')
        }
      }
    }, BUILD_POLL_INTERVAL_MS)
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [buildStatus.running, refetch, refetchBuildStatus])

  const uploadOne = useCallback(
    async (file: File, category: RagCategory): Promise<boolean> => {
      const form = new FormData()
      form.append('category', category)
      form.append('file', file)
      const res = await apiFetch<{ overwritten: boolean; rel_path: string }>(
        `${base(planId)}/files`,
        {
          method: 'POST',
          body: form,
          fallbackError: `Upload failed: ${file.name}`,
        },
      )
      if (res.ok) {
        toast.success(
          res.data.overwritten ? `Overwrote ${res.data.rel_path}` : `Uploaded ${res.data.rel_path}`,
        )
      }
      return res.ok
    },
    [planId],
  )

  // Runs all uploads concurrently; refetches status exactly once after the
  // batch settles, regardless of success mix.
  const upload = useCallback(
    async (files: File[], category: RagCategory): Promise<boolean[]> => {
      setLoading(true)
      try {
        const results = await Promise.all(files.map((f) => uploadOne(f, category)))
        await refetch()
        return results
      } finally {
        setLoading(false)
      }
    },
    [uploadOne, refetch],
  )

  const remove = useCallback(
    async (category: RagCategory, filename: string) => {
      setLoading(true)
      try {
        const res = await apiFetch<unknown>(
          `${base(planId)}/files/${category}/${encodeURIComponent(filename)}`,
          { method: 'DELETE', fallbackError: 'Delete failed' },
        )
        if (res.ok) {
          toast.success(`Deleted ${category}/${filename}`)
          await refetch()
        }
        return res.ok
      } finally {
        setLoading(false)
      }
    },
    [planId, refetch],
  )

  const rebuild = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiFetch<unknown>(`${base(planId)}/rebuild`, {
        method: 'POST',
        silent: true,
      })
      if (!res.ok) {
        if (res.status === 409) toast.info('Build already running')
        else toast.error('Failed to start rebuild')
        return false
      }
      // Optimistically flip to running so polling kicks in.
      setBuildStatus((prev) => ({ ...prev, running: true, last_error: null }))
      return true
    } finally {
      setLoading(false)
    }
  }, [planId])

  return {
    status,
    buildStatus,
    loading,
    upload,
    remove,
    rebuild,
    refetch,
  }
}
