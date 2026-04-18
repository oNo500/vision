import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRag } from './use-rag'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
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

function mockJson(body: unknown, init: ResponseInit = {}) {
  return {
    ok: init.status === undefined || init.status < 400,
    status: init.status ?? 200,
    json: async () => body,
  } as Response
}

describe('useRag', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('fetches status and build status on mount', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJson(emptyStatus))
      .mockResolvedValueOnce(mockJson(idleBuild))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    expect(result.current.status).toEqual(emptyStatus)
    expect(result.current.buildStatus).toEqual(idleBuild)
  })

  it('uploads file and refetches status', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJson(emptyStatus))    // initial status
      .mockResolvedValueOnce(mockJson(idleBuild))      // initial build
      .mockResolvedValueOnce(mockJson({ rel_path: 'scripts/a.md', overwritten: false }, { status: 201 }))
      .mockResolvedValueOnce(mockJson({ ...emptyStatus, file_count: 1 }))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    const file = new File(['hello'], 'a.md', { type: 'text/markdown' })

    await act(async () => {
      await result.current.upload(file, 'scripts')
    })

    await waitFor(() => expect(result.current.status?.file_count).toBe(1))

    const uploadCall = vi.mocked(fetch).mock.calls[2]!
    expect(uploadCall[0]).toBe('http://localhost:8000/live/plans/p1/rag/files')
    expect((uploadCall[1] as RequestInit).method).toBe('POST')
  })

  it('surfaces 409 during rebuild as info toast', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJson(emptyStatus))
      .mockResolvedValueOnce(mockJson(idleBuild))
      .mockResolvedValueOnce(mockJson({ detail: 'build already running' }, { status: 409 }))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    await act(async () => {
      await result.current.rebuild()
    })

    expect(toast.info).toHaveBeenCalledWith('Build already running')
  })

  it('deletes file and refetches', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJson(emptyStatus))
      .mockResolvedValueOnce(mockJson(idleBuild))
      .mockResolvedValueOnce({ ok: true, status: 204, json: async () => ({}) } as Response)
      .mockResolvedValueOnce(mockJson({ ...emptyStatus, file_count: 0 }))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    await act(async () => {
      await result.current.remove('scripts', 'a.md')
    })

    const deleteCall = vi.mocked(fetch).mock.calls[2]!
    expect(deleteCall[0]).toBe('http://localhost:8000/live/plans/p1/rag/files/scripts/a.md')
    expect((deleteCall[1] as RequestInit).method).toBe('DELETE')
  })

  it('rebuild flips buildStatus.running true immediately on 202', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJson(emptyStatus))
      .mockResolvedValueOnce(mockJson(idleBuild))
      .mockResolvedValueOnce(mockJson({ scheduled: true }, { status: 202 }))

    const { result } = renderHook(() => useRag('p1'))
    await waitFor(() => expect(result.current.status).not.toBeNull())

    await act(async () => {
      await result.current.rebuild()
    })

    expect(result.current.buildStatus.running).toBe(true)
  })
})
