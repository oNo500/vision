import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/components/page-header', () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <div data-testid="page-header">{children}</div>,
}))
vi.mock('@/features/live/components/plan-sidebar', () => ({
  PlanSidebar: (props: { running: boolean }) => (
    <div data-testid="plan-sidebar" data-running={String(props.running)} />
  ),
}))
vi.mock('@/features/live/components/plan-panel', () => ({
  PlanPanel: () => <div data-testid="plan-panel" />,
}))
vi.mock('@/features/live/components/danmaku-feed', () => ({
  DanmakuFeed: () => <div data-testid="danmaku-feed" />,
}))
vi.mock('@/features/live/components/session-controls', () => ({
  SessionControls: () => <div data-testid="session-controls" />,
}))
vi.mock('@/features/live/components/broadcast-pipeline', () => ({
  BroadcastPipeline: () => <div data-testid="broadcast-pipeline" />,
}))
vi.mock('@/features/live/hooks/use-ai-session', () => ({
  useAiSession: () => ({
    state: { running: false, queue_depth: 0 },
    loading: false,
    error: null,
    start: vi.fn(),
    stop: vi.fn(),
  }),
}))
vi.mock('@/features/live/hooks/use-danmaku-session', () => ({
  useDanmakuSession: () => ({
    state: { running: false, buffer_size: 0 },
    loading: false,
    error: null,
    start: vi.fn(),
    stop: vi.fn(),
  }),
}))
vi.mock('@/features/live/hooks/use-strategy', () => ({
  useStrategy: () => ({ strategy: 'immediate', setStrategy: vi.fn() }),
}))
vi.mock('@/features/live/hooks/use-live-stream', () => ({
  useLiveStream: () => ({
    events: [],
    connected: false,
    onlineCount: null,
    scriptState: null,
    pending: [],
    synthesized: [],
    nowPlayingItem: null,
    history: [],
    urgentCount: 0,
  }),
}))
vi.mock('@/features/live/hooks/use-plan-active', () => ({
  usePlanActive: () => ({
    id: '1',
    name: '示例方案',
    created_at: '',
    updated_at: '',
    product: { name: '护肤套装', description: '', price: '299', highlights: [], faq: [] },
    persona: { name: '小美', style: '', catchphrases: [], forbidden_words: [] },
    script: { segments: [] },
  }),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

import LivePage from './page'

describe('LivePage', () => {
  it('renders main layout components', () => {
    render(<LivePage />)
    expect(screen.getByTestId('plan-sidebar')).toBeInTheDocument()
    expect(screen.getByTestId('broadcast-pipeline')).toBeInTheDocument()
    expect(screen.getByTestId('danmaku-feed')).toBeInTheDocument()
    expect(screen.getByTestId('session-controls')).toBeInTheDocument()
  })

  it('renders page title', () => {
    render(<LivePage />)
    expect(screen.getByText('直播控场')).toBeInTheDocument()
  })

  it('passes session.state.running to PlanSidebar', () => {
    render(<LivePage />)
    expect(screen.getByTestId('plan-sidebar')).toHaveAttribute('data-running', 'false')
  })
})
