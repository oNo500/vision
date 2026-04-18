import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRag } from './use-rag'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

const emptyStatus = {
  indexed: false,
  dirty: false,
  chunk_count: 0,
  build_time: null,
  file_count: 0,
  sources: [],
}

const idleBuild = {
  running: false,
  last_build_time: null,
  last_error: null,
}

function ok<T>(data: T, status = 200) {
  return { ok: true as const, data, status }
}

function fail(status = 400) {
  return { ok: false as const, status }
}

describe('useRag', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches status and build status on mount', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    expect(result.current.status).toEqual(emptyStatus)
    expect(result.current.buildStatus).toEqual(idleBuild)
  })

  it('uploads file and refetches status', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
      .mockResolvedValueOnce(ok({ rel_path: 'scripts/a.md', overwritten: false }, 201))
      .mockResolvedValueOnce(ok({ ...emptyStatus, file_count: 1 }))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    const file = new File(['hello'], 'a.md', { type: 'text/markdown' })

    await act(async () => {
      await result.current.upload([file], 'scripts')
    })

    await waitFor(() => expect(result.current.status?.file_count).toBe(1))

    const uploadCall = mockApiFetch.mock.calls[2]!
    expect(uploadCall[0]).toBe('live/plans/p1/rag/files')
    expect(uploadCall[1].method).toBe('POST')
    expect(uploadCall[1].body).toBeInstanceOf(FormData)
  })

  it('surfaces 409 during rebuild as info toast', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
      .mockResolvedValueOnce(fail(409))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    await act(async () => {
      await result.current.rebuild()
    })

    expect(toast.info).toHaveBeenCalledWith('Build already running')
  })

  it('deletes file and refetches', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
      .mockResolvedValueOnce(ok({}, 204))
      .mockResolvedValueOnce(ok({ ...emptyStatus, file_count: 0 }))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    await act(async () => {
      await result.current.remove('scripts', 'a.md')
    })

    const deleteCall = mockApiFetch.mock.calls[2]!
    expect(deleteCall[0]).toBe('live/plans/p1/rag/files/scripts/a.md')
    expect(deleteCall[1].method).toBe('DELETE')
  })

  it('rebuild flips buildStatus.running true immediately on 202', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
      .mockResolvedValueOnce(ok({ scheduled: true }, 202))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    await act(async () => {
      await result.current.rebuild()
    })

    expect(result.current.buildStatus.running).toBe(true)
  })
})
