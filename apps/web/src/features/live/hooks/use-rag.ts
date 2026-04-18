'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { toast } from '@workspace/ui/components/sonner'

import { env } from '@/config/env'

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

const BUILD_POLL_INTERVAL_MS = 1500

function base(planId: string): string {
  return `${env.NEXT_PUBLIC_API_URL}/live/plans/${planId}/rag`
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
    try {
      const res = await fetch(`${base(planId)}/`)
      if (res.ok) setStatus(await res.json())
    } catch { /* backend unreachable */ }
  }, [planId])

  const refetchBuildStatus = useCallback(async () => {
    try {
      const res = await fetch(`${base(planId)}/rebuild/status`)
      if (res.ok) {
        const next = (await res.json()) as RagBuildStatus
        setBuildStatus(next)
        return next
      }
    } catch { /* backend unreachable */ }
    return null
  }, [planId])

  useEffect(() => {
    refetch()
    refetchBuildStatus()
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

  const upload = useCallback(
    async (file: File, category: RagCategory) => {
      setLoading(true)
      try {
        const form = new FormData()
        form.append('category', category)
        form.append('file', file)
        const res = await fetch(`${base(planId)}/files`, {
          method: 'POST',
          body: form,
        })
        if (!res.ok) {
          const detail = await res.json().catch(() => null)
          toast.error(
            typeof detail?.detail === 'string' ? detail.detail : 'Upload failed',
          )
          return false
        }
        const body = (await res.json()) as { overwritten: boolean; rel_path: string }
        toast.success(body.overwritten ? `Overwrote ${body.rel_path}` : `Uploaded ${body.rel_path}`)
        await refetch()
        return true
      } catch {
        toast.error('Cannot reach backend')
        return false
      } finally {
        setLoading(false)
      }
    },
    [planId, refetch],
  )

  const remove = useCallback(
    async (category: RagCategory, filename: string) => {
      setLoading(true)
      try {
        const res = await fetch(
          `${base(planId)}/files/${category}/${encodeURIComponent(filename)}`,
          { method: 'DELETE' },
        )
        if (!res.ok) {
          toast.error('Delete failed')
          return false
        }
        toast.success(`Deleted ${category}/${filename}`)
        await refetch()
        return true
      } catch {
        toast.error('Cannot reach backend')
        return false
      } finally {
        setLoading(false)
      }
    },
    [planId, refetch],
  )

  const rebuild = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${base(planId)}/rebuild`, { method: 'POST' })
      if (res.status === 409) {
        toast.info('Build already running')
        return false
      }
      if (!res.ok) {
        toast.error('Failed to start rebuild')
        return false
      }
      // Optimistically flip to running so polling kicks in.
      setBuildStatus((prev) => ({ ...prev, running: true, last_error: null }))
      return true
    } catch {
      toast.error('Cannot reach backend')
      return false
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
