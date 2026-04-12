import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiOutput } from '../hooks/use-live-stream'
import { AiStatusCard } from './ai-status-card'

vi.mock('@/config/env', () => ({
  env: {
    NEXT_PUBLIC_API_URL: 'http://localhost:8000',
  },
}))

const mockAiOutput: AiOutput = {
  content: 'This is AI generated text',
  source: 'script',
  speech_prompt: 'speech prompt text',
  ts: 1234567890,
}

describe('AiStatusCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "等待 AI 输出…" when latest is null', () => {
    render(<AiStatusCard latest={null} queueDepth={0} />)
    expect(screen.getByText('等待 AI 输出…')).toBeInTheDocument()
  })

  it('shows latest.content when provided', () => {
    render(<AiStatusCard latest={mockAiOutput} queueDepth={0} />)
    expect(screen.getByText('This is AI generated text')).toBeInTheDocument()
  })

  it('shows correct source badge label for script source', () => {
    render(<AiStatusCard latest={mockAiOutput} queueDepth={0} />)
    expect(screen.getByText('script')).toBeInTheDocument()
  })

  it('shows correct source badge label for agent source', () => {
    const agentOutput: AiOutput = {
      ...mockAiOutput,
      source: 'agent',
    }
    render(<AiStatusCard latest={agentOutput} queueDepth={0} />)
    expect(screen.getByText('agent')).toBeInTheDocument()
  })

  it('shows correct source badge label for inject source', () => {
    const injectOutput: AiOutput = {
      ...mockAiOutput,
      source: 'inject',
    }
    render(<AiStatusCard latest={injectOutput} queueDepth={0} />)
    expect(screen.getByText('inject')).toBeInTheDocument()
  })

  it('shows queue depth number', () => {
    render(<AiStatusCard latest={mockAiOutput} queueDepth={5} />)
    expect(screen.getByText(/队列 5 句/)).toBeInTheDocument()
  })

  it('shows queue depth as 0 when queueDepth is 0', () => {
    render(<AiStatusCard latest={mockAiOutput} queueDepth={0} />)
    expect(screen.getByText(/队列 0 句/)).toBeInTheDocument()
  })

  it('queue depth text uses foreground color when > 0', () => {
    const { container } = render(<AiStatusCard latest={mockAiOutput} queueDepth={3} />)
    const queueText = screen.getByText(/队列 3 句/)
    expect(queueText).toHaveClass('text-foreground')
  })

  it('queue depth text uses muted-foreground color when = 0', () => {
    const { container } = render(<AiStatusCard latest={mockAiOutput} queueDepth={0} />)
    const queueText = screen.getByText(/队列 0 句/)
    expect(queueText).toHaveClass('text-muted-foreground')
  })

  it('displays AI 状态 header', () => {
    render(<AiStatusCard latest={null} queueDepth={0} />)
    expect(screen.getByText('AI 状态')).toBeInTheDocument()
  })

  it('renders without crashing with null latest and positive queueDepth', () => {
    render(<AiStatusCard latest={null} queueDepth={10} />)
    expect(screen.getByText('等待 AI 输出…')).toBeInTheDocument()
    expect(screen.getByText(/队列 10 句/)).toBeInTheDocument()
  })
})
