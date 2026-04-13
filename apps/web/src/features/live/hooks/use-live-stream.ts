'use client'

import { useEffect, useRef, useState } from 'react'

import { env } from '@/config/env'

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

export type ScriptState = {
  segment_id: string
  remaining_seconds: number
  segment_duration: number
  finished: boolean
}

const MAX_EVENTS = 200
const SKIP_TYPES = new Set(['ping', 'agent', 'script', 'tts_output'])
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

export function useLiveStream() {
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [aiOutputs, setAiOutputs] = useState<AiOutput[]>([])
  const [scriptState, setScriptState] = useState<ScriptState | null>(null)
  const [connected, setConnected] = useState(false)
  const [onlineCount, setOnlineCount] = useState<number | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    // Restore cache on client only (avoids SSR/hydration mismatch)
    const cachedEvents = loadCache<LiveEvent>(EVENTS_KEY)
    const cachedOutputs = loadCache<AiOutput>(AI_OUTPUTS_KEY)
    if (cachedEvents.length > 0) setEvents(cachedEvents)
    if (cachedOutputs.length > 0) setAiOutputs(cachedOutputs)
  }, [])

  useEffect(() => {
    const es = new EventSource(`${env.NEXT_PUBLIC_API_URL}/live/stream`)
    esRef.current = es

    es.onopen = () => setConnected(true)

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
            remaining_seconds: raw['remaining_seconds'] as number,
            segment_duration: (raw['segment_duration'] as number) ?? 0,
            finished: (raw['finished'] as boolean) ?? false,
          })
          return
        }

        if (type === 'tts_output') {
          const output: AiOutput = {
            content: raw['content'] as string,
            source: raw['source'] as AiOutput['source'],
            speech_prompt: (raw['speech_prompt'] as string) ?? '',
            ts: raw['ts'] as number,
          }
          setAiOutputs((prev) => {
            const next = [...prev, output]
            const trimmed = next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next
            saveCache(AI_OUTPUTS_KEY, trimmed)
            return trimmed
          })
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
    }
  }, [])

  return { events, connected, onlineCount, aiOutputs, scriptState }
}
