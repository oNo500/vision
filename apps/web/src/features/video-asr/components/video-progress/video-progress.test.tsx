import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VideoProgress } from './index'
import type { VideoProgressState } from '@/features/video-asr/hooks/use-video-progress'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

const mockState: VideoProgressState = {
  stages: [
    { stage: 'ingest', status: 'done', duration_sec: 5.2 },
    { stage: 'preprocess', status: 'done', duration_sec: 30.1 },
    { stage: 'transcribe', status: 'running', duration_sec: null },
  ],
  transcribeProgress: {
    done: 4,
    total: 12,
    chunks: [
      { id: 0, engine: 'gemini-2.5-flash' },
      { id: 1, engine: 'funasr-paraformer-large' },
    ],
  },
  costUsd: 0.0456,
  finished: false,
  connected: true,
}

describe('VideoProgress', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders stage names', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText('ingest')).toBeDefined()
    expect(screen.getByText('transcribe')).toBeDefined()
  })

  it('shows chunk progress for transcribe stage', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText('4 / 12')).toBeDefined()
  })

  it('shows cost', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText(/0\.0456/)).toBeDefined()
  })

  it('renders chunk engine badges', () => {
    render(<VideoProgress state={mockState} />)
    // G badge for gemini, F badge for funasr
    const badges = screen.getAllByTitle(/gemini|funasr/)
    expect(badges.length).toBe(2)
  })
})
