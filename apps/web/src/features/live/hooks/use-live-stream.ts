'use client'

import { useEffect, useMemo, useRef, useState } from 'react'

import { env } from '@/config/env'
import { apiFetch } from '@/lib/api-fetch'

export type LiveEvent = {
  type: string
  user: string
  text: string | null
  gift: string | null
  value: number
  is_follower: boolean
  ts: number
}

export type AiOutput = {
  content: string
  source: 'script' | 'agent' | 'inject'
  speech_prompt: string
  ts: number
}

export type TtsQueueItem = {
  id: string
  content: string
  speech_prompt: string | null
}

export type PipelineStage = 'pending' | 'synthesized' | 'playing' | 'done'

export type PipelineItem = {
  id: string
  content: string
  speech_prompt: string | null
  stage: PipelineStage
  urgent: boolean
  ts: number
}

export type ScriptState = {
  segment_id: string
  title: string
  goal: string
  cue: string[]
  must_say: boolean
  remaining_seconds: number
  segment_duration: number
  finished: boolean
}

const MAX_EVENTS = 200
const SKIP_TYPES = new Set(['ping', 'agent', 'script', 'tts_output', 'tts_playing', 'tts_queued', 'tts_synthesized', 'tts_done'])
const EVENTS_KEY = 'live_events_cache'
const AI_OUTPUTS_KEY = 'live_ai_outputs_cache'

function loadCache<T>(key: string): T[] {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return []
    return JSON.parse(raw) as T[]
  } catch {
    return []
  }
}

function saveCache<T>(key: string, items: T[]): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(items))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

export function applyLiveEvent(prev: PipelineItem[], raw: Record<string, unknown>): PipelineItem[] {
  const type = raw['type'] as string
  const id = raw['id'] as string | undefined

  if (type === 'tts_queued' && id) {
    return [
      ...prev,
      {
        id,
        content: raw['content'] as string,
        speech_prompt: (raw['speech_prompt'] as string | null) ?? null,
        stage: (raw['stage'] as PipelineStage) ?? 'pending',
        urgent: Boolean(raw['urgent']),
        ts: (raw['ts'] as number) ?? Date.now() / 1000,
      },
    ]
  }

  if (type === 'tts_synthesized' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    const current = prev[idx]
    if (idx < 0 || !current) return prev
    const updated = [...prev]
    updated[idx] = { ...current, stage: 'synthesized' }
    return updated
  }

  if (type === 'tts_playing' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    const current = prev[idx]
    if (idx < 0 || !current) {
      return [
        ...prev,
        {
          id,
          content: raw['content'] as string,
          speech_prompt: (raw['speech_prompt'] as string | null) ?? null,
          stage: 'playing',
          urgent: false,
          ts: (raw['ts'] as number) ?? Date.now() / 1000,
        },
      ]
    }
    const updated = [...prev]
    updated[idx] = { ...current, stage: 'playing' }
    return updated
  }

  if (type === 'tts_done' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    const current = prev[idx]
    if (idx < 0 || !current) return prev
    const updated = [...prev]
    updated[idx] = { ...current, stage: 'done' }
    return updated
  }

  if (type === 'tts_removed' && id) {
    const idx = prev.findIndex((p) => p.id === id)
    if (idx < 0) return prev
    return prev.filter((p) => p.id !== id)
  }

  if (type === 'tts_edited' && id) {
    const newId = raw['new_id'] as string | undefined
    const content = raw['content'] as string | undefined
    const speech_prompt = (raw['speech_prompt'] as string | null | undefined) ?? null
    const idx = prev.findIndex((p) => p.id === id)

    if (newId && newId !== id) {
      // id swap: retire old, append new at pending tail
      const filtered = prev.filter((p) => p.id !== id)
      return [
        ...filtered,
        {
          id: newId,
          content: content ?? '',
          speech_prompt,
          stage: (raw['stage'] as PipelineStage) ?? 'pending',
          urgent: Boolean(raw['urgent']),
          ts: (raw['ts'] as number) ?? Date.now() / 1000,
        },
      ]
    }

    const current = prev[idx]
    if (idx < 0 || !current) return prev
    const updated = [...prev]
    updated[idx] = {
      ...current,
      content: content ?? current.content,
      speech_prompt,
    }
    return updated
  }

  if (type === 'tts_reordered') {
    const stage = raw['stage'] as PipelineStage
    const ids = raw['ids'] as string[] | undefined
    if (!ids || !Array.isArray(ids)) return prev

    const staged = prev.filter((p) => p.stage === stage)
    if (staged.length !== ids.length) return prev
    const byId = new Map(staged.map((p) => [p.id, p]))
    if (ids.some((id_) => !byId.has(id_))) return prev

    const reorderedStage: PipelineItem[] = ids.map((id_) => byId.get(id_)!)
    const others = prev.filter((p) => p.stage !== stage)

    // Preserve non-target-stage items; append reordered stage at the end.
    // Derived views (pending/synthesized/playing/done) filter by stage so
    // absolute order in the combined array doesn't affect UI presentation.
    return [...others, ...reorderedStage]
  }

  return prev
}

export function useLiveStream() {
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [pipeline, setPipeline] = useState<PipelineItem[]>([])
  const [scriptState, setScriptState] = useState<ScriptState | null>(null)
  const [connected, setConnected] = useState(false)
  const [onlineCount, setOnlineCount] = useState<number | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    // Restore cache on client only (avoids SSR/hydration mismatch)
    const cachedEvents = loadCache<LiveEvent>(EVENTS_KEY)
    const cachedOutputs = loadCache<AiOutput>(AI_OUTPUTS_KEY)
    if (cachedEvents.length > 0) setEvents(cachedEvents)
    if (cachedOutputs.length > 0) {
      // Historical outputs are rehydrated as `done`-stage pipeline items so
      // the legacy `aiOutputs` derivation continues to return them.
      setPipeline((prev) => {
        const restored: PipelineItem[] = cachedOutputs.map((o, i) => ({
          id: `cache-${o.ts}-${i}`,
          content: o.content,
          speech_prompt: o.speech_prompt || null,
          stage: 'done',
          urgent: false,
          ts: o.ts,
        }))
        return [...restored, ...prev]
      })
    }
  }, [])

  useEffect(() => {
    const es = new EventSource(`${env.NEXT_PUBLIC_API_URL}/live/stream`)
    esRef.current = es

    es.onopen = async () => {
      setConnected(true)
      const res = await apiFetch<Array<{
        id: string
        content: string
        speech_prompt: string | null
        stage: PipelineStage
        urgent: boolean
      }>>('live/tts/queue/snapshot', { silent: true })
      if (!res.ok) return   // SSE events will catch up
      setPipeline((prev) => {
        const keep = prev.filter((p) => p.stage === 'playing' || p.stage === 'done')
        const fresh: PipelineItem[] = res.data.map((s) => ({
          id: s.id,
          content: s.content,
          speech_prompt: s.speech_prompt,
          stage: s.stage,
          urgent: s.urgent,
          ts: Date.now() / 1000,
        }))
        return [...keep, ...fresh]
      })
    }

    es.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data) as Record<string, unknown>
        const type = raw['type'] as string

        if (type === 'ping' || type === 'agent') return

        if (type === 'stats') {
          setOnlineCount(raw['value'] as number)
          return
        }

        if (type === 'script') {
          setScriptState({
            segment_id: raw['segment_id'] as string,
            title: (raw['title'] as string) ?? '',
            goal: (raw['goal'] as string) ?? '',
            cue: (raw['cue'] as string[]) ?? [],
            must_say: (raw['must_say'] as boolean) ?? false,
            remaining_seconds: raw['remaining_seconds'] as number,
            segment_duration: (raw['segment_duration'] as number) ?? 0,
            finished: (raw['finished'] as boolean) ?? false,
          })
          return
        }

        if (
          type === 'tts_queued' ||
          type === 'tts_synthesized' ||
          type === 'tts_playing' ||
          type === 'tts_done'
        ) {
          setPipeline((prev) => applyLiveEvent(prev, raw))
          return
        }

        // live interaction events
        if (SKIP_TYPES.has(type)) return
        const event = raw as unknown as LiveEvent
        setEvents((prev) => {
          const next = [...prev, event]
          const trimmed = next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next
          saveCache(EVENTS_KEY, trimmed)
          return trimmed
        })
      } catch {
        // ignore malformed frames
      }
    }

    es.onerror = () => setConnected(false)

    return () => {
      es.close()
      esRef.current = null
      setConnected(false)
      // Clear transient playback state on disconnect — stale pending/synthesized
      // items would pile up on reconnect since the server won't re-send them.
      // Keep `done` items (history) so the UI preserves log continuity.
      setPipeline((prev) => prev.filter((p) => p.stage === 'done'))
    }
  }, [])

  const pending = useMemo(() => pipeline.filter((p) => p.stage === 'pending'), [pipeline])
  const synthesized = useMemo(() => pipeline.filter((p) => p.stage === 'synthesized'), [pipeline])
  const nowPlaying = useMemo<AiOutput | null>(() => {
    const found = pipeline.find((p) => p.stage === 'playing')
    return found
      ? { content: found.content, source: 'agent', speech_prompt: found.speech_prompt ?? '', ts: found.ts }
      : null
  }, [pipeline])
  const history = useMemo(
    () => pipeline.filter((p) => p.stage === 'done').slice(-MAX_EVENTS),
    [pipeline],
  )
  const aiOutputs = useMemo<AiOutput[]>(
    () =>
      history.map((p) => ({
        content: p.content,
        source: 'agent' as const,
        speech_prompt: p.speech_prompt ?? '',
        ts: p.ts,
      })),
    [history],
  )
  const ttsQueue = useMemo<TtsQueueItem[]>(
    () =>
      [...pending, ...synthesized].map((p) => ({
        id: p.id,
        content: p.content,
        speech_prompt: p.speech_prompt,
      })),
    [pending, synthesized],
  )
  const nowPlayingItem = useMemo(
    () => pipeline.find((p) => p.stage === 'playing') ?? null,
    [pipeline],
  )
  const urgentCount = useMemo(
    () => pipeline.filter((p) => p.urgent && (p.stage === 'pending' || p.stage === 'synthesized')).length,
    [pipeline],
  )

  // Persist history so cached outputs survive a full page reload.
  useEffect(() => {
    if (aiOutputs.length === 0) return
    saveCache(AI_OUTPUTS_KEY, aiOutputs)
  }, [aiOutputs])

  return {
    events,
    connected,
    onlineCount,
    aiOutputs,
    nowPlaying,
    nowPlayingItem,
    ttsQueue,
    scriptState,
    pending,
    synthesized,
    history,
    pipeline,
    urgentCount,
  }
}
