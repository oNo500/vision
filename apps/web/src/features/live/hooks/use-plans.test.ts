import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePlans } from './use-plans'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

const mockPlans = [
  { id: '1', name: 'Plan A', updated_at: '2026-04-13T00:00:00Z' },
  { id: '2', name: 'Plan B', updated_at: '2026-04-12T00:00:00Z' },
]

describe('usePlans', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches and returns plan list', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: mockPlans, status: 200 })

    const { result } = renderHook(() => usePlans())
    await waitFor(() => expect(result.current.plans).toHaveLength(2))
    expect(result.current.plans[0]!.name).toBe('Plan A')
  })

  it('does not refetch when deletePlan fails', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: mockPlans, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 400 })

    const { result } = renderHook(() => usePlans())
    await waitFor(() => expect(result.current.plans).toHaveLength(2))

    await act(async () => {
      await result.current.deletePlan('1')
    })

    // apiFetch was called for initial fetch + delete, but no refetch on failure.
    expect(mockApiFetch).toHaveBeenCalledTimes(2)
  })

  it('refetches after deletePlan succeeds', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: mockPlans, status: 200 })
      .mockResolvedValueOnce({ ok: true, data: {}, status: 204 })
      .mockResolvedValueOnce({ ok: true, data: [mockPlans[1]], status: 200 })

    const { result } = renderHook(() => usePlans())
    await waitFor(() => expect(result.current.plans).toHaveLength(2))

    await act(async () => {
      await result.current.deletePlan('1')
    })

    await waitFor(() => expect(result.current.plans).toHaveLength(1))
  })
})
