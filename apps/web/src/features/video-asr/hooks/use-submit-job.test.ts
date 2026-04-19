import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useSubmitJob } from './use-submit-job'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: 'test-key' },
}))

describe('useSubmitJob', () => {
  it('submits URLs and returns job_id on success', async () => {
    mockApiFetch.mockResolvedValue({
      ok: true, status: 200,
      data: { job_id: 'job-123', video_ids: ['BV1abc'], status: 'accepted' },
    })
    const { result } = renderHook(() => useSubmitJob())
    let jobId: string | null = null
    await act(async () => {
      jobId = await result.current.submit(['https://www.bilibili.com/video/BV1abc'])
    })
    expect(jobId).toBe('job-123')
    expect(result.current.submitting).toBe(false)
  })

  it('returns null on failure', async () => {
    mockApiFetch.mockResolvedValue({ ok: false, status: 400 })
    const { result } = renderHook(() => useSubmitJob())
    let jobId: string | null = 'sentinel'
    await act(async () => {
      jobId = await result.current.submit(['https://invalid'])
    })
    expect(jobId).toBeNull()
  })
})
