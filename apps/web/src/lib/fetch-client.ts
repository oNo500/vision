import { createClient } from '@infra-x/fwrap'

import { env } from '@/config/env'

// fwrap v0.1.1 stores `options.fetch` and later invokes it without binding
// `this`, which triggers TypeError: Illegal invocation in the browser where
// `fetch` must be called on Window. Wrap in an arrow to keep the binding.
const boundFetch: typeof fetch = (...args) => globalThis.fetch(...args)

export const fetchClient = createClient({
  prefixUrl: env.NEXT_PUBLIC_API_URL,
  timeout: 30_000,
  throwHttpErrors: false,
  fetch: boundFetch,
  retry: {
    limit: 2,
    methods: ['GET', 'PUT', 'HEAD', 'DELETE', 'OPTIONS', 'TRACE'],
    statusCodes: [408, 413, 429, 500, 502, 503, 504],
  },
})
