import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAiSession } from './use-ai-session'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn() },
}))

describe('useAiSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ running: false }),
    }))
  })

  it('shows error toast when start fails with non-ok response', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ running: false }) } as Response)
      .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: 'No script loaded' }) } as Response)

    const { result } = renderHook(() => useAiSession())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => { await result.current.start() })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('shows error toast when start throws (network error)', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ running: false }) } as Response)
      .mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useAiSession())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => { await result.current.start() })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('shows error toast when stop fails with non-ok response', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ running: true }) } as Response)
      .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: 'Not running' }) } as Response)

    const { result } = renderHook(() => useAiSession())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => { await result.current.stop() })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('shows error toast when stop throws (network error)', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ running: true }) } as Response)
      .mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useAiSession())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => { await result.current.stop() })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('does not show error toast when start succeeds', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ running: false }) } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ running: true }) } as Response)

    const { result } = renderHook(() => useAiSession())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => { await result.current.start() })

    expect(toast.error).not.toHaveBeenCalled()
  })
})
