import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePlan } from './use-plan'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockPlan = {
  id: '1',
  name: 'Plan A',
  updated_at: '2026-04-13T00:00:00Z',
  created_at: '2026-04-13T00:00:00Z',
  product: { name: 'P', description: 'D', price: '99', highlights: [], faq: [] },
  persona: { name: '主播', style: 'friendly', catchphrases: [], forbidden_words: [] },
  script: { segments: [] },
}

describe('usePlan', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('fetches plan by id', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPlan,
    } as Response)

    const { result } = renderHook(() => usePlan('1'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())
    expect(result.current.plan?.name).toBe('Plan A')
  })

  it('shows error toast when save fails', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => mockPlan } as Response)
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) } as Response)

    const { result } = renderHook(() => usePlan('1'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())

    await act(async () => {
      await result.current.savePlan(mockPlan)
    })

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('shows success toast when save succeeds', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    vi.mocked(fetch)
      .mockResolvedValueOnce({ ok: true, json: async () => mockPlan } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => mockPlan } as Response)

    const { result } = renderHook(() => usePlan('1'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())

    await act(async () => {
      await result.current.savePlan(mockPlan)
    })

    expect(toast.success).toHaveBeenCalledOnce()
  })
})
