'use client'

import { useEffect, useRef, useState } from 'react'
import { env } from '@/config/env'

export type StageStatus = {
  stage: string
  status: 'running' | 'done' | 'failed' | 'pending'
  duration_sec: number | null
  started_at: string | null
}

export type ChunkInfo = {
  id: number
  engine: string
}

export type RetryingChunk = {
  id: number
  attempt: number
  wait_sec: number | null
  error: string | null
}

export type TranscribeProgress = {
  done: number
  total: number | null
  chunks: ChunkInfo[]
  retrying: RetryingChunk[]
}

export type VideoProgressState = {
  stages: StageStatus[]
  transcribeProgress: TranscribeProgress
  costUsd: number
  finished: boolean
  connected: boolean
  now: number
}

const INITIAL: VideoProgressState = {
  stages: [],
  transcribeProgress: { done: 0, total: null, chunks: [], retrying: [] },
  costUsd: 0,
  finished: false,
  connected: false,
  now: Date.now(),
}

const STAGE_ORDER = ['ingest', 'preprocess', 'transcribe', 'merge', 'render', 'analyze', 'load']

export function useVideoProgress(videoId: string): VideoProgressState {
  const [state, setState] = useState<VideoProgressState>(INITIAL)
  const hasRunning = state.stages.some((s) => s.status === 'running')
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const keyParam = env.NEXT_PUBLIC_API_KEY ? `?api_key=${encodeURIComponent(env.NEXT_PUBLIC_API_KEY)}` : ''
    const url = `${env.NEXT_PUBLIC_API_URL}/api/intelligence/video-asr/videos/${videoId}/progress${keyParam}`
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
          now: Date.now(),
        })
      } catch {
        // ignore malformed frames
      }
    })

    return () => es.close()
  }, [videoId])

  // tick every second while a stage is running to update elapsed time
  useEffect(() => {
    if (hasRunning) {
      tickRef.current = setInterval(() => {
        setState((s) => ({ ...s, now: Date.now() }))
      }, 1000)
    } else {
      if (tickRef.current) clearInterval(tickRef.current)
    }
    return () => {
      if (tickRef.current) clearInterval(tickRef.current)
    }
  }, [hasRunning])

  return state
}
