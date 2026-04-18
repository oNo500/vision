import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from './api-fetch'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

const mockFetchClient = vi.fn()
vi.mock('./fetch-client', () => ({
  fetchClient: (...args: unknown[]) => mockFetchClient(...args),
}))

type FetchResult<T> = {
  data: T | null
  error: Error | null
  response: Response | null
}

function fakeOk<T>(data: T, status = 200): FetchResult<T> {
  return {
    data,
    error: null,
    response: { ok: status >= 200 && status < 300, status } as Response,
  }
}

function fakeHttpError(status: number, body: unknown = null): FetchResult<unknown> {
  return {
    data: body,
    error: null,
    response: { ok: false, status } as Response,
  }
}

function fakeNetworkError(): FetchResult<unknown> {
  return { data: null, error: new Error('ENOTFOUND'), response: null }
}

describe('apiFetch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns ok=true with data on 2xx', async () => {
    mockFetchClient.mockResolvedValueOnce(fakeOk({ hello: 'world' }))
    const result = await apiFetch<{ hello: string }>('live/x')
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.data.hello).toBe('world')
  })

  it('passes through request options to fetchClient', async () => {
    mockFetchClient.mockResolvedValueOnce(fakeOk({}))
    await apiFetch('live/x', { method: 'POST', body: { a: 1 } })
    expect(mockFetchClient).toHaveBeenCalledWith(
      'live/x',
      expect.objectContaining({ method: 'POST', body: { a: 1 } }),
    )
  })

  it('strips leading slash from path', async () => {
    mockFetchClient.mockResolvedValueOnce(fakeOk({}))
    await apiFetch('/live/x')
    expect(mockFetchClient).toHaveBeenCalledWith('live/x', expect.anything())
  })

  it('shows toast with body.detail when server returns non-ok with string detail', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockFetchClient.mockResolvedValueOnce(
      fakeHttpError(400, { detail: 'invalid input' }),
    )
    const result = await apiFetch('live/x')
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.status).toBe(400)
    expect(toast.error).toHaveBeenCalledWith('invalid input')
  })

  it('falls back to fallbackError when detail is absent', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockFetchClient.mockResolvedValueOnce(fakeHttpError(500, {}))
    await apiFetch('live/x', { fallbackError: 'Failed to save' })
    expect(toast.error).toHaveBeenCalledWith('Failed to save')
  })

  it('shows networkError toast when fetch itself fails', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockFetchClient.mockResolvedValueOnce(fakeNetworkError())
    const result = await apiFetch('live/x')
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.status).toBeNull()
    expect(toast.error).toHaveBeenCalledWith('Cannot reach backend')
  })

  it('accepts custom networkError text', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockFetchClient.mockResolvedValueOnce(fakeNetworkError())
    await apiFetch('live/x', { networkError: '无法连接到后端' })
    expect(toast.error).toHaveBeenCalledWith('无法连接到后端')
  })

  it('silent=true suppresses all toasts', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockFetchClient.mockResolvedValueOnce(fakeHttpError(404, {}))
    await apiFetch('live/x', { silent: true })
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('silent=true also suppresses networkError toast', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    mockFetchClient.mockResolvedValueOnce(fakeNetworkError())
    const result = await apiFetch('live/x', { silent: true })
    expect(result.ok).toBe(false)
    expect(toast.error).not.toHaveBeenCalled()
  })
})
