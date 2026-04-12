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

const MAX_EVENTS = 200

export function useLiveStream() {
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource(`${env.NEXT_PUBLIC_API_URL}/live/stream`)
    esRef.current = es

    es.onopen = () => setConnected(true)

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as LiveEvent & { type: string }
        // skip internal events
        if (event.type === 'ping' || event.type === 'agent' || event.type === 'script' || event.type === 'tts_output') {
          return
        }
        setEvents((prev) => {
          const next = [event, ...prev]
          return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next
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

  return { events, connected }
}
