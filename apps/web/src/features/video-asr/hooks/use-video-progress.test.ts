import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))

class MockEventSource {
  static instance: MockEventSource | null = null
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private listeners = new Map<string, EventListener>()
  close = vi.fn()

  constructor(public url: string) {
    MockEventSource.instance = this
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener)
  }

  emit(eventType: string, data: unknown) {
    const listener = this.listeners.get(eventType)
    listener?.({ data: JSON.stringify(data) } as MessageEvent)
  }
}

vi.stubGlobal('EventSource', MockEventSource)

import { useVideoProgress } from './use-video-progress'

describe('useVideoProgress', () => {
  afterEach(() => {
    MockEventSource.instance = null
    vi.clearAllMocks()
  })

  it('parses progress events', () => {
    const { result } = renderHook(() => useVideoProgress('BV1abc'))
    act(() => {
      MockEventSource.instance?.emit('progress', {
        stages: [{ stage: 'ingest', status: 'done', duration_sec: 5 }],
        transcribe_progress: { done: 2, total: 4, chunks: [] },
        cost_usd: 0.01,
      })
    })
    expect(result.current.stages).toHaveLength(1)
    expect(result.current.stages[0]?.status).toBe('done')
    expect(result.current.transcribeProgress.done).toBe(2)
    expect(result.current.costUsd).toBe(0.01)
  })

  it('sets finished=true when all 7 stages are done or failed', () => {
    const { result } = renderHook(() => useVideoProgress('BV1abc'))
    const allStages = ['ingest', 'preprocess', 'transcribe', 'merge', 'render', 'analyze', 'load']
    act(() => {
      MockEventSource.instance?.emit('progress', {
        stages: allStages.map((s) => ({ stage: s, status: 'done', duration_sec: 1 })),
        transcribe_progress: { done: 1, total: 1, chunks: [] },
        cost_usd: 0.05,
      })
    })
    expect(result.current.finished).toBe(true)
  })

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useVideoProgress('BV1abc'))
    unmount()
    expect(MockEventSource.instance?.close).toHaveBeenCalled()
  })
})
