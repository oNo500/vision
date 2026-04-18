import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePlan } from './use-plan'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
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
  })

  it('fetches plan by id', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: mockPlan, status: 200 })

    const { result } = renderHook(() => usePlan('1'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())
    expect(result.current.plan?.name).toBe('Plan A')
  })

  it('does not toast-success when save fails', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: mockPlan, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 400 })

    const { result } = renderHook(() => usePlan('1'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())

    await act(async () => {
      await result.current.savePlan(mockPlan)
    })

    // apiFetch is responsible for the error toast; usePlan only shows success.
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('shows success toast when save succeeds', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: mockPlan, status: 200 })
      .mockResolvedValueOnce({ ok: true, data: mockPlan, status: 200 })

    const { result } = renderHook(() => usePlan('1'))
    await waitFor(() => expect(result.current.plan).not.toBeNull())

    await act(async () => {
      await result.current.savePlan(mockPlan)
    })

    expect(toast.success).toHaveBeenCalledOnce()
  })
})
