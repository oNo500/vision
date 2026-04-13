import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlanPanel } from './plan-panel'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('next/link', () => ({
  default: ({ children, href, onClick, className }: { children: React.ReactNode; href: string; onClick?: (e: React.MouseEvent) => void; className?: string }) => (
    <a href={href} onClick={onClick} className={className}>{children}</a>
  ),
}))

const mockPlan = {
  id: '1',
  name: '夏季护肤套装',
  created_at: '2026-04-13T00:00:00Z',
  updated_at: '2026-04-13T00:00:00Z',
  product: { name: '护肤套装', description: '', price: '299', highlights: [], faq: [] },
  persona: { name: '温柔姐姐', style: '专业亲切', catchphrases: [], forbidden_words: [] },
  script: { segments: [{ id: 's1', title: '开场预热', goal: '欢迎观众', duration: 60, cue: [], must_say: false, keywords: [] }] },
}

describe('PlanPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('shows 未加载方案 when no active plan', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ plan: null }),
    } as Response)

    render(<PlanPanel scriptState={null} running={false} />)
    await waitFor(() => expect(screen.getByText(/未加载方案/)).toBeInTheDocument())
    expect(screen.getByText(/前往方案库/)).toBeInTheDocument()
  })

  it('shows plan name and summary when plan is loaded', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ plan: mockPlan }),
    } as Response)

    render(<PlanPanel scriptState={null} running={false} />)
    await waitFor(() => expect(screen.getByText('夏季护肤套装')).toBeInTheDocument())
    expect(screen.getByText(/切换方案/)).toBeInTheDocument()
  })

  it('shows script title and remaining time when running', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ plan: mockPlan }),
    } as Response)

    const scriptState = {
      segment_id: 's1', title: '产品介绍', goal: '讲卖点', cue: ['益生菌'], must_say: false,
      remaining_seconds: 90, segment_duration: 300, finished: false,
    }

    render(<PlanPanel scriptState={scriptState} running={true} />)
    await waitFor(() => expect(screen.getByText('夏季护肤套装')).toBeInTheDocument())
    expect(screen.getByText('产品介绍')).toBeInTheDocument()
    expect(screen.getByText(/1:30/)).toBeInTheDocument()
  })
})
