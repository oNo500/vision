import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useTtsMutations } from './use-tts-mutations'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

describe('useTtsMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiFetch.mockResolvedValue({ ok: true, data: {}, status: 200 })
  })

  it('remove calls DELETE at live/tts/queue/:id', async () => {
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.remove('abc') })
    expect(mockApiFetch).toHaveBeenCalledWith(
      'live/tts/queue/abc',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('edit PATCHes with text and optional speech_prompt', async () => {
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.edit('x', { text: 'new', speech_prompt: 'p' }) })
    expect(mockApiFetch).toHaveBeenCalledWith(
      'live/tts/queue/x',
      expect.objectContaining({
        method: 'PATCH',
        body: { text: 'new', speech_prompt: 'p' },
      }),
    )
  })

  it('edit omits speech_prompt when undefined', async () => {
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.edit('x', { text: 'new' }) })
    expect(mockApiFetch).toHaveBeenCalledWith(
      'live/tts/queue/x',
      expect.objectContaining({
        method: 'PATCH',
        body: { text: 'new' },
      }),
    )
  })

  it('reorder posts stage + ids', async () => {
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.reorder('pending', ['a', 'b']) })
    expect(mockApiFetch).toHaveBeenCalledWith(
      'live/tts/queue/reorder',
      expect.objectContaining({
        method: 'POST',
        body: { stage: 'pending', ids: ['a', 'b'] },
      }),
    )
  })

  it('returns false when apiFetch returns ok=false', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    const { result } = renderHook(() => useTtsMutations())
    let ok: boolean | undefined
    await act(async () => { ok = await result.current.remove('ghost') })
    expect(ok).toBe(false)
  })
})
