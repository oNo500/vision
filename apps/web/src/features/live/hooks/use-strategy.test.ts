import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useStrategy } from './use-strategy'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn() },
}))

describe('useStrategy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('shows error toast when setStrategy POST fails with non-ok response', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ strategy: 'immediate' }) } as Response)
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) } as Response)

    const { result } = renderHook(() => useStrategy())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => {
      await result.current.setStrategy('intelligent')
    })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('shows error toast when setStrategy POST throws (network error)', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ strategy: 'immediate' }) } as Response)
      .mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useStrategy())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => {
      await result.current.setStrategy('intelligent')
    })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('does not show error toast when setStrategy succeeds', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')

    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ strategy: 'immediate' }) } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ strategy: 'intelligent' }) } as Response)

    const { result } = renderHook(() => useStrategy())

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    await act(async () => {
      await result.current.setStrategy('intelligent')
    })

    expect(toast.error).not.toHaveBeenCalled()
  })
})
