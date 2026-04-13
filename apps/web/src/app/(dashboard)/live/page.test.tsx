import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { AiOutput } from '@/features/live/hooks/use-live-stream'

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
vi.mock('@/features/live/components/ai-status-card', () => ({
  AiStatusCard: (props: { nowPlaying: AiOutput | null; latest: AiOutput | null; ttsQueueDepth: number; urgentQueueDepth: number }) => (
    <div
      data-testid="ai-status-card"
      data-tts-queue-depth={String(props.ttsQueueDepth)}
      data-urgent-queue-depth={String(props.urgentQueueDepth)}
      data-has-latest={String(props.latest !== null)}
      data-has-now-playing={String(props.nowPlaying !== null)}
    />
  ),
}))
vi.mock('@/features/live/components/ai-output-log', () => ({
  AiOutputLog: (props: { outputs: AiOutput[] }) => (
    <div data-testid="ai-output-log" data-count={String(props.outputs.length)} />
  ),
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
    aiOutputs: [],
    scriptState: null,
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
    expect(screen.getByTestId('ai-status-card')).toBeInTheDocument()
    expect(screen.getByTestId('ai-output-log')).toBeInTheDocument()
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

  it('passes last aiOutput as latest to AiStatusCard', () => {
    render(<LivePage />)
    expect(screen.getByTestId('ai-status-card')).toHaveAttribute('data-has-latest', 'false')
  })

  it('passes tts_queue_depth from session state to AiStatusCard', () => {
    render(<LivePage />)
    expect(screen.getByTestId('ai-status-card')).toHaveAttribute('data-tts-queue-depth', '0')
    expect(screen.getByTestId('ai-status-card')).toHaveAttribute('data-urgent-queue-depth', '0')
  })

  it('passes aiOutputs to AiOutputLog', () => {
    render(<LivePage />)
    expect(screen.getByTestId('ai-output-log')).toHaveAttribute('data-count', '0')
  })
})
