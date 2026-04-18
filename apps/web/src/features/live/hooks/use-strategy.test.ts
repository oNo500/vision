import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useStrategy } from './use-strategy'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

describe('useStrategy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads initial strategy on mount', async () => {
    mockApiFetch.mockResolvedValueOnce({
      ok: true, data: { strategy: 'intelligent' }, status: 200,
    })
    const { result } = renderHook(() => useStrategy())
    await waitFor(() => expect(result.current.strategy).toBe('intelligent'))
  })

  it('does not change strategy when POST fails', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: { strategy: 'immediate' }, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 400 })

    const { result } = renderHook(() => useStrategy())
    await waitFor(() => expect(result.current.strategy).toBe('immediate'))

    await act(async () => {
      await result.current.setStrategy('intelligent')
    })

    expect(result.current.strategy).toBe('immediate')
  })

  it('updates strategy when POST succeeds', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: { strategy: 'immediate' }, status: 200 })
      .mockResolvedValueOnce({ ok: true, data: { strategy: 'intelligent' }, status: 200 })

    const { result } = renderHook(() => useStrategy())
    await waitFor(() => expect(result.current.strategy).toBe('immediate'))

    await act(async () => {
      await result.current.setStrategy('intelligent')
    })

    expect(result.current.strategy).toBe('intelligent')
  })
})
