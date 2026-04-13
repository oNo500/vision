import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePlans } from './use-plans'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn() },
}))

const mockPlans = [
  { id: '1', name: 'Plan A', updated_at: '2026-04-13T00:00:00Z' },
  { id: '2', name: 'Plan B', updated_at: '2026-04-12T00:00:00Z' },
]

describe('usePlans', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('fetches and returns plan list', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPlans,
    } as Response)

    const { result } = renderHook(() => usePlans())
    await waitFor(() => expect(result.current.plans).toHaveLength(2))
    expect(result.current.plans[0].name).toBe('Plan A')
  })

  it('shows error toast when deletePlan fails', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => mockPlans } as Response)
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) } as Response)

    const { result } = renderHook(() => usePlans())
    await waitFor(() => expect(result.current.plans).toHaveLength(2))

    await act(async () => {
      await result.current.deletePlan('1')
    })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('refetches after deletePlan succeeds', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => mockPlans } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => [mockPlans[1]] } as Response)

    const { result } = renderHook(() => usePlans())
    await waitFor(() => expect(result.current.plans).toHaveLength(2))

    await act(async () => {
      await result.current.deletePlan('1')
    })

    await waitFor(() => expect(result.current.plans).toHaveLength(1))
  })
})
