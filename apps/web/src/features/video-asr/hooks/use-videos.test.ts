import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useVideos } from './use-videos'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

const mockVideos = [
  {
    video_id: 'BV1abc',
    url: 'https://example.com/video1',
    source: 'bilibili',
    title: 'Test Video 1',
    uploader: 'Creator A',
    duration_sec: 1234,
    asr_model: 'gemini-2.5-flash',
    processed_at: '2026-04-19T10:00:00Z',
  },
  {
    video_id: 'BV1def',
    url: 'https://example.com/video2',
    source: 'bilibili',
    title: 'Test Video 2',
    uploader: 'Creator B',
    duration_sec: 5678,
    asr_model: 'gemini-2.5-flash',
    processed_at: '2026-04-19T11:00:00Z',
  },
]

describe('useVideos', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns videos on success', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: mockVideos, status: 200 })

    const { result } = renderHook(() => useVideos())
    await waitFor(() => expect(result.current.videos).toHaveLength(2))
    expect(result.current.videos[0]!.video_id).toBe('BV1abc')
    expect(result.current.videos[1]!.video_id).toBe('BV1def')
    expect(result.current.loading).toBe(false)
  })

  it('returns empty array on error', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: false, status: 500 })

    const { result } = renderHook(() => useVideos())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.videos).toEqual([])
  })

  it('maintains loading state during fetch', async () => {
    mockApiFetch.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({ ok: true, data: mockVideos, status: 200 })
          }, 10)
        }),
    )

    const { result } = renderHook(() => useVideos())
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
  })
})
