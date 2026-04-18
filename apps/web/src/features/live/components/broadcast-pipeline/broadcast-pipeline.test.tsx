import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

import { BroadcastPipeline } from './index'

vi.mock('@/features/live/hooks/use-tts-mutations', () => ({
  useTtsMutations: () => ({ remove: vi.fn(), edit: vi.fn(), reorder: vi.fn(), loading: false }),
}))

const mk = (id: string, stage: PipelineItem['stage'], content = id): PipelineItem => ({
  id, content, speech_prompt: null, stage, urgent: false, ts: 0,
})

describe('BroadcastPipeline', () => {
  it('renders all four stages', () => {
    render(
      <BroadcastPipeline
        pending={[mk('p1', 'pending')]}
        synthesized={[mk('s1', 'synthesized')]}
        nowPlayingItem={mk('play1', 'playing')}
        history={[mk('d1', 'done')]}
        llmGenerating={false}
        ttsSpeaking={true}
        urgentCount={0}
      />,
    )

    expect(screen.getByText('p1')).toBeInTheDocument()
    expect(screen.getByText('s1')).toBeInTheDocument()
    expect(screen.getByText('play1')).toBeInTheDocument()
  })

  it('renders urgent badge when urgent item present', () => {
    render(
      <BroadcastPipeline
        pending={[{ ...mk('u', 'pending'), urgent: true }]}
        synthesized={[]}
        nowPlayingItem={null}
        history={[]}
        llmGenerating={false}
        ttsSpeaking={false}
        urgentCount={1}
      />,
    )

    expect(screen.getByTestId('urgent-badge-u')).toBeInTheDocument()
  })

  it('shows generating indicator when llmGenerating', () => {
    render(
      <BroadcastPipeline
        pending={[]}
        synthesized={[]}
        nowPlayingItem={null}
        history={[]}
        llmGenerating={true}
        ttsSpeaking={false}
        urgentCount={0}
      />,
    )
    expect(screen.getByTestId('llm-generating-indicator')).toBeInTheDocument()
  })
})
