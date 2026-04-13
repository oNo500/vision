import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlanPanel } from './plan-panel'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

vi.mock('next/link', () => ({
  default: ({ children, href, className }: { children: React.ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  ),
}))

vi.mock('@/features/live/hooks/use-plan-active', () => ({
  usePlanActive: vi.fn(),
}))

import { usePlanActive } from '@/features/live/hooks/use-plan-active'

describe('PlanPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows 未加载方案 when no active plan', async () => {
    vi.mocked(usePlanActive).mockReturnValue(null)
    render(<PlanPanel />)
    await waitFor(() => expect(screen.getByText(/未加载方案/)).toBeInTheDocument())
    expect(screen.getByText(/前往方案库/)).toBeInTheDocument()
  })

  it('shows plan name when plan is loaded', () => {
    vi.mocked(usePlanActive).mockReturnValue({
      id: '1', name: '夏季护肤套装', created_at: '', updated_at: '',
      product: { name: '护肤套装', description: '', price: '299', highlights: [], faq: [] },
      persona: { name: '小美', style: '', catchphrases: [], forbidden_words: [] },
      script: { segments: [] },
    })
    render(<PlanPanel />)
    expect(screen.getByText('夏季护肤套装')).toBeInTheDocument()
  })
})
