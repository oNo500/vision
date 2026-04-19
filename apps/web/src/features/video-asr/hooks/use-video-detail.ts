'use client'

import { useEffect, useState } from 'react'
import { env } from '@/config/env'
import { apiFetch } from '@/lib/api-fetch'
import type { VideoItem } from './use-videos'

type VideoDetail = {
  meta: VideoItem | null
  transcriptMd: string | null
  summaryMd: string | null
  loading: boolean
}

export function useVideoDetail(videoId: string): VideoDetail {
  const [meta, setMeta] = useState<VideoItem | null>(null)
  const [transcriptMd, setTranscriptMd] = useState<string | null>(null)
  const [summaryMd, setSummaryMd] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const base = `api/intelligence/video-asr/videos/${videoId}`
    const headers = env.NEXT_PUBLIC_API_KEY ? { 'X-API-Key': env.NEXT_PUBLIC_API_KEY } : undefined
    Promise.all([
      apiFetch<VideoItem>(base, { silent: true, headers }),
      apiFetch<string>(`${base}/transcript.md`, { silent: true, headers }),
      apiFetch<string>(`${base}/summary`, { silent: true, headers }),
    ]).then(([metaRes, transcriptRes, summaryRes]) => {
      if (!mounted) return
      if (metaRes.ok) setMeta(metaRes.data)
      if (transcriptRes.ok) setTranscriptMd(transcriptRes.data)
      if (summaryRes.ok) setSummaryMd(summaryRes.data)
      setLoading(false)
    })
    return () => { mounted = false }
  }, [videoId])

  return { meta, transcriptMd, summaryMd, loading }
}
