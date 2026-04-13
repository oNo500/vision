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

describe('AiStatusCard', () => {
  it('shows "等待 AI 输出…" when latest is null', () => {
    render(<AiStatusCard latest={null} ttsQueueDepth={0} urgentQueueDepth={0} />)
    expect(screen.getByText('等待 AI 输出…')).toBeInTheDocument()
  })

  it('shows latest.content when provided', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={0} urgentQueueDepth={0} />)
    expect(screen.getByText('This is AI generated text')).toBeInTheDocument()
  })

  it('shows correct source badge label for script source', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={0} urgentQueueDepth={0} />)
    expect(screen.getByText('script')).toBeInTheDocument()
  })

  it('shows correct source badge label for agent source', () => {
    const agentOutput: AiOutput = {
      ...mockAiOutput,
      source: 'agent',
    }
    render(<AiStatusCard latest={agentOutput} ttsQueueDepth={0} urgentQueueDepth={0} />)
    expect(screen.getByText('agent')).toBeInTheDocument()
  })

  it('shows correct source badge label for inject source', () => {
    const injectOutput: AiOutput = {
      ...mockAiOutput,
      source: 'inject',
    }
    render(<AiStatusCard latest={injectOutput} ttsQueueDepth={0} urgentQueueDepth={0} />)
    expect(screen.getByText('inject')).toBeInTheDocument()
  })

  it('shows tts queue depth', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={5} urgentQueueDepth={0} />)
    expect(screen.getByText(/TTS 5 句/)).toBeInTheDocument()
  })

  it('shows urgent queue depth', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={0} urgentQueueDepth={3} />)
    expect(screen.getByText(/紧急 3/)).toBeInTheDocument()
  })

  it('tts queue text uses foreground color when > 0', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={3} urgentQueueDepth={0} />)
    const queueText = screen.getByText(/TTS 3 句/)
    expect(queueText).toHaveClass('text-foreground')
  })

  it('tts queue text uses muted-foreground color when = 0', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={0} urgentQueueDepth={0} />)
    const queueText = screen.getByText(/TTS 0 句/)
    expect(queueText).toHaveClass('text-muted-foreground')
  })

  it('urgent queue text uses amber color when > 0', () => {
    render(<AiStatusCard latest={mockAiOutput} ttsQueueDepth={0} urgentQueueDepth={2} />)
    const urgentText = screen.getByText(/紧急 2/)
    expect(urgentText).toHaveClass('text-amber-500')
  })

  it('displays AI 状态 header', () => {
    render(<AiStatusCard latest={null} ttsQueueDepth={0} urgentQueueDepth={0} />)
    expect(screen.getByText('AI 状态')).toBeInTheDocument()
  })
})
