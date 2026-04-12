import { render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'


import type { AiOutput } from '../hooks/use-live-stream'
import { AiOutputLog } from './ai-output-log'


// jsdom does not implement scrollIntoView
beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

const mockOutput: AiOutput = {
  content: 'Test content',
  source: 'script',
  speech_prompt: '',
  ts: 1700000000,
}

describe('AiOutputLog', () => {
  it('shows "暂无输出记录" when outputs is empty', () => {
    render(<AiOutputLog outputs={[]} />)
    expect(screen.getByText('暂无输出记录')).toBeInTheDocument()
  })

  it('shows "AI 输出历史" header', () => {
    render(<AiOutputLog outputs={[]} />)
    expect(screen.getByText('AI 输出历史')).toBeInTheDocument()
  })

  it('shows count badge with correct number', () => {
    render(<AiOutputLog outputs={[mockOutput, { ...mockOutput, ts: 1700000001 }]} />)
    expect(screen.getByText('(2)')).toBeInTheDocument()
  })

  it('shows count badge as (0) when outputs is empty', () => {
    render(<AiOutputLog outputs={[]} />)
    expect(screen.getByText('(0)')).toBeInTheDocument()
  })

  it('renders content text for each output', () => {
    const outputs: AiOutput[] = [
      { ...mockOutput, content: 'First output', ts: 1700000000 },
      { ...mockOutput, content: 'Second output', ts: 1700000001 },
    ]
    render(<AiOutputLog outputs={outputs} />)
    expect(screen.getByText('First output')).toBeInTheDocument()
    expect(screen.getByText('Second output')).toBeInTheDocument()
  })

  it('renders source badge for script source', () => {
    render(<AiOutputLog outputs={[mockOutput]} />)
    expect(screen.getByText('script')).toBeInTheDocument()
  })

  it('renders source badge for agent source', () => {
    render(<AiOutputLog outputs={[{ ...mockOutput, source: 'agent' }]} />)
    expect(screen.getByText('agent')).toBeInTheDocument()
  })

  it('renders source badge for inject source', () => {
    render(<AiOutputLog outputs={[{ ...mockOutput, source: 'inject' }]} />)
    expect(screen.getByText('inject')).toBeInTheDocument()
  })

  it('renders formatted timestamp as HH:MM:SS pattern', () => {
    render(<AiOutputLog outputs={[mockOutput]} />)
    // toLocaleTimeString output varies by TZ, check for HH:MM:SS pattern
    const timePattern = /\d{2}:\d{2}:\d{2}/
    expect(screen.getByText(timePattern)).toBeInTheDocument()
  })

  it('does NOT show empty state when outputs provided', () => {
    render(<AiOutputLog outputs={[mockOutput]} />)
    expect(screen.queryByText('暂无输出记录')).not.toBeInTheDocument()
  })

  it('source badge for script has correct classes', () => {
    render(<AiOutputLog outputs={[mockOutput]} />)
    const badge = screen.getByText('script')
    expect(badge).toHaveClass('bg-primary/15')
    expect(badge).toHaveClass('text-primary')
  })
})
