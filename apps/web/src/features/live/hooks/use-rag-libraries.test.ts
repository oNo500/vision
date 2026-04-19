import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRagLibraries } from './use-rag-libraries'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

function ok<T>(data: T) {
  return { ok: true as const, data, status: 200 }
}

describe('useRagLibraries', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches library list on mount', async () => {
    const libs = [{ id: 'dong-yuhui', name: '董宇辉', created_at: '2026-01-01T00:00:00Z' }]
    mockApiFetch.mockResolvedValueOnce(ok(libs))
    const { result } = renderHook(() => useRagLibraries())
    await waitFor(() => expect(result.current.libraries).toHaveLength(1))
    expect(result.current.libraries[0].id).toBe('dong-yuhui')
  })

  it('creates library and refetches', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok([]))
      .mockResolvedValueOnce(ok({ id: 'new-lib', name: 'New', created_at: '' }))
      .mockResolvedValueOnce(ok([{ id: 'new-lib', name: 'New', created_at: '' }]))
    const { result } = renderHook(() => useRagLibraries())
    await waitFor(() => expect(result.current.libraries).toEqual([]))
    await act(() => result.current.createLibrary('new-lib', 'New'))
    await waitFor(() => expect(result.current.libraries).toHaveLength(1))
  })
})
