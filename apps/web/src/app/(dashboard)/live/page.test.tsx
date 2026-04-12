import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// Mock all child components and hooks
vi.mock('@/features/live/components/danmaku-feed', () => ({
  DanmakuFeed: () => <div data-testid="danmaku-feed" />,
}))
vi.mock('@/features/live/components/session-controls', () => ({
  SessionControls: () => <div data-testid="session-controls" />,
}))
vi.mock('@/features/live/components/script-card', () => ({
  ScriptCard: () => <div data-testid="script-card" />,
}))
vi.mock('@/features/live/components/ai-status-card', () => ({
  AiStatusCard: () => <div data-testid="ai-status-card" />,
}))
vi.mock('@/features/live/components/ai-output-log', () => ({
  AiOutputLog: () => <div data-testid="ai-output-log" />,
}))
vi.mock('@/features/live/hooks/use-live-session', () => ({
  useLiveSession: () => ({
    state: { running: false },
    loading: false,
    error: null,
    start: vi.fn(),
    stop: vi.fn(),
  }),
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
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

import LivePage from './page'

describe('LivePage', () => {
  it('renders all three columns', () => {
    render(<LivePage />)
    expect(screen.getByTestId('script-card')).toBeInTheDocument()
    expect(screen.getByTestId('ai-status-card')).toBeInTheDocument()
    expect(screen.getByTestId('ai-output-log')).toBeInTheDocument()
    expect(screen.getByTestId('danmaku-feed')).toBeInTheDocument()
    expect(screen.getByTestId('session-controls')).toBeInTheDocument()
  })

  it('renders page title', () => {
    render(<LivePage />)
    expect(screen.getByText('直播控场')).toBeInTheDocument()
  })
})
