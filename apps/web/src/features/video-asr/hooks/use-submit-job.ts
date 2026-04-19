'use client'

import { useCallback, useState } from 'react'

import { env } from '@/config/env'
import { apiFetch } from '@/lib/api-fetch'

type JobResponse = {
  job_id: string
  video_ids: string[]
  status: string
}

export function useSubmitJob() {
  const [submitting, setSubmitting] = useState(false)

  const submit = useCallback(async (urls: string[]): Promise<string | null> => {
    setSubmitting(true)
    const res = await apiFetch<JobResponse>('api/intelligence/video-asr/jobs', {
      method: 'POST',
      body: { urls },
      headers: env.NEXT_PUBLIC_API_KEY ? { 'X-API-Key': env.NEXT_PUBLIC_API_KEY } : {},
      fallbackError: '提交任务失败',
    })
    setSubmitting(false)
    return res.ok ? res.data.job_id : null
  }, [])

  return { submit, submitting }
}
