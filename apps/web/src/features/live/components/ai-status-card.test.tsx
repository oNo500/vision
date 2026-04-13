import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

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

const defaultProps = {
  latest: null,
  ttsQueueDepth: 0,
  urgentQueueDepth: 0,
  ttsSpeaking: false,
  llmGenerating: false,
}

describe('AiStatusCard', () => {
  it('shows "等待 AI 输出…" when latest is null', () => {
    render(<AiStatusCard {...defaultProps} />)
    expect(screen.getByText('等待 AI 输出…')).toBeInTheDocument()
  })

  it('shows latest.content when provided', () => {
    render(<AiStatusCard {...defaultProps} latest={mockAiOutput} />)
    expect(screen.getByText('This is AI generated text')).toBeInTheDocument()
  })

  it('shows correct source badge label for script source', () => {
    render(<AiStatusCard {...defaultProps} latest={mockAiOutput} />)
    expect(screen.getByText('script')).toBeInTheDocument()
  })

  it('shows correct source badge label for agent source', () => {
    const agentOutput: AiOutput = { ...mockAiOutput, source: 'agent' }
    render(<AiStatusCard {...defaultProps} latest={agentOutput} />)
    expect(screen.getByText('agent')).toBeInTheDocument()
  })

  it('shows correct source badge label for inject source', () => {
    const injectOutput: AiOutput = { ...mockAiOutput, source: 'inject' }
    render(<AiStatusCard {...defaultProps} latest={injectOutput} />)
    expect(screen.getByText('inject')).toBeInTheDocument()
  })

  it('shows tts queue depth', () => {
    render(<AiStatusCard {...defaultProps} ttsQueueDepth={5} />)
    expect(screen.getByText(/队列 5/)).toBeInTheDocument()
  })

  it('shows urgent queue depth', () => {
    render(<AiStatusCard {...defaultProps} urgentQueueDepth={3} />)
    expect(screen.getByText(/紧急 3/)).toBeInTheDocument()
  })

  it('tts queue text uses foreground color when > 0', () => {
    render(<AiStatusCard {...defaultProps} ttsQueueDepth={3} />)
    expect(screen.getByText(/队列 3/)).toHaveClass('text-foreground')
  })

  it('tts queue text uses muted-foreground color when = 0', () => {
    render(<AiStatusCard {...defaultProps} />)
    expect(screen.getByText(/队列 0/)).toHaveClass('text-muted-foreground')
  })

  it('urgent queue text uses amber color when > 0', () => {
    render(<AiStatusCard {...defaultProps} urgentQueueDepth={2} />)
    expect(screen.getByText(/紧急 2/)).toHaveClass('text-amber-500')
  })

  it('displays AI 状态 header', () => {
    render(<AiStatusCard {...defaultProps} />)
    expect(screen.getByText('AI 状态')).toBeInTheDocument()
  })
})
