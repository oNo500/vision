import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRagLibrary } from './use-rag-library'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

function ok<T>(data: T) { return { ok: true as const, data, status: 200 } }

const emptyStatus = { indexed: false, dirty: false, chunk_count: 0, build_time: null, file_count: 0, sources: [] }
const idleBuild = { running: false, last_build_time: null, last_error: null }

describe('useRagLibrary', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches status and build status on mount', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
    const { result } = renderHook(() => useRagLibrary('dong-yuhui'))
    await waitFor(() => expect(result.current.status).not.toBeNull())
    expect(result.current.status).toEqual(emptyStatus)
  })

  it('importTranscript calls correct endpoint', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
      .mockResolvedValueOnce(ok({ imported: ['competitor_clips/vid.md'], video_id: 'vid' }))
      .mockResolvedValueOnce(ok(emptyStatus))
      .mockResolvedValueOnce(ok(idleBuild))
    const { result } = renderHook(() => useRagLibrary('dong-yuhui'))
    await waitFor(() => expect(result.current.status).not.toBeNull())
    await act(() => result.current.importTranscript('vid'))
    expect(mockApiFetch).toHaveBeenCalledWith(
      'api/intelligence/rag-libraries/dong-yuhui/import-transcript',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
