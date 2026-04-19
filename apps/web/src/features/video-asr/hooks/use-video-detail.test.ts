import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useVideoDetail } from './use-video-detail'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

describe('useVideoDetail', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('fetches metadata, transcript and summary in parallel', async () => {
    mockApiFetch
      .mockResolvedValueOnce({
        ok: true, status: 200,
        data: { video_id: 'BV1abc', title: 'Test', url: 'https://x.com', source: 'bilibili', uploader: 'U', duration_sec: 60, asr_model: 'gemini', processed_at: '' },
      })
      .mockResolvedValueOnce({ ok: true, status: 200, data: '## Transcript\nHello' })
      .mockResolvedValueOnce({ ok: true, status: 200, data: '## Summary\nWorld' })

    const { result } = renderHook(() => useVideoDetail('BV1abc'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.meta?.title).toBe('Test')
    expect(result.current.transcriptMd).toBe('## Transcript\nHello')
    expect(result.current.summaryMd).toBe('## Summary\nWorld')
  })

  it('partial failure: sets available fields, others null', async () => {
    mockApiFetch
      .mockResolvedValueOnce({
        ok: true, status: 200,
        data: { video_id: 'BV1abc', title: 'T', url: 'https://x.com', source: 'bilibili', uploader: null, duration_sec: null, asr_model: 'gemini', processed_at: '' },
      })
      .mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce({ ok: false, status: 404 })

    const { result } = renderHook(() => useVideoDetail('BV1abc'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.meta?.video_id).toBe('BV1abc')
    expect(result.current.transcriptMd).toBeNull()
    expect(result.current.summaryMd).toBeNull()
  })
})
