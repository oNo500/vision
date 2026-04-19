import { toast } from '@workspace/ui/components/sonner'

import { fetchClient } from './fetch-client'
import type { FetchClientOptions } from './fetch-client'

export type ApiResult<T> =
  | { ok: true; data: T; status: number }
  | { ok: false; status: number | null }

export interface ApiFetchOptions extends FetchClientOptions {
  /** User-visible fallback when the server returns a non-ok status without a string `detail`. */
  fallbackError?: string
  /** User-visible toast when the request never reached the server. */
  networkError?: string
  /** Suppress toasts entirely. Callers that want to handle errors inline pass `silent: true`. */
  silent?: boolean
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<ApiResult<T>> {
  const {
    fallbackError = 'Request failed',
    networkError = 'Cannot reach backend',
    silent = false,
    ...requestOptions
  } = options

  const normalized = path.startsWith('/') ? path.slice(1) : path
  const { data, error, response } = await fetchClient<T>(normalized, requestOptions)

  if (error || !response) {
    if (!silent) toast.error(networkError)
    return { ok: false, status: response?.status ?? null }
  }

  if (!response.ok) {
    if (!silent) {
      const detail = (data as { detail?: unknown } | null)?.detail
      toast.error(typeof detail === 'string' ? detail : fallbackError)
    }
    return { ok: false, status: response.status }
  }

  return { ok: true, data: (data as T), status: response.status }
}
