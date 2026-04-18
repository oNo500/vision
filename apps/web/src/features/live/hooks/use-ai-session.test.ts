import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAiSession } from './use-ai-session'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

describe('useAiSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiFetch.mockResolvedValue({ ok: true, data: { running: false }, status: 200 })
  })

  it('sets error state when start fails', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: { running: false }, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 400 })

    const { result } = renderHook(() => useAiSession())
    await waitFor(() => expect(mockApiFetch).toHaveBeenCalled())

    await act(async () => { await result.current.start() })

    expect(result.current.error).toBe('Failed to start')
  })

  it('clears error when start succeeds', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: { running: false }, status: 200 })
      .mockResolvedValueOnce({ ok: true, data: { running: true }, status: 200 })

    const { result } = renderHook(() => useAiSession())
    await waitFor(() => expect(mockApiFetch).toHaveBeenCalled())

    await act(async () => { await result.current.start() })

    expect(result.current.error).toBeNull()
    expect(result.current.state.running).toBe(true)
  })

  it('sets error state when stop fails', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: { running: true }, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 400 })

    const { result } = renderHook(() => useAiSession())
    await waitFor(() => expect(mockApiFetch).toHaveBeenCalled())

    await act(async () => { await result.current.stop() })

    expect(result.current.error).toBe('Failed to stop')
  })
})
