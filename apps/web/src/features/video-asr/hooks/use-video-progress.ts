'use client'

import { useEffect, useState } from 'react'
import { env } from '@/config/env'

export type StageStatus = {
  stage: string
  status: 'running' | 'done' | 'failed' | 'pending'
  duration_sec: number | null
}

export type ChunkInfo = {
  id: number
  engine: string
}

export type TranscribeProgress = {
  done: number
  total: number | null
  chunks: ChunkInfo[]
}

export type VideoProgressState = {
  stages: StageStatus[]
  transcribeProgress: TranscribeProgress
  costUsd: number
  finished: boolean
  connected: boolean
}

const INITIAL: VideoProgressState = {
  stages: [],
  transcribeProgress: { done: 0, total: null, chunks: [] },
  costUsd: 0,
  finished: false,
  connected: false,
}

const STAGE_ORDER = ['ingest', 'preprocess', 'transcribe', 'merge', 'render', 'analyze', 'load']

export function useVideoProgress(videoId: string): VideoProgressState {
  const [state, setState] = useState<VideoProgressState>(INITIAL)

  useEffect(() => {
    const url = `${env.NEXT_PUBLIC_API_URL}/api/intelligence/video-asr/videos/${videoId}/progress`
    const es = new EventSource(url)

    es.onopen = () => setState((s) => ({ ...s, connected: true }))
    es.onerror = () => setState((s) => ({ ...s, connected: false }))

    es.addEventListener('progress', (e: Event) => {
      const msg = e as MessageEvent
      try {
        const data = JSON.parse(msg.data as string) as {
          stages: StageStatus[]
          transcribe_progress: TranscribeProgress
          cost_usd: number
        }
        const statuses = new Map(data.stages.map((s) => [s.stage, s.status]))
        const finished =
          data.stages.length === STAGE_ORDER.length &&
          STAGE_ORDER.every((s) => statuses.get(s) === 'done' || statuses.get(s) === 'failed')
        setState({
          stages: data.stages,
          transcribeProgress: data.transcribe_progress,
          costUsd: data.cost_usd,
          finished,
          connected: true,
        })
      } catch {
        // ignore malformed frames
      }
    })

    return () => es.close()
  }, [videoId])

  return state
}
