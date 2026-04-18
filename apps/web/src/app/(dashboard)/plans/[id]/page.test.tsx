import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import React, { Suspense } from 'react'

// Mock React.use to synchronously unwrap already-resolved promises in tests.
// React 19's use() always triggers Suspense in JSDOM, even for pre-resolved
// Promises. This mock intercepts use() calls and returns resolved values
// synchronously when the Promise is already settled.
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal<typeof React>()
  return {
    ...actual,
    use: (p: unknown) => {
      if (p instanceof Promise) {
        const tracked = p as Promise<unknown> & { status?: string; value?: unknown; reason?: unknown }
        if (tracked.status === 'fulfilled') return tracked.value
        if (tracked.status === 'rejected') throw tracked.reason
        tracked.then(
          (v) => { tracked.status = 'fulfilled'; tracked.value = v },
          (e) => { tracked.status = 'rejected'; tracked.reason = e },
        )
        if (tracked.status === 'fulfilled') return tracked.value
        if (tracked.status === 'rejected') throw tracked.reason
        throw p
      }
      return (actual.use as (p: unknown) => unknown)(p)
    },
  }
})

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('next/link', () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))
vi.mock('@atlaskit/pragmatic-drag-and-drop/element/adapter', () => ({
  draggable: () => () => {},
  dropTargetForElements: () => () => {},
  monitorForElements: () => () => {},
}))
vi.mock('@atlaskit/pragmatic-drag-and-drop/combine', () => ({ combine: (...fns: Array<() => void>) => () => fns.forEach(f => f()) }))
vi.mock('@atlaskit/pragmatic-drag-and-drop-hitbox/list-item', () => ({
  attachInstruction: (_data: unknown, _opts: unknown) => _data,
  extractInstruction: () => null,
}))
vi.mock('@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/list-item', () => ({
  DropIndicator: () => null,
}))

const mockPlan = {
  id: 'plan-1',
  name: '测试方案',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  product: { name: '', description: '', price: '', highlights: [], faq: [] },
  persona: { name: '', style: '', catchphrases: [], forbidden_words: [] },
  script: {
    segments: [
      { id: 's1', title: '开场', goal: '欢迎观众', duration: 300, cue: ['欢迎来到直播间'], must_say: false, keywords: [] },
      { id: 's2', title: '促单', goal: '引导下单', duration: 180, cue: ['限时优惠'], must_say: true, keywords: ['优惠'] },
    ],
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  mockApiFetch.mockResolvedValue({ ok: true, data: mockPlan, status: 200 })
})

async function renderAndNavigateToScript() {
  const params = Promise.resolve({ id: 'plan-1' })
  // Pre-resolve the promise so the mocked use() returns synchronously
  await params
  const { default: Page } = await import('./page')
  const user = userEvent.setup()
  render(<Suspense fallback={null}><Page params={params} /></Suspense>)
  // Wait for plan to load (tab buttons appear after fetch resolves)
  await waitFor(() => expect(screen.getByText('直播脚本')).toBeInTheDocument())
  // Navigate to the script tab
  await user.click(screen.getByText('直播脚本'))
  return user
}

describe('segment editor', () => {
  it('renders title and goal fields for each segment', async () => {
    await renderAndNavigateToScript()
    await waitFor(() => {
      expect(screen.getByDisplayValue('开场')).toBeInTheDocument()
      expect(screen.getByDisplayValue('欢迎观众')).toBeInTheDocument()
    })
  })

  it('renders must_say checkbox checked for must_say segment', async () => {
    await renderAndNavigateToScript()
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.some((cb) => (cb as HTMLInputElement).checked)).toBe(true)
    })
  })

  it('does not render up/down move buttons', async () => {
    await renderAndNavigateToScript()
    await waitFor(() => {
      expect(screen.queryByText('up')).not.toBeInTheDocument()
      expect(screen.queryByText('down')).not.toBeInTheDocument()
    })
  })
})
