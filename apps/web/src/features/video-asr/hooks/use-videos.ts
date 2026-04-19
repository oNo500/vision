'use client'

import { useCallback, useEffect, useState } from 'react'

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
    const res = await apiFetch<VideoItem[]>('api/intelligence/video-asr/videos', { silent: true })
    if (res.ok) setVideos(res.data)
    setLoading(false)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { videos, loading, refresh }
}
