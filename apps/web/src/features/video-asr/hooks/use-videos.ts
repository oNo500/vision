'use client'

import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'
import { apiFetch } from '@/lib/api-fetch'

export type VideoItem = {
  video_id: string
  url: string
  source: string
  title: string | null
  uploader: string | null
  duration_sec: number | null
  asr_model: string
  processed_at: string
}

export function useVideos() {
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const headers = env.NEXT_PUBLIC_API_KEY ? { 'X-API-Key': env.NEXT_PUBLIC_API_KEY } : undefined
    const res = await apiFetch<VideoItem[]>('api/intelligence/video-asr/videos', { silent: true, headers })
    if (res.ok) setVideos(res.data)
    setLoading(false)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { videos, loading, refresh }
}
