import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useTtsMutations } from './use-tts-mutations'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

const { toastError } = vi.hoisted(() => ({ toastError: vi.fn() }))
vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: toastError, success: vi.fn() },
}))

describe('useTtsMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('remove calls DELETE /live/tts/queue/:id', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.remove('abc') })
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/live/tts/queue/abc', expect.objectContaining({ method: 'DELETE' }))
  })

  it('edit PATCHes with text and optional speech_prompt', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.edit('x', { text: 'new', speech_prompt: 'p' }) })
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/live/tts/queue/x',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ text: 'new', speech_prompt: 'p' }),
      }),
    )
  })

  it('edit omits speech_prompt when undefined', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.edit('x', { text: 'new' }) })
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls).toHaveLength(1)
    const call = calls[0]
    if (!call) throw new Error('expected fetch call')
    expect(JSON.parse(call[1].body)).toEqual({ text: 'new' })
  })

  it('reorder posts stage + ids', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const { result } = renderHook(() => useTtsMutations())
    await act(async () => { await result.current.reorder('pending', ['a', 'b']) })
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/live/tts/queue/reorder',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ stage: 'pending', ids: ['a', 'b'] }),
      }),
    )
  })

  it('on 4xx, toasts error and returns false', async () => {
    ;(fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: 'nope' }) })
    const { result } = renderHook(() => useTtsMutations())
    let ok: boolean | undefined
    await act(async () => { ok = await result.current.remove('ghost') })
    expect(ok).toBe(false)
    await waitFor(() => expect(toastError).toHaveBeenCalled())
  })
})
