import { env } from '@/config/env'

export type FetchClientOptions = Omit<RequestInit, 'body'> & {
  body?: Record<string, unknown> | unknown[] | BodyInit | null
  searchParams?: Record<string, string | number | boolean | undefined>
  timeout?: number
}

export type FetchResult<T> = {
  data: T | null
  error: Error | null
  response: Response | null
}

const RETRY_METHODS = new Set(['GET', 'PUT', 'HEAD', 'DELETE', 'OPTIONS', 'TRACE'])
const MAX_RETRIES = 2

async function parseBody<T>(response: Response): Promise<T | null> {
  const ct = response.headers.get('content-type') ?? ''
  try {
    if (ct.includes('application/json')) return (await response.json()) as T
    return (await response.text()) as unknown as T
  } catch {
    return null
  }
}

export async function fetchClient<T>(
  path: string,
  options: FetchClientOptions = {},
): Promise<FetchResult<T>> {
  const { body, searchParams, timeout = 30_000, ...init } = options

  let url = `${env.NEXT_PUBLIC_API_URL}/${path}`
  if (searchParams) {
    const params = new URLSearchParams(
      Object.entries(searchParams)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    )
    url = `${url}?${params}`
  }

  const method = (init.method ?? 'GET').toUpperCase()
  const serializedBody =
    body != null && typeof body === 'object' && !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer) && !(body instanceof FormData) &&
    !(body instanceof URLSearchParams) && !(body instanceof ReadableStream) &&
    typeof (body as BodyInit) !== 'string'
      ? JSON.stringify(body)
      : (body as BodyInit | null | undefined)

  const headers = new Headers(init.headers)
  if (serializedBody != null && !headers.has('content-type')) {
    headers.set('content-type', 'application/json')
  }

  const controller = new AbortController()
  const timer = timeout ? setTimeout(() => controller.abort(), timeout) : null

  let lastError: Error | null = null
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await globalThis.fetch(url, {
        ...init,
        method,
        headers,
        body: serializedBody,
        signal: controller.signal,
      })
      clearTimeout(timer ?? undefined)
      const data = await parseBody<T>(response)
      return { data, error: null, response }
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err))
      const isRetryableMethod = RETRY_METHODS.has(method)
      if (!isRetryableMethod || attempt >= MAX_RETRIES) break
    }
  }

  clearTimeout(timer ?? undefined)
  return { data: null, error: lastError, response: null }
}
