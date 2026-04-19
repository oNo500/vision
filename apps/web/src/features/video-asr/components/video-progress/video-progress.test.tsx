import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VideoProgress } from './index'
import type { VideoProgressState } from '@/features/video-asr/hooks/use-video-progress'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

const mockState: VideoProgressState = {
  stages: [
    { stage: 'ingest', status: 'done', duration_sec: 5.2, started_at: null },
    { stage: 'preprocess', status: 'done', duration_sec: 30.1, started_at: null },
    { stage: 'transcribe', status: 'running', duration_sec: null, started_at: '2026-01-01T00:00:00Z' },
  ],
  transcribeProgress: {
    done: 4,
    total: 12,
    chunks: [
      { id: 0, engine: 'gemini-2.5-flash' },
      { id: 1, engine: 'funasr-paraformer-large' },
    ],
    retrying: [],
  },
  costUsd: 0.0456,
  finished: false,
  connected: true,
  now: Date.now(),
}

describe('VideoProgress', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders stage labels in Chinese', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText('下载')).toBeDefined()
    expect(screen.getByText('转录')).toBeDefined()
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
